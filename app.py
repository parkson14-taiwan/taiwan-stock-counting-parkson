from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent / "data" / "taiex.csv"


@st.cache_data
def load_data() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"找不到資料檔案: {DATA_PATH}")
    df = pd.read_csv(DATA_PATH)
    df = df.rename(columns={"交易日期": "date", "收盤": "close"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["date", "close"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def compute_strategy(
    df: pd.DataFrame,
    ma10: int,
    ma20: int,
    ma60: int,
    x: float,
    y: float,
    a: float,
    b: float,
    initial_leverage: float,
    fee_rate: float,
    slippage_rate: float,
    max_leverage: float | None,
) -> pd.DataFrame:
    df = df.copy()
    df["ma10"] = df["close"].rolling(window=ma10).mean()
    df["ma20"] = df["close"].rolling(window=ma20).mean()
    df["ma60"] = df["close"].rolling(window=ma60).mean()

    c1 = df["close"].shift(1)
    c2 = df["close"].shift(2)
    ma10_1 = df["ma10"].shift(1)
    ma10_2 = df["ma10"].shift(2)
    ma20_1 = df["ma20"].shift(1)
    ma20_2 = df["ma20"].shift(2)
    ma60_1 = df["ma60"].shift(1)

    df["UP_EVENT"] = (c2 <= ma10_2) & (c2 <= ma20_2) & (c1 >= ma10_1) & (c1 >= ma20_1)
    df["DOWN_EVENT"] = (c2 >= ma10_2) & (c2 >= ma20_2) & (c1 <= ma10_1) & (c1 <= ma20_1)

    df["SEASON_UP"] = c1 >= ma60_1
    df["SEASON_DOWN"] = c1 < ma60_1

    leverage_values: list[float] = []
    previous_leverage = initial_leverage
    leverage_cap = abs(max_leverage) if max_leverage is not None else None

    for _, row in df.iterrows():
        target: float | None = None
        if row["UP_EVENT"] and row["SEASON_UP"]:
            target = x
        elif row["DOWN_EVENT"] and row["SEASON_UP"]:
            target = y
        elif row["UP_EVENT"] and row["SEASON_DOWN"]:
            target = a
        elif row["DOWN_EVENT"] and row["SEASON_DOWN"]:
            target = b

        leverage_today = previous_leverage
        if target is not None:
            leverage_today = target

        if leverage_cap is not None and leverage_cap > 0:
            if abs(leverage_today) > leverage_cap:
                leverage_today = np.sign(leverage_today) * leverage_cap

        leverage_values.append(leverage_today)
        previous_leverage = leverage_today

    df["leverage_today"] = leverage_values
    df["leverage_yesterday"] = df["leverage_today"].shift(1).fillna(initial_leverage)

    df["return"] = df["close"].pct_change()
    trade_cost = np.where(
        df["leverage_today"] != df["leverage_yesterday"],
        fee_rate + slippage_rate,
        0.0,
    )
    df["strategy_return"] = df["return"] * df["leverage_today"] - trade_cost
    df["strategy_return"] = df["strategy_return"].fillna(0)
    df["equity"] = (1 + df["strategy_return"]).cumprod()

    return df


def main() -> None:
    st.set_page_config(page_title="台股回測", layout="wide")
    st.title("台股 MA 回測 (CSV 自動讀取)")

    df = load_data()
    st.subheader("資料預覽 (前 20 行)")
    st.dataframe(df.head(20))

    with st.sidebar:
        st.header("均線參數")
        ma10 = st.number_input("MA10 週期", min_value=1, value=10, step=1)
        ma20 = st.number_input("MA20 週期", min_value=1, value=20, step=1)
        ma60 = st.number_input("MA60 週期", min_value=1, value=60, step=1)

        st.header("策略倍率")
        x = st.number_input("X (UP & 季線上)", value=1.0, step=0.1, format="%.2f")
        y = st.number_input("Y (DOWN & 季線上)", value=-1.0, step=0.1, format="%.2f")
        a = st.number_input("A (UP & 季線下)", value=1.0, step=0.1, format="%.2f")
        b = st.number_input("B (DOWN & 季線下)", value=-1.0, step=0.1, format="%.2f")

        st.header("成本與槓桿")
        initial_leverage = st.number_input(
            "初始倍率", value=0.0, step=0.1, format="%.2f"
        )
        fee_rate = st.number_input("手續費率", value=0.0, step=0.0001, format="%.4f")
        slippage_rate = st.number_input(
            "滑價率", value=0.0, step=0.0001, format="%.4f"
        )
        use_max_leverage = st.checkbox("限制最大槓桿")
        max_leverage = None
        if use_max_leverage:
            max_leverage = st.number_input(
                "最大槓桿 (取絕對值)", value=2.0, step=0.1, format="%.2f"
            )

    result = compute_strategy(
        df,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        x=x,
        y=y,
        a=a,
        b=b,
        initial_leverage=initial_leverage,
        fee_rate=fee_rate,
        slippage_rate=slippage_rate,
        max_leverage=max_leverage,
    )

    total_return = result["equity"].iloc[-1] - 1 if not result.empty else np.nan
    running_max = result["equity"].cummax()
    drawdown = result["equity"] / running_max - 1
    max_drawdown = drawdown.min() if not drawdown.empty else np.nan
    valid_returns = result["strategy_return"].replace(0, np.nan).dropna()
    win_rate = (valid_returns > 0).mean() if not valid_returns.empty else np.nan
    trades_count = (result["leverage_today"] != result["leverage_yesterday"]).sum()

    st.subheader("回測結果")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("總報酬", f"{total_return:.2%}" if pd.notna(total_return) else "N/A")
    col2.metric("最大回撤", f"{max_drawdown:.2%}" if pd.notna(max_drawdown) else "N/A")
    col3.metric("勝率", f"{win_rate:.2%}" if pd.notna(win_rate) else "N/A")
    col4.metric("交易次數", f"{int(trades_count)}")

    st.subheader("Equity Curve")
    fig, ax = plt.subplots()
    ax.plot(result["date"], result["equity"], label="Equity")
    ax.set_xlabel("Date")
    ax.set_ylabel("Equity")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend()
    st.pyplot(fig)

    st.subheader("觸發事件表")
    events = result[result["UP_EVENT"] | result["DOWN_EVENT"]].copy()
    if not events.empty:
        events["event"] = np.where(events["UP_EVENT"], "UP", "DOWN")
        events["season"] = np.where(events["SEASON_UP"], "季線上", "季線下")
        st.dataframe(
            events[["date", "event", "season", "leverage_today"]].reset_index(drop=True)
        )
    else:
        st.write("沒有觸發事件")

    st.subheader("下載結果")
    output_cols = [
        "date",
        "close",
        "ma10",
        "ma20",
        "ma60",
        "leverage_today",
        "strategy_return",
        "equity",
        "UP_EVENT",
        "DOWN_EVENT",
        "SEASON_UP",
    ]
    csv_data = result[output_cols].to_csv(index=False)
    st.download_button("下載 CSV", data=csv_data, file_name="backtest_results.csv")


if __name__ == "__main__":
    main()
