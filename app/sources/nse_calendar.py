from datetime import date


# NSE equity-market holidays.
#
# Source: official NSE annual trading-holiday calendars.
#
# Keep this data explicit and version-controlled so historical
# backtests do not depend on today's calendar.
NSE_HOLIDAYS: set[date] = {
    # 2021
    date(2021, 1, 26),
    date(2021, 3, 11),
    date(2021, 3, 29),
    date(2021, 4, 2),
    date(2021, 4, 14),
    date(2021, 4, 21),
    date(2021, 5, 13),
    date(2021, 7, 21),
    date(2021, 8, 19),
    date(2021, 9, 10),
    date(2021, 10, 15),
    date(2021, 11, 5),
    date(2021, 11, 19),

    # 2022
    date(2022, 1, 26),
    date(2022, 3, 1),
    date(2022, 3, 18),
    date(2022, 4, 14),
    date(2022, 4, 15),
    date(2022, 5, 3),
    date(2022, 8, 9),
    date(2022, 8, 15),
    date(2022, 8, 31),
    date(2022, 10, 5),
    date(2022, 10, 26),
    date(2022, 11, 8),

    # 2023
    date(2023, 1, 26),
    date(2023, 3, 7),
    date(2023, 3, 30),
    date(2023, 4, 4),
    date(2023, 4, 7),
    date(2023, 4, 14),
    date(2023, 5, 1),
    date(2023, 6, 29),
    date(2023, 8, 15),
    date(2023, 9, 19),
    date(2023, 10, 2),
    date(2023, 10, 24),
    date(2023, 11, 14),
    date(2023, 11, 27),
    date(2023, 12, 25),

    # 2024
    date(2024, 1, 22),
    date(2024, 1, 26),
    date(2024, 3, 8),
    date(2024, 3, 25),
    date(2024, 3, 29),
    date(2024, 4, 11),
    date(2024, 4, 17),
    date(2024, 5, 1),
    date(2024, 5, 20),
    date(2024, 6, 17),
    date(2024, 7, 17),
    date(2024, 8, 15),
    date(2024, 10, 2),
    date(2024, 11, 15),
    date(2024, 11, 20),
    date(2024, 12, 25),

    # 2025
    date(2025, 2, 26),
    date(2025, 3, 14),
    date(2025, 3, 31),
    date(2025, 4, 10),
    date(2025, 4, 14),
    date(2025, 4, 18),
    date(2025, 5, 1),
    date(2025, 8, 15),
    date(2025, 8, 27),
    date(2025, 10, 2),
    date(2025, 10, 22),
    date(2025, 11, 5),
    date(2025, 12, 25),

    # 2026
    date(2026, 1, 15),
    date(2026, 1, 26),
    date(2026, 3, 3),
    date(2026, 3, 26),
    date(2026, 3, 31),
    date(2026, 4, 3),
    date(2026, 4, 14),
    date(2026, 5, 1),
    date(2026, 5, 28),
    date(2026, 6, 26),
    date(2026, 9, 14),
}

NSE_SPECIAL_TRADING_DAYS: set[date] = {
    # Diwali Muhurat Trading
    date(2021, 11, 4),
    date(2022, 10, 24),
    date(2023, 11, 12),
    date(2024, 11, 1),
    date(2025, 10, 21),
    date(2026, 11, 8),
}

class NSETradingCalendar:
    """Historical NSE equity trading-day calendar."""

    def is_weekend(self, trade_date: date) -> bool:
        return trade_date.weekday() >= 5

    def is_holiday(self, trade_date: date) -> bool:
        return trade_date in NSE_HOLIDAYS

    def is_special_trading_day(self, trade_date: date) -> bool:
        return trade_date in NSE_SPECIAL_TRADING_DAYS

    def is_trading_day(self, trade_date: date) -> bool:
        if self.is_special_trading_day(trade_date):
            return True

        return (
            not self.is_weekend(trade_date)
            and not self.is_holiday(trade_date)
        )

    def classify(self, trade_date: date) -> str:
        if self.is_special_trading_day(trade_date):
            return "SPECIAL_TRADING_DAY"

        if self.is_weekend(trade_date):
            return "WEEKEND"

        if self.is_holiday(trade_date):
            return "NSE_HOLIDAY"

        return "TRADING_DAY"