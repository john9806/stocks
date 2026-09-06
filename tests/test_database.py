from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from stocks import MarketDataStore


class MarketDataStoreImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.store = MarketDataStore(self.base_path / "market_data.db")
        self.store.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_daily_price_csv_requires_ticker_source(self) -> None:
        csv_path = self.base_path / "prices.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["trade_date", "open_price", "close_price"])
            writer.writeheader()
            writer.writerow({"trade_date": "2024-04-10", "open_price": "10", "close_price": "11"})

        with self.assertRaisesRegex(ValueError, "ticker argument or a ticker column"):
            self.store.import_daily_prices_csv(csv_path)

    def test_dividend_csv_requires_ticker_source(self) -> None:
        csv_path = self.base_path / "dividends.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["ex_date", "dividend_amount"])
            writer.writeheader()
            writer.writerow({"ex_date": "2024-04-10", "dividend_amount": "1.5"})

        with self.assertRaisesRegex(ValueError, "ticker argument or a ticker column"):
            self.store.import_dividend_events_csv(csv_path)


if __name__ == "__main__":
    unittest.main()
