"""Find position 1819578332 and check all exit details."""
import MetaTrader5 as mt5
from datetime import datetime

mt5.initialize(path=r"C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe")

deals = mt5.history_deals_get(datetime(2026,7,13), datetime(2026,7,24))
if not deals:
    print("NO_DEALS")
    mt5.shutdown()
    exit(1)

print(f"Total deals: {len(deals)}")

# Show position 1819578332
for d in deals:
    if d.position_id == 1819578332:
        print(f"\n=== DEAL pid=1819578332 ===")
        attrs = [a for a in dir(d) if not a.startswith('_')]
        for a in attrs:
            try:
                val = getattr(d, a)
                print(f"  {a}: {val}")
            except Exception as e:
                print(f"  {a}: ERROR {e}")

# Search for deals with profit ~56.16
print("\n=== Deals with profit ~56.16 ===")
found = 0
for d in deals:
    try:
        p = d.profit
        if abs(p - 56.16) < 0.1:
            found += 1
            pid = d.position_id
            t = d.time
            entry = d.entry
            print(f"  pos={pid} profit={p} time={t} entry={entry} comment={getattr(d,'comment','')}")
    except:
        pass

if found == 0:
    print("  No deals with profit 56.16 found")
    print("\n  All deals with non-zero profit:")
    for d in deals:
        try:
            p = d.profit
            if p != 0:
                print(f"    pos={d.position_id} profit={p} time={d.time} entry={getattr(d,'entry','?')} comment={getattr(d,'comment','')}")
        except:
            pass

mt5.shutdown()
