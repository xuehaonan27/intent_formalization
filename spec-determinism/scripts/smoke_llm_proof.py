#!/usr/bin/env python3
"""End-to-end smoke test for spec_determinism.llm_proof.

Validates the LLM-proof escalation wiring in ``run_single_file``.
Mocks ``CopilotCLI`` so we don't burn real LLM tokens. Two scenarios:

  * **Test A — graceful failure path** (real Verus run): the mocked
    response is the worked-example proof block for atmosphere's
    ``set_owning_container``. This case fundamentally needs both
    Phase-2 view-eq AND an LLM proof (see
    ``docs/examples/idea_a_set_owning_container/README.md``), so Verus
    will reject. Expect: ``llm_assisted=False``,
    ``llm_proof_last_status='verus_fail'``, bucket=``ok_inconclusive``.

  * **Test B — simulated success path** (Verus mocked to return rc=0):
    same input as Test A, but ``_run_verus`` is patched to always
    succeed. Validates the success-promotion logic. Expect:
    ``r0_z3='unsat'``, ``llm_assisted=True``, bucket=``complete_llm``,
    winning_proof artifacts written.

Usage:
    python3 scripts/smoke_llm_proof.py
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

# So this script is runnable from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

# A real (sufficient-on-page_array-only) proof block from the worked example.
PROOF_BLOCK = '''    if post1_self_.page_array.wf()
        && (forall|i: int|
            #![trigger post1_self_.page_array@[i]]
            #![trigger pre_self_.page_array@[i]]
            0 <= i < NUM_PAGES && i != index ==> post1_self_.page_array@[i] =~= pre_self_.page_array@[i])
        && post1_self_.page_array@[index as int].addr =~= pre_self_.page_array@[index as int].addr
        && post1_self_.page_array@[index as int].state =~= pre_self_.page_array@[index as int].state
        && post1_self_.page_array@[index as int].owning_container =~= owning_container_op
        && post2_self_.page_array.wf()
        && (forall|i: int|
            #![trigger post2_self_.page_array@[i]]
            #![trigger pre_self_.page_array@[i]]
            0 <= i < NUM_PAGES && i != index ==> post2_self_.page_array@[i] =~= pre_self_.page_array@[i])
        && post2_self_.page_array@[index as int].addr =~= pre_self_.page_array@[index as int].addr
        && post2_self_.page_array@[index as int].state =~= pre_self_.page_array@[index as int].state
        && post2_self_.page_array@[index as int].owning_container =~= owning_container_op
    {
        assert(post1_self_.page_array@ =~= post2_self_.page_array@);
    }
'''

MOCK_RESPONSE = f"""I will bring the ensures hypothesis into scope.

```verus
{PROOF_BLOCK}```

```json
{{"strategy": "case_split_on_index"}}
```
"""

# --- Mock CopilotCLI BEFORE importing run_single_file ---
from spec_determinism.llm import copilot as _cp

class _MockClient:
    def __init__(self, *a, **kw):
        pass
    def query(self, prompt: str, run_dir):
        run_dir = Path(run_dir); run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt.md").write_text(prompt)
        (run_dir / "response.md").write_text(MOCK_RESPONSE)
        return MOCK_RESPONSE

_cp.CopilotCLI = _MockClient
import spec_determinism.llm_proof.prover as _pv
_pv.CopilotCLI = _MockClient

from spec_determinism.verus.single_file import run_single_file
from spec_determinism.classify import (
    classify_ok, BUCKET_PROVED_LLM, BUCKET_INCONCLUSIVE,
)

SRC = Path(
    "/home/xuehaonan/intent_formalization/verusage/source-projects/"
    "atmosphere/verified/allocator/"
    "allocator__page_allocator_spec_impl__impl2__remove_mapping_4k_helper2.rs"
)
if not SRC.exists():
    print(f"ERROR: source file not found: {SRC}")
    sys.exit(2)


def _run_test_a() -> bool:
    print("=" * 60)
    print("Test A: graceful failure path (real Verus)")
    print("=" * 60)
    art = Path("/tmp/smoke_llm_proof_A")
    if art.exists(): shutil.rmtree(art)
    art.mkdir()
    result = run_single_file(
        SRC, "set_owning_container",
        artifact_dir=art,
        use_llm_proof=True,
        llm_proof_max_attempts=2,
        timeout=180,
    )
    bucket = classify_ok(result) if result.get("status") == "ok" else "non-ok"
    print(f"  status={result.get('status')} r0_z3={result.get('r0_z3')} "
          f"llm_assisted={result.get('llm_assisted')} bucket={bucket}")
    print(f"  llm_proof_attempts={result.get('llm_proof_attempts')} "
          f"last_status={result.get('llm_proof_last_status')}")
    ok = (
        result.get("status") == "ok"
        and result.get("r0_z3") == "unknown"
        and result.get("llm_assisted") is False
        and result.get("llm_proof_attempts") == 2
        and result.get("llm_proof_last_status") == "verus_fail"
        and bucket == BUCKET_INCONCLUSIVE
    )
    print("  Test A:", "PASS" if ok else "FAIL")
    return ok


def _run_test_b() -> bool:
    print()
    print("=" * 60)
    print("Test B: simulated success path (Verus mocked rc=0)")
    print("=" * 60)
    art = Path("/tmp/smoke_llm_proof_B")
    if art.exists(): shutil.rmtree(art)
    art.mkdir()
    cache = Path("/tmp/smoke_llm_proof_cache")
    if cache.exists(): shutil.rmtree(cache)
    cache.mkdir()
    _real = _pv._run_verus
    _pv._run_verus = lambda *a, **kw: (0, "9 verified, 0 errors", 42)
    try:
        result = run_single_file(
            SRC, "set_owning_container",
            artifact_dir=art,
            use_llm_proof=True,
            llm_proof_max_attempts=2,
            timeout=180,
            llm_proof_cache_dir=cache,
            llm_proof_cache_mode="use",
        )
    finally:
        _pv._run_verus = _real
    bucket = classify_ok(result) if result.get("status") == "ok" else "non-ok"
    print(f"  status={result.get('status')} r0_z3={result.get('r0_z3')} "
          f"llm_assisted={result.get('llm_assisted')} bucket={bucket}")
    print(f"  llm_proof_attempts={result.get('llm_proof_attempts')}")
    artifacts_ok = (
        (art / "llm_proof_block.txt").exists()
        and (art / "llm_proof.verus_pass.rs").exists()
    )
    cache_files = list(cache.glob("*.json"))
    print(f"  winning artifacts written: {artifacts_ok}")
    print(f"  cache entries written: {len(cache_files)}")
    ok = (
        result.get("status") == "ok"
        and result.get("r0_z3") == "unsat"
        and result.get("llm_assisted") is True
        and result.get("llm_proof_attempts") == 1
        and bucket == BUCKET_PROVED_LLM
        and artifacts_ok
        and len(cache_files) == 1
    )
    print("  Test B:", "PASS" if ok else "FAIL")
    return ok


def _run_test_c() -> bool:
    """Cache hit re-uses prior proof without calling LLM."""
    print()
    print("=" * 60)
    print("Test C: cache hit (skip LLM, re-verify via Verus)")
    print("=" * 60)
    cache = Path("/tmp/smoke_llm_proof_cache")  # populated by Test B
    if not cache.exists() or not list(cache.glob("*.json")):
        print("  SKIP — Test B did not populate the cache")
        return False
    art = Path("/tmp/smoke_llm_proof_C")
    if art.exists(): shutil.rmtree(art)
    art.mkdir()

    # Patch CopilotCLI to raise — should not be called on a cache hit.
    class _ExplodingClient:
        def __init__(self, *a, **kw): pass
        def query(self, *a, **kw):
            raise AssertionError("LLM must not be called on a cache hit")
    _real_cli = _pv.CopilotCLI
    _pv.CopilotCLI = _ExplodingClient
    _real_verus = _pv._run_verus
    _pv._run_verus = lambda *a, **kw: (0, "re-verified", 17)
    try:
        result = run_single_file(
            SRC, "set_owning_container",
            artifact_dir=art,
            use_llm_proof=True,
            llm_proof_max_attempts=2,
            timeout=180,
            llm_proof_cache_dir=cache,
            llm_proof_cache_mode="use",
        )
    finally:
        _pv.CopilotCLI = _real_cli
        _pv._run_verus = _real_verus

    bucket = classify_ok(result) if result.get("status") == "ok" else "non-ok"
    print(f"  status={result.get('status')} r0_z3={result.get('r0_z3')} "
          f"llm_assisted={result.get('llm_assisted')} bucket={bucket}")
    print(f"  llm_proof_attempts={result.get('llm_proof_attempts')} "
          f"notes={result.get('llm_proof_notes')}")
    ok = (
        result.get("status") == "ok"
        and result.get("r0_z3") == "unsat"
        and result.get("llm_assisted") is True
        and result.get("llm_proof_notes") == "cache_hit_verified"
        and bucket == BUCKET_PROVED_LLM
    )
    print("  Test C:", "PASS" if ok else "FAIL")
    return ok


def _run_test_d() -> bool:
    """Agentic mode: one Copilot CLI session per target."""
    print()
    print("=" * 60)
    print("Test D: agentic mode (CLI session mocked, Verus mocked rc=0)")
    print("=" * 60)
    art = Path("/tmp/smoke_llm_proof_D")
    if art.exists(): shutil.rmtree(art)
    art.mkdir()
    cache = Path("/tmp/smoke_llm_proof_cache_agentic")
    if cache.exists(): shutil.rmtree(cache)
    cache.mkdir()

    # Mock just the Copilot CLI session function (NOT subprocess.run
    # globally — that would break single_file.py's own Verus invocation).
    # The mock 'edits' det.rs by replacing the placeholder with a fake
    # proof and writes the agent's result.json, then returns a happy
    # AgenticSession.
    import spec_determinism.llm_proof.agentic as _ag

    FAKE_PROOF = "assert(true);  // pretend the agent proved it"

    def _fake_session(*, prompt, timeout_s, cwd, log_dir):
        det = Path(cwd) / "det.rs"
        if det.exists():
            text = det.read_text()
            det.write_text(text.replace(_ag._INITIAL_PLACEHOLDER, FAKE_PROOF))
        (Path(cwd) / "result.json").write_text(
            json.dumps({"status": "pass", "iterations": 3,
                        "notes": "mocked agent: replaced placeholder"})
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "cli.stdout").write_text("mock CLI ok\n")
        (log_dir / "cli.stderr").write_text("")
        s = _ag.AgenticSession()
        s.started_at = _ag._utc_now()
        s.finished_at = _ag._utc_now()
        s.cli_returncode = 0
        s.cli_stderr_tail = ""
        s.cli_ms = 12
        return s

    _real_verus = _ag._run_verus
    _real_session = _ag._run_copilot_session
    _ag._run_verus = lambda *a, **kw: (0, "0 verified mocked", 17)
    _ag._run_copilot_session = _fake_session
    try:
        result = run_single_file(
            SRC, "set_owning_container",
            artifact_dir=art,
            use_llm_proof=True,
            llm_proof_max_attempts=1,
            timeout=180,
            llm_proof_cache_dir=cache,
            llm_proof_cache_mode="use",
            llm_proof_mode="agentic",
            llm_proof_session_timeout=30,  # don't care, mocked
        )
    finally:
        _ag._run_verus = _real_verus
        _ag._run_copilot_session = _real_session

    bucket = classify_ok(result) if result.get("status") == "ok" else "non-ok"
    cache_files = list(cache.glob("*.json"))
    print(f"  status={result.get('status')} r0_z3={result.get('r0_z3')} "
          f"llm_assisted={result.get('llm_assisted')} bucket={bucket}")
    print(f"  llm_proof_attempts={result.get('llm_proof_attempts')} "
          f"notes={result.get('llm_proof_notes')}")
    print(f"  cache entries: {len(cache_files)}")
    block_ok = (art / "llm_proof_block.txt").exists() and (
        FAKE_PROOF in (art / "llm_proof_block.txt").read_text()
    )
    outcome_dump_ok = (art / "agentic_outcome.json").exists()
    print(f"  proof_block written + matches mock: {block_ok}")
    print(f"  agentic_outcome.json written: {outcome_dump_ok}")
    ok = (
        result.get("status") == "ok"
        and result.get("r0_z3") == "unsat"
        and result.get("llm_assisted") is True
        and result.get("llm_proof_attempts") == 1
        and (result.get("llm_proof_notes") or "").startswith("agentic_session")
        and bucket == BUCKET_PROVED_LLM
        and len(cache_files) == 1
        and block_ok and outcome_dump_ok
    )
    print("  Test D:", "PASS" if ok else "FAIL")
    return ok


def main() -> int:
    a = _run_test_a()
    b = _run_test_b()
    c = _run_test_c()
    d = _run_test_d()
    print()
    print("=" * 60)
    all_ok = a and b and c and d
    print(f"OVERALL: {'PASS' if all_ok else 'FAIL'}")
    print("=" * 60)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
