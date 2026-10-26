"""Renders a synthetic tilted-camera shot of a building, runs it through the
compiled DCTL harness, measures how much the walls lean before and after,
and writes docs/before_after.png.

    cc -O2 -o /tmp/harness tools/dctl_harness.c -lm
    python3 tools/render_demo.py /tmp/harness
"""

import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageDraw

import reference as ref

W, H, FOV, TILT = 960, 540, 84.0, 22.0
HERE = os.path.dirname(os.path.abspath(__file__))


def render_scene(ss=3):
    """Ray-trace a facade at depth 40 seen by a camera pitched up by TILT,
    supersampled ss x ss for clean edges."""
    pr = ref.params(W, H, tilt_v=TILT, fov=FOV, auto_fill=False)
    ys, xs = np.mgrid[0:H * ss, 0:W * ss].astype(np.float64) / ss
    sx, sy = xs + 0.5 / ss - W / 2, H / 2 - (ys + 0.5 / ss)
    # vectorised source_to_level
    x1 = sx * pr["cr"] - sy * pr["sr"]
    y1 = sx * pr["sr"] + sy * pr["cr"]
    y2 = y1 * pr["cp"] + pr["f"] * pr["sp"]
    z2 = -y1 * pr["sp"] + pr["f"] * pr["cp"]
    X = 40.0 * x1 / z2
    Y = 40.0 * y2 / z2 - 8.0  # camera 8 units above the ground

    img = np.empty(X.shape + (3,), np.float32)
    img[:] = (0.55, 0.75, 0.95)                      # sky
    building = (np.abs(X) < 22) & (Y < 70) & (Y > -8)
    img[building] = (0.82, 0.78, 0.70)
    win = building & ((np.mod(X, 5.0) > 1.6) & (np.mod(X, 5.0) < 3.4)) \
        & (np.mod(Y, 6.0) > 2.0) & (Y > -4) & (Y < 66)
    img[win] = (0.20, 0.27, 0.36)
    edge = building & ((np.abs(np.abs(X) - 22) < 0.35))
    img[edge] = (0.35, 0.25, 0.20)
    img[(Y <= -8) & (z2 > 0)] = (0.35, 0.40, 0.30)   # ground
    return img.reshape(H, ss, W, ss, 3).mean(axis=(1, 3))


def lean(img, row_a, row_b):
    """Horizontal distance between the left wall edge at two rows (pixels)."""
    def left_edge(row):
        r = img[row]
        dark = (r[:, 0] < 0.6) & (r[:, 2] < 0.45)  # wall-edge colour
        assert dark.any(), f"no wall edge found on row {row}"
        return np.argmax(dark)
    return abs(int(left_edge(row_a)) - int(left_edge(row_b)))


def main(harness):
    src = render_scene()
    with tempfile.TemporaryDirectory() as d:
        fin, fout = os.path.join(d, "in.rgbf"), os.path.join(d, "out.rgbf")
        src.astype("<f4").tofile(fin)
        subprocess.check_call([harness, fin, fout, str(W), str(H),
                               str(TILT), "0", "0", "100", str(FOV), "1", "0", "0",
                               "1", "0", "0"])
        out = np.fromfile(fout, "<f4").reshape(H, W, 3)

    rows = (int(H * 0.15), int(H * 0.75))
    before, after = lean(src, *rows), lean(out, *rows)
    print(f"left wall lean over {rows[1] - rows[0]} rows: before {before}px, after {after}px")

    def label(a, text):
        im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
        ImageDraw.Draw(im).text((12, 10), text, fill=(255, 255, 255))
        return im

    sheet = Image.new("RGB", (W * 2 + 10, H), (20, 20, 20))
    sheet.paste(label(src, f"BEFORE - camera tilted up {TILT:g} deg"), (0, 0))
    sheet.paste(label(out, "AFTER - Vertical Line Corrector"), (W + 10, 0))
    dst = os.path.join(HERE, "..", "docs", "before_after.png")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    sheet.save(dst)
    return before, after


if __name__ == "__main__":
    b, a = main(sys.argv[1])
    sys.exit(0 if b > 20 and a <= 1 else 1)
