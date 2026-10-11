import unittest

from playlist_nav import (
    auto_advance_index,
    cycle_loop_mode,
    loop_status_mpris,
    next_playlist_index,
)


class FakeRng:
    def __init__(self, value):
        self.value = value

    def choice(self, seq):
        return seq[self.value % len(seq)]


class TestPlaylistNav(unittest.TestCase):
    def test_cycle_loop_mode(self):
        self.assertEqual(cycle_loop_mode("off"), "all")
        self.assertEqual(cycle_loop_mode("all"), "one")
        self.assertEqual(cycle_loop_mode("one"), "off")
        self.assertEqual(cycle_loop_mode("nope"), "all")

    def test_loop_status_mpris(self):
        self.assertEqual(loop_status_mpris("off"), "None")
        self.assertEqual(loop_status_mpris("one"), "Track")
        self.assertEqual(loop_status_mpris("all"), "Playlist")

    def test_next_stops_at_ends_without_loop(self):
        self.assertEqual(next_playlist_index(0, 3, 1, "off"), 1)
        self.assertIsNone(next_playlist_index(2, 3, 1, "off"))
        self.assertIsNone(next_playlist_index(0, 3, -1, "off"))

    def test_next_wraps_when_loop_all(self):
        self.assertEqual(next_playlist_index(2, 3, 1, "all"), 0)
        self.assertEqual(next_playlist_index(0, 3, -1, "all"), 2)

    def test_shuffle_picks_other_index(self):
        idx = next_playlist_index(1, 4, 1, "off", shuffle=True, rng=FakeRng(0))
        self.assertIn(idx, (0, 2, 3))
        self.assertNotEqual(idx, 1)

    def test_auto_advance_repeat_one(self):
        self.assertEqual(auto_advance_index(2, 5, "one"), 2)

    def test_auto_advance_stops_at_end(self):
        self.assertIsNone(auto_advance_index(2, 3, "off"))
        self.assertEqual(auto_advance_index(1, 3, "off"), 2)

    def test_auto_advance_loop_all_wraps(self):
        self.assertEqual(auto_advance_index(2, 3, "all"), 0)

    def test_empty_playlist(self):
        self.assertIsNone(next_playlist_index(0, 0, 1, "all"))
        self.assertIsNone(auto_advance_index(0, 0, "all"))
