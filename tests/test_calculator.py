import pytest
from attendiq.service.calculator import AttendanceCalculator

calc = AttendanceCalculator(75, 80)


def test_percentage():
    assert calc.percentage(30, 44) == 68.18
    assert calc.percentage(0, 0) == 0.0


def test_classes_needed_matches_formula():
    assert calc.classes_needed(30, 44) == 12            # 3*44 - 4*30
    for a, t in [(10, 20), (5, 30), (44, 50), (0, 8), (33, 40)]:
        x = calc.classes_needed(a, t)
        assert (a + x) * 100 >= 75 * (t + x)             # reaches the threshold
        if x > 0:
            assert (a + x - 1) * 100 < 75 * (t + x - 1)  # and x is the smallest such number


def test_safe_bunks():
    assert calc.safe_bunks(36, 44) == 4                  # 36/48 = 75%
    for a, t in [(36, 44), (50, 60), (8, 10), (0, 5)]:
        y = calc.safe_bunks(a, t)
        assert a * 100 >= 75 * (t + y) or a == 0
        if a:
            assert a * 100 < 75 * (t + y + 1)


def test_status_boundaries():
    assert calc.status(75, 100) == "Warning"             # exactly 75% is NOT shortage
    assert calc.status(74, 100) == "Shortage"
    assert calc.status(80, 100) == "Safe"
    assert calc.status(0, 0) == "No data"


def test_what_if():
    r = calc.what_if(30, 40, miss=3)
    assert (r["attended"], r["total"]) == (30, 43) and r["status"] == "Shortage"
    assert calc.what_if(30, 40, attend=5)["percentage"] == 77.78


def test_invalid_threshold():
    with pytest.raises(ValueError):
        AttendanceCalculator(100)
