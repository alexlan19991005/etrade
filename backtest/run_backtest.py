"""Download data with the Nasdaq public API and run the full backtest.

Period: 2021-01-01 through the latest available trading day.
Starting capital: $100,000 per strategy. Commission $0, slippage 5 bps.
Outputs (in results/):
  backtest_results.json — per-strategy metrics, EW portfolio, benchmark
  summary.csv           — same metrics in tabular form
  equity_curves.csv     — daily equity of every strategy + EW + benchmark
"""

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.data import download_data
from backtest.engine import compute_metrics, equal_weight_portfolio, run_backtest
from strategies import ALL_STRATEGIES
from strategies.momentum_rotation import UNIVERSE

START = "2021-01-01"
INITIAL_CAPITAL = 100_000.0
SLIPPAGE_BPS = 5.0

BASE_SYMBOLS = ["SPY", "QQQ", "TLT", "BIL"]
ALL_SYMBOLS = sorted(set(BASE_SYMBOLS) | set(UNIVERSE))


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "results"
    out_dir.mkdir(exist_ok=True)
    cache_dir = Path(__file__).resolve().parents[1] / "data" / "raw"

    print(f"Downloading data from {START} ...")
    data = download_data(ALL_SYMBOLS, start=START, cache_dir=cache_dir)
    closes = data["close"]
    opens = data["open"]
    print(f"Data: {len(closes)} trading days, "
          f"{closes.index[0].date()} to {closes.index[-1].date()}")

    results: dict = {
        "start_date": str(closes.index[0].date()),
        "end_date": str(closes.index[-1].date()),
        "n_days": len(closes),
        "initial_capital": INITIAL_CAPITAL,
        "commission": 0.0,
        "slippage_bps": SLIPPAGE_BPS,
        "risk_free_rate": 0.0,
        "strategies": {},
    }
    equity_curves: dict[str, pd.Series] = {}

    for cls in ALL_STRATEGIES:
        strat = cls()
        print(f"Running {strat.name} ...")
        signals = strat.generate_signals(closes, data)
        res = run_backtest(
            opens, closes, signals,
            initial_capital=INITIAL_CAPITAL,
            slippage_bps=SLIPPAGE_BPS,
        )
        results["strategies"][strat.name] = res["metrics"]
        equity_curves[strat.name] = res["equity"]
        print(f"  final ${res['metrics']['final_equity']:,.0f}  "
              f"CAGR {res['metrics']['cagr']:.2%}  "
              f"MaxDD {res['metrics']['max_drawdown']:.2%}  "
              f"trades {res['metrics']['n_trades']}")

    print("Running benchmark (SPY buy-and-hold) ...")
    bench_signals = pd.DataFrame(
        {"SPY": 1.0}, index=closes.index, dtype=float
    )
    bench = run_backtest(
        opens, closes, bench_signals,
        initial_capital=INITIAL_CAPITAL,
        slippage_bps=SLIPPAGE_BPS,
    )
    results["benchmark_spy_buy_hold"] = bench["metrics"]
    equity_curves["benchmark_spy"] = bench["equity"]

    print("Building equal-weight portfolio (20% each, monthly rebalance) ...")
    ew_equity = equal_weight_portfolio(
        {k: v for k, v in equity_curves.items() if k != "benchmark_spy"}
    )
    ew_equity = ew_equity / ew_equity.iloc[0] * INITIAL_CAPITAL
    ew_metrics = compute_metrics(ew_equity)
    ew_metrics["n_trades"] = sum(
        m["n_trades"] for m in results["strategies"].values()
    )
    ew_metrics["win_rate"] = float("nan")  # not defined at portfolio level
    ew_metrics["n_closed_legs"] = sum(
        m["n_closed_legs"] for m in results["strategies"].values()
    )
    results["equal_weight_portfolio"] = ew_metrics
    equity_curves["equal_weight"] = ew_equity

    with open(out_dir / "backtest_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    rows = []
    for name, m in results["strategies"].items():
        rows.append({"strategy": name, **m})
    rows.append({"strategy": "equal_weight_portfolio",
                 **results["equal_weight_portfolio"]})
    rows.append({"strategy": "benchmark_spy_buy_hold",
                 **results["benchmark_spy_buy_hold"]})
    pd.DataFrame(rows).to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(equity_curves).to_csv(out_dir / "equity_curves.csv")

    print("\n=== SUMMARY ===")
    print(pd.DataFrame(rows)[
        ["strategy", "total_return", "cagr", "max_drawdown",
         "sharpe_ratio", "win_rate", "n_trades", "final_equity"]
    ].to_string(index=False))
    print(f"\nResults written to {out_dir}")


if __name__ == "__main__":
    main()
