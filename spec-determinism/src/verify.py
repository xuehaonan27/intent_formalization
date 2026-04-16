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

from .types import VerifyResult

logger = logging.getLogger(__name__)


def inject_proof_fn(proof_file: str, code: str, marker: str = "} // end verus!") -> str:
    """
    Inject proof fn code into a .proof.rs file before the closing marker.
    Falls back to the last `}` if the specific marker isn't found.
    Returns the original content (for restoration).
    """
    original = Path(proof_file).read_text()
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
) -> dict:
    """
    Run cargo verus verify on a crate.

    Returns raw dict: {returncode, stdout, stderr, duration_ms}
    """
    env = os.environ.copy()
    env["PATH"] = verus_path + ":" + env.get("PATH", "")
    env["RUSTC_BOOTSTRAP"] = "1"

    cmd = [
        "cargo", "+nightly-2025-12-08", "verus", "verify",
        "-p", crate_name,
    ]
    if features:
        cmd.extend(["--features", ",".join(features)])
    if extra_args:
        cmd.extend(extra_args)

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
    ):
        self.crate_dir = crate_dir
        self.crate_name = crate_name
        self.proof_file = proof_file
        self.verus_path = verus_path
        self.features = features
        self.timeout = timeout
        self._original: str | None = None
        self._call_count = 0

    def check(self, code: str, fn_name: str) -> VerifyResult:
        """Inject code, run Verus, parse result, restore file."""
        self._original = inject_proof_fn(self.proof_file, code)
        try:
            raw = run_cargo_verus(
                self.crate_dir, self.crate_name,
                self.verus_path, self.features, self.timeout,
            )
            self._call_count += 1
            return parse_result(raw, fn_name)
        finally:
            restore_file(self.proof_file, self._original)

    @property
    def call_count(self) -> int:
        return self._call_count
