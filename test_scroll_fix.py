import unittest

from scroll_fix import DOWN, UP, ScrollFilter


def run(f, ticks):
    """ticks: list of (direction, time_ms). Returns output directions."""
    return [f.process(d, t) for d, t in ticks]


class ScrollFilterTest(unittest.TestCase):
    def test_reversal_after_threshold_is_corrected(self):
        f = ScrollFilter(threshold=3, timeout_ms=400)
        out = run(f, [(DOWN, 0), (DOWN, 50), (DOWN, 100), (UP, 150), (DOWN, 200)])
        self.assertEqual(out, [DOWN, DOWN, DOWN, DOWN, DOWN])

    def test_reversal_before_threshold_is_accepted(self):
        f = ScrollFilter(threshold=3, timeout_ms=400)
        out = run(f, [(DOWN, 0), (DOWN, 50), (UP, 100), (UP, 150)])
        self.assertEqual(out, [DOWN, DOWN, UP, UP])

    def test_pause_resets(self):
        f = ScrollFilter(threshold=3, timeout_ms=400)
        out = run(f, [(DOWN, 0), (DOWN, 50), (DOWN, 100), (UP, 600), (UP, 650)])
        self.assertEqual(out, [DOWN, DOWN, DOWN, UP, UP])

    def test_corrected_ticks_keep_session_alive(self):
        f = ScrollFilter(threshold=3, timeout_ms=400)
        out = run(f, [(DOWN, 0), (DOWN, 300), (DOWN, 600), (UP, 900), (UP, 1200)])
        self.assertEqual(out, [DOWN] * 5)

    def test_confirm_allows_deliberate_reversal(self):
        f = ScrollFilter(threshold=3, timeout_ms=400, confirm=3)
        out = run(f, [(DOWN, 0), (DOWN, 50), (DOWN, 100),
                      (UP, 150), (UP, 200), (UP, 250), (UP, 300)])
        self.assertEqual(out, [DOWN, DOWN, DOWN, DOWN, DOWN, UP, UP])

    def test_confirm_counter_resets_on_correct_tick(self):
        f = ScrollFilter(threshold=3, timeout_ms=400, confirm=2)
        out = run(f, [(DOWN, 0), (DOWN, 50), (DOWN, 100),
                      (UP, 150), (DOWN, 200), (UP, 250), (DOWN, 300)])
        self.assertEqual(out, [DOWN] * 7)

    def test_tick_counter_wraparound(self):
        f = ScrollFilter(threshold=2, timeout_ms=400)
        start = 0xFFFFFFFF - 60
        out = run(f, [(UP, start), (UP, start + 50), (DOWN, 30)])
        self.assertEqual(out, [UP, UP, UP])


if __name__ == "__main__":
    unittest.main()
