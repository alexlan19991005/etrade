# Trading Strategies

Five systematic, long-only US equity/ETF strategies — a mix of long, medium
and short horizons — with a vectorised daily-bar backtester and an E*Trade
execution adapter. Everything is designed so the **same strategy code runs
in backtest and live**: strategies output target weights, the backtester
simulates fills, and `etrade/client.py` turns weights into E*Trade orders.

> **Risk note — read first.** Backtests use historical data and do not
> predict future returns. Every strategy here has losing periods (see
> `results/summary.csv` for max drawdown). These strategies are a research
> starting point, not investment advice. Test in the E*Trade sandbox
> before risking real money, start small, and never trade money you cannot
> afford to lose.

## The five strategies

| # | Strategy | Horizon | What it does |
|---|----------|---------|--------------|
| 1 | `trend_ma` | Long-term | Hold SPY while its 50-day average is above its 200-day average; otherwise cash. Rides bull markets, sits out bear markets; whipsaws in choppy markets. |
| 2 | `momentum_rotation` | Medium-term | Each month, hold the top 5 of 20 liquid large caps by 6-month return, equal weight. Rides persistent leaders; hurts when leadership reverses sharply. |
| 3 | `mean_reversion_rsi` | Short-term | Buy SPY when 14-day RSI < 30, exit when RSI > 70 or after 10 days. Profits from snap-back after sell-offs; catches falling knives in real bear markets. |
| 4 | `breakout_donchian` | Medium-short | Buy QQQ on a 20-day-high breakout confirmed by above-average volume; exit on a 10-day-low break. Rides strong growth trends; loses on false breakouts. |
| 5 | `defensive_rotation` | Long-term | SPY when above its 200-day average, else TLT (Treasuries) when TLT is above its average, else BIL (cash). Cushions bear markets; slow to re-enter after V-shaped recoveries. |

Each strategy lives in `strategies/` with its logic, parameters, horizon
and failure modes documented in the file header. All strategies implement
`generate_signals(prices, data=None) -> DataFrame` of target weights and
use **only past data** (rolling windows / `shift(1)`); the backtester
executes a signal at the **next open**, so no lookahead is possible.

There is also an equal-weight portfolio of the five (20% each, rebalanced
monthly) and an SPY buy-and-hold benchmark in every backtest run.

## Backtest

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m backtest.run_backtest
```

- Data: Nasdaq public historical API (no key required), 2021-01-01 to the
  latest trading day. Prices are split-adjusted but **not
  dividend-adjusted**, so total returns are slightly understated (roughly
  by each holding's dividend yield, ~1.3%/yr for SPY). The understatement
  applies equally to every strategy and to the SPY benchmark, so strategy
  comparisons are still valid. Raw downloads are cached in `data/raw/`.
- Starting capital $100,000 per strategy, no leverage, max 100% invested.
- Commission $0 (E*Trade stocks/ETFs are commission-free), slippage 5 bps
  per trade.
- Metrics per strategy (and the equal-weight portfolio, and the SPY
  benchmark): total return, CAGR, max drawdown, Sharpe (risk-free rate 0),
  win rate, number of trades, final equity.
- Outputs in `results/`: `backtest_results.json`, `summary.csv`,
  `equity_curves.csv`.

## Going live with E*Trade

1. Create a free developer account at https://developer.etrade.com and
   create an app to get a consumer key / secret. **Sandbox keys and
   production keys are separate.**
2. `cp .env.example .env` and fill in the keys. Never commit `.env`.
3. Authenticate once (interactive OAuth — E*Trade shows a verification
   code you paste back):
   ```python
   from etrade.client import ETradeClient
   client = ETradeClient()          # sandbox by default
   client.authenticate_interactive()
   ```
   Tokens are cached in `~/.etrade_tokens.json` (outside the repo).
4. Dry-run orders first — `place_market_order` defaults to dry-run
   logging and sends nothing to E*Trade:
   ```python
   client.place_market_order("SPY", 10, "BUY")            # dry run
   client.place_market_order("SPY", 10, "BUY", live=True) # real order
   ```
5. Test the full flow in the sandbox. Only then set
   `ETRADE_ENV=production` — and only with money you are prepared to
   lose. Suggested rollout: $5,000 total, $1,000 per strategy, then scale
   gradually as live behaviour matches the backtest.

## Layout

```
strategies/            # one file per strategy + common interface
etrade/client.py       # E*Trade adapter (pyetrade), sandbox-first, dry-run default
backtest/engine.py     # daily-bar backtester (next-open execution, 5 bps slippage)
backtest/run_backtest.py  # downloads data, runs all strategies + EW + benchmark
results/               # backtest outputs (regenerated on each run)
```
