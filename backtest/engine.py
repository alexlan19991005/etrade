"""Daily-bar backtester.

Rules
-----
- A signal computed from closes at day ``t`` is executed at the open of
  day ``t+1`` (no lookahead: signals never see the execution price).
- Rebalancing happens only when the target weights change; between signal
  days the share counts are held fixed (weights drift with prices, as in a
  real account).
- Commission is $0 (E*Trade stocks/ETFs are commission-free). Slippage is
  5 bps of traded notional per trade, deducted from cash on the trade day.
- Starting capital is $100,000, no leverage, max 100% invested, cash earns
  0%. Fractional shares are allowed (keeps the math clean; at live scale
  E*Trade supports fractional shares for most names, otherwise round down).
- "Trades" counts each (symbol, day) on which more than $10 of that symbol
  was bought or sold. "Win rate" is the share of closed position legs
  (sales) whose realised P&L was positive, using average cost basis.
"""

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


def compute_metrics(equity: pd.Series) -> dict:
    """Return/risk metrics for a daily equity curve."""
    equity = equity.dropna()
    if len(equity) < 2:
        raise ValueError("equity curve too short to compute metrics")
    initial = float(equity.iloc[0])
    final = float(equity.iloc[-1])
    n_days = len(equity)
    total_return = final / initial - 1.0
    years = n_days / TRADING_DAYS_PER_YEAR
    cagr = (final / initial) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    daily_ret = equity.pct_change().fillna(0.0)
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    max_dd = float(drawdown.min())
    vol = float(daily_ret.std(ddof=1)) if len(daily_ret) > 1 else 0.0
    sharpe = (
        float(daily_ret.mean() / vol * np.sqrt(TRADING_DAYS_PER_YEAR))
        if vol > 0
        else 0.0
    )
    return {
        "initial_equity": initial,
        "final_equity": final,
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "volatility_annual": vol * np.sqrt(TRADING_DAYS_PER_YEAR),
        "n_days": int(n_days),
    }


def run_backtest(
    opens: pd.DataFrame,
    closes: pd.DataFrame,
    signals: pd.DataFrame,
    initial_capital: float = 100_000.0,
    slippage_bps: float = 5.0,
    min_trade_value: float = 10.0,
) -> dict:
    """Run one strategy through daily bars.

    Parameters
    ----------
    opens, closes: DataFrames of daily open/close prices, same index,
        columns = symbols traded. Rows are trading days.
    signals: DataFrame of target weights, same index as closes, columns a
        subset of the price columns. ``signals`` at row ``t`` is executed
        at the open of row ``t+1``.
    """
    symbols = list(signals.columns)
    opens = opens[symbols]
    closes = closes[symbols]
    idx = closes.index
    slippage = slippage_bps / 10_000.0

    shares = pd.Series(0.0, index=symbols)
    avg_cost = {s: 0.0 for s in symbols}
    cash = float(initial_capital)
    equity_curve = []
    n_trades = 0
    realized_wins = 0
    realized_legs = 0
    prev_target: pd.Series | None = None

    for i in range(len(idx)):
        if i > 0:
            # Execute yesterday's signal at today's open, but only when
            # the target weights actually changed. Rebalancing every day
            # to chase drift would invent thousands of micro-trades.
            target = signals.iloc[i - 1]
            if prev_target is None or not target.equals(prev_target):
                prev_target = target.copy()
                open_px = opens.iloc[i]
                value_open = cash + float((shares * open_px).sum())
                desired_value = target * value_open
                new_shares = pd.Series(0.0, index=symbols)
                valid = (open_px > 0) & open_px.notna()
                new_shares[valid] = desired_value[valid] / open_px[valid]
                traded_value = (new_shares - shares).abs() * open_px
                total_traded = float(traded_value.sum())
                if total_traded > min_trade_value:
                    cost = slippage * total_traded
                    for s in symbols:
                        delta = float(new_shares[s] - shares[s])
                        if abs(delta) * float(open_px[s]) <= min_trade_value:
                            continue
                        n_trades += 1
                        if delta < 0:
                            sold = -delta
                            pnl = (float(open_px[s]) - avg_cost[s]) * sold
                            realized_legs += 1
                            realized_wins += 1 if pnl > 0 else 0
                        else:
                            old = float(shares[s])
                            if old > 0:
                                avg_cost[s] = (
                                    avg_cost[s] * old
                                    + float(open_px[s]) * delta
                                ) / (old + delta)
                            else:
                                avg_cost[s] = float(open_px[s])
                    shares = new_shares
                    cash = value_open - float((new_shares * open_px).sum()) - cost
        equity_curve.append(cash + float((shares * closes.iloc[i]).sum()))

    equity = pd.Series(equity_curve, index=idx, dtype=float)
    metrics = compute_metrics(equity)
    metrics["n_trades"] = int(n_trades)
    metrics["win_rate"] = (
        realized_wins / realized_legs if realized_legs > 0 else float("nan")
    )
    metrics["n_closed_legs"] = int(realized_legs)
    return {"equity": equity, "metrics": metrics}


def equal_weight_portfolio(
    equity_curves: dict[str, pd.Series],
) -> pd.Series:
    """Combine strategy equity curves into a 20%-each portfolio.

    Each sleeve starts at 20% of capital and is rebalanced back to equal
    weight at the end of every month. Sleeve values are rescaled (not
    traded) — the approximation is that rebalancing between sleeves is
    frictionless at month end, which is reasonable for a monthly rebalance
    of liquid ETFs/stocks.
    """
    names = list(equity_curves.keys())
    n = len(names)
    norm = pd.DataFrame(
        {k: v / v.iloc[0] for k, v in equity_curves.items()}
    )
    sleeve_value = pd.DataFrame(0.0, index=norm.index, columns=names)
    sleeve_value.iloc[0] = 1.0 / n
    months = norm.index.to_period("M").to_series()
    month_end = months != months.shift(-1)
    for i in range(1, len(norm)):
        ret = norm.iloc[i] / norm.iloc[i - 1]
        sleeve_value.iloc[i] = sleeve_value.iloc[i - 1] * ret
        if month_end.iloc[i - 1]:
            total = sleeve_value.iloc[i].sum()
            sleeve_value.iloc[i] = total / n
    portfolio = sleeve_value.sum(axis=1)
    return portfolio
