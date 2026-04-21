# Legacy backends

Frozen snapshots of the pre-Z3-backend pipeline, kept for fallback and
reference. These files are NOT imported by the current pipeline and
may diverge from the live sources in `src/`.

- `binary_search.py`: subprocess-Verus search loop, one Verus call per
  narrowing round. Used when Z3 model extraction returns `unknown`.
- `verify.py`: `cargo verus build/verify` subprocess wrapper.
