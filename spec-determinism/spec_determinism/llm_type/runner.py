"""Tier 1.5 — orchestrator.

End-to-end pipeline:

    complete_types(spec, project_root)
        ├── detect_gaps(spec, source)                       (no LLM)
        │     if no gaps → return early
        ├── for each cached patch in cache → apply directly
        ├── for remaining gaps → invoke Copilot CLI once
        │     ├── build prompt
        │     ├── _run_copilot_session
        │     ├── read <work_dir>/type_patches.json
        │     ├── parse_llm_output
        │     ├── run_gates  (V1 evidence, V2 type-str, V3 codegen smoke)
        │     ├── apply_patches accepted
        │     └── store accepted/rejected in cache
        └── return CompletionResult{ spec, telemetry }

The runner deliberately calls the LLM **at most once per spec**. We bundle
all gaps into one prompt because the agent typically resolves them
together (they live in the same file / module).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from spec_determinism.extract.types import FunctionSpec

from .apply import TypePatch, apply_patches
from .cache import CacheEntry, TypeCompletionCache
from .gaps import Gap, detect_gaps
from .prompt import build_prompt, parse_llm_output
from .validator import run_gates


logger = logging.getLogger(__name__)


@dataclass
class CompletionTelemetry:
    gap_count: int = 0
    gaps: list[str] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    # Per-gap source: name → "live" | "pinned" | "miss".
    # Only recorded for the first lookup in a target (per :meth:`get_with_source`).
    gap_sources: dict[str, str] = field(default_factory=dict)
    # Aggregate counters for quick triage.
    cache_hits_live: int = 0
    cache_hits_pinned: int = 0
    # A/B reproducibility metadata.
    current_source_hash: str = ""
    pinned_hash: str = ""
    pinned_hash_matches: Optional[bool] = None
    pinned_cache_dir: str = ""
    llm_invoked: bool = False
    llm_returncode: int = 0
    llm_timed_out: bool = False
    llm_wall_ms: int = 0
    rounds_run: int = 0
    patches_proposed: int = 0
    patches_accepted: int = 0
    patches_rejected: int = 0
    reject_reasons: list[str] = field(default_factory=list)
    rejected_by_gate: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "gap_count": self.gap_count,
            "gaps": list(self.gaps),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "gap_sources": dict(self.gap_sources),
            "cache_hits_live": self.cache_hits_live,
            "cache_hits_pinned": self.cache_hits_pinned,
            "current_source_hash": self.current_source_hash,
            "pinned_hash": self.pinned_hash,
            "pinned_hash_matches": self.pinned_hash_matches,
            "pinned_cache_dir": self.pinned_cache_dir,
            "llm_invoked": self.llm_invoked,
            "llm_returncode": self.llm_returncode,
            "llm_timed_out": self.llm_timed_out,
            "llm_wall_ms": self.llm_wall_ms,
            "rounds_run": self.rounds_run,
            "patches_proposed": self.patches_proposed,
            "patches_accepted": self.patches_accepted,
            "patches_rejected": self.patches_rejected,
            "reject_reasons": list(self.reject_reasons),
            "rejected_by_gate": dict(self.rejected_by_gate),
        }


@dataclass
class CompletionResult:
    spec: FunctionSpec                       # mutated in place if patches accepted
    telemetry: CompletionTelemetry
    applied_patches: list[TypePatch] = field(default_factory=list)
    rejected_patches: list[tuple[TypePatch, str]] = field(default_factory=list)


def _read_source(project_root: str) -> str:
    """Concatenate all .rs source under project_root (best-effort).

    detect_gaps wants a single big source blob to grep for macros etc.
    Keep this cheap; the gap detector only does regex on it.
    """
    chunks: list[str] = []
    for dirpath, _, fnames in os.walk(project_root):
        rel = os.path.relpath(dirpath, project_root)
        if any(p in {"target", ".git", "node_modules", ".venv"}
               for p in rel.split(os.sep)):
            continue
        for fn in fnames:
            if not fn.endswith(".rs"):
                continue
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8",
                          errors="replace") as f:
                    chunks.append(f.read())
            except OSError:
                continue
    return "\n".join(chunks)


def _invoke_copilot(
    prompt: str,
    cwd: Path,
    out_path: Path,
    timeout_s: int,
    log_dir: Path,
):
    """Wrapper around llm_proof.agentic._run_copilot_session.

    Returns the AgenticSession (with cli_returncode, cli_timed_out, cli_ms).
    Reading out_path is the caller's responsibility.
    """
    # Lazy import to avoid pulling agentic deps at module-import time
    from spec_determinism.llm_proof.agentic import _run_copilot_session
    return _run_copilot_session(
        prompt=prompt,
        timeout_s=timeout_s,
        cwd=cwd,
        log_dir=log_dir,
    )


def complete_types(
    spec: FunctionSpec,
    project_root: str,
    *,
    cache: Optional[TypeCompletionCache] = None,
    work_dir: Optional[str] = None,
    timeout_s: int = 300,
    skip_v3: bool = False,
    max_rounds: int = 3,
    invoke_copilot=_invoke_copilot,         # injectable for tests
) -> CompletionResult:
    """Tier 1.5 entry point.

    Mutates ``spec.type_defs`` in place with any accepted patches.

    Iterates: after applying patches in round N, re-runs ``detect_gaps``
    in case the newly-resolved types reference yet-unresolved types
    (e.g. ``CSingleMessage`` whose ``Message`` variant carries an
    ``EndPoint``). Caps at ``max_rounds`` to bound LLM cost.

    The shape-mismatch probe loop (formerly "Bug B") has been moved out
    of the main path: it added almost no steady-state value (every
    on-corpus measurement showed ``shape_det=0`` once the cache was
    warm) and complicated A/B reasoning. The probe utilities live in
    :mod:`spec_determinism.llm_type.probe` and
    :func:`spec_determinism.llm_type.gaps.gaps_from_compile_stderr`,
    invoked by ``scripts/validate_tier15_cache.py`` during deliberate
    re-baseline events. See ``docs/determinism-funnel-framework.md`` §6.2.1.
    """
    tel = CompletionTelemetry()
    result = CompletionResult(spec=spec, telemetry=tel)

    source = _read_source(project_root)
    initial_gaps = detect_gaps(spec, source)
    tel.gap_count = len(initial_gaps)
    tel.gaps = sorted({g.name for g in initial_gaps})

    if not initial_gaps:
        return result

    if cache is None:
        cache = TypeCompletionCache(project_root)

    # Capture cache identity for A/B reproducibility — recorded once per run.
    tel.current_source_hash = cache.current_source_hash
    tel.pinned_hash = cache.pinned_hash or ""
    tel.pinned_hash_matches = cache.pinned_hash_matches
    tel.pinned_cache_dir = cache.pinned_cache_dir or ""

    if work_dir is None:
        work_dir = os.path.join("/tmp", f"llmtype_{int(time.time()*1000)}_{os.getpid()}")
    os.makedirs(work_dir, exist_ok=True)

    resolved_names: set[str] = set()  # gaps fully handled (accepted or rejected)

    for round_idx in range(max_rounds):
        gaps = detect_gaps(spec, source)
        gaps = [g for g in gaps if g.name not in resolved_names]
        if not gaps:
            break
        tel.rounds_run = round_idx + 1
        round_dir = os.path.join(work_dir, f"round_{round_idx}")
        os.makedirs(round_dir, exist_ok=True)
        _run_one_round(
            spec=spec, gaps=gaps, project_root=project_root,
            cache=cache, work_dir=round_dir, timeout_s=timeout_s,
            skip_v3=skip_v3, invoke_copilot=invoke_copilot,
            result=result, tel=tel, resolved_names=resolved_names,
        )

    # Persist telemetry artifact for debugging.
    try:
        (Path(work_dir) / "telemetry.json").write_text(
            json.dumps(tel.to_dict(), indent=2)
        )
    except OSError:
        pass

    return result


def _run_one_round(
    *,
    spec: FunctionSpec,
    gaps: list[Gap],
    project_root: str,
    cache: TypeCompletionCache,
    work_dir: str,
    timeout_s: int,
    skip_v3: bool,
    invoke_copilot,
    result: CompletionResult,
    tel: CompletionTelemetry,
    resolved_names: set[str],
) -> None:
    # 1. Try cache first (per-type).
    remaining_gaps: list[Gap] = []
    cached_patches: list[TypePatch] = []
    seen_names: set[str] = set()
    for g in gaps:
        if g.name in seen_names:
            continue
        seen_names.add(g.name)
        entry, source = cache.get_with_source(g.name)
        if entry is None:
            tel.cache_misses += 1
            tel.gap_sources.setdefault(g.name, "miss")
            remaining_gaps.append(g)
            continue
        # Record provenance once per name (first lookup wins; subsequent
        # rounds may re-resolve via LLM but the initial source is what
        # matters for A/B audit).
        tel.gap_sources.setdefault(g.name, source)
        if source == "live":
            tel.cache_hits_live += 1
        elif source == "pinned":
            tel.cache_hits_pinned += 1
        if entry.validator_verdict == "rejected":
            tel.cache_hits += 1
            tel.rejected_by_gate["cache_negative"] = (
                tel.rejected_by_gate.get("cache_negative", 0) + 1
            )
            result.rejected_patches.append(
                (entry.patch, f"cache-negative: {entry.reject_reason}")
            )
            resolved_names.add(g.name)
        else:
            tel.cache_hits += 1
            cached_patches.append(entry.patch)

    # 2. Apply cached patches (these have already passed V1/V2/V3 once).
    if cached_patches:
        results = apply_patches(spec, cached_patches)
        for p, r in zip(cached_patches, results):
            if r.accepted:
                result.applied_patches.append(p)
                tel.patches_accepted += 1
            else:
                result.rejected_patches.append((p, f"apply-skipped: {r.reason}"))
                tel.patches_rejected += 1
            resolved_names.add(p.name)

    if not remaining_gaps:
        return

    # 3. LLM call for remaining gaps in this round.
    out_path = os.path.join(work_dir, "type_patches.json")
    if os.path.isfile(out_path):
        os.unlink(out_path)  # ensure stale file doesn't pollute

    prompt = build_prompt(spec, remaining_gaps, out_path)
    (Path(work_dir) / "prompt.txt").write_text(prompt)

    tel.llm_invoked = True
    t0 = time.monotonic()
    session = invoke_copilot(
        prompt=prompt,
        cwd=Path(project_root),
        out_path=Path(out_path),
        timeout_s=timeout_s,
        log_dir=Path(work_dir),
    )
    tel.llm_wall_ms += int((time.monotonic() - t0) * 1000)
    tel.llm_returncode = getattr(session, "cli_returncode", -1)
    tel.llm_timed_out = bool(getattr(session, "cli_timed_out", False))

    # 4. Read agent output.
    raw_patches: list[dict] = []
    if os.path.isfile(out_path):
        try:
            with open(out_path) as f:
                raw_text = f.read()
            raw_patches = parse_llm_output(raw_text)
        except (OSError, ValueError) as e:
            logger.warning("Tier1.5: failed to read/parse %s: %s", out_path, e)
            for g in remaining_gaps:
                cache.put_rejected(g.name, f"LLM output parse error: {e}")
                tel.rejected_by_gate["parse"] = tel.rejected_by_gate.get("parse", 0) + 1
                resolved_names.add(g.name)
    else:
        logger.warning("Tier1.5: agent did not write %s", out_path)
        for g in remaining_gaps:
            cache.put_rejected(g.name, "LLM did not produce output file")
            tel.rejected_by_gate["no_output"] = tel.rejected_by_gate.get("no_output", 0) + 1
            resolved_names.add(g.name)

    tel.patches_proposed += len(raw_patches)

    # 5. Convert raw → TypePatch, run V1/V2/V3.
    proposed: list[TypePatch] = []
    proposed_names: set[str] = set()
    for d in raw_patches:
        try:
            p = TypePatch.from_dict(d)
            proposed.append(p)
            proposed_names.add(p.name)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Tier1.5: bad patch dict skipped: %s", e)
            tel.rejected_by_gate["schema"] = tel.rejected_by_gate.get("schema", 0) + 1
            tel.patches_rejected += 1

    # Any requested gap the LLM declined to resolve in this round → mark as
    # processed-this-round so we don't re-prompt for the same name. (A
    # transitive re-detection in the next round would be a new entry.)
    for g in remaining_gaps:
        if g.name not in proposed_names:
            resolved_names.add(g.name)
            cache.put_rejected(g.name, "LLM did not propose a patch")

    accepted, rejected = run_gates(spec, proposed, project_root, skip_v3=skip_v3)

    for p, gate_result in rejected:
        result.rejected_patches.append((p, gate_result.reason))
        tel.reject_reasons.append(gate_result.reason)
        gate_id = gate_result.reason.split(":", 1)[0] if ":" in gate_result.reason else "unknown"
        tel.rejected_by_gate[gate_id] = tel.rejected_by_gate.get(gate_id, 0) + 1
        tel.patches_rejected += 1
        cache.put_rejected(p.name, gate_result.reason)
        resolved_names.add(p.name)

    if accepted:
        apply_results = apply_patches(spec, accepted)
        now_ms = int(time.time() * 1000)
        for p, r in zip(accepted, apply_results):
            if r.accepted:
                result.applied_patches.append(p)
                tel.patches_accepted += 1
                cache.put(CacheEntry(
                    patch=p, cached_at_ms=now_ms,
                    llm_round_count=1, validator_verdict="accepted",
                ))
            else:
                result.rejected_patches.append((p, f"apply: {r.reason}"))
                tel.patches_rejected += 1
                tel.rejected_by_gate["apply"] = tel.rejected_by_gate.get("apply", 0) + 1
                cache.put_rejected(p.name, f"apply: {r.reason}")
            resolved_names.add(p.name)


# ---------------------------------------------------------------------------
# Self-tests
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    import tempfile, textwrap
    from spec_determinism.extract.types import (
        FunctionSpec, Param, TypeInfo as TI, TypeKind as TK,
    )

    ok = True

    with tempfile.TemporaryDirectory() as proj, \
         tempfile.TemporaryDirectory() as cache_root:
        os.makedirs(os.path.join(proj, "src"))
        with open(os.path.join(proj, "src", "host.rs"), "w") as f:
            f.write(textwrap.dedent("""\
                // line 1
                pub struct HashMap<V> {
                    pub m: collections::HashMap<EndPoint, V>,
                }
                impl<V> HashMap<V> {
                    pub uninterp spec fn view(self) -> Map<AbstractEndPoint, V>;
                }
            """))
        with open(os.path.join(proj, "Cargo.toml"), "w") as f:
            f.write("[package]\nname='x'\n")

        # Path 1: no gaps, returns early.
        spec_no_gap = FunctionSpec(
            name="f", params=[],
            return_type=TI(TK.UNIT, "()"),
            requires=[], ensures=[],
            type_defs={},
        )
        r = complete_types(
            spec_no_gap, proj,
            cache=TypeCompletionCache(proj, cache_root=cache_root),
        )
        if r.telemetry.gap_count != 0 or r.telemetry.llm_invoked:
            print(f"FAIL: no-gap path tripped LLM: {r.telemetry.to_dict()}")
            ok = False

        # Path 2: gaps + fake LLM that writes correct output.
        spec_with_gap = FunctionSpec(
            name="receive_ack",
            params=[Param(name="h", type=TI(TK.UNKNOWN, "HashMap<u8>"))],
            return_type=TI(TK.UNIT, "()"),
            requires=[], ensures=["self.h@ == post.h@"],
            type_defs={},
        )

        def fake_copilot(*, prompt, cwd, out_path, timeout_s, log_dir):
            # Inspect prompt and write a plausible patch
            assert "HashMap" in prompt
            out = {
                "type_patches": [{
                    "name": "HashMap",
                    "kind": "struct",
                    "type_params": ["V"],
                    "fields": [{"name": "m", "type_str": "u8"}],
                    "spec_view": {"type_str": "Map<AbstractEndPoint, V>"},
                    "source_evidence": {
                        "rel_path": "src/host.rs",
                        "line": 6,
                        "snippet": "pub uninterp spec fn view(self) -> Map<AbstractEndPoint, V>;",
                    },
                }]
            }
            out_path.write_text(json.dumps(out))

            class FakeSession:
                cli_returncode = 0
                cli_timed_out = False
                cli_ms = 100
            return FakeSession()

        r = complete_types(
            spec_with_gap, proj,
            cache=TypeCompletionCache(proj, cache_root=cache_root),
            skip_v3=True,
            max_rounds=1,
            invoke_copilot=fake_copilot,
        )
        if r.telemetry.gap_count == 0:
            print(f"FAIL: gap path should detect a gap")
            ok = False
        if not r.telemetry.llm_invoked:
            print("FAIL: gap path should invoke LLM")
            ok = False
        if r.telemetry.patches_accepted != 1:
            print(f"FAIL: should accept 1 patch, got {r.telemetry.patches_accepted}")
            ok = False
        if "HashMap" not in spec_with_gap.type_defs:
            print("FAIL: HashMap not added to type_defs")
            ok = False

        # Path 3: cache hit — fake LLM should NOT be called this time.
        invoked = []

        def cant_call(*, prompt, cwd, out_path, timeout_s, log_dir):
            invoked.append(True)
            raise AssertionError("should not be called: cache hit")

        spec_with_gap2 = FunctionSpec(
            name="receive_ack",
            params=[Param(name="h", type=TI(TK.UNKNOWN, "HashMap<u8>"))],
            return_type=TI(TK.UNIT, "()"),
            requires=[], ensures=["self.h@ == post.h@"],
            type_defs={},
        )
        r = complete_types(
            spec_with_gap2, proj,
            cache=TypeCompletionCache(proj, cache_root=cache_root),
            skip_v3=True,
            max_rounds=1,
            invoke_copilot=cant_call,
        )
        if invoked:
            print("FAIL: cache should have served HashMap; LLM was called")
            ok = False
        if r.telemetry.cache_hits < 1:
            print(f"FAIL: cache_hits should be ≥1, got {r.telemetry.cache_hits}")
            ok = False
        if "HashMap" not in spec_with_gap2.type_defs:
            print("FAIL: cached path did not populate type_defs")
            ok = False

        # Path 4: LLM produces bad evidence (V1 fails); cache stores negative
        spec_bad = FunctionSpec(
            name="z",
            params=[Param(name="m", type=TI(TK.UNKNOWN, "Mystery"))],
            return_type=TI(TK.UNIT, "()"),
            requires=[], ensures=[],
            type_defs={},
        )

        def fake_bad(*, prompt, cwd, out_path, timeout_s, log_dir):
            out = {
                "type_patches": [{
                    "name": "Mystery", "kind": "struct", "fields": [],
                    "source_evidence": {
                        "rel_path": "src/host.rs",
                        "line": 1,
                        "snippet": "this snippet does not exist anywhere",
                    },
                }]
            }
            out_path.write_text(json.dumps(out))
            class S: cli_returncode=0; cli_timed_out=False; cli_ms=10
            return S()

        r = complete_types(
            spec_bad, proj,
            cache=TypeCompletionCache(proj, cache_root=cache_root),
            skip_v3=True,
            max_rounds=1,
            invoke_copilot=fake_bad,
        )
        if r.telemetry.patches_accepted != 0:
            print(f"FAIL: bad evidence should reject; got accepted={r.telemetry.patches_accepted}")
            ok = False
        if r.telemetry.patches_rejected < 1:
            print(f"FAIL: should record rejection; got {r.telemetry.patches_rejected}")
            ok = False

    print("runner self-test:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    import sys
    sys.exit(0 if _self_test() else 1)
