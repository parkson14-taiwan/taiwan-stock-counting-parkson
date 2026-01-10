import io
from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st


@dataclass
class BacktestResult:
    data: pd.DataFrame
    total_return: float
    max_drawdown: float
    win_rate: float
    trades_count: int


def compute_max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    return drawdown.min()


def compute_backtest(
    data: pd.DataFrame,
    x: float,
    y: float,
    a: float,
    b: float,
    initial_leverage: float,
    max_leverage: float | None,
    fee_rate: float,
    slippage_rate: float,
) -> BacktestResult:
    df = data.copy()
    df["ma10"] = df["close"].rolling(10).mean()
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma60"] = df["close"].rolling(60).mean()

    c1 = df["close"].shift(1)
    c2 = df["close"].shift(2)
    ma10_1 = df["ma10"].shift(1)
    ma10_2 = df["ma10"].shift(2)
    ma20_1 = df["ma20"].shift(1)
    ma20_2 = df["ma20"].shift(2)
    ma60_1 = df["ma60"].shift(1)

    df["up_event"] = (c2 <= ma10_2) & (c2 <= ma20_2) & (c1 >= ma10_1) & (c1 >= ma20_1)
    df["down_event"] = (c2 >= ma10_2) & (c2 >= ma20_2) & (c1 <= ma10_1) & (c1 <= ma20_1)
    df["season_up"] = c1 >= ma60_1
    df["season_down"] = c1 < ma60_1

    targets = []
    for up, down, season_up, season_down in zip(
        df["up_event"],
        df["down_event"],
        df["season_up"],
        df["season_down"],
    ):
        if up and season_up:
            targets.append(x)
        elif down and season_up:
            targets.append(y)
        elif up and season_down:
            targets.append(a)
        elif down and season_down:
            targets.append(b)
        else:
            targets.append(None)

    df["target"] = targets

    leverage = []
    prev_leverage = initial_leverage
    for target in df["target"]:
        current = prev_leverage if target is None else float(target)
        if max_leverage is not None:
            current = float(np.clip(current, -max_leverage, max_leverage))
        leverage.append(current)
        prev_leverage = current

    df["leverage"] = leverage
    df["return"] = df["close"].pct_change().fillna(0)

    leverage_shift = df["leverage"].shift(1).fillna(initial_leverage)
    trade_cost = np.where(df["leverage"] != leverage_shift, fee_rate + slippage_rate, 0.0)

    df["strategy_return"] = df["return"] * df["leverage"] - trade_cost
    df["equity"] = (1 + df["strategy_return"]).cumprod()

    total_return = df["equity"].iloc[-1] - 1
    max_drawdown = compute_max_drawdown(df["equity"])
    win_rate = (df["strategy_return"] > 0).mean() if len(df) else 0.0
    trades_count = int((df["leverage"] != leverage_shift).sum())

    return BacktestResult(
        data=df,
        total_return=total_return,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        trades_count=trades_count,
    )


def load_csv(file: io.BytesIO) -> pd.DataFrame:
    df = pd.read_csv(file)
    required = {"date", "close"}
    missing = required.difference(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing columns: {', '.join(sorted(missing))}")

    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isna().any():
        raise ValueError("Invalid date values detected.")

    df = df.sort_values("date").reset_index(drop=True)
    return df[["date", "close"]]


def main() -> None:
    st.set_page_config(page_title="台指期/台灣大盤回測", layout="wide")
    st.title("台指期 / 台灣大盤（日線）策略回測")

    with st.sidebar:
        st.header("策略參數")
        x = st.number_input("X", value=1.0, step=0.1, format="%.4f")
        y = st.number_input("Y", value=-1.0, step=0.1, format="%.4f")
        a = st.number_input("A", value=1.0, step=0.1, format="%.4f")
        b = st.number_input("B", value=-1.0, step=0.1, format="%.4f")
        initial_leverage = st.number_input(
            "initial_leverage", value=0.0, step=0.1, format="%.4f"
        )
        max_leverage_enabled = st.checkbox("啟用 max_leverage cap", value=False)
        max_leverage = None
        if max_leverage_enabled:
            max_leverage = st.number_input("max_leverage", value=3.0, step=0.1)

        st.subheader("成本參數")
        fee_rate = st.number_input("fee_rate", value=0.0, step=0.0001, format="%.6f")
        slippage_rate = st.number_input(
            "slippage_rate", value=0.0, step=0.0001, format="%.6f"
        )

    uploaded = st.file_uploader("上傳 CSV（至少含 date, close）", type=["csv"])
    if not uploaded:
        st.info("請先上傳 CSV。")
        return

    try:
        df = load_csv(uploaded)
    except ValueError as exc:
        st.error(str(exc))
        return

    if len(df) < 3:
        st.warning("資料筆數不足，請提供至少 3 筆資料。")
        return

    result = compute_backtest(
        data=df,
        x=x,
        y=y,
        a=a,
        b=b,
        initial_leverage=initial_leverage,
        max_leverage=max_leverage,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
    )

    metrics = st.columns(4)
    metrics[0].metric("total_return", f"{result.total_return:.2%}")
    metrics[1].metric("max_drawdown", f"{result.max_drawdown:.2%}")
    metrics[2].metric("win_rate", f"{result.win_rate:.2%}")
    metrics[3].metric("trades_count", f"{result.trades_count}")

    st.subheader("Equity Curve")
    st.line_chart(result.data.set_index("date")["equity"])

    output = result.data[
        [
            "date",
            "close",
            "ma10",
            "ma20",
            "ma60",
            "leverage",
            "strategy_return",
            "equity",
            "up_event",
            "down_event",
            "season_up",
            "season_down",
            "target",
        ]
    ].copy()

    csv_buffer = io.StringIO()
    output.to_csv(csv_buffer, index=False)
    st.download_button(
        "下載回測結果 CSV",
        data=csv_buffer.getvalue(),
        file_name="backtest_results.csv",
        mime="text/csv",
    )

    st.subheader("回測結果預覽")
    st.dataframe(output.tail(20))


if __name__ == "__main__":
    main()
