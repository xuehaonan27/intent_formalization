#!/usr/bin/env python3
"""Inventory specification-related declaration sites in a vstd source tree.

The scanner reports source-level declaration sites, not macro-expanded items.
It uses tree-sitter-verus for function classification and lexical fallbacks for
constructs that the currently installed grammar does not parse completely
(notably assume_specification and default_ensures).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

import tree_sitter as ts
import tree_sitter_verus as tsv

from spec_determinism.extract.aliases import normalize_verus_aliases


FUNCTION_NODE_TYPES = {"function_item", "function_signature_item"}

GROUP_ORDER = [
    "Mathematical foundations",
    "Rust standard-library specs",
    "Runtime collections and data",
    "Memory and ownership",
    "Concurrency and prophecy",
    "Resources and protocols",
    "Experimental exec-spec",
    "Infrastructure",
]

REPORT_BEGIN = "<!-- BEGIN GENERATED MODULE INVENTORY -->"
REPORT_END = "<!-- END GENERATED MODULE INVENTORY -->"

CRITICAL_MODULES = {
    "view",
    "function",
    "seq",
    "seq_lib",
    "set",
    "set_lib",
    "map",
    "map_lib",
    "multiset",
    "multiset_lib",
    "raw_ptr",
    "std_specs::cmp",
    "std_specs::hash",
    "std_specs::iter",
    "std_specs::num",
    "std_specs::ops",
    "std_specs::option",
    "std_specs::range",
    "std_specs::result",
    "std_specs::slice",
    "std_specs::vec",
}

HIGH_MODULES = {
    "array",
    "atomic",
    "bytes",
    "cell",
    "cell::invcell",
    "cell::pcell",
    "cell::pcell_maybe_uninit",
    "hash_map",
    "hash_set",
    "invariant",
    "layout",
    "rwlock",
    "simple_pptr",
    "slice",
    "string",
    "std_specs::alloc",
    "std_specs::atomic",
    "std_specs::bits",
    "std_specs::btree",
    "std_specs::clone",
    "std_specs::convert",
    "std_specs::default",
    "std_specs::maybe_uninit",
    "std_specs::smart_ptrs",
    "std_specs::vecdeque",
    "utf8",
}

SUPPORT_MODULES = {
    "build",
    "calc_macro",
    "modes",
    "pervasive",
    "prelude",
    "state_machine_internal",
    "vstd",
}


@dataclass
class ModuleStats:
    module: str
    file: str
    group: str
    importance: str
    lines: int
    parser_error: bool
    macro_rules_sites: int
    function_sites_ast: int
    exec_function_sites: int
    exec_body_sites: int
    exec_signature_sites: int
    exec_body_post_sites: int
    exec_body_requires_only_sites: int
    exec_body_no_contract_sites: int
    public_exec_body_sites: int
    public_exec_body_post_sites: int
    public_exec_body_requires_only_sites: int
    public_exec_body_no_contract_sites: int
    public_exec_body_no_post_sites: int
    exec_contract_sites: int
    exec_post_sites: int
    trait_exec_contract_sites: int
    public_exec_no_post_sites: int
    assume_spec_sites: int
    assume_spec_with_post_sites: int
    assume_spec_without_post_sites: int
    model_spec_fn_sites: int
    proof_fn_sites: int
    axiom_fn_sites: int
    requires_clause_sites: int
    ensures_clause_sites: int
    returns_clause_sites: int
    default_ensures_sites: int
    external_trait_spec_sites: int
    external_type_spec_sites: int
    external_body_sites: int
    view_impl_sites: int
    deep_view_impl_sites: int
    broadcast_group_sites: int
    total_contract_sites: int
    total_spec_sites: int


@dataclass
class ExecItem:
    module: str
    file: str
    line: int
    name: str
    context: str
    node_kind: str
    visibility: str
    contract_status: str
    post_kinds: str
    flags: str


def mask_comments(source: str) -> str:
    """Replace comments with spaces while preserving string length and lines."""
    chars = list(source)
    i = 0
    block_depth = 0
    in_line = False
    while i < len(chars):
        if in_line:
            if chars[i] == "\n":
                in_line = False
            else:
                chars[i] = " "
            i += 1
            continue
        if block_depth:
            if i + 1 < len(chars) and chars[i] == "/" and chars[i + 1] == "*":
                chars[i] = chars[i + 1] = " "
                block_depth += 1
                i += 2
                continue
            if i + 1 < len(chars) and chars[i] == "*" and chars[i + 1] == "/":
                chars[i] = chars[i + 1] = " "
                block_depth -= 1
                i += 2
                continue
            if chars[i] != "\n":
                chars[i] = " "
            i += 1
            continue
        if i + 1 < len(chars) and chars[i] == "/" and chars[i + 1] == "/":
            chars[i] = chars[i + 1] = " "
            in_line = True
            i += 2
            continue
        if i + 1 < len(chars) and chars[i] == "/" and chars[i + 1] == "*":
            chars[i] = chars[i + 1] = " "
            block_depth = 1
            i += 2
            continue
        i += 1
    return "".join(chars)


def iter_nodes(node: ts.Node) -> Iterable[ts.Node]:
    yield node
    for child in node.children:
        yield from iter_nodes(child)


def attrs_text(node: ts.Node) -> str:
    parent = node.parent
    if parent is None or parent.type != "declaration_with_attrs":
        return ""
    return "\n".join(
        child.text.decode(errors="replace")
        for child in parent.children
        if child.type == "attribute_item"
    )


def declaration_prefix(node: ts.Node) -> str:
    parent = node.parent
    if parent is None or parent.type != "declaration_with_attrs":
        return ""
    prefix_len = max(0, node.start_byte - parent.start_byte)
    return parent.text[:prefix_len].decode(errors="replace")


def function_mode(text: str, attrs: str) -> str:
    header = attrs + "\n" + text.split("{", 1)[0].split(";", 1)[0]
    if re.search(r"\baxiom\s+fn\b", header):
        return "axiom"
    if re.search(r"\bproof\s+fn\b", header) or "verifier::proof" in attrs:
        return "proof"
    if (
        re.search(r"\b(?:(?:open|closed|uninterp)\s+)?spec\s+fn\b", header)
        or "verifier::spec" in attrs
    ):
        return "spec"
    return "exec"


def enclosing_trait(node: ts.Node) -> Optional[ts.Node]:
    parent = node.parent
    while parent is not None:
        if parent.type == "trait_item":
            return parent
        parent = parent.parent
    return None


def enclosing_context(node: ts.Node) -> str:
    parent = node.parent
    while parent is not None:
        text = parent.text.decode(errors="replace")
        if parent.type == "trait_item":
            match = re.search(r"\btrait\s+([A-Za-z_][A-Za-z0-9_]*)", text)
            return f"trait {match.group(1)}" if match else "trait"
        if parent.type == "impl_item":
            header = " ".join(text.split("{", 1)[0].split())
            return header[:160] + ("..." if len(header) > 160 else "")
        parent = parent.parent
    return "free"


def is_public_function(
    text: str,
    node: ts.Node,
    modifiers: str = "",
) -> bool:
    header = (modifiers + " " + text).split("{", 1)[0].split(";", 1)[0]
    if re.search(r"(^|\s)pub(?:\([^)]*\))?\s+", header):
        return True
    trait = enclosing_trait(node)
    if trait is None:
        return False
    trait_header = trait.text.decode(errors="replace").split("{", 1)[0]
    return bool(re.search(r"(^|\s)pub(?:\([^)]*\))?\s+trait\b", trait_header))


def has_keyword(text: str, keyword: str) -> bool:
    return bool(re.search(rf"(?<![.\w]){re.escape(keyword)}\b", text))


def lexical_count(masked: str, pattern: str) -> int:
    return len(re.findall(pattern, masked, flags=re.MULTILINE))


def assume_spec_counts(source: str, masked: str) -> tuple[int, int]:
    total = 0
    with_post = 0
    for match in re.finditer(r"\bpub\s+assume_specification\b", masked):
        total += 1
        end = masked.find(";", match.end())
        if end < 0:
            end = len(masked)
        item = source[match.start() : end]
        if any(has_keyword(item, kw) for kw in ("ensures", "returns", "default_ensures")):
            with_post += 1
    return total, with_post


def module_name(relative_path: Path) -> str:
    if relative_path.name == "vstd.rs":
        return "vstd"
    if relative_path.name == "mod.rs":
        return "::".join(relative_path.parent.parts)
    return "::".join(relative_path.with_suffix("").parts)


def module_group(module: str) -> str:
    if module.startswith("std_specs"):
        return "Rust standard-library specs"
    if module.startswith("resource") or module == "tokens":
        return "Resources and protocols"
    if module.startswith("contrib"):
        return "Experimental exec-spec"
    if module in {
        "atomic",
        "atomic_ghost",
        "future",
        "invariant",
        "logatom",
        "proph",
        "rwlock",
        "shared",
        "thread",
    }:
        return "Concurrency and prophecy"
    if module == "cell" or module.startswith("cell::") or module in {
        "raw_ptr",
        "simple_pptr",
    }:
        return "Memory and ownership"
    if module in SUPPORT_MODULES:
        return "Infrastructure"
    if module.startswith("arithmetic") or module in {
        "bits",
        "compute",
        "function",
        "imap",
        "imap_lib",
        "iset",
        "iset_lib",
        "laws_cmp",
        "laws_eq",
        "map",
        "map_lib",
        "math",
        "multiset",
        "multiset_lib",
        "predicate",
        "relations",
        "seq",
        "seq_lib",
        "set",
        "set_lib",
        "view",
    }:
        return "Mathematical foundations"
    return "Runtime collections and data"


def module_importance(module: str, group: str) -> str:
    if module in CRITICAL_MODULES:
        return "critical"
    if module in HIGH_MODULES:
        return "high"
    if group in {"Resources and protocols", "Concurrency and prophecy"}:
        return "specialized"
    if group in {"Infrastructure", "Experimental exec-spec"}:
        return "support"
    return "medium"


def scan_file(
    parser: ts.Parser,
    root: Path,
    path: Path,
) -> tuple[ModuleStats, list[ExecItem]]:
    source = path.read_text(errors="replace")
    # Normalize `verus_!`-style macro aliases so functions inside alias
    # blocks are visible (line numbers preserved).
    source = normalize_verus_aliases(source)
    source_bytes = source.encode()
    masked = mask_comments(source)
    tree = parser.parse(source_bytes)
    relative = path.relative_to(root)
    module = module_name(relative)
    group = module_group(module)

    ast_counts: dict[str, int] = defaultdict(int)
    exec_items: list[ExecItem] = []
    for node in iter_nodes(tree.root_node):
        if node.type not in FUNCTION_NODE_TYPES:
            continue
        text = node.text.decode(errors="replace")
        attrs = attrs_text(node)
        line_start = source_bytes.rfind(b"\n", 0, node.start_byte) + 1
        line_prefix = source_bytes[line_start : node.start_byte].decode(
            errors="replace"
        )
        modifiers = declaration_prefix(node) + "\n" + line_prefix
        mode = function_mode(text, attrs + "\n" + modifiers)
        has_requires = has_keyword(text, "requires")
        has_ensures = has_keyword(text, "ensures")
        has_returns = has_keyword(text, "returns")
        has_default = has_keyword(text, "default_ensures")
        has_post = has_ensures or has_returns or has_default
        has_contract = has_requires or has_post
        is_public = is_public_function(text, node, modifiers)

        ast_counts["function_sites"] += 1
        ast_counts[f"{mode}_sites"] += 1
        if mode == "exec":
            name_match = re.search(
                r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)",
                text,
            )
            post_kinds = [
                keyword
                for keyword, present in (
                    ("ensures", has_ensures),
                    ("returns", has_returns),
                    ("default_ensures", has_default),
                )
                if present
            ]
            if has_post:
                contract_status = "post"
            elif has_requires:
                contract_status = "requires-only"
            else:
                contract_status = "no-contract"
            flags = []
            if "external_body" in attrs:
                flags.append("external_body")
            elif re.search(r"verifier::external(?:\]|\))", attrs):
                flags.append("external")
            if "doc(hidden)" in attrs:
                flags.append("hidden")
            if "when_used_as_spec" in attrs:
                flags.append("when_used_as_spec")
            exec_items.append(
                ExecItem(
                    module=module,
                    file=str(relative),
                    line=source_bytes[: node.start_byte].count(b"\n") + 1,
                    name=name_match.group(1) if name_match else "?",
                    context=enclosing_context(node),
                    node_kind=(
                        "definition"
                        if node.type == "function_item"
                        else "signature"
                    ),
                    visibility="public" if is_public else "private",
                    contract_status=contract_status,
                    post_kinds="+".join(post_kinds),
                    flags="+".join(flags),
                )
            )
            if node.type == "function_item":
                ast_counts["exec_body_sites"] += 1
                if has_post:
                    ast_counts["exec_body_post_sites"] += 1
                elif has_requires:
                    ast_counts["exec_body_requires_only_sites"] += 1
                else:
                    ast_counts["exec_body_no_contract_sites"] += 1
                if is_public:
                    ast_counts["public_exec_body_sites"] += 1
                    if has_post:
                        ast_counts["public_exec_body_post_sites"] += 1
                    elif has_requires:
                        ast_counts["public_exec_body_requires_only_sites"] += 1
                    else:
                        ast_counts["public_exec_body_no_contract_sites"] += 1
                    if not has_post:
                        ast_counts["public_exec_body_no_post_sites"] += 1
            else:
                ast_counts["exec_signature_sites"] += 1
            if has_contract:
                ast_counts["exec_contract_sites"] += 1
            if has_post:
                ast_counts["exec_post_sites"] += 1
            if enclosing_trait(node) is not None and has_contract:
                ast_counts["trait_exec_contract_sites"] += 1
            if is_public and not has_post:
                ast_counts["public_exec_no_post_sites"] += 1

    assume_total, assume_with_post = assume_spec_counts(source, masked)

    spec_lexical = lexical_count(
        masked, r"\b(?:(?:open|closed|uninterp)\s+)?spec\s+fn\b"
    )
    proof_lexical = lexical_count(masked, r"\b(?:broadcast\s+)?proof\s+fn\b")
    axiom_lexical = lexical_count(masked, r"\b(?:broadcast\s+)?axiom\s+fn\b")

    model_spec_sites = max(ast_counts["spec_sites"], spec_lexical)
    proof_sites = max(ast_counts["proof_sites"], proof_lexical)
    axiom_sites = max(ast_counts["axiom_sites"], axiom_lexical)
    exec_post_sites = ast_counts["exec_post_sites"]
    total_contract_sites = exec_post_sites + assume_with_post
    total_spec_sites = (
        total_contract_sites + model_spec_sites + proof_sites + axiom_sites
    )

    return (
        ModuleStats(
            module=module,
            file=str(relative),
            group=group,
            importance=module_importance(module, group),
            lines=source.count("\n") + (0 if source.endswith("\n") else 1),
            parser_error=tree.root_node.has_error,
            macro_rules_sites=lexical_count(masked, r"\bmacro_rules\s*!"),
            function_sites_ast=ast_counts["function_sites"],
            exec_function_sites=ast_counts["exec_sites"],
            exec_body_sites=ast_counts["exec_body_sites"],
            exec_signature_sites=ast_counts["exec_signature_sites"],
            exec_body_post_sites=ast_counts["exec_body_post_sites"],
            exec_body_requires_only_sites=ast_counts[
                "exec_body_requires_only_sites"
            ],
            exec_body_no_contract_sites=ast_counts[
                "exec_body_no_contract_sites"
            ],
            public_exec_body_sites=ast_counts["public_exec_body_sites"],
            public_exec_body_post_sites=ast_counts[
                "public_exec_body_post_sites"
            ],
            public_exec_body_requires_only_sites=ast_counts[
                "public_exec_body_requires_only_sites"
            ],
            public_exec_body_no_contract_sites=ast_counts[
                "public_exec_body_no_contract_sites"
            ],
            public_exec_body_no_post_sites=ast_counts[
                "public_exec_body_no_post_sites"
            ],
            exec_contract_sites=ast_counts["exec_contract_sites"],
            exec_post_sites=exec_post_sites,
            trait_exec_contract_sites=ast_counts[
                "trait_exec_contract_sites"
            ],
            public_exec_no_post_sites=ast_counts[
                "public_exec_no_post_sites"
            ],
            assume_spec_sites=assume_total,
            assume_spec_with_post_sites=assume_with_post,
            assume_spec_without_post_sites=assume_total - assume_with_post,
            model_spec_fn_sites=model_spec_sites,
            proof_fn_sites=proof_sites,
            axiom_fn_sites=axiom_sites,
            requires_clause_sites=lexical_count(
                masked, r"(?<![.\w])requires\b"
            ),
            ensures_clause_sites=lexical_count(
                masked, r"(?<![.\w])ensures\b"
            ),
            returns_clause_sites=lexical_count(
                masked, r"(?<![.\w])returns\b"
            ),
            default_ensures_sites=lexical_count(
                masked, r"(?<![.\w])default_ensures\b"
            ),
            external_trait_spec_sites=lexical_count(
                masked,
                r"#\s*\[\s*verifier::external_trait_specification\s*\]",
            ),
            external_type_spec_sites=lexical_count(
                masked,
                r"#\s*\[\s*verifier::external_type_specification\s*\]",
            ),
            external_body_sites=lexical_count(
                masked, r"#\s*\[\s*verifier(?:::|\s*\()\s*external_body"
            ),
            view_impl_sites=lexical_count(
                masked, r"(?<!Deep)\bView\s+for\b"
            ),
            deep_view_impl_sites=lexical_count(
                masked, r"\bDeepView\s+for\b"
            ),
            broadcast_group_sites=lexical_count(
                masked, r"\bbroadcast\s+group\b"
            ),
            total_contract_sites=total_contract_sites,
            total_spec_sites=total_spec_sites,
        ),
        exec_items,
    )


def aggregate(rows: list[ModuleStats], key: str) -> list[dict]:
    grouped: dict[str, list[ModuleStats]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, key)].append(row)

    result = []
    for name, items in grouped.items():
        result.append(
            {
                key: name,
                "modules": len(items),
                "lines": sum(item.lines for item in items),
                "exec_body_sites": sum(item.exec_body_sites for item in items),
                "exec_body_post_sites": sum(
                    item.exec_body_post_sites for item in items
                ),
                "exec_body_requires_only_sites": sum(
                    item.exec_body_requires_only_sites for item in items
                ),
                "exec_body_no_contract_sites": sum(
                    item.exec_body_no_contract_sites for item in items
                ),
                "exec_signature_sites": sum(
                    item.exec_signature_sites for item in items
                ),
                "public_exec_body_sites": sum(
                    item.public_exec_body_sites for item in items
                ),
                "public_exec_body_post_sites": sum(
                    item.public_exec_body_post_sites for item in items
                ),
                "public_exec_body_requires_only_sites": sum(
                    item.public_exec_body_requires_only_sites for item in items
                ),
                "public_exec_body_no_contract_sites": sum(
                    item.public_exec_body_no_contract_sites for item in items
                ),
                "public_exec_body_no_post_sites": sum(
                    item.public_exec_body_no_post_sites for item in items
                ),
                "exec_post_sites": sum(item.exec_post_sites for item in items),
                "assume_spec_with_post_sites": sum(
                    item.assume_spec_with_post_sites for item in items
                ),
                "model_spec_fn_sites": sum(
                    item.model_spec_fn_sites for item in items
                ),
                "proof_fn_sites": sum(item.proof_fn_sites for item in items),
                "axiom_fn_sites": sum(item.axiom_fn_sites for item in items),
                "total_contract_sites": sum(
                    item.total_contract_sites for item in items
                ),
                "total_spec_sites": sum(item.total_spec_sites for item in items),
                "parser_error_modules": sum(item.parser_error for item in items),
                "macro_rules_sites": sum(item.macro_rules_sites for item in items),
            }
        )
    return result


def totals(rows: list[ModuleStats]) -> dict:
    if not rows:
        return {"modules": 0, "parser_error_modules": 0}
    numeric_fields = [
        name
        for name, value in asdict(rows[0]).items()
        if isinstance(value, int) and name != "parser_error"
    ]
    result = {name: sum(getattr(row, name) for row in rows) for name in numeric_fields}
    result["modules"] = len(rows)
    result["parser_error_modules"] = sum(row.parser_error for row in rows)
    return result


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(text: str) -> str:
    return text.replace("|", r"\|").replace("\n", " ")


def render_markdown(
    metadata: dict,
    group_rows: list[dict],
    modules: list[ModuleStats],
    exec_items: list[ExecItem],
) -> str:
    lines = [
        "## Appendix: generated module inventory",
        "",
        f"- Snapshot: `{metadata['source']}`",
        f"- Commit: `{metadata['commit']}`",
        f"- Snapshot date: `{metadata['snapshot_date']}`",
        "- Counting unit: source declaration sites; macro templates count once.",
        "- `Total spec sites` = exec postconditions + assume specs with postconditions + model spec fns + proof fns + axiom fns.",
        "",
        "## Group summary",
        "",
        "| Group | Modules | Lines | Exec bodies | Public exec | Public no-post | Signature-only | Contract sites | Total spec sites | Parse errors |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    group_rank = {name: index for index, name in enumerate(GROUP_ORDER)}
    for row in sorted(group_rows, key=lambda item: group_rank.get(item["group"], 999)):
        lines.append(
            "| {group} | {modules} | {lines} | {exec_body_sites} | "
            "{public_exec_body_sites} | {public_exec_body_no_post_sites} | "
            "{exec_signature_sites} | {total_contract_sites} | {total_spec_sites} | "
            "{parser_error_modules} |".format(**row)
        )

    lines.extend(
        [
            "",
            "## Per-module inventory",
            "",
            "| Module | Group | Importance | Lines | Exec bodies | Public exec | Public post | Public requires-only | Public no-contract | Signature-only | Assume post/all | Model spec fn | Proof+axiom | Parse error |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in sorted(
        modules,
        key=lambda item: (
            group_rank.get(item.group, 999),
            {"critical": 0, "high": 1, "medium": 2, "specialized": 3, "support": 4}.get(
                item.importance, 9
            ),
            item.module,
        ),
    ):
        lines.append(
            f"| `{row.module}` | {row.group} | {row.importance} | {row.lines} | "
            f"{row.exec_body_sites} | {row.public_exec_body_sites} | "
            f"{row.public_exec_body_post_sites} | "
            f"{row.public_exec_body_requires_only_sites} | "
            f"{row.public_exec_body_no_contract_sites} | "
            f"{row.exec_signature_sites} | "
            f"{row.assume_spec_with_post_sites}/{row.assume_spec_sites} | "
            f"{row.model_spec_fn_sites} | "
            f"{row.proof_fn_sites + row.axiom_fn_sites} | "
            f"{'yes' if row.parser_error else ''} |"
        )

    lines.extend(
        [
            "",
            "## Exec function list grouped by module",
            "",
            "This list includes every source-level exec definition and signature found by the scanner.",
            "`definition` has a function body; `signature` is a trait/declaration-only item.",
            "",
        ]
    )
    items_by_module: dict[str, list[ExecItem]] = defaultdict(list)
    for item in exec_items:
        items_by_module[item.module].append(item)

    sorted_modules = sorted(
        modules,
        key=lambda item: (
            group_rank.get(item.group, 999),
            {"critical": 0, "high": 1, "medium": 2, "specialized": 3, "support": 4}.get(
                item.importance, 9
            ),
            item.module,
        ),
    )
    for module_row in sorted_modules:
        items = items_by_module.get(module_row.module, [])
        if not items:
            continue
        definitions = sum(item.node_kind == "definition" for item in items)
        signatures = len(items) - definitions
        lines.extend(
            [
                f"### `{module_row.module}`",
                "",
                f"- Definitions: {definitions}",
                f"- Signature-only declarations: {signatures}",
                "",
                "| Line | Kind | Function | Context | Visibility | Contract | Flags |",
                "|---:|---|---|---|---|---|---|",
            ]
        )
        for item in sorted(
            items,
            key=lambda value: (value.line, value.node_kind, value.name),
        ):
            contract = item.contract_status
            if item.post_kinds:
                contract += f" ({item.post_kinds})"
            lines.append(
                f"| {item.line} | {item.node_kind} | `{markdown_cell(item.name)}` | "
                f"`{markdown_cell(item.context)}` | {item.visibility} | "
                f"{markdown_cell(contract)} | {markdown_cell(item.flags)} |"
            )
    return "\n".join(lines) + "\n"


def update_report(path: Path, generated: str) -> None:
    if not path.is_file():
        raise SystemExit(f"report template not found: {path}")
    text = path.read_text()
    try:
        begin = text.index(REPORT_BEGIN)
        end = text.index(REPORT_END, begin)
    except ValueError as exc:
        raise SystemExit(
            f"report markers not found in {path}: "
            f"{REPORT_BEGIN!r} / {REPORT_END!r}"
        ) from exc
    prefix = text[: begin + len(REPORT_BEGIN)]
    suffix = text[end:]
    path.write_text(
        prefix + "\n\n" + generated.rstrip() + "\n\n" + suffix
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vstd-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--commit", default="unknown")
    parser.add_argument("--snapshot-date", default="unknown")
    parser.add_argument(
        "--source", default="verus-lang/verus source/vstd"
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="write JSON/CSV only; do not update README",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.vstd_root.resolve()
    if not (root / "vstd.rs").is_file():
        raise SystemExit(f"not a vstd source root: {root}")

    parser = ts.Parser(ts.Language(tsv.language()))
    scanned = [
        scan_file(parser, root, path)
        for path in sorted(root.rglob("*.rs"))
        if path.name != "build.rs"
    ]
    modules = [module for module, _ in scanned]
    exec_items = [
        item
        for _, module_items in scanned
        for item in module_items
    ]
    group_rows = aggregate(modules, "group")
    importance_rows = aggregate(modules, "importance")
    group_rank = {name: index for index, name in enumerate(GROUP_ORDER)}
    group_rows.sort(key=lambda row: group_rank.get(row["group"], 999))
    importance_rank = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "specialized": 3,
        "support": 4,
    }
    importance_rows.sort(
        key=lambda row: importance_rank.get(row["importance"], 999)
    )
    metadata = {
        "source": args.source,
        "commit": args.commit,
        "snapshot_date": args.snapshot_date,
        "vstd_root": str(root),
        "counting_model": (
            "Source declaration sites. Macro templates count once; "
            "tree-sitter parse-error modules are explicitly marked."
        ),
    }
    payload = {
        "metadata": metadata,
        "totals": totals(modules),
        "groups": group_rows,
        "importance": importance_rows,
        "modules": [asdict(row) for row in modules],
        "exec_functions": [asdict(item) for item in exec_items],
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inventory.json").write_text(json.dumps(payload, indent=2) + "\n")
    module_dicts = [asdict(row) for row in modules]
    write_csv(
        out_dir / "modules.csv",
        module_dicts,
        list(module_dicts[0].keys()),
    )
    write_csv(
        out_dir / "groups.csv",
        group_rows,
        list(group_rows[0].keys()),
    )
    exec_dicts = [asdict(item) for item in exec_items]
    write_csv(
        out_dir / "exec_functions.csv",
        exec_dicts,
        list(exec_dicts[0].keys()),
    )
    if not args.no_report:
        update_report(
            out_dir.parent / "README.md",
            render_markdown(metadata, group_rows, modules, exec_items),
        )

    print(
        f"wrote {len(modules)} modules, "
        f"{len(exec_items)} exec declarations, "
        f"{payload['totals']['total_spec_sites']} spec sites to {out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
