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

from typing import Protocol, runtime_checkable
from .types import DetCheckSpec, VerifyResult


@runtime_checkable
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


@runtime_checkable
class ModelProvidingBackend(DetBackend, Protocol):
    """A DetBackend that also exposes the last SMT model on `fail`.

    Used by `binary_search` to skip narrowing when the backend already
    produced a full witness (e.g. `Z3Backend` reading Verus's
    `(get-model)` response from the SMT transcript).

    `last_model` maps SMT symbol name -> (sort, value_sexpr). It is reset
    at the start of every `check()` call and populated only on `fail`.
    `set_det_spec` lets the backend know which symbols the caller cares
    about so it can decide which ones to read from the model.
    """

    last_model: dict[str, tuple[str, str]] | None

    def set_det_spec(self, det_spec: DetCheckSpec) -> None: ...
