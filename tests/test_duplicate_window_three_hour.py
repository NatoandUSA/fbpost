from services.job_executor import resolve_duplicate_window_hours


def test_three_hour_duplicate_window_is_supported():
    assert resolve_duplicate_window_hours(3) == 3
    assert resolve_duplicate_window_hours("3") == 3


def test_unknown_duplicate_window_still_fails_safe_to_24_hours():
    assert resolve_duplicate_window_hours(2) == 24
    assert resolve_duplicate_window_hours("bad") == 24
