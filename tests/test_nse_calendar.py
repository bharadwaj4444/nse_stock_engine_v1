from datetime import date

from app.sources.nse_calendar import NSETradingCalendar
from app.pipeline import date_range


calendar = NSETradingCalendar()


def test_normal_weekday_is_trading_day():
    d = date(2025, 10, 3)

    assert calendar.is_trading_day(d)
    assert calendar.classify(d) == "TRADING_DAY"


def test_nse_holiday_is_not_trading_day():
    d = date(2025, 10, 2)

    assert not calendar.is_trading_day(d)
    assert calendar.classify(d) == "NSE_HOLIDAY"


def test_weekend_is_not_trading_day():
    d = date(2025, 10, 4)

    assert not calendar.is_trading_day(d)
    assert calendar.classify(d) == "WEEKEND"


def test_muhurat_trading_day():
    d = date(2021, 11, 4)

    assert calendar.is_special_trading_day(d)
    assert calendar.is_trading_day(d)
    assert calendar.classify(d) == "SPECIAL_TRADING_DAY"


def test_weekend_muhurat_trading_day():
    d = date(2023, 11, 12)

    assert d.weekday() == 6
    assert calendar.is_special_trading_day(d)
    assert calendar.is_trading_day(d)
    assert calendar.classify(d) == "SPECIAL_TRADING_DAY"


def test_date_range_excludes_holidays_and_weekends():
    dates = list(
        date_range(
            date(2025, 10, 1),
            date(2025, 10, 5),
        )
    )

    assert dates == [
        date(2025, 10, 1),
        date(2025, 10, 3),
    ]


def test_all_known_muhurat_days_are_trading_days():
    expected = {
        date(2021, 11, 4),
        date(2022, 10, 24),
        date(2023, 11, 12),
        date(2024, 11, 1),
        date(2025, 10, 21),
        date(2026, 11, 8),
    }

    for d in expected:
        assert calendar.is_special_trading_day(d)
        assert calendar.is_trading_day(d)
        assert calendar.classify(d) == "SPECIAL_TRADING_DAY"