from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from stocks import DailyPrice, DividendEvent, MarketDataStore, analyze_ex_dividend_day


class AnalyzeExDividendDayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "market_data.db"
        self.store = MarketDataStore(self.database_path)
        self.store.initialize()

        for price in (
            DailyPrice("ABC", date(2024, 1, 2), 98.0, 100.0),
            DailyPrice("ABC", date(2024, 1, 3), 101.0, 105.0),
            DailyPrice("ABC", date(2024, 2, 14), 106.0, 110.0),
            DailyPrice("ABC", date(2024, 2, 15), 107.0, 108.0),
            DailyPrice("ABC", date(2024, 4, 9), 118.0, 120.0),
            DailyPrice("ABC", date(2024, 4, 10), 116.0, 117.0),
            DailyPrice("SPY", date(2024, 4, 8), 497.0, 500.0),
            DailyPrice("SPY", date(2024, 4, 9), 500.0, 510.0),
        ):
            self.store.upsert_daily_price(price)

        for event in (
            DividendEvent("ABC", date(2024, 2, 15), 2.0),
            DividendEvent("ABC", date(2024, 4, 10), 3.0),
        ):
            self.store.upsert_dividend_event(event)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_analysis_calculates_current_and_previous_event_metrics(self) -> None:
        result = analyze_ex_dividend_day(self.store, "ABC", date(2024, 4, 10), benchmark_ticker="SPY")

        self.assertEqual(result.ex_date, date(2024, 4, 10))
        self.assertAlmostEqual(result.previous_close, 120.0)
        self.assertAlmostEqual(result.dividend_percent, 2.5)
        self.assertAlmostEqual(result.open_drop_percent, 3.3333333333, places=6)
        self.assertAlmostEqual(result.close_drop_percent, 2.5)
        self.assertAlmostEqual(result.open_drop_minus_dividend_percent, 0.8333333333, places=6)
        self.assertAlmostEqual(result.close_drop_minus_dividend_percent, 0.0)
        self.assertAlmostEqual(result.previous_trading_day_return_percent, 11.1111111111, places=6)
        self.assertAlmostEqual(result.benchmark_previous_day_return_percent, 2.0)
        self.assertEqual(result.previous_ex_date, date(2024, 2, 15))
        self.assertAlmostEqual(result.previous_ex_dividend_percent, 1.8181818181, places=6)
        self.assertAlmostEqual(result.previous_ex_close_drop_percent, 1.8181818181, places=6)

    def test_analysis_requires_dividend_event(self) -> None:
        with self.assertRaisesRegex(ValueError, "No dividend event found"):
            analyze_ex_dividend_day(self.store, "ABC", date(2024, 5, 1))

    def test_analysis_returns_none_for_missing_optional_context(self) -> None:
        isolated_store = MarketDataStore(Path(self.temp_dir.name) / "isolated.db")
        isolated_store.initialize()
        isolated_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 9), 49.0, 50.0))
        isolated_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 10), 48.5, 49.0))
        isolated_store.upsert_dividend_event(DividendEvent("XYZ", date(2024, 5, 10), 1.0))

        result = analyze_ex_dividend_day(isolated_store, "XYZ", date(2024, 5, 10), benchmark_ticker="QQQ")

        self.assertIsNone(result.previous_trading_day_return_percent)
        self.assertIsNone(result.benchmark_previous_day_return_percent)
        self.assertIsNone(result.previous_ex_date)
        self.assertIsNone(result.previous_ex_dividend_percent)
        self.assertIsNone(result.previous_ex_close_drop_percent)

    def test_analysis_requires_ex_day_trading_data(self) -> None:
        missing_ex_day_store = MarketDataStore(Path(self.temp_dir.name) / "missing-ex-day.db")
        missing_ex_day_store.initialize()
        missing_ex_day_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 9), 49.0, 50.0))
        missing_ex_day_store.upsert_dividend_event(DividendEvent("XYZ", date(2024, 5, 10), 1.0))

        with self.assertRaisesRegex(ValueError, "No trading data found"):
            analyze_ex_dividend_day(missing_ex_day_store, "XYZ", date(2024, 5, 10))

    def test_analysis_requires_previous_trading_day(self) -> None:
        first_day_store = MarketDataStore(Path(self.temp_dir.name) / "first-day.db")
        first_day_store.initialize()
        first_day_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 10), 48.5, 49.0))
        first_day_store.upsert_dividend_event(DividendEvent("XYZ", date(2024, 5, 10), 1.0))

        with self.assertRaisesRegex(ValueError, "No previous trading day found"):
            analyze_ex_dividend_day(first_day_store, "XYZ", date(2024, 5, 10))

    def test_analysis_rejects_zero_previous_close(self) -> None:
        invalid_price_store = MarketDataStore(Path(self.temp_dir.name) / "invalid-close.db")
        invalid_price_store.initialize()
        invalid_price_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 9), 0.5, 0.0))
        invalid_price_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 10), 48.5, 49.0))
        invalid_price_store.upsert_dividend_event(DividendEvent("XYZ", date(2024, 5, 10), 1.0))

        with self.assertRaisesRegex(ValueError, "close_price must be positive"):
            analyze_ex_dividend_day(invalid_price_store, "XYZ", date(2024, 5, 10))

    def test_analysis_rejects_negative_previous_close(self) -> None:
        invalid_price_store = MarketDataStore(Path(self.temp_dir.name) / "negative-close.db")
        invalid_price_store.initialize()
        invalid_price_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 9), 0.5, -1.0))
        invalid_price_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 10), 48.5, 49.0))
        invalid_price_store.upsert_dividend_event(DividendEvent("XYZ", date(2024, 5, 10), 1.0))

        with self.assertRaisesRegex(ValueError, "close_price must be positive"):
            analyze_ex_dividend_day(invalid_price_store, "XYZ", date(2024, 5, 10))

    def test_invalid_previous_event_history_does_not_break_current_analysis(self) -> None:
        store = MarketDataStore(Path(self.temp_dir.name) / "invalid-previous-event.db")
        store.initialize()
        for price in (
            DailyPrice("XYZ", date(2024, 2, 14), 10.5, -10.0),
            DailyPrice("XYZ", date(2024, 2, 15), 9.5, 9.0),
            DailyPrice("XYZ", date(2024, 4, 8), 11.0, 12.0),
            DailyPrice("XYZ", date(2024, 4, 9), 12.0, 13.0),
            DailyPrice("XYZ", date(2024, 4, 10), 12.0, 12.5),
        ):
            store.upsert_daily_price(price)
        for event in (
            DividendEvent("XYZ", date(2024, 2, 15), 1.0),
            DividendEvent("XYZ", date(2024, 4, 10), 0.5),
        ):
            store.upsert_dividend_event(event)

        result = analyze_ex_dividend_day(store, "XYZ", date(2024, 4, 10))

        self.assertEqual(result.previous_ex_date, date(2024, 2, 15))
        self.assertIsNone(result.previous_ex_dividend_percent)
        self.assertIsNone(result.previous_ex_close_drop_percent)

    def test_benchmark_context_aligns_to_stock_previous_trading_day(self) -> None:
        store = MarketDataStore(Path(self.temp_dir.name) / "benchmark-alignment.db")
        store.initialize()
        for price in (
            DailyPrice("XYZ", date(2024, 5, 8), 100.0, 100.0),
            DailyPrice("XYZ", date(2024, 5, 10), 98.0, 99.0),
            DailyPrice("QQQ", date(2024, 5, 7), 197.0, 198.0),
            DailyPrice("QQQ", date(2024, 5, 8), 199.0, 200.0),
            DailyPrice("QQQ", date(2024, 5, 9), 209.0, 210.0),
        ):
            store.upsert_daily_price(price)
        store.upsert_dividend_event(DividendEvent("XYZ", date(2024, 5, 10), 1.0))

        result = analyze_ex_dividend_day(store, "XYZ", date(2024, 5, 10), benchmark_ticker="QQQ")

        self.assertAlmostEqual(result.benchmark_previous_day_return_percent, 1.0101010101, places=6)

    def test_analysis_rejects_non_positive_ex_day_prices(self) -> None:
        invalid_price_store = MarketDataStore(Path(self.temp_dir.name) / "invalid-ex-day.db")
        invalid_price_store.initialize()
        invalid_price_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 9), 49.0, 50.0))
        invalid_price_store.upsert_daily_price(DailyPrice("XYZ", date(2024, 5, 10), 0.0, 49.0))
        invalid_price_store.upsert_dividend_event(DividendEvent("XYZ", date(2024, 5, 10), 1.0))

        with self.assertRaisesRegex(ValueError, "open_price must be positive"):
            analyze_ex_dividend_day(invalid_price_store, "XYZ", date(2024, 5, 10))


if __name__ == "__main__":
    unittest.main()
