"""
Backend protocol for determinism checking.

Two backends today:

- VerusBackend (src/verify.py :: VerusRunner)
    Subprocess-invokes `cargo verus build`. Used as the fallback.

- Z3Backend   (src/z3_backend.py :: Z3Backend)
    Re-uses Verus's SMT transcript and Z3's model response to answer
    determinism questions in-process, without spawning cargo for each
    narrowing round.

Both implement `DetBackend.check(code, fn_name) -> VerifyResult`.
The search logic in `binary_search.py` depends only on this interface.
"""

from typing import Protocol
from .types import VerifyResult


class DetBackend(Protocol):
    """Anything that can answer `is this det_<fn> proof-obligation satisfied?`."""

    def check(self, code: str, fn_name: str) -> VerifyResult:
        """
        Inject `code` (full Verus source of the det_<fn> proof fn + its
        equal-fn) into the target crate, run the proof obligation, and
        return a VerifyResult.

        `status` is one of:
          - "pass"    : determinism proven (no witness under current assumes)
          - "fail"    : proof failed (witness exists; narrowing can continue)
          - "timeout" : solver/time budget exhausted
          - "error"   : template compilation failure or backend internal error
        """
        ...
