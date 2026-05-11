"""Render a per-project dep graph (the JSON produced by
``python -m spec_determinism.type_registry deps``) as a Graphviz DOT
file and SVG / PNG.

Usage:
    python scripts/visualize_deps.py results-verusage/type_registry/atmosphere_deps.json \
        --out /tmp/atmosphere_deps

Produces:
    /tmp/atmosphere_deps.dot
    /tmp/atmosphere_deps.svg
    /tmp/atmosphere_deps.png
"""
import argparse
import json
import subprocess
from pathlib import Path

# Color palette by classification.
COLOR = {
    "struct":    {"fill": "#E3F2FD", "border": "#1976D2"},   # blue
    "enum":      {"fill": "#FFF3E0", "border": "#F57C00"},   # orange
    "alias":     {"fill": "#F3E5F5", "border": "#7B1FA2"},   # purple
    "union":     {"fill": "#E0F7FA", "border": "#0097A7"},   # cyan
    "container": {"fill": "#E8F5E9", "border": "#388E3C"},   # green
    "primitive": {"fill": "#FAFAFA", "border": "#616161"},   # grey
    "external":  {"fill": "#FFEBEE", "border": "#C62828"},   # red
}


def render(deps_json: Path, out_stem: Path,
           hide_containers: bool = False,
           hide_external: bool = False,
           focus: list[str] | None = None,
           layer_topo: bool = True) -> None:
    data = json.loads(deps_json.read_text())
    ag = data["aggregate"]
    nodes = ag["nodes"]
    forward = ag["forward"]
    classification = ag["classification"]
    sccs = ag["sccs"]

    # ---- focus mode: keep only `focus`, their forward closure, their
    # reverse closure, plus the focus types themselves --------------------
    if focus:
        keep: set[str] = set()
        for f in focus:
            keep.add(f)
            keep.update(ag["forward_closure"].get(f, []))
            keep.update(ag["reverse_closure"].get(f, []))
        nodes = [n for n in nodes if n in keep]

    if hide_containers:
        nodes = [n for n in nodes if classification.get(n) != "container"]
    if hide_external:
        nodes = [n for n in nodes if classification.get(n) != "external"]

    node_set = set(nodes)
    scc_for: dict[str, int] = {}
    for i, comp in enumerate(sccs):
        for n in comp:
            scc_for[n] = i

    out: list[str] = []
    out.append(f'digraph "{deps_json.stem}" {{')
    out.append('  rankdir=TB;')               # top→bottom = sources→leaves
    out.append('  graph [bgcolor="white", fontname="Helvetica", '
               'fontsize=12, splines=true, overlap=false, '
               'nodesep=0.25, ranksep=0.75];')
    out.append('  node [shape=box, style="rounded,filled", '
               'fontname="Helvetica", fontsize=11, margin="0.10,0.05"];')
    out.append('  edge [arrowsize=0.6, color="#90A4AE", penwidth=0.8];')

    if layer_topo:
        # Compute longest-path depth from each node to any leaf within the
        # currently-visible subgraph. Memoized DFS; cycles short-circuit.
        kept_forward = {n: [d for d in forward.get(n, []) if d in node_set]
                        for n in nodes}
        depth_cache: dict[str, int] = {}
        in_stack: set[str] = set()

        def depth_of(n: str) -> int:
            if n in depth_cache:
                return depth_cache[n]
            if n in in_stack:
                return 0
            in_stack.add(n)
            outs = kept_forward.get(n, [])
            d = 0 if not outs else 1 + max(depth_of(c) for c in outs)
            in_stack.discard(n)
            depth_cache[n] = d
            return d

        layer_of = {n: depth_of(n) for n in nodes}
        # Group by layer.
        layers: dict[int, list[str]] = {}
        for n, d in layer_of.items():
            layers.setdefault(d, []).append(n)
        # rank=same forces nodes in the same layer onto one row; TB then
        # places higher-layer (deeper) groups below lower-layer groups,
        # so sources are at the top and leaves at the bottom of the graph.
        for d in sorted(layers, reverse=True):    # sources first → top
            same = " ".join(f'"{n}"' for n in layers[d])
            out.append(f'  {{ rank=same; {same} }}')

    for i, comp in enumerate(sccs):
        if len(comp) <= 1:
            continue
        members = [n for n in comp if n in node_set]
        if len(members) <= 1:
            continue
        out.append(f'  subgraph cluster_scc_{i} {{')
        out.append(f'    label=<<b>cycle</b>>;')
        out.append(f'    style="rounded,dashed";')
        out.append(f'    color="#D84315";')
        out.append(f'    fontcolor="#D84315";')
        for n in members:
            out.append(f'    "{n}";')
        out.append('  }')

    for n in nodes:
        cls = classification.get(n, "external")
        col = COLOR.get(cls, COLOR["external"])
        label = f'{n}\\n<{cls}>'
        if focus and n in focus:
            out.append(f'  "{n}" [label="{label}", '
                       f'fillcolor="{col["fill"]}", '
                       f'color="{col["border"]}", '
                       f'penwidth=3.0];')
        else:
            out.append(f'  "{n}" [label="{label}", '
                       f'fillcolor="{col["fill"]}", '
                       f'color="{col["border"]}"];')

    for src, dsts in forward.items():
        if src not in node_set:
            continue
        for d in dsts:
            if d not in node_set:
                continue
            same_scc = (
                scc_for.get(src) is not None
                and scc_for.get(src) == scc_for.get(d)
                and len([m for m in sccs[scc_for[src]] if m in node_set]) > 1
            )
            if same_scc:
                out.append(f'  "{src}" -> "{d}" [color="#D84315", '
                           f'penwidth=1.5];')
            else:
                out.append(f'  "{src}" -> "{d}";')

    out.append('  subgraph cluster_legend {')
    out.append('    label="legend"; style="rounded"; color="#9E9E9E";')
    out.append('    fontcolor="#616161"; fontsize=10;')
    out.append('    node [shape=box, style="rounded,filled", fontsize=9, '
               'margin="0.06,0.03"];')
    for cls, col in COLOR.items():
        out.append(f'    leg_{cls} [label="{cls}", '
                   f'fillcolor="{col["fill"]}", color="{col["border"]}"];')
    out.append('  }')

    out.append('}')
    dot_path = out_stem.with_suffix(".dot")
    dot_path.write_text("\n".join(out))

    for fmt in ("svg", "png"):
        target = out_stem.with_suffix(f".{fmt}")
        subprocess.run(
            ["dot", f"-T{fmt}", str(dot_path), "-o", str(target)],
            check=True,
        )
    print(f"wrote {dot_path}, .svg, .png ({len(nodes)} nodes shown)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("deps_json", type=Path)
    ap.add_argument("--out", type=Path, required=True,
                    help="Output path stem (no extension).")
    ap.add_argument("--hide-containers", action="store_true")
    ap.add_argument("--hide-external", action="store_true")
    ap.add_argument("--focus", nargs="+", default=None,
                    help="Only render these types + their fwd/rev closure.")
    args = ap.parse_args()
    render(args.deps_json, args.out,
           hide_containers=args.hide_containers,
           hide_external=args.hide_external,
           focus=args.focus)
