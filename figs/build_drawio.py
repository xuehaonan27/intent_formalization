#!/usr/bin/env python3
"""Build a semantic drawio reconstruction of spec-determin.png.

The output is made from editable drawio elements: text, frames, arrows, and
separate icon cells. It intentionally avoids embedding the full PNG or a
pixel/color-block trace.
"""

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom


ROOT = Path(__file__).resolve().parent
DRAWIO_PATH = ROOT / "spec-determin.drawio"
ICON_DIR = ROOT / "icons"
W, H = 1536, 1024


cells: list[dict[str, object]] = []
_next_id = 10


def nid() -> str:
    global _next_id
    _next_id += 1
    return str(_next_id)


def add_cell(
    value: str,
    x: float,
    y: float,
    w: float,
    h: float,
    style: str,
    *,
    parent: str = "1",
) -> str:
    cid = nid()
    cells.append(
        {
            "id": cid,
            "value": value,
            "style": style,
            "parent": parent,
            "vertex": "1",
            "geo": (x, y, w, h),
        }
    )
    return cid


def add_edge(
    src: str,
    tgt: str,
    style: str = "endArrow=classic;html=1;strokeColor=#111827;strokeWidth=1.4;",
    *,
    label: str = "",
) -> str:
    cid = nid()
    cells.append(
        {
            "id": cid,
            "value": label,
            "style": style,
            "parent": "1",
            "edge": "1",
            "source": src,
            "target": tgt,
            "geo_edge": True,
        }
    )
    return cid


def anchor(x: float, y: float) -> str:
    return add_cell("", x, y, 1, 1, "shape=none;fillColor=none;strokeColor=none;")


def text(value: str, x: float, y: float, w: float, h: float, style: str = "") -> str:
    base = "text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;"
    return add_cell(value, x, y, w, h, base + style)


def box(x: float, y: float, w: float, h: float, stroke: str, fill: str = "#FFFFFF", extra: str = "") -> str:
    return add_cell(
        "",
        x,
        y,
        w,
        h,
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=3;fillColor={fill};strokeColor={stroke};{extra}",
    )


def line(x1: float, y1: float, x2: float, y2: float, color: str = "#111827", width: float = 1.3) -> str:
    a = anchor(x1, y1)
    b = anchor(x2, y2)
    return add_edge(a, b, f"endArrow=none;html=1;strokeColor={color};strokeWidth={width};")


def arrow(x1: float, y1: float, x2: float, y2: float, color: str = "#111827", width: float = 1.4) -> str:
    a = anchor(x1, y1)
    b = anchor(x2, y2)
    return add_edge(a, b, f"endArrow=classic;html=1;strokeColor={color};strokeWidth={width};")


def img_cell(path: Path, x: float, y: float, w: float, h: float) -> str:
    ext = path.suffix.lower().lstrip(".")
    mime = "image/svg+xml" if ext == "svg" else f"image/{ext}"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return add_cell(
        "",
        x,
        y,
        w,
        h,
        "shape=image;html=1;verticalLabelPosition=bottom;verticalAlign=top;"
        f"imageAspect=0;aspect=fixed;image=data:{mime},{data};",
    )


def label_box(
    value: str,
    x: float,
    y: float,
    w: float,
    h: float,
    stroke: str,
    fill: str,
    text_style: str,
    box_extra: str = "",
) -> tuple[str, str]:
    frame = box(x, y, w, h, stroke, fill, box_extra)
    label = text(value, x + 6, y + 6, w - 12, h - 12, text_style)
    return frame, label


def code_html(body: str, size: float = 10.2, pad: int = 7, line_height: float = 1.45) -> str:
    return (
        f"<div style='font-family:Consolas,monospace;font-size:{size}px;"
        f"text-align:left;padding:{pad}px;line-height:{line_height};'>{body}</div>"
    )


BLUE = "#0B4FB3"
BLUE_STROKE = "#3B82F6"
GREEN = "#0B5A16"
GREEN_STROKE = "#6BB684"
ORANGE = "#FF4B00"
ORANGE_STROKE = "#FF7A22"
RED = "#D80000"
PURPLE = "#0000A0"
NAVY = "#071738"
GRAY_TEXT = "#1F2937"


# Background
add_cell("", 0, 0, W, H, "rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=none;")

# Title
text(
    "<font style='font-size:36px'><b>Spec-Determinism Pipeline: From One Function to a Verdict</b></font>",
    160,
    4,
    1215,
    52,
    f"align=center;verticalAlign=middle;fontColor={NAVY};fontFamily=Arial;",
)
text(
    "<font style='font-size:16px'><i>Determine whether a function&rsquo;s specification uniquely determines its post-state.</i></font>",
    355,
    62,
    820,
    28,
    "align=center;verticalAlign=middle;fontColor=#4B5563;fontFamily=Arial;",
)


# Input panel
input_panel = box(15, 221, 116, 340, "#6B7280", "#FFFFFF", "arcSize=8;")
text("<b>Input</b>", 35, 239, 76, 25, "align=center;verticalAlign=middle;fontSize=16;fontColor=#111111;fontFamily=Arial;")
add_cell("", 47, 276, 58, 48, "shape=folder;html=1;whiteSpace=wrap;fillColor=#F8CE7E;strokeColor=#D18B16;tabWidth=22;tabHeight=10;tabPosition=left;")
text("Repository", 31, 338, 86, 22, "align=center;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")
add_cell("", 55, 376, 38, 42, "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=#FFFFFF;strokeColor=#6B7280;")
line(62, 388, 82, 388, "#9CA3AF", 1)
line(62, 396, 84, 396, "#9CA3AF", 1)
line(62, 404, 79, 404, "#9CA3AF", 1)
text("Target function<br><b>f(...)</b>", 26, 431, 94, 42, "align=center;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")
text("(source code<br>+ ensures)", 25, 490, 94, 42, "align=center;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")


# Panel 1: Build Obligation
p1 = box(155, 107, 322, 652, BLUE_STROKE, "#FFFFFF", "arcSize=2;")
line(155, 153, 477, 153, BLUE_STROKE, 1)
add_cell("<b>1</b>", 225, 115, 29, 29, f"ellipse;html=1;fillColor={BLUE};strokeColor={BLUE};fontColor=#FFFFFF;align=center;verticalAlign=middle;fontStyle=1;fontSize=16;")
text("<b>Build Obligation</b>", 265, 120, 170, 28, f"align=left;verticalAlign=middle;fontSize=16;fontColor={BLUE};fontFamily=Arial;")

text("Extract specification", 232, 169, 170, 23, "align=center;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")
sig = code_html(
    "Original signature:<br>"
    "fn values_agree(&amp;self, lo: usize, hi: usize,<br>"
    "&nbsp;&nbsp;v: &amp;ID) -&gt; (ret: (bool, bool))<br><br>"
    "requires P(x)<br>"
    "ensures Q(x, y)",
    10.0,
    8,
    1.45,
)
add_cell(sig, 168, 193, 293, 108, f"rounded=1;whiteSpace=wrap;html=1;arcSize=3;fillColor=#FFFFFF;strokeColor={BLUE_STROKE};verticalAlign=top;")
arrow(313, 301, 313, 326)
text("Generate two functions", 231, 332, 170, 23, "align=center;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")

eq_frame = box(168, 359, 294, 122, BLUE_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{BLUE}'>Equal fn (view &amp; ret equivalence)</font></b>", 184, 371, 260, 18, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;")
text(
    code_html(
        "fn values_agree(&amp;self, lo: usize, hi: usize,v: &amp;ID,<br>"
        "&nbsp;&nbsp;y1: (bool, bool), y2: (bool, bool)) -&gt; bool<br><br>"
        "// checks post-self views equal on [lo, hi]<br>"
        "// and returns ret equality",
        10.0,
        0,
        1.42,
    ),
    176,
    397,
    278,
    68,
    "align=left;verticalAlign=top;fontFamily=Consolas;fontSize=10;fontColor=#111111;",
)

det_frame = box(168, 493, 294, 159, BLUE_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{BLUE}'>Determinism obligation (proof fn)</font></b>", 184, 503, 260, 20, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;")
text(
    code_html(
        "proof fn check(&amp;self,x: (lo, hi,v:&amp;ID),<br>"
        "&nbsp;&nbsp;y1: (bool, bool), y2: (bool, bool))<br>"
        "requires P(x)<br>"
        "ensures Q(x, y1) &amp;&amp; Q(x, y2)<br>"
        "&nbsp;&nbsp;==&gt;values_agree(self, lo, hi, v, y1, y2)<br>"
        "{ ... }",
        10.0,
        0,
        1.55,
    ),
    176,
    530,
    278,
    111,
    "align=left;verticalAlign=top;fontFamily=Consolas;fontSize=10;fontColor=#111111;",
)

out_frame = box(168, 668, 294, 79, BLUE_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{BLUE}'>Outputs of this stage</font></b>", 181, 677, 240, 18, "align=left;verticalAlign=middle;fontSize=12;fontFamily=Arial;")
text("&bull;&nbsp; values_agree(...)<br>&bull;&nbsp; check(...)", 181, 704, 250, 35, "align=left;verticalAlign=middle;fontSize=12;fontFamily=Consolas;fontColor=#111111;")


# Panel 2: Prover Loop
p2 = box(503, 107, 409, 641, GREEN_STROKE, "#FFFFFF", "arcSize=2;")
line(503, 153, 912, 153, GREEN_STROKE, 1)
add_cell("<b>2</b>", 579, 115, 29, 29, f"ellipse;html=1;fillColor={GREEN};strokeColor={GREEN};fontColor=#FFFFFF;align=center;verticalAlign=middle;fontStyle=1;fontSize=16;")
text("<b>Prover Loop: Try to Prove check</b>", 617, 120, 280, 28, f"align=left;verticalAlign=middle;fontSize=16;fontColor={GREEN};fontFamily=Arial;")

goal_frame = box(518, 175, 377, 84, GREEN_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{GREEN}'>Goal (obligation)</font></b>", 530, 187, 350, 20, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;")
text(
    "Given P(x) &and; Q(x, y1) &and; Q(x, y2),<br>"
    "prove values_agree(self, lo, hi, v, y1, y2)",
    547,
    213,
    320,
    36,
    "align=center;verticalAlign=middle;fontSize=12;fontFamily=Consolas;fontColor=#111111;",
)
arrow(706, 259, 706, 291)

iter_outer = box(518, 292, 377, 253, GREEN_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{GREEN}'>Each Iteration</font></b>", 642, 304, 130, 21, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;")
improve = box(533, 329, 344, 103, GREEN_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{GREEN}'>(Optional) Improve attempt (always done)</font></b>", 547, 343, 260, 18, "align=left;verticalAlign=middle;fontSize=12;fontFamily=Arial;")
text(
    "&bull;&nbsp; Add proof code / lemmas<br>"
    "&bull;&nbsp; Refine or strengthen equal function<br>"
    "&bull;&nbsp; Record justification for the change",
    545,
    366,
    258,
    52,
    "align=left;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;",
)
add_cell("", 786, 376, 19, 25, "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=#FFFFFF;strokeColor=#9CA3AF;")
line(790, 385, 800, 385, "#9CA3AF", 0.8)
line(790, 390, 801, 390, "#9CA3AF", 0.8)
text("proof.rs", 812, 381, 58, 18, "align=left;verticalAlign=middle;fontSize=10;fontColor=#111111;fontFamily=Consolas;")
add_cell("", 786, 414, 19, 25, "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=#FFFFFF;strokeColor=#9CA3AF;")
line(790, 423, 800, 423, "#9CA3AF", 0.8)
line(790, 428, 801, 428, "#9CA3AF", 0.8)
text("equal_fn.rs", 812, 419, 70, 18, "align=left;verticalAlign=middle;fontSize=10;fontColor=#111111;fontFamily=Consolas;")
line(518, 456, 895, 456, GREEN_STROKE, 1)
text("&bull;&nbsp; <b>Call Verus / Z3 (required)</b>", 531, 470, 245, 24, "align=left;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")
text("&#9881;", 566, 492, 43, 43, "align=center;verticalAlign=middle;fontSize=16;fontColor=#8B8F99;fontFamily=Arial;")
text("<b>verus</b>", 618, 501, 58, 24, "align=left;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")
arrow(676, 513, 704, 513, "#111827", 1.5)
z3 = add_cell("", 721, 497, 31, 39, "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=11;fillColor=#FFFFFF;strokeColor=#9CA3AF;fontSize=10;align=center;verticalAlign=middle;direction=east;")
text("<b>Z3</b><br><font style='font-size:10px'>(SMT Solver)</font>", 759, 500, 90, 37, "align=left;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")

unsat = box(513, 581, 110, 130, GREEN_STROKE, "#F2FBF2", "arcSize=4;")
sat = box(636, 581, 128, 130, "#F87171", "#FFF7F7", "arcSize=4;")
unknown = box(778, 581, 113, 130, "#A78BFA", "#FFFFFF", "arcSize=4;")
text(f"<b><font style='font-size:16px' color='{GREEN}'>UNSAT</font></b><br><font style='font-size:10px'>(proved)</font><br><br>Obligation holds.<br>Spec is complete.<br><font color='{GREEN}' style='font-size:16px'>&#10003;</font>", 520, 603, 96, 96, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;fontColor=#111111;")
text(f"<b><font style='font-size:16px' color='{RED}'>SAT</font></b><br><font style='font-size:10px'>(counterexample exists)</font><br><br>Go to Stage 3<br>(construct witness)", 642, 603, 116, 91, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;fontColor=#111111;")
text(f"<b><font style='font-size:16px' color='{PURPLE}'>UNKNOWN</font></b><br><font style='font-size:10px'>(inconclusive)</font><br><br>Refine and try<br>again in next<br>iteration", 784, 603, 101, 96, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;fontColor=#111111;")

for x in (568, 700, 834):
    arrow(x, 545, x, 581)
footer = box(528, 725, 346, 31, GREEN_STROKE, "#F2FBF2", "arcSize=4;")
text("<b>Iterate until: UNSAT (complete) or SAT (counterexample)</b>", 534, 732, 336, 17, f"align=center;verticalAlign=middle;fontSize=12;fontColor={GREEN};fontFamily=Arial;")
arrow(700, 711, 700, 725)
add_edge(
    unknown,
    improve,
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#111827;strokeWidth=1.3;exitX=1;exitY=0.55;entryX=1;entryY=0.5;",
)


# Panel 3: Witness Construction
p3 = box(932, 107, 587, 596, ORANGE_STROKE, "#FFFFFF", "arcSize=2;")
line(932, 153, 1519, 153, ORANGE_STROKE, 1)
add_cell("<b>3</b>", 1051, 115, 29, 29, f"ellipse;html=1;fillColor=#E66900;strokeColor=#E66900;fontColor=#FFFFFF;align=center;verticalAlign=middle;fontStyle=1;fontSize=16;")
text("<b>Witness Construction (always SAT here)</b>", 1087, 120, 350, 28, f"align=left;verticalAlign=middle;fontSize=16;fontColor={ORANGE};fontFamily=Arial;")
text(
    "Find concrete <font face='Consolas'>(x, y1, y2)</font> satisfying all assumptions<br>"
    "but violating <font face='Consolas'>values_agree(self, lo, hi, v, y1, y2)</font>",
    1038,
    164,
    374,
    38,
    "align=center;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;",
)

tree_panel = box(945, 217, 320, 468, ORANGE_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{ORANGE}'>Type-Guided Narrowing</font></b><br><font style='font-size:10px' color='{ORANGE}'>Dependency tree of variables and leaves</font>", 976, 232, 256, 38, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;lineHeight=1.15;")

def tree_node(label: str, x: float, y: float, w: float, h: float, *, group: bool = False) -> str:
    fill = "#FFE8D6" if group else "#FFF7F0"
    size = 12 if group else 10
    return add_cell(
        label,
        x,
        y,
        w,
        h,
        f"rounded=1;whiteSpace=wrap;html=1;arcSize=4;fillColor={fill};strokeColor={ORANGE_STROKE};"
        f"fontSize={size};fontFamily=Consolas;align=center;verticalAlign=middle;",
    )

TREE_LINE = "#374151"

root_xy = (1045, 286, 120, 30)
x_xy = (962, 362, 54, 30)
y1_xy = (1078, 362, 54, 30)
y2_xy = (1184, 362, 54, 30)

x_pre_xy = (950, 478, 72, 28)
x_lo_xy = (1030, 478, 36, 28)
x_hi_xy = (992, 550, 36, 28)

y1_post_xy = (1068, 478, 76, 28)
y1_b0_xy = (1048, 606, 52, 28)
y1_b1_xy = (1104, 606, 52, 28)

y2_post_xy = (1168, 478, 76, 28)
y2_b0_xy = (1160, 606, 52, 28)
y2_b1_xy = (1212, 606, 52, 28)

def cx(rect: tuple[float, float, float, float]) -> float:
    return rect[0] + rect[2] / 2

def cy(rect: tuple[float, float, float, float]) -> float:
    return rect[1] + rect[3] / 2

def bottom(rect: tuple[float, float, float, float]) -> float:
    return rect[1] + rect[3]

def top(rect: tuple[float, float, float, float]) -> float:
    return rect[1]

# Straight, v10-style tree connectors.
main_bus_y = 338
line(cx(root_xy), bottom(root_xy), cx(root_xy), main_bus_y, TREE_LINE, 1.2)
line(cx(x_xy), main_bus_y, cx(y2_xy), main_bus_y, TREE_LINE, 1.2)
for child in (x_xy, y1_xy, y2_xy):
    line(cx(child), main_bus_y, cx(child), top(child), TREE_LINE, 1.2)

x_bus_y = 442
line(cx(x_xy), bottom(x_xy), cx(x_xy), x_bus_y, TREE_LINE, 1.2)
line(cx(x_pre_xy), x_bus_y, cx(x_hi_xy), x_bus_y, TREE_LINE, 1.2)
for child in (x_pre_xy, x_lo_xy, x_hi_xy):
    line(cx(child), x_bus_y, cx(child), top(child), TREE_LINE, 1.2)

y1_bus_y = 442
y1_bool_bus_y = 582
line(cx(y1_xy), bottom(y1_xy), cx(y1_xy), y1_bool_bus_y, TREE_LINE, 1.2)
line(cx(y1_post_xy), y1_bus_y, cx(y1_xy), y1_bus_y, TREE_LINE, 1.2)
line(cx(y1_post_xy), y1_bus_y, cx(y1_post_xy), top(y1_post_xy), TREE_LINE, 1.2)
line(cx(y1_b0_xy), y1_bool_bus_y, cx(y1_b1_xy), y1_bool_bus_y, TREE_LINE, 1.2)
for child in (y1_b0_xy, y1_b1_xy):
    line(cx(child), y1_bool_bus_y, cx(child), top(child), TREE_LINE, 1.2)

y2_bus_y = 442
y2_bool_bus_y = 582
line(cx(y2_xy), bottom(y2_xy), cx(y2_xy), y2_bool_bus_y, TREE_LINE, 1.2)
line(cx(y2_post_xy), y2_bus_y, cx(y2_xy), y2_bus_y, TREE_LINE, 1.2)
line(cx(y2_post_xy), y2_bus_y, cx(y2_post_xy), top(y2_post_xy), TREE_LINE, 1.2)
line(cx(y2_b0_xy), y2_bool_bus_y, cx(y2_b1_xy), y2_bool_bus_y, TREE_LINE, 1.2)
for child in (y2_b0_xy, y2_b1_xy):
    line(cx(child), y2_bool_bus_y, cx(child), top(child), TREE_LINE, 1.2)

root = tree_node("(x, y1, y2)", *root_xy, group=True)
x_node = tree_node("x", *x_xy, group=True)
y1_node = tree_node("y1", *y1_xy, group=True)
y2_node = tree_node("y2", *y2_xy, group=True)

x_pre = tree_node("pre(self)", *x_pre_xy)
x_lo = tree_node("lo", *x_lo_xy)
x_hi = tree_node("hi", *x_hi_xy)
text("...", x_pre_xy[0] + 20, bottom(x_pre_xy) + 6, 32, 18, "align=center;verticalAlign=middle;fontSize=10;fontColor=#111111;fontFamily=Consolas;")

y1_post = tree_node("post(self)", *y1_post_xy)
y1_b0 = tree_node(".0: bool", *y1_b0_xy)
y1_b1 = tree_node(".1: bool", *y1_b1_xy)
text("...", y1_post_xy[0] + 22, bottom(y1_post_xy) + 6, 32, 18, "align=center;verticalAlign=middle;fontSize=10;fontColor=#111111;fontFamily=Consolas;")

y2_post = tree_node("post(self)", *y2_post_xy)
y2_b0 = tree_node(".0: bool", *y2_b0_xy)
y2_b1 = tree_node(".1: bool", *y2_b1_xy)
text("...", y2_post_xy[0] + 22, bottom(y2_post_xy) + 6, 32, 18, "align=center;verticalAlign=middle;fontSize=10;fontColor=#111111;fontFamily=Consolas;")


inc_panel = box(1281, 217, 224, 468, ORANGE_STROKE, "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{ORANGE}'>Incremental Narrowing</font></b>", 1295, 235, 200, 20, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;")

def step(label: str, y: float, hhh: float) -> str:
    return add_cell(label, 1295, y, 200, hhh, f"rounded=1;whiteSpace=wrap;html=1;arcSize=3;fillColor=#FFFFFF;strokeColor={ORANGE_STROKE};fontSize=12;fontFamily=Arial;align=center;verticalAlign=middle;")

s1 = step("<b>Start:</b> no assumptions<br>(all unknowns)", 255, 50)
s2 = step("Select next leaf<br>by type &amp; structure", 317, 48)
s3 = step("Add assumption<br>(e.g., len() == 1,<br>keys@[0] == K::zero_spec(),<br>.0 == true,...)", 379, 78)
s4 = step("Query Verus / Z3<br>under all current assumptions", 470, 46)
s5 = step("If more models remain:<br>add more assumptions<br>(narrow further)", 529, 68)
s6 = step("If still SAT and unequal:<br>we have a concrete witness", 609, 45)
for a, b in [(s1, s2), (s2, s3), (s3, s4), (s4, s5), (s5, s6)]:
    add_edge(a, b, "endArrow=classic;html=1;strokeColor=#111827;strokeWidth=1.2;exitX=0.5;exitY=1;entryX=0.5;entryY=0;")


# Bottom: Final Verdict
fv = box(99, 780, 526, 213, BLUE_STROKE, "#FFFFFF", "arcSize=2;")
img_cell(ROOT / "天平.svg", 114, 792, 48, 48)
text("<b>Final Verdict</b>", 180, 798, 170, 30, f"align=left;verticalAlign=middle;fontSize=16;fontColor={BLUE};fontFamily=Arial;")
complete = box(113, 834, 229, 146, GREEN_STROKE, "#FFFFFF", "arcSize=3;")
incomplete = box(358, 834, 255, 146, "#F87171", "#FFFFFF", "arcSize=3;")
text(f"<b><font color='{GREEN}'>Complete (Deterministic)</font></b><br><br>check is proven.<br><br>No two models can satisfy the<br>spec while violating values_agree.", 125, 852, 205, 110, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;fontColor=#111111;")
text(f"<b><font color='{RED}'>Incomplete (Non-deterministic)</font></b><br><br>Found witness (x, y1, y2) such that<br><br>P(x) &and; Q(x, y1) &and; Q(x, y2) &and;<br><br>!values_agree(self, lo, hi, v, y1, y2).", 369, 852, 231, 111, "align=center;verticalAlign=middle;fontSize=12;fontFamily=Arial;fontColor=#111111;")


# Bottom: Witness Output
wo = box(672, 765, 847, 237, ORANGE_STROKE, "#FFFFFF", "arcSize=2;")
add_cell("", 691, 777, 28, 32, "shape=document;whiteSpace=wrap;html=1;boundedLbl=1;fillColor=#FFFFFF;strokeColor=#8B5CF6;fontColor=#8B5CF6;")
line(697, 789, 711, 789, "#8B5CF6", 1)
line(697, 796, 713, 796, "#8B5CF6", 1)
text("<b>Witness Output (concrete and verified)</b>", 728, 777, 360, 28, f"align=left;verticalAlign=middle;fontSize=16;fontColor={ORANGE};fontFamily=Arial;")
cw = box(682, 809, 495, 179, ORANGE_STROKE, "#FFFFFF", "arcSize=3;")
text("<b>Concrete witness (x, y1, y2)</b>", 694, 818, 250, 20, "align=left;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")
text(
    "&bull;&nbsp; lo == 0<br>"
    "&bull;&nbsp; hi == 0<br>"
    "&bull;&nbsp; self_.keys@.len() == 1<br>"
    "&bull;&nbsp; self_.keys@[0] == K::zero_spec()<br>"
    "&bull;&nbsp; self_.vals@.len() == 1<br>"
    "&bull;&nbsp; self_.vals@[0] == EndPoint{ id: seq![1u8]}<br>"
    "&bull;&nbsp; v == EndPoint{ id: seq![1u8] }",
    694,
    842,
    250,
    128,
    "align=left;verticalAlign=top;fontSize=10;fontColor=#111111;fontFamily=Consolas;lineHeight=1.35;",
)
line(954, 840, 954, 965, "#D1D5DB", 1)
text(
    "&bull;&nbsp; r1.0 == true<br>"
    "&bull;&nbsp; r1.1 == true<br>"
    "&bull;&nbsp; r2.0 == true<br>"
    "&bull;&nbsp; r2.1 == false<br>"
    "&bull;&nbsp; !values_agree(self, lo, hi, v, r1, r2)",
    966,
    842,
    198,
    103,
    "align=left;verticalAlign=top;fontSize=10;fontColor=#111111;fontFamily=Consolas;lineHeight=1.45;",
)
text("Verified by Verus", 1198, 793, 160, 22, "align=left;verticalAlign=middle;fontSize=12;fontColor=#111111;fontFamily=Arial;")
verus_code = box(1197, 813, 229, 172, ORANGE_STROKE, "#FFFFFF", "arcSize=3;")
text(
    code_html(
        "proof fn check_witness(...)<br>"
        "requires P(x)<br>"
        "requires Q(x, y1)<br>"
        "requires Q(x, y2)<br>"
        "requires &lt;all assumptions above&gt;<br>"
        "ensures !values_agree(self, lo, hi, v, y1, y2)<br>"
        "{<br>"
        "&nbsp;&nbsp;assert(!values_agree(...));<br>"
        "}",
        10.0,
        0,
        1.38,
    ),
    1207,
    823,
    207,
    149,
    "align=left;verticalAlign=top;fontSize=10;fontFamily=Consolas;fontColor=#111111;",
)
z3_2 = add_cell("<b>Verus / Z3</b><br><font style='font-size:10px'>(SMT)</font>", 1446, 845, 61, 64, "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=12;fillColor=#FFFFFF;strokeColor=#D97706;fontSize=10;align=center;verticalAlign=middle;direction=east;")
add_edge(verus_code, z3_2, "endArrow=classic;html=1;strokeColor=#111827;strokeWidth=1.4;exitX=1;exitY=0.36;entryX=0;entryY=0.5;")


# Cross-panel arrows
add_edge(input_panel, p1, "endArrow=classic;html=1;strokeColor=#111827;strokeWidth=1.4;exitX=1;exitY=0.51;entryX=0;entryY=0.44;")
add_edge(p1, p2, "endArrow=classic;html=1;strokeColor=#111827;strokeWidth=1.4;exitX=1;exitY=0.44;entryX=0;entryY=0.44;")
arrow(342, 759, 342, 780, "#111827", 1.4)
add_edge(p2, fv, "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeColor=#111827;strokeWidth=1.4;exitX=0.03;exitY=1;entryX=0.72;entryY=0;")
arrow(1157, 703, 1157, 765, "#111827", 1.4)
add_edge(wo, fv, "endArrow=classic;html=1;strokeColor=#111827;strokeWidth=1.4;exitX=0;exitY=0.47;entryX=1;entryY=0.45;")


# Build XML
mxfile = ET.Element("mxfile", host="app.diagrams.net")
diagram = ET.SubElement(mxfile, "diagram", id="spec-det", name="Spec-Determinism")
graph = ET.SubElement(
    diagram,
    "mxGraphModel",
    dx=str(W),
    dy=str(H),
    grid="1",
    gridSize="10",
    guides="1",
    tooltips="1",
    connect="1",
    arrows="1",
    fold="1",
    page="1",
    pageScale="1",
    pageWidth=str(W),
    pageHeight=str(H),
    math="0",
    shadow="0",
)
root_el = ET.SubElement(graph, "root")
ET.SubElement(root_el, "mxCell", id="0")
ET.SubElement(root_el, "mxCell", id="1", parent="0")

for cell_data in cells:
    attrs = {
        "id": str(cell_data["id"]),
        "value": str(cell_data.get("value", "")),
        "style": str(cell_data.get("style", "")),
        "parent": str(cell_data.get("parent", "1")),
    }
    if cell_data.get("vertex"):
        attrs["vertex"] = "1"
    if cell_data.get("edge"):
        attrs["edge"] = "1"
        if cell_data.get("source"):
            attrs["source"] = str(cell_data["source"])
        if cell_data.get("target"):
            attrs["target"] = str(cell_data["target"])
    mx_cell = ET.SubElement(root_el, "mxCell", attrs)
    if cell_data.get("geo"):
        x, y, w, h = cell_data["geo"]  # type: ignore[misc]
        ET.SubElement(mx_cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), **{"as": "geometry"})
    if cell_data.get("geo_edge"):
        ET.SubElement(mx_cell, "mxGeometry", relative="1", **{"as": "geometry"})

xml = ET.tostring(mxfile, encoding="unicode")
xml = xml.replace("fontFamily=Arial", "fontFamily=Helvetica")
xml = xml.replace("fontColor=#111111", "fontColor=#1F2937")
DRAWIO_PATH.write_text(minidom.parseString(xml).toprettyxml(indent="  "), encoding="utf-8")
print(f"Wrote {DRAWIO_PATH.name} with {len(cells)} semantic cells")
print("Embedded full PNG: no")
print("Pixel color-block trace: no")
