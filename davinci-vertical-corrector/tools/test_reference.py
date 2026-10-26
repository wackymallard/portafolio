"""Checks the correction geometry. Run: python3 tools/test_reference.py"""

import math
import random
import unittest

import reference as ref


def tilted_camera_projection(pr, X, Y, Z):
    """Project a world point with the *tilted* camera described by pr."""
    sx, sy, ok = ref.level_to_source(pr, pr["f"] * X / Z, pr["f"] * Y / Z)
    assert ok
    return sx, sy


class Geometry(unittest.TestCase):
    def test_round_trip(self):
        pr = ref.params(3840, 2160, tilt_v=17, tilt_h=-9, roll=3, fov=84)
        rnd = random.Random(1)
        for _ in range(500):
            x, y = rnd.uniform(-1500, 1500), rnd.uniform(-900, 900)
            lx, ly, ok = ref.source_to_level(pr, x, y)
            self.assertTrue(ok)
            sx, sy, ok = ref.level_to_source(pr, lx, ly)
            self.assertAlmostEqual(sx, x, places=6)
            self.assertAlmostEqual(sy, y, places=6)

    def test_world_verticals_come_out_vertical(self):
        for tv, th, roll in ((20, 0, 0), (-25, 0, 0), (15, 10, 4), (35, -5, -2)):
            pr = ref.params(3840, 2160, tilt_v=tv, tilt_h=th, roll=roll, fov=84)
            for X in (-30, -4, 0, 7, 22):
                pts = []
                for Y in (-10, 0, 10, 20):
                    sx, sy = tilted_camera_projection(pr, X, Y, 60)
                    pts.append(ref.source_to_level(pr, sx, sy)[:2])
                xs = [p[0] for p in pts]
                self.assertLess(max(xs) - min(xs), 1e-6, (tv, th, roll, X))

    def test_verticals_converge_in_raw_footage(self):
        # sanity check that the test above is not trivially true
        pr = ref.params(3840, 2160, tilt_v=20, fov=84)
        top = tilted_camera_projection(pr, 20, 20, 60)[0]
        bottom = tilted_camera_projection(pr, 20, -10, 60)[0]
        self.assertGreater(abs(top - bottom), 50)

    def test_auto_fill_has_no_black_corners(self):
        for kw in (dict(tilt_v=25), dict(tilt_v=-18, tilt_h=12, roll=5),
                   dict(tilt_v=10, shift_y=0.2), dict(tilt_h=30, fov=100)):
            pr = ref.params(1920, 1080, fov=kw.pop("fov", 84), **kw)
            for ox, oy in ((-960, 540), (960, 540), (960, -540), (-960, -540)):
                sx, sy, ok = ref.output_to_source(pr, ox, oy)
                self.assertTrue(ok)
                self.assertLessEqual(abs(sx), 960 + 1e-6)
                self.assertLessEqual(abs(sy), 540 + 1e-6)

    def test_auto_fill_is_tight(self):
        # at least one output corner should sit on the footage boundary
        pr = ref.params(1920, 1080, tilt_v=22, fov=84)
        worst = 0.0
        for ox, oy in ((-960, 540), (960, 540), (960, -540), (-960, -540)):
            sx, sy, _ = ref.output_to_source(pr, ox, oy)
            worst = max(worst, abs(sx) / 960, abs(sy) / 540)
        self.assertAlmostEqual(worst, 1.0, places=6)

    def test_zero_settings_are_identity(self):
        pr = ref.params(1920, 1080)
        sx, sy, _ = ref.output_to_source(pr, 123.0, -456.0)
        self.assertAlmostEqual(sx, 123.0)
        self.assertAlmostEqual(sy, -456.0)

    def test_amount_scales_angle(self):
        half = ref.params(1920, 1080, tilt_v=20, amount=50)
        ten = ref.params(1920, 1080, tilt_v=10)
        self.assertTrue(math.isclose(half["sp"], ten["sp"]))


if __name__ == "__main__":
    unittest.main()
