"""
Spec-Fuzzing Pipeline (src/pipeline_fuzz/)

Generates concrete (pre-state, args, post-state, return) cases, uses an LLM
oracle to label each as ACCEPT/REJECT, then uses Verus to check spec
admission. Oracle x Verus disagreement surfaces spec bugs.
"""
