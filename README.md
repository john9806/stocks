# stocks

Find patterns in the stock market.

This repository now includes a small SQLite-backed data model for collecting the data needed to study ex-dividend ("X day") moves:

- daily stock prices per ticker and day (`open`, `close`, optional `high`, `low`, `volume`)
- dividend events per ticker and ex-date
- optional benchmark/index prices stored the same way as stocks for market-context comparisons

## What it supports

Use `stocks.MarketDataStore` to create a local database and load data, then use `stocks.analyze_ex_dividend_day(...)` to answer:

- did the stock drop by more or less than the dividend percentage on the ex-date?
- what was the stock's previous trading day return?
- what was the general market's previous day return?
- how did the previous ex-dividend event behave for the same stock?

## Example

```python
from datetime import date

from stocks import DailyPrice, DividendEvent, MarketDataStore, analyze_ex_dividend_day

store = MarketDataStore("data/stocks.db")
store.initialize()

store.upsert_daily_price(DailyPrice("ABC", date(2024, 4, 9), 118.0, 120.0))
store.upsert_daily_price(DailyPrice("ABC", date(2024, 4, 10), 116.0, 117.0))
store.upsert_dividend_event(DividendEvent("ABC", date(2024, 4, 10), 3.0))

result = analyze_ex_dividend_day(store, "ABC", date(2024, 4, 10))
print(result.close_drop_percent, result.dividend_percent)
```

## CSV imports

The store also supports standard-library CSV imports:

- `import_daily_prices_csv(...)` with columns `ticker,trade_date,open_price,close_price,high_price,low_price,volume`
- `import_dividend_events_csv(...)` with columns `ticker,ex_date,dividend_amount`

## Tests

Run:

```bash
python -m unittest discover -s tests
```
