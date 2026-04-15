"""
LLM fallback wrapper — unified interface for all modules.

Each module calls `llm_fallback(task, context)` when parser path fails.
This module routes to the appropriate LLM and validates the response.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class LLMFallback:
    """
    Unified LLM fallback handler.
    
    Wraps an LLM client and provides task-specific methods
    that each module can call when the parser path fails.
    """

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: An object with a .chat(system_prompt, user_prompt) method
                        that returns an object with a .content attribute.
                        Compatible with src/utils/llm.py LLMClient.
        """
        self.client = llm_client
        self._call_count = 0

    @property
    def available(self) -> bool:
        return self.client is not None

    @property
    def call_count(self) -> int:
        return self._call_count

    def _call(self, system: str, user: str) -> str:
        """Make an LLM call and return the response content."""
        if not self.client:
            raise RuntimeError("No LLM client configured")
        self._call_count += 1
        resp = self.client.chat(system_prompt=system, user_prompt=user)
        return resp.content.strip()

    # ----- Module 1: extract -----

    def extract_spec(self, source_snippet: str, fn_name: str) -> dict:
        """
        Fallback for extract module.
        Returns a dict with keys matching FunctionSpec fields.
        """
        prompt = (
            f"Extract the Verus function specification for `{fn_name}` from this source.\n\n"
            f"```rust\n{source_snippet}\n```\n\n"
            f"Return JSON with fields:\n"
            f"- name: string\n"
            f"- params: [{{name, type, is_mut_ref}}]\n"
            f"- return_type: string\n"
            f"- requires: [clause strings]\n"
            f"- ensures: [clause strings]\n"
            f"Return ONLY valid JSON, no explanation."
        )
        text = self._call("You are a Verus parser.", prompt)
        # Extract JSON from response
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            import json
            return json.loads(m.group())
        raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")

    # ----- Module 2: gen_det -----

    def substitute_ensures(
        self,
        ensures_raw: str,
        var_mapping: dict[str, str],
    ) -> str:
        """
        Fallback for gen_det module.
        Apply variable substitution to an ensures clause.
        """
        mapping_str = "\n".join(f"  {k} → {v}" for k, v in var_mapping.items())
        prompt = (
            f"Apply this variable substitution to the Verus ensures clause.\n\n"
            f"Substitution map:\n{mapping_str}\n\n"
            f"Ensures clause:\n```\n{ensures_raw}\n```\n\n"
            f"Return ONLY the substituted Verus expression. Copy structure exactly, "
            f"only change variable names per the map."
        )
        return self._call(
            "You are a Verus code transformer. Be precise.",
            prompt,
        )

    # ----- Module 4: binary_search -----

    def suggest_narrowing(
        self,
        type_name: str,
        var_name: str,
        current_assumes: list[str],
    ) -> str:
        """
        Fallback for binary_search module.
        Suggest a narrowing constraint for an unknown type.
        """
        assumes_str = "\n".join(f"  {a}" for a in current_assumes) or "  (none)"
        prompt = (
            f"Given a Verus variable `{var_name}` of type `{type_name}`, "
            f"suggest one assume() constraint to narrow its value.\n"
            f"Current constraints:\n{assumes_str}\n\n"
            f"Return ONLY the Verus expression for inside assume(), e.g.:\n"
            f"  {var_name} == <some_concrete_value>"
        )
        return self._call(
            "You are a Verus expert. Suggest concrete narrowing constraints.",
            prompt,
        )

    def generate_assume_code(
        self,
        type_name: str,
        var_name: str,
        constraint_intent: str,
    ) -> str:
        """
        Fallback for assume_codegen.
        Generate Verus expression for a constraint.
        """
        prompt = (
            f"Generate a Verus expression for this constraint:\n"
            f"Variable: `{var_name}` of type `{type_name}`\n"
            f"Intent: {constraint_intent}\n\n"
            f"Return ONLY the Verus expression."
        )
        return self._call(
            "You are a Verus syntax expert.",
            prompt,
        )

    # ----- Module 5: witness -----

    def classify_gap(
        self,
        function_name: str,
        assumes: list[str],
    ) -> tuple[str, str]:
        """
        Fallback for witness module.
        Classify the spec gap and generate description.
        """
        assumes_str = "\n".join(f"  {a}" for a in assumes)
        prompt = (
            f"A Verus function `{function_name}` has a nondeterministic spec.\n"
            f"Witness constraints:\n{assumes_str}\n\n"
            f"Classify as: liveness, error_wildcard, frame_condition, "
            f"design_choice, type_abstraction, totality, other.\n"
            f"Format: TYPE: one-line description"
        )
        text = self._call(
            "You are a formal verification expert.",
            prompt,
        )
        if ":" in text:
            parts = text.split(":", 1)
            return parts[0].strip().lower(), parts[1].strip()
        return "other", text
