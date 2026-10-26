"""Generates VerticalLineCorrector.setting, the Fusion macro version.

The macro is a single Corner Positioner whose four corners are driven by
Lua expressions that port the math in reference.py. Writing those
expressions by hand is error-prone, so they are built here and, with
--check, evaluated in Python against reference.py before being written.

    python3 tools/build_macro.py           # check, then write the .setting
"""

import math
import os
import random
import types

import reference as ref

TOOL = "VLCWarp"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "VerticalLineCorrector.setting")

# (id, label, default, min, max) for the visible sliders, in UI order.
SLIDERS = [
    ("TiltV", "Vertical Tilt", 0.0, -60.0, 60.0),
    ("TiltH", "Horizontal Tilt", 0.0, -60.0, 60.0),
    ("Roll", "Level Horizon", 0.0, -45.0, 45.0),
    ("Amount", "Correction Amount", 100.0, 0.0, 150.0),
    ("FOV", "Lens Horizontal FOV", 82.0, 20.0, 140.0),
    ("Zoom", "Zoom", 1.0, 0.5, 3.0),
    ("ShiftX", "Shift X", 0.0, -1.0, 1.0),
    ("ShiftY", "Shift Y", 0.0, -1.0, 1.0),
]


def v(name):
    return f"{TOOL}.{name}"


def source_to_level_expr(x, y):
    """String port of reference.source_to_level, using the hidden helpers."""
    f, cp, sp, cy, sy, cr, sr = (v(n) for n in ("FL", "CP", "SP", "CY", "SY", "CR", "SR"))
    x1 = f"({x}*{cr} - {y}*{sr})"
    y1 = f"({x}*{sr} + {y}*{cr})"
    y2 = f"({y1}*{cp} + {f}*{sp})"
    z2 = f"(-{y1}*{sp} + {f}*{cp})"
    x3 = f"({x1}*{cy} + {z2}*{sy})"
    z3 = f"math.max(-{x1}*{sy} + {z2}*{cy}, 0.000001)"
    return f"{f}*{x3}/{z3}", f"{f}*{y2}/{z3}"


def hidden_exprs():
    """Ordered (id, expression) for every hidden helper control."""
    w, h = v("Input.OriginalWidth"), v("Input.OriginalHeight")
    rad = f"math.pi/180*{v('Amount')}/100"
    e = [
        ("IW", w), ("IH", h),
        ("FL", f"{v('IW')}/2/math.tan(math.pi/360*{v('FOV')})"),
        ("CP", f"math.cos({v('TiltV')}*{rad})"), ("SP", f"math.sin({v('TiltV')}*{rad})"),
        ("CY", f"math.cos({v('TiltH')}*{rad})"), ("SY", f"math.sin({v('TiltH')}*{rad})"),
        ("CR", f"math.cos({v('Roll')}*{rad})"), ("SR", f"math.sin({v('Roll')}*{rad})"),
    ]
    hw, hh = f"{v('IW')}/2", f"{v('IH')}/2"
    # footage corners TL, TR, BR, BL (clockwise, y up) and centre, in level space
    pts = {"TL": (f"-{hw}", hh), "TR": (hw, hh), "BR": (hw, f"-{hh}"),
           "BL": (f"-{hw}", f"-{hh}"), "C0": ("0", "0")}
    for name, (x, y) in pts.items():
        lx, ly = source_to_level_expr(f"({x})", f"({y})")
        e += [(name + "x", lx), (name + "y", ly)]
    e += [("SHX", f"{v('C0x')} + {v('ShiftX')}*{hw}"),
          ("SHY", f"{v('C0y')} + {v('ShiftY')}*{hh}")]
    fits = []
    for p, q in (("TL", "TR"), ("TR", "BR"), ("BR", "BL"), ("BL", "TL")):
        nx = f"(-({v(q + 'y')} - {v(p + 'y')}))"
        ny = f"({v(q + 'x')} - {v(p + 'x')})"
        fits.append(f"({nx}*({v(p + 'x')} - {v('SHX')}) + {ny}*({v(p + 'y')} - {v('SHY')}))"
                    f"/(math.abs({nx})*{hw} + math.abs({ny})*{hh} + 0.000000001)")
    e.append(("K", f"math.max(math.min({', '.join(fits)}), 0.05)"))
    e.append(("S", f"({v('AutoFill')} > 0.5 and {v('Zoom')}/{v('K')} or {v('Zoom')})"))
    return e


def corner_exprs():
    out = {}
    for name, inp in (("TL", "TopLeft"), ("TR", "TopRight"),
                      ("BR", "BottomRight"), ("BL", "BottomLeft")):
        x = f"0.5 + ({v(name + 'x')} - {v('SHX')})*{v('S')}/{v('IW')}"
        y = f"0.5 + ({v(name + 'y')} - {v('SHY')})*{v('S')}/{v('IH')}"
        out[inp] = (x, y)
    return out


# --- verification -----------------------------------------------------------

class _LuaMath:
    pi = math.pi
    sin, cos, tan, abs = staticmethod(math.sin), staticmethod(math.cos), \
        staticmethod(math.tan), staticmethod(abs)
    min, max = staticmethod(min), staticmethod(max)


def evaluate(width, height, **kw):
    kw = dict(kw)
    tool = types.SimpleNamespace(
        Input=types.SimpleNamespace(OriginalWidth=width, OriginalHeight=height),
        AutoFill=1.0 if kw.pop("auto_fill", True) else 0.0)
    for sid, _, default, _, _ in SLIDERS:
        setattr(tool, sid, kw.get(sid, default))
    env = {TOOL: tool, "math": _LuaMath}
    for name, expr in hidden_exprs():
        assert "--" not in expr, f"'--' would start a Lua comment in {name}"
        setattr(tool, name, eval(expr, env))
    return {k: (eval(x, env), eval(y, env)) for k, (x, y) in corner_exprs().items()}


def check():
    rnd = random.Random(7)
    for _ in range(300):
        w, h = rnd.choice([(1920, 1080), (3840, 2160), (2720, 1530), (1080, 1920)])
        kw = dict(TiltV=rnd.uniform(-35, 35), TiltH=rnd.uniform(-20, 20),
                  Roll=rnd.uniform(-8, 8), Amount=rnd.uniform(40, 120),
                  FOV=rnd.uniform(50, 110), Zoom=rnd.uniform(0.8, 1.5),
                  ShiftX=rnd.uniform(-0.2, 0.2), ShiftY=rnd.uniform(-0.2, 0.2),
                  auto_fill=rnd.random() < 0.7)
        got = evaluate(w, h, **kw)
        pr = ref.params(w, h, tilt_v=kw["TiltV"], tilt_h=kw["TiltH"], roll=kw["Roll"],
                        amount=kw["Amount"], fov=kw["FOV"], zoom=kw["Zoom"],
                        shift_x=kw["ShiftX"], shift_y=kw["ShiftY"],
                        auto_fill=kw["auto_fill"])
        corners = dict(zip(("TopLeft", "TopRight", "BottomRight", "BottomLeft"),
                           ref.source_corners_in_level(pr)))
        for k, (lx, ly) in corners.items():
            ex = 0.5 + (lx - pr["shx"]) * pr["scale"] / w
            ey = 0.5 + (ly - pr["shy"]) * pr["scale"] / h
            assert math.isclose(got[k][0], ex, rel_tol=1e-9, abs_tol=1e-9), (k, kw)
            assert math.isclose(got[k][1], ey, rel_tol=1e-9, abs_tol=1e-9), (k, kw)
    print("macro expressions match reference.py (300 random cases)")


# --- .setting writer -----------------------------------------------------------

def lua_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build():
    uc = []
    for sid, label, default, lo, hi in SLIDERS:
        uc.append(f"""\t\t\t\t\t\t{sid} = {{
\t\t\t\t\t\t\tLINKS_Name = {lua_str(label)},
\t\t\t\t\t\t\tLINKID_DataType = "Number",
\t\t\t\t\t\t\tINPID_InputControl = "SliderControl",
\t\t\t\t\t\t\tINP_Default = {default},
\t\t\t\t\t\t\tINP_MinScale = {lo},
\t\t\t\t\t\t\tINP_MaxScale = {hi},
\t\t\t\t\t\t\tICS_ControlPage = "Controls",
\t\t\t\t\t\t}},""")
    uc.append("""\t\t\t\t\t\tAutoFill = {
\t\t\t\t\t\t\tLINKS_Name = "Auto Fill Frame",
\t\t\t\t\t\t\tLINKID_DataType = "Number",
\t\t\t\t\t\t\tINPID_InputControl = "CheckboxControl",
\t\t\t\t\t\t\tINP_Integer = true,
\t\t\t\t\t\t\tINP_Default = 1,
\t\t\t\t\t\t\tICS_ControlPage = "Controls",
\t\t\t\t\t\t},""")
    for name, _ in hidden_exprs():
        uc.append(f"""\t\t\t\t\t\t{name} = {{
\t\t\t\t\t\t\tLINKS_Name = "{name}",
\t\t\t\t\t\t\tLINKID_DataType = "Number",
\t\t\t\t\t\t\tINPID_InputControl = "SliderControl",
\t\t\t\t\t\t\tIC_Visible = false,
\t\t\t\t\t\t\tINP_Passive = true,
\t\t\t\t\t\t\tICS_ControlPage = "Controls",
\t\t\t\t\t\t}},""")

    inputs = [f"\t\t\t\t\t\t{n} = Input {{ Expression = {lua_str(e)}, }}," for n, e in hidden_exprs()]
    for inp, (x, y) in corner_exprs().items():
        inputs.append(f"\t\t\t\t\t\t{inp} = Input {{ Expression = {lua_str(f'Point({x}, {y})')}, }},")

    inst = ['\t\t\t\tMainInput1 = InstanceInput { SourceOp = "VLCWarp", Source = "Input", },']
    for sid, _, default, _, _ in SLIDERS:
        inst.append(f'\t\t\t\t{sid} = InstanceInput {{ SourceOp = "VLCWarp", Source = "{sid}", Default = {default}, }},')
    inst.append('\t\t\t\tAutoFill = InstanceInput { SourceOp = "VLCWarp", Source = "AutoFill", Default = 1, },')

    nl = "\n"
    return f"""-- Vertical Line Corrector (Fusion macro / Edit page effect)
-- Generated by tools/build_macro.py - edit that script, not this file.
{{
\tTools = ordered() {{
\t\tVerticalLineCorrector = MacroOperator {{
\t\t\tCtrlWZoom = false,
\t\t\tInputs = ordered() {{
{nl.join(inst)}
\t\t\t}},
\t\t\tOutputs = {{
\t\t\t\tMainOutput1 = InstanceOutput {{ SourceOp = "VLCWarp", Source = "Output", }},
\t\t\t}},
\t\t\tViewInfo = GroupInfo {{ Pos = {{ 0, 0 }} }},
\t\t\tTools = ordered() {{
\t\t\t\tVLCWarp = CornerPositioner {{
\t\t\t\t\tCtrlWZoom = false,
\t\t\t\t\tInputs = {{
{nl.join(inputs)}
\t\t\t\t\t}},
\t\t\t\t\tViewInfo = OperatorInfo {{ Pos = {{ 0, 0 }} }},
\t\t\t\t\tUserControls = ordered() {{
{nl.join(uc)}
\t\t\t\t\t}},
\t\t\t\t}},
\t\t\t}},
\t\t}},
\t}},
\tActiveTool = "VerticalLineCorrector"
}}
"""


if __name__ == "__main__":
    check()
    with open(OUT, "w") as fh:
        fh.write(build())
    print("wrote", os.path.normpath(OUT))
