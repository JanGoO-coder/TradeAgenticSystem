from datetime import datetime

from app.hub.tools import get_session_window


def test_utc_killzone_boundaries_london_and_ny() -> None:
    london_open = get_session_window(datetime(2026, 1, 1, 2, 0, 0))
    london_closed = get_session_window(datetime(2026, 1, 1, 5, 0, 0))

    ny_open = get_session_window(datetime(2026, 1, 1, 7, 0, 0))
    ny_closed = get_session_window(datetime(2026, 1, 1, 10, 0, 0))

    assert london_open["in_killzone"] is True
    assert london_open["session"] == "London kill zone"
    assert london_closed["in_killzone"] is False

    assert ny_open["in_killzone"] is True
    assert ny_open["session"] == "NY kill zone"
    assert ny_closed["in_killzone"] is False
