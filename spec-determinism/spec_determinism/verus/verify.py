"""
Module 3: verify — Verus Runner

Pure I/O module. Injects proof fn into crate, runs Verus, parses result.
No LLM fallback needed.
"""

import os
import re
import subprocess
import time
import logging
from pathlib import Path

from spec_determinism.extract.types import VerifyResult

logger = logging.getLogger(__name__)


_INJECT_BLOCK_RE = re.compile(
    r"\n*// === INJECTED DET CHECK ===.*?// === END INJECTED ===\n*",
    re.DOTALL,
)


def inject_proof_fn(proof_file: str, code: str, marker: str = "} // end verus!") -> str:
    """
    Inject proof fn code into a .proof.rs file before the closing marker.
    Falls back to the last `}` if the specific marker isn't found.

    Defensive: any pre-existing INJECTED DET CHECK block (left over from a
    previous crashed/killed run) is stripped before injection. The original
    content returned for restoration is the on-disk content with stale
    injections also stripped — restoring it leaves the file clean.
    """
    raw = Path(proof_file).read_text()
    cleaned = _INJECT_BLOCK_RE.sub("\n", raw)
    if cleaned != raw:
        logger.warning(
            f"inject_proof_fn: stripped stale INJECTED DET CHECK from {proof_file}"
        )
    original = cleaned
    idx = original.rfind(marker)
    if idx == -1:
        # Fallback: inject before the last closing brace (end of verus! block)
        idx = original.rfind("}")
    if idx == -1:
        raise ValueError(f"No suitable injection point found in {proof_file}")

    new_content = (
        original[:idx]
        + "\n// === INJECTED DET CHECK ===\n"
        + code
        + "\n// === END INJECTED ===\n\n"
        + original[idx:]
    )
    Path(proof_file).write_text(new_content)
    return original


def restore_file(proof_file: str, original_content: str):
    """Restore original file content."""
    Path(proof_file).write_text(original_content)


def run_cargo_verus(
    crate_dir: str,
    crate_name: str,
    verus_path: str,
    features: list[str] | None = None,
    timeout: int = 120,
    extra_args: list[str] | None = None,
    verify_module: str | None = None,
    verify_function: str | None = None,
    use_build: bool = True,
    verus_extra_args: list[str] | None = None,
) -> dict:
    """
    Run cargo verus on a crate.

    If verify_module is set, restrict verification to that module (and
    optionally one function inside it via verify_function). The
    restriction is forwarded only to the root crate via
    `--fwd-verus-args-to roots` so dependencies still verify normally.

    If use_build is True (default) we invoke `cargo verus build` instead
    of `verify`. `build` actually produces the crate's final artifact
    (.rlib for libs, .elf for bins) which satisfies cargo's fingerprint
    check; `verify` skips codegen and leaves the artifact missing, which
    makes cargo mark the crate stale on every invocation and forces a
    full re-verify even when source is unchanged. Some bin crates with
    nightly features that collide with Verus's wrapper (e.g. a duplicate
    `#![feature(stmt_expr_attributes)]`) can't be built by the wrapper;
    those should pass use_build=False.

    Returns raw dict: {returncode, stdout, stderr, duration_ms}
    """
    env = os.environ.copy()
    env["PATH"] = verus_path + ":" + env.get("PATH", "")
    env["RUSTC_BOOTSTRAP"] = "1"

    cmd = [
        "cargo", "+nightly-2025-12-08", "verus",
        "build" if use_build else "verify",
    ]
    scoped = bool(verify_module) or bool(verify_function)
    if scoped:
        cmd.extend(["--fwd-verus-args-to", "roots"])
    cmd.extend(["-p", crate_name])
    if features:
        cmd.extend(["--features", ",".join(features)])
    if extra_args:
        cmd.extend(extra_args)
    if scoped:
        verus_args = ["--"]
        if verify_module:
            verus_args.extend(["--verify-only-module", verify_module])
        else:
            # Injected det_X fns live at the crate root (the proof file
            # is `include!`d directly into lib.rs). Scope Verus SMT to
            # that single fn via --verify-root.
            verus_args.append("--verify-root")
        if verify_function:
            verus_args.extend(["--verify-function", verify_function])
        if verus_extra_args:
            verus_args.extend(verus_extra_args)
        cmd.extend(verus_args)
    elif verus_extra_args:
        cmd.append("--")
        cmd.extend(verus_extra_args)

    logger.info(f"Running: {' '.join(cmd)} in {crate_dir}")
    start = time.monotonic()

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=crate_dir, env=env,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"TIMEOUT after {timeout}s",
            "duration_ms": timeout * 1000,
        }


def parse_result(raw: dict, fn_name: str) -> VerifyResult:
    """Parse raw Verus output into VerifyResult for a specific proof fn."""
    combined = raw["stdout"] + "\n" + raw["stderr"]

    # Check for compile errors first
    if "could not compile" in combined and "postcondition not satisfied" not in combined:
        return VerifyResult(
            status="error",
            function=fn_name,
            duration_ms=raw["duration_ms"],
            stderr=combined,
        )

    # Check timeout
    if raw["returncode"] == -1:
        return VerifyResult(
            status="timeout",
            function=fn_name,
            duration_ms=raw["duration_ms"],
            stderr=combined,
        )

    # Check if our specific function failed
    # Verus error format: "postcondition not satisfied" then fn name on nearby lines
    fn_failed = bool(re.search(
        rf"postcondition not satisfied", combined
    )) and bool(re.search(
        rf"\b{re.escape(fn_name)}\b", combined
    ))

    # Also check: "error" line mentioning fn name directly
    if not fn_failed:
        fn_failed = bool(re.search(
            rf"error.*\b{re.escape(fn_name)}\b", combined
        ))

    if fn_failed:
        return VerifyResult(
            status="fail",
            function=fn_name,
            duration_ms=raw["duration_ms"],
            stderr=combined,
        )

    # Check overall results
    m = re.search(r"(\d+)\s+verified,\s+(\d+)\s+errors?", combined)
    if m:
        errors = int(m.group(2))
        if errors == 0:
            return VerifyResult(
                status="pass",
                function=fn_name,
                duration_ms=raw["duration_ms"],
            )

    # Ambiguous — treat as error
    return VerifyResult(
        status="error",
        function=fn_name,
        duration_ms=raw["duration_ms"],
        stderr=combined,
    )


class VerusRunner:
    """Stateful Verus runner that manages injection and restoration."""

    def __init__(
        self,
        crate_dir: str,
        crate_name: str,
        proof_file: str,
        verus_path: str,
        features: list[str] | None = None,
        timeout: int = 120,
        extra_args: list[str] | None = None,
        verify_module: str | None = None,
        use_build: bool = True,
    ):
        self.crate_dir = crate_dir
        self.crate_name = crate_name
        self.proof_file = proof_file
        self.verus_path = verus_path
        self.features = features
        self.timeout = timeout
        self.extra_args = extra_args
        self.verify_module = verify_module
        self.use_build = use_build
        self._original: str | None = None
        self._call_count = 0
        self._baseline_checked = False

    def _ensure_baseline(self) -> None:
        """Run one full verify (no injection, no module restriction) to
        confirm the baseline crate is clean. Raises RuntimeError if not.
        Cached: only runs once per VerusRunner instance."""
        if self._baseline_checked:
            return
        logger.info(
            f"Baseline preflight: full verify of {self.crate_name} "
            f"(no injection)"
        )
        # Baseline uses `verify` unconditionally: `build` with no module
        # scope can trip on primary-package codegen (e.g. duplicate
        # `#![feature(stmt_expr_attributes)]` on the kernel bin). The
        # baseline only runs once per session, so its perf is irrelevant.
        raw = run_cargo_verus(
            self.crate_dir, self.crate_name,
            self.verus_path, self.features, self.timeout,
            extra_args=self.extra_args,
            use_build=False,
        )
        combined = raw["stdout"] + "\n" + raw["stderr"]
        if "could not compile" in combined or raw["returncode"] != 0:
            raise RuntimeError(
                f"Baseline verify of {self.crate_name} FAILED "
                f"(no injection). Tool would inject into a broken crate.\n"
                f"stderr tail:\n{combined[-2000:]}"
            )
        # Sanity: check for at least one "X verified, 0 errors" line.
        # NOTE: `cargo verus build` may hit the cache (no verify output) when
        # the crate is already up-to-date — this is a valid OK state.
        m = re.findall(r"(\d+)\s+verified,\s+(\d+)\s+errors?", combined)
        if m and any(int(e) != 0 for _, e in m):
            raise RuntimeError(
                f"Baseline verify of {self.crate_name} reports errors:\n"
                f"{combined[-2000:]}"
            )
        if m:
            logger.info(
                f"Baseline OK: {sum(int(v) for v, _ in m)} verified, 0 errors"
            )
        else:
            logger.info(
                f"Baseline OK: {self.crate_name} cached "
                f"(no recompile needed)"
            )
        self._baseline_checked = True

    def check(self, code: str, fn_name: str) -> VerifyResult:
        """Inject code, run Verus, parse result, restore file.

        On first call, runs a baseline preflight verify of the crate
        without any injection to ensure we're not building on a broken
        baseline. If verify_module was set, subsequent runs are scoped
        to that module + the injected fn_name (avoids proof-stability
        collateral damage on unrelated functions)."""
        self._ensure_baseline()
        self._original = inject_proof_fn(self.proof_file, code)
        try:
            raw = run_cargo_verus(
                self.crate_dir, self.crate_name,
                self.verus_path, self.features, self.timeout,
                extra_args=self.extra_args,
                verify_module=self.verify_module,
                verify_function=fn_name,
                use_build=self.use_build,
            )
            self._call_count += 1
            return parse_result(raw, fn_name)
        finally:
            restore_file(self.proof_file, self._original)

    @property
    def call_count(self) -> int:
        return self._call_count
