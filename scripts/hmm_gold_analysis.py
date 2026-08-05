#!/usr/bin/env python3
"""
hmm_gold_analysis.py — HMM 隐马尔可夫模型分析 XAUUSD 状态切换与趋势判断
数据源: Yahoo Finance GC=F (Comex 黄金期货, 与 XAUUSD 高度相关)
方法: GaussianHMM 拟合对数收益率 + 波动特征 → 识别隐藏市场状态
输出: JSON (供 cron agent 生成中文报告)
"""
import json
import warnings
import numpy as np
import pandas as pd
import yfinance as yf
from hmmlearn import hmm
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

LOOKBACK_DAYS = 180   # 训练窗口 ~6个月
N_STATES = 3          # 3状态: 趋势上涨 / 震荡 / 趋势下跌 (或按波动分)
HORIZON = 5           # 预测展望天数


def fetch_gold(days=LOOKBACK_DAYS):
    d = yf.download("GC=F", period=f"{days}d", interval="1d", progress=False, auto_adjust=True)
    close = d["Close"]
    if hasattr(close, "columns"):  # MultiIndex columns → squeeze to Series
        close = close.iloc[:, 0]
    return close.dropna()


def build_features(close):
    """对数收益率 + 5日滚动波动率作为观测特征"""
    ret = np.log(close / close.shift(1)).dropna()
    vol = ret.rolling(5).std().dropna()
    df = pd.DataFrame({"ret": ret, "vol": vol}).dropna()
    return df


def fit_hmm(df, n_states=N_STATES, seed=42):
    model = hmm.GaussianHMM(
        n_components=n_states,
        covariance_type="full",
        n_iter=200,
        random_state=seed,
    )
    X = df[["ret", "vol"]].values
    model.fit(X)
    states = model.predict(X)
    return model, states


def describe_states(model, states, df):
    """按均值收益排序状态: 0=最空/弱, ... , N-1=最强"""
    state_means = {}
    for s in range(model.n_components):
        mask = states == s
        state_means[s] = {
            "count": int(mask.sum()),
            "mean_ret": float(df["ret"][mask].mean()),
            "mean_vol": float(df["vol"][mask].mean()),
            "std_ret": float(df["ret"][mask].std()),
        }
    # 排序: 收益从低到高
    order = sorted(state_means.keys(), key=lambda s: state_means[s]["mean_ret"])
    label_map = {order[0]: "弱势/下跌", order[1]: "震荡/中性"}
    if N_STATES >= 3:
        label_map[order[-1]] = "强势/上涨"
    return state_means, label_map, order


def main():
    close = fetch_gold()
    if len(close) < 60:
        print(json.dumps({"error": "insufficient data", "rows": len(close)}, ensure_ascii=False))
        return

    df = build_features(close)
    model, states = fit_hmm(df)
    state_means, label_map, order = describe_states(model, states, df)

    current_state = states[-1]
    current_label = label_map.get(current_state, f"状态{current_state}")

    # 最近 10 个交易日状态序列
    recent_dates = df.index[-10:].strftime("%m-%d").tolist()
    recent_states = [label_map.get(s, f"S{s}") for s in states[-10:]]

    # 状态转移概率 (当前状态 → 下一状态)
    trans = model.transmat_[current_state]
    next_probs = {label_map.get(s, f"S{s}"): round(float(p) * 100, 1)
                  for s, p in enumerate(trans)}

    # 5日展望: 用状态均值收益估算
    outlook = {}
    for s in range(model.n_components):
        mu = model.means_[s][0]
        outlook[label_map.get(s, f"S{s}")] = round(float(np.expm1(mu * HORIZON)) * 100, 2)

    # 当前价格
    price = float(close.iloc[-1])
    price_prev = float(close.iloc[-2])
    daily_chg = (price / price_prev - 1) * 100

    report = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M BJT"),
        "symbol": "GC=F (黄金期货, 代理 XAUUSD)",
        "data_window": f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')} ({len(df)} 交易日)",
        "price": round(price, 2),
        "daily_chg_pct": round(daily_chg, 2),
        "hmm": {
            "n_states": N_STATES,
            "current_state": int(current_state),
            "current_label": current_label,
            "state_means": {label_map.get(s, f"S{s}"): {
                "mean_daily_ret_pct": round(m["mean_ret"] * 100, 3),
                "mean_vol": round(m["mean_vol"], 4),
                "count": m["count"],
            } for s, m in state_means.items()},
            "recent_10d": list(zip(recent_dates, recent_states)),
            "transition_from_current": next_probs,
            "outlook_5d_pct": outlook,
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
