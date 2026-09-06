from __future__ import annotations

import csv
import sqlite3
from datetime import date
from pathlib import Path

from .models import DailyPrice, DividendEvent


def _to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


class MarketDataStore:
    def __init__(self, database_path: str | Path = "stocks.db") -> None:
        self.database_path = Path(database_path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS daily_prices (
                    ticker TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    high_price REAL,
                    low_price REAL,
                    volume INTEGER,
                    PRIMARY KEY (ticker, trade_date)
                );

                CREATE TABLE IF NOT EXISTS dividend_events (
                    ticker TEXT NOT NULL,
                    ex_date TEXT NOT NULL,
                    dividend_amount REAL NOT NULL,
                    PRIMARY KEY (ticker, ex_date)
                );

                CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date
                    ON daily_prices (ticker, trade_date);
                CREATE INDEX IF NOT EXISTS idx_dividend_events_ticker_date
                    ON dividend_events (ticker, ex_date);
                """
            )

    def upsert_daily_price(self, price: DailyPrice) -> None:
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO daily_prices (
                    ticker,
                    trade_date,
                    open_price,
                    close_price,
                    high_price,
                    low_price,
                    volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(ticker, trade_date) DO UPDATE SET
                    open_price = excluded.open_price,
                    close_price = excluded.close_price,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    volume = excluded.volume
                """,
                (
                    price.ticker,
                    price.trade_date.isoformat(),
                    price.open_price,
                    price.close_price,
                    price.high_price,
                    price.low_price,
                    price.volume,
                ),
            )

    def upsert_dividend_event(self, event: DividendEvent) -> None:
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dividend_events (ticker, ex_date, dividend_amount)
                VALUES (?, ?, ?)
                ON CONFLICT(ticker, ex_date) DO UPDATE SET
                    dividend_amount = excluded.dividend_amount
                """,
                (event.ticker, event.ex_date.isoformat(), event.dividend_amount),
            )

    def import_daily_prices_csv(self, csv_path: str | Path, ticker: str | None = None) -> int:
        rows_inserted = 0
        with Path(csv_path).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                self.upsert_daily_price(
                    DailyPrice(
                        ticker=ticker or row["ticker"],
                        trade_date=_to_date(row["trade_date"]),
                        open_price=float(row["open_price"]),
                        close_price=float(row["close_price"]),
                        high_price=float(row["high_price"]) if row.get("high_price") else None,
                        low_price=float(row["low_price"]) if row.get("low_price") else None,
                        volume=int(row["volume"]) if row.get("volume") else None,
                    )
                )
                rows_inserted += 1
        return rows_inserted

    def import_dividend_events_csv(self, csv_path: str | Path, ticker: str | None = None) -> int:
        rows_inserted = 0
        with Path(csv_path).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                self.upsert_dividend_event(
                    DividendEvent(
                        ticker=ticker or row["ticker"],
                        ex_date=_to_date(row["ex_date"]),
                        dividend_amount=float(row["dividend_amount"]),
                    )
                )
                rows_inserted += 1
        return rows_inserted

    def get_daily_price(self, ticker: str, trade_date: str | date) -> DailyPrice | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT ticker, trade_date, open_price, close_price, high_price, low_price, volume
                FROM daily_prices
                WHERE ticker = ? AND trade_date = ?
                """,
                (ticker, _to_date(trade_date).isoformat()),
            ).fetchone()
        return self._row_to_daily_price(row) if row else None

    def get_previous_trading_day(self, ticker: str, trade_date: str | date) -> DailyPrice | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT ticker, trade_date, open_price, close_price, high_price, low_price, volume
                FROM daily_prices
                WHERE ticker = ? AND trade_date < ?
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                (ticker, _to_date(trade_date).isoformat()),
            ).fetchone()
        return self._row_to_daily_price(row) if row else None

    def get_dividend_event(self, ticker: str, ex_date: str | date) -> DividendEvent | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT ticker, ex_date, dividend_amount
                FROM dividend_events
                WHERE ticker = ? AND ex_date = ?
                """,
                (ticker, _to_date(ex_date).isoformat()),
            ).fetchone()
        return self._row_to_dividend_event(row) if row else None

    def get_previous_dividend_event(self, ticker: str, ex_date: str | date) -> DividendEvent | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT ticker, ex_date, dividend_amount
                FROM dividend_events
                WHERE ticker = ? AND ex_date < ?
                ORDER BY ex_date DESC
                LIMIT 1
                """,
                (ticker, _to_date(ex_date).isoformat()),
            ).fetchone()
        return self._row_to_dividend_event(row) if row else None

    @staticmethod
    def _row_to_daily_price(row: sqlite3.Row) -> DailyPrice:
        return DailyPrice(
            ticker=row["ticker"],
            trade_date=_to_date(row["trade_date"]),
            open_price=row["open_price"],
            close_price=row["close_price"],
            high_price=row["high_price"],
            low_price=row["low_price"],
            volume=row["volume"],
        )

    @staticmethod
    def _row_to_dividend_event(row: sqlite3.Row) -> DividendEvent:
        return DividendEvent(
            ticker=row["ticker"],
            ex_date=_to_date(row["ex_date"]),
            dividend_amount=row["dividend_amount"],
        )
