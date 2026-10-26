"""Reference model of the Vertical Line Corrector math.

The DCTL and the Fusion macro are both ports of the functions in this file,
so this is the place to test changes to the geometry before touching Resolve.

Model: the footage was shot by a pinhole camera that was yawed, pitched and
rolled away from level. We render it again from a virtual *level* camera with
the same optical centre, then slide the frame (like a shift lens) so the original
centre of the shot stays centred. Because only the rotation changes, the
mapping is a pure homography and every vertical edge in the world becomes
vertical in the output.

Coordinates are in pixels, centred on the frame, with +y pointing up.
"""

import math


def params(width, height, tilt_v=0.0, tilt_h=0.0, roll=0.0, amount=100.0,
           fov=82.0, zoom=1.0, shift_x=0.0, shift_y=0.0, auto_fill=True):
    a = amount / 100.0
    p = math.radians(tilt_v * a)
    y = math.radians(tilt_h * a)
    r = math.radians(roll * a)
    pr = {
        "w": width, "h": height,
        "f": (width / 2.0) / math.tan(math.radians(fov) / 2.0),
        "cp": math.cos(p), "sp": math.sin(p),
        "cy": math.cos(y), "sy": math.sin(y),
        "cr": math.cos(r), "sr": math.sin(r),
    }
    # Shift-lens recentre: keep what was in the middle of the footage in the
    # middle of the output, instead of re-aiming the camera at the horizon.
    c0x, c0y, _ = source_to_level(pr, 0.0, 0.0)
    pr["shx"] = c0x + shift_x * width / 2.0
    pr["shy"] = c0y + shift_y * height / 2.0
    k = fill_factor(pr) if auto_fill else 1.0
    pr["scale"] = zoom / k
    return pr


def level_to_source(pr, x, y):
    """Ray through level-camera pixel (x, y) -> pixel in the tilted footage.

    Returns (sx, sy, ok); ok is False when the ray points behind the camera.
    """
    f = pr["f"]
    # yaw
    x1 = x * pr["cy"] - f * pr["sy"]
    z1 = x * pr["sy"] + f * pr["cy"]
    # pitch
    y2 = y * pr["cp"] - z1 * pr["sp"]
    z2 = y * pr["sp"] + z1 * pr["cp"]
    # roll
    x3 = x1 * pr["cr"] + y2 * pr["sr"]
    y3 = -x1 * pr["sr"] + y2 * pr["cr"]
    if z2 <= 1e-6:
        return 0.0, 0.0, False
    return f * x3 / z2, f * y3 / z2, True


def source_to_level(pr, x, y):
    """Exact inverse of level_to_source (transposed rotations, reverse order)."""
    f = pr["f"]
    # undo roll
    x1 = x * pr["cr"] - y * pr["sr"]
    y1 = x * pr["sr"] + y * pr["cr"]
    # undo pitch
    y2 = y1 * pr["cp"] + f * pr["sp"]
    z2 = -y1 * pr["sp"] + f * pr["cp"]
    # undo yaw
    x3 = x1 * pr["cy"] + z2 * pr["sy"]
    z3 = -x1 * pr["sy"] + z2 * pr["cy"]
    # Clamp like the DCTL/macro so points past the horizon stay finite.
    zc = max(z3, 1e-6)
    return f * x3 / zc, f * y2 / zc, z3 > 1e-6


def source_corners_in_level(pr):
    """Footage corners TL, TR, BR, BL (clockwise in y-up) in level space."""
    hw, hh = pr["w"] / 2.0, pr["h"] / 2.0
    return [source_to_level(pr, cx, cy)[:2]
            for cx, cy in ((-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh))]


def fill_factor(pr):
    """Largest k so a frame-aspect rect of half size (k*w/2, k*h/2), centred
    on the shift point, still fits inside the warped footage."""
    a, b = pr["w"] / 2.0, pr["h"] / 2.0
    cx, cy = pr["shx"], pr["shy"]
    c = source_corners_in_level(pr)
    k = 1e9
    for i in range(4):
        px, py = c[i]
        qx, qy = c[(i + 1) % 4]
        nx, ny = -(qy - py), qx - px  # outward normal of a clockwise edge
        k = min(k, (nx * (px - cx) + ny * (py - cy)) / (abs(nx) * a + abs(ny) * b + 1e-9))
    return max(k, 0.05)


def output_to_source(pr, x, y):
    """What the DCTL does per pixel: output pixel -> footage pixel."""
    return level_to_source(pr, x / pr["scale"] + pr["shx"],
                           y / pr["scale"] + pr["shy"])
