import random

LOOP_MODES = ("off", "all", "one")


def cycle_loop_mode(mode):
    if mode not in LOOP_MODES:
        return "all"
    return LOOP_MODES[(LOOP_MODES.index(mode) + 1) % len(LOOP_MODES)]


def loop_status_mpris(mode):
    return {"off": "None", "one": "Track", "all": "Playlist"}.get(mode, "None")


def next_playlist_index(current, count, delta=1, loop_mode="off", shuffle=False, rng=None):
    if count <= 0:
        return None
    current = 0 if current < 0 else current
    if shuffle and count > 1:
        rng = rng or random
        choices = [i for i in range(count) if i != current]
        return rng.choice(choices)
    nxt = current + delta
    if 0 <= nxt < count:
        return nxt
    if loop_mode == "all" and count:
        return nxt % count
    return None


def auto_advance_index(current, count, loop_mode="off", shuffle=False, rng=None):
    if count <= 0:
        return None
    if loop_mode == "one":
        return max(current, 0)
    if shuffle:
        if count == 1:
            return 0 if loop_mode == "all" else None
        return next_playlist_index(current, count, 1, "all", True, rng)
    return next_playlist_index(current, count, 1, loop_mode, False, rng)
