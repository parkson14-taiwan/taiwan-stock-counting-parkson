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
    ma5: int,
    ma10: int,
    ma60: int,
    x: float,
    y: float,
    a: float,
    b: float,
    initial_capital: float,
    contract_multiplier: float,
    max_leverage: float | None,
) -> pd.DataFrame:
    df = df.copy()
    df["ma5"] = df["close"].rolling(window=ma5).mean()
    df["ma10"] = df["close"].rolling(window=ma10).mean()
    df["ma60"] = df["close"].rolling(window=ma60).mean()

    c1 = df["close"].shift(1)
    c2 = df["close"].shift(2)
    ma5_1 = df["ma5"].shift(1)
    ma5_2 = df["ma5"].shift(2)
    ma10_1 = df["ma10"].shift(1)
    ma10_2 = df["ma10"].shift(2)
    ma60_1 = df["ma60"].shift(1)

    df["UP_EVENT"] = (c2 <= ma5_2) & (c2 <= ma10_2) & (c1 >= ma5_1) & (c1 >= ma10_1)
    df["DOWN_EVENT"] = (c2 >= ma5_2) & (c2 >= ma10_2) & (c1 <= ma5_1) & (c1 <= ma10_1)

    df["SEASON_UP"] = c1 >= ma60_1
    df["SEASON_DOWN"] = c1 < ma60_1

    equity_values: list[float] = []
    contracts_values: list[int] = []
    leverage_values: list[float] = []
    strategy_returns: list[float] = []

    leverage_cap = abs(max_leverage) if max_leverage is not None else None
    previous_equity = initial_capital
    previous_close: float | None = None
    previous_contracts = 0
    previous_target_leverage = 0.0

    for _, row in df.iterrows():
        contract_value = row["close"] * contract_multiplier
        target: float | None = None
        if row["UP_EVENT"] and row["SEASON_UP"]:
            target = x
        elif row["DOWN_EVENT"] and row["SEASON_UP"]:
            target = y
        elif row["UP_EVENT"] and row["SEASON_DOWN"]:
            target = a
        elif row["DOWN_EVENT"] and row["SEASON_DOWN"]:
            target = b

        if previous_close is None:
            pnl = 0.0
            equity_today = previous_equity
            strategy_return = 0.0
        else:
            pnl = previous_contracts * (row["close"] - previous_close) * contract_multiplier
            equity_today = previous_equity + pnl
            strategy_return = (
                0.0 if previous_equity == 0 else (equity_today - previous_equity) / previous_equity
            )

        if target is not None:
            previous_target_leverage = target
        target_leverage = previous_target_leverage

        if contract_value == 0:
            desired_contracts = 0
        else:
            desired_contracts = int(
                np.floor((equity_today * target_leverage) / contract_value)
            )

        if leverage_cap is not None and leverage_cap > 0:
            if contract_value == 0:
                max_contracts = 0
            else:
                max_contracts = int(
                    np.floor((equity_today * leverage_cap) / contract_value)
                )
            if abs(desired_contracts) > max_contracts:
                desired_contracts = int(np.sign(desired_contracts) * max_contracts)

        contracts_today = desired_contracts

        position_value = contracts_today * contract_value
        leverage_today = 0.0 if equity_today == 0 else position_value / equity_today

        equity_values.append(equity_today)
        contracts_values.append(contracts_today)
        leverage_values.append(leverage_today)
        strategy_returns.append(strategy_return)

        previous_equity = equity_today
        previous_close = row["close"]
        previous_contracts = contracts_today

    df["contracts"] = contracts_values
    df["leverage_today"] = leverage_values
    df["leverage_yesterday"] = (
        pd.Series(leverage_values, index=df.index).shift(1).fillna(0.0)
    )
    df["strategy_return"] = strategy_returns
    df["equity"] = equity_values

    return df


def main() -> None:
    st.set_page_config(page_title="台股回測", layout="wide")
    st.title("台股 MA 回測 (CSV 自動讀取)")

    df = load_data()
    st.subheader("資料預覽 (前 20 行)")
    st.dataframe(df.head(20))

    with st.sidebar:
        st.header("均線參數")
        ma5 = st.number_input("MA5 週期", min_value=1, value=5, step=1)
        ma10 = st.number_input("MA10 週期", min_value=1, value=10, step=1)
        ma60 = st.number_input("MA60 週期", min_value=1, value=60, step=1)

        st.header("策略倍率")
        x = st.number_input("X (UP & 季線上)", value=1.0, step=0.1, format="%.2f")
        y = st.number_input("Y (DOWN & 季線上)", value=-1.0, step=0.1, format="%.2f")
        a = st.number_input("A (UP & 季線下)", value=1.0, step=0.1, format="%.2f")
        b = st.number_input("B (DOWN & 季線下)", value=-1.0, step=0.1, format="%.2f")

        st.header("資金與槓桿")
        initial_capital = 1_000_000.0
        contract_multiplier = 10.0
        st.number_input(
            "初始資金",
            value=initial_capital,
            step=10_000.0,
            format="%.0f",
            disabled=True,
        )
        st.number_input(
            "微台合約乘數",
            value=contract_multiplier,
            step=1.0,
            format="%.0f",
            disabled=True,
        )
        use_max_leverage = st.checkbox("限制最大槓桿")
        max_leverage = None
        if use_max_leverage:
            max_leverage = st.number_input(
                "最大槓桿 (取絕對值)", value=2.0, step=0.1, format="%.2f"
            )

    result = compute_strategy(
        df,
        ma5=ma5,
        ma10=ma10,
        ma60=ma60,
        x=x,
        y=y,
        a=a,
        b=b,
        initial_capital=initial_capital,
        contract_multiplier=contract_multiplier,
        max_leverage=max_leverage,
    )

    total_return = (
        result["equity"].iloc[-1] / initial_capital - 1 if not result.empty else np.nan
    )
    running_max = result["equity"].cummax()
    drawdown = result["equity"] / running_max - 1
    max_drawdown = drawdown.min() if not drawdown.empty else np.nan
    valid_returns = result["strategy_return"].replace(0, np.nan).dropna()
    win_rate = (valid_returns > 0).mean() if not valid_returns.empty else np.nan
    trades_count = (result["leverage_today"] != result["leverage_yesterday"]).sum()
    equity_collapse_threshold = initial_capital * 0.01

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

    st.subheader("每日口數 / 權益 / 槓桿")
    st.dataframe(
        result[["date", "contracts", "equity", "leverage_today"]].reset_index(drop=True)
    )

    st.subheader("Equity 崩潰位置報告")
    collapse_returns = result[result["strategy_return"] <= -1].copy()
    collapse_equity = result[result["equity"] <= equity_collapse_threshold].copy()
    if collapse_returns.empty and collapse_equity.empty:
        st.write("沒有偵測到 Equity 崩潰或單日報酬 <= -100%。")
    else:
        st.caption(
            f"當 equity <= {equity_collapse_threshold:.2f} 或單日報酬 <= -100% 視為崩潰。"
        )
        if not collapse_returns.empty:
            st.write("單日報酬 <= -100% 的時間點")
            st.dataframe(
                collapse_returns[
                    ["date", "close", "strategy_return", "leverage_today", "equity"]
                ].reset_index(drop=True)
            )
        if not collapse_equity.empty:
            st.write(f"Equity <= {equity_collapse_threshold:.2f} 的時間點")
            st.dataframe(
                collapse_equity[
                    ["date", "close", "strategy_return", "leverage_today", "equity"]
                ].reset_index(drop=True)
            )

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
        "ma5",
        "ma10",
        "ma60",
        "contracts",
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
