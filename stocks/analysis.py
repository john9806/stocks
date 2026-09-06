from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .database import MarketDataStore
from .models import DividendEvent


@dataclass(frozen=True)
class DividendDropAnalysis:
    ticker: str
    ex_date: date
    dividend_amount: float
    dividend_percent: float
    previous_close: float
    ex_day_open: float
    ex_day_close: float
    open_drop_percent: float
    close_drop_percent: float
    open_drop_minus_dividend_percent: float
    close_drop_minus_dividend_percent: float
    previous_trading_day_return_percent: float | None
    benchmark_previous_day_return_percent: float | None
    previous_ex_date: date | None
    previous_ex_dividend_percent: float | None
    previous_ex_close_drop_percent: float | None


@dataclass(frozen=True)
class PreviousEventAnalysis:
    dividend_percent: float | None
    close_drop_percent: float | None


def _percent_drop(from_price: float, to_price: float) -> float:
    return ((from_price - to_price) / from_price) * 100


def _percent_return(start_price: float, end_price: float) -> float:
    return ((end_price - start_price) / start_price) * 100


def _require_positive_close(close_price: float, ticker: str, trade_date: date) -> None:
    if close_price <= 0:
        raise ValueError(
            f"Invalid close price for {ticker} on {trade_date}: close_price must be positive"
        )


def _require_positive_price(price: float, ticker: str, trade_date: date, field_name: str) -> None:
    if price <= 0:
        raise ValueError(
            f"Invalid {field_name} for {ticker} on {trade_date}: {field_name} must be positive"
        )


def analyze_ex_dividend_day(
    store: MarketDataStore,
    ticker: str,
    ex_date: str | date,
    benchmark_ticker: str | None = None,
) -> DividendDropAnalysis:
    event = store.get_dividend_event(ticker, ex_date)
    if event is None:
        raise ValueError(f"No dividend event found for {ticker} on {ex_date}")

    ex_day_price = store.get_daily_price(ticker, event.ex_date)
    if ex_day_price is None:
        raise ValueError(f"No trading data found for {ticker} on {event.ex_date}")

    previous_day = store.get_previous_trading_day(ticker, event.ex_date)
    if previous_day is None:
        raise ValueError(f"No previous trading day found for {ticker} before {event.ex_date}")
    _require_positive_close(previous_day.close_price, ticker, previous_day.trade_date)
    _require_positive_price(ex_day_price.open_price, ticker, ex_day_price.trade_date, "open_price")
    _require_positive_price(ex_day_price.close_price, ticker, ex_day_price.trade_date, "close_price")

    prior_stock_day = store.get_previous_trading_day(ticker, previous_day.trade_date)
    previous_trading_day_return_percent = None
    if prior_stock_day is not None:
        _require_positive_close(prior_stock_day.close_price, ticker, prior_stock_day.trade_date)
        previous_trading_day_return_percent = _percent_return(
            prior_stock_day.close_price,
            previous_day.close_price,
        )

    benchmark_previous_day_return_percent = None
    if benchmark_ticker:
        benchmark_previous_day = store.get_latest_trading_day_on_or_before(
            benchmark_ticker,
            previous_day.trade_date,
        )
        if benchmark_previous_day is not None:
            _require_positive_close(
                benchmark_previous_day.close_price,
                benchmark_ticker,
                benchmark_previous_day.trade_date,
            )
            prior_benchmark_day = store.get_previous_trading_day(
                benchmark_ticker,
                benchmark_previous_day.trade_date,
            )
            if prior_benchmark_day is not None:
                _require_positive_close(
                    prior_benchmark_day.close_price,
                    benchmark_ticker,
                    prior_benchmark_day.trade_date,
                )
                benchmark_previous_day_return_percent = _percent_return(
                    prior_benchmark_day.close_price,
                    benchmark_previous_day.close_price,
                )

    previous_event = store.get_previous_dividend_event(ticker, event.ex_date)
    previous_ex_dividend_percent = None
    previous_ex_close_drop_percent = None
    previous_ex_date = None
    if previous_event is not None:
        previous_ex_date = previous_event.ex_date
        previous_ex_analysis = _analyze_previous_event(store, previous_event)
        previous_ex_dividend_percent = previous_ex_analysis.dividend_percent
        previous_ex_close_drop_percent = previous_ex_analysis.close_drop_percent

    dividend_percent = (event.dividend_amount / previous_day.close_price) * 100
    open_drop_percent = _percent_drop(previous_day.close_price, ex_day_price.open_price)
    close_drop_percent = _percent_drop(previous_day.close_price, ex_day_price.close_price)

    return DividendDropAnalysis(
        ticker=ticker,
        ex_date=event.ex_date,
        dividend_amount=event.dividend_amount,
        dividend_percent=dividend_percent,
        previous_close=previous_day.close_price,
        ex_day_open=ex_day_price.open_price,
        ex_day_close=ex_day_price.close_price,
        open_drop_percent=open_drop_percent,
        close_drop_percent=close_drop_percent,
        open_drop_minus_dividend_percent=open_drop_percent - dividend_percent,
        close_drop_minus_dividend_percent=close_drop_percent - dividend_percent,
        previous_trading_day_return_percent=previous_trading_day_return_percent,
        benchmark_previous_day_return_percent=benchmark_previous_day_return_percent,
        previous_ex_date=previous_ex_date,
        previous_ex_dividend_percent=previous_ex_dividend_percent,
        previous_ex_close_drop_percent=previous_ex_close_drop_percent,
    )


def _analyze_previous_event(store: MarketDataStore, event: DividendEvent) -> PreviousEventAnalysis:
    previous_trading_day = store.get_previous_trading_day(event.ticker, event.ex_date)
    ex_day_price = store.get_daily_price(event.ticker, event.ex_date)
    if previous_trading_day is None or ex_day_price is None:
        return PreviousEventAnalysis(dividend_percent=None, close_drop_percent=None)
    try:
        _require_positive_close(previous_trading_day.close_price, event.ticker, previous_trading_day.trade_date)
        _require_positive_price(ex_day_price.close_price, event.ticker, ex_day_price.trade_date, "close_price")
    except ValueError:
        return PreviousEventAnalysis(dividend_percent=None, close_drop_percent=None)

    dividend_percent = (event.dividend_amount / previous_trading_day.close_price) * 100
    close_drop_percent = _percent_drop(previous_trading_day.close_price, ex_day_price.close_price)
    return PreviousEventAnalysis(
        dividend_percent=dividend_percent,
        close_drop_percent=close_drop_percent,
    )
