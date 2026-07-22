import MetaTrader5 as mt5
import json
from datetime import datetime, timedelta

# Initialize MT5
if not mt5.initialize(path="C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe"):
    print(f"MT5 init failed: {mt5.last_error()}")
    exit(1)

# Get account info
acc = mt5.account_info()
if acc is None:
    print("No account info")
    mt5.shutdown()
    exit(1)

print(f"Account: {acc.login} Balance: ${acc.balance:.2f} Equity: ${acc.equity:.2f}")

# Get trade history from July 13 onward
from_date = datetime(2026, 7, 13)
to_date = datetime.now()

# Get history deals
deals = mt5.history_deals_get(from_date, to_date)
if deals is None:
    print(f"No deals found: {mt5.last_error()}")
    mt5.shutdown()
    exit(1)

# Group deals by position ID to calculate per-trade PnL
positions = {}
for deal in deals:
    pos_id = deal.position_id
    if pos_id not in positions:
        positions[pos_id] = {
            "position_id": pos_id,
            "symbol": deal.symbol,
            "type": "BUY" if deal.type == 0 else ("SELL" if deal.type == 1 else "OTHER"),
            "volume": deal.volume,
            "open_time": None,
            "close_time": None,
            "open_price": None,
            "close_price": None,
            "profit": 0.0,
            "commission": 0.0,
            "swap": 0.0,
            "ticket_open": None,
            "ticket_close": None,
        }
    
    if deal.entry == 0:  # Entry (open)
        positions[pos_id]["open_time"] = str(deal.time)
        positions[pos_id]["open_price"] = deal.price
        positions[pos_id]["ticket_open"] = deal.ticket
    elif deal.entry == 1:  # Exit (close)
        positions[pos_id]["close_time"] = str(deal.time)
        positions[pos_id]["close_price"] = deal.price
        positions[pos_id]["profit"] = deal.profit
        positions[pos_id]["commission"] = deal.commission
        positions[pos_id]["swap"] = deal.swap
        positions[pos_id]["ticket_close"] = deal.ticket

# Filter to closed trades (have profit)
closed_trades = [p for p in positions.values() if p["profit"] != 0.0]
# Sort by close time (newest first)
closed_trades.sort(key=lambda x: x["close_time"] or "", reverse=True)

trades_out = []
for t in closed_trades[:20]:
    trades_out.append({
        "time": t["close_time"][:19] if t["close_time"] else "",
        "symbol": t["symbol"],
        "type": t["type"],
        "lots": t["volume"] / 100,
        "open": t["open_price"],
        "close": t["close_price"],
        "profit": round(t["profit"], 2),
        "commission": round(t["commission"], 2),
        "swap": round(t["swap"], 2),
        "netPnL": round(t["profit"], 2),
    })

# Daily PnL aggregation
daily = {}
for t in closed_trades:
    day = t["close_time"][:10] if t["close_time"] else "unknown"
    if day not in daily:
        daily[day] = {"pnl": 0, "trades": 0, "wins": 0}
    daily[day]["pnl"] += t["profit"]
    daily[day]["trades"] += 1
    if t["profit"] > 0:
        daily[day]["wins"] += 1

for d in sorted(daily.keys()):
    dd = daily[d]
    wr = round(dd["wins"] / dd["trades"] * 100, 1) if dd["trades"] > 0 else 0
    print(f"  {d}: {dd['trades']} trades PnL=${dd['pnl']:.2f} WR={wr}%")

total_pnl = sum(t['profit'] for t in closed_trades)
print(f"\nTotal closed: {len(closed_trades)}")
print(f"Total PnL (Jul 13+): ${total_pnl:.2f}")

print("\n=== LAST 10 TRADES ===")
for t in trades_out[:10]:
    print(f"  {t['time']} {t['type']} {t['lots']}lot {t['symbol']} @{t['open']}->{t['close']} PnL=${t['profit']:.2f}")

mt5.shutdown()
