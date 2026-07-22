import MetaTrader5 as mt5, json, sys
from datetime import datetime, timezone

try:
    mt5.initialize(path="C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe")
    acc = mt5.account_info()
    if not acc:
        print("NO_ACCOUNT"); sys.exit(1)

    deals = mt5.history_deals_get(datetime(2026, 7, 13), datetime.now())
    pos = {}
    for d in deals:
        pid = d.position_id
        if pid not in pos:
            pos[pid] = {"sym": d.symbol, "tp": "BUY" if d.type == 0 else "SELL",
                        "lt": float(d.volume), "pnl": 0.0, "ct": ""}
        if d.entry == 1:
            pos[pid]["pnl"] = round(d.profit, 2)
            pos[pid]["ct"] = str(d.time)

    closed = [p for p in pos.values() if p["pnl"] != 0]
    closed.sort(key=lambda x: x["ct"], reverse=True)

    dn = {}
    for t in closed:
        day = datetime.fromtimestamp(int(t["ct"])).strftime("%Y-%m-%d")
        dn.setdefault(day, {"pnl": 0.0, "cnt": 0, "win": 0})
        dn[day]["pnl"] += t["pnl"]
        dn[day]["cnt"] += 1
        if t["pnl"] > 0:
            dn[day]["win"] += 1

    last10 = []
    for t in closed[:10]:
        dt = datetime.fromtimestamp(int(t["ct"]))
        last10.append({
            "time": dt.strftime("%m/%d %H:%M"),
            "type": t["tp"],
            "lot": t["lt"],
            "pnl": t["pnl"]
        })

    total = sum(t["pnl"] for t in closed)
    dh = []
    cum = 0
    for k in sorted(dn.keys()):
        v = dn[k]
        wr = round(v["win"] / v["cnt"] * 100, 1) if v["cnt"] > 0 else 0
        cum += round(v["pnl"], 2)
        dh.append({
            "date": k,
            "pnl": round(v["pnl"], 2),
            "trades": v["cnt"],
            "winRate": wr,
            "cumulative": round(cum, 2)
        })

    out = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M BJT"),
        "note": "MT5 Account History from 2026-07-13",
        "account": {
            "balance": round(acc.balance, 2),
            "equity": round(acc.equity, 2),
            "dayPnL": round(dn.get(datetime.now().strftime("%Y-%m-%d"), {}).get("pnl", 0), 2),
            "cumulativePnL": round(cum, 2),
            "positions": 0,
            "status": "RUNNING"
        },
        "lastTrades": last10,
        "tradeHistory": dh
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    mt5.shutdown()
except Exception as e:
    print(f"ERR:{e}")
    try:
        mt5.shutdown()
    except:
        pass
