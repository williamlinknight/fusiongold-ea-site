#!/usr/bin/env python3
"""One-shot probe: dump ALL deals 08-10..now grouped by BJT day, plus balance chain.
SCP once, SSH once.  Used to verify the 08-14 $3000 baseline."""
import json, subprocess, sys, tempfile, os, time
from datetime import datetime

VPS_HOST = "43.162.99.220"
VPS_USER = "Administrator"
VPS_PASS = "Kingfisher@12"
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
VPS_SCRIPT = r"C:\Users\Administrator\Desktop\_probe_days.py"
SSH_OPTS = "-o StrictHostKeyChecking=no -o ConnectTimeout=30"
SSH_BASE = f"sshpass -p '{VPS_PASS}' ssh -T {SSH_OPTS} {VPS_USER}@{VPS_HOST}"

MT5_SCRIPT = r"""import MetaTrader5 as mt5, json, sys
from datetime import datetime, timezone, timedelta
SERVER_UTC_OFFSET = 3
BJT_UTC_OFFSET = 8
TZ_FIX = timedelta(hours=BJT_UTC_OFFSET - SERVER_UTC_OFFSET)  # +5h

def _to_bjt(ts_int):
    return datetime.fromtimestamp(int(ts_int), tz=timezone.utc) + TZ_FIX

try:
    mt5.initialize(path="C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe")
    acc = mt5.account_info()
    if not acc:
        sys.exit(1)
    deals = mt5.history_deals_get(datetime(2026, 8, 1), datetime(2027, 1, 1)) or []
    rows = []
    for d in deals:
        dt = _to_bjt(d.time)
        rows.append({
            "time": dt.strftime("%m/%d %H:%M"),
            "pid": d.position_id,
            "type": d.type,
            "entry": d.entry,
            "volume": float(d.volume),
            "profit": round(d.profit, 2),
            "commission": round(d.commission, 2),
            "swap": round(d.swap, 2),
            "comment": str(d.comment),
            "reason": d.reason
        })
    rows.sort(key=lambda r: (r["pid"], r["time"]))
    print(json.dumps({
        "balance": round(acc.balance, 2),
        "equity": round(acc.equity, 2),
        "rows": rows
    }, ensure_ascii=False))
    mt5.shutdown()
except Exception as e:
    print(f"ERR:{e}")
    try: mt5.shutdown()
    except: pass
"""

def _decode_stderr(b):
    for enc in ["gbk", "gb18030", "utf-8"]:
        try:
            return b.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return b.decode("utf-8", errors="replace")

def main():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(MT5_SCRIPT)
        tmp_path = f.name
    scp_target = VPS_SCRIPT.replace("\\", "/")
    r = subprocess.run(
        f"sshpass -p '{VPS_PASS}' scp {SSH_OPTS} {tmp_path} {VPS_USER}@{VPS_HOST}:{scp_target}",
        shell=True, capture_output=True, timeout=60
    )
    os.unlink(tmp_path)
    if r.returncode != 0:
        print("SCP failed:", _decode_stderr(r.stderr)[:300]); sys.exit(1)

    py_fwd = PYTHON.replace("\\", "/")
    script_fwd = VPS_SCRIPT.replace("\\", "/")
    remote_cmd = f'"{py_fwd}" {script_fwd}'
    full = f"{SSH_BASE} '{remote_cmd}'"
    rr = None
    for attempt in range(4):
        rr = subprocess.run(full, shell=True, capture_output=True, timeout=180)
        if rr.returncode == 0 and rr.stdout.strip():
            break
        if attempt < 3:
            time.sleep(30 + attempt * 20)
    out = rr.stdout.decode("utf-8", errors="replace").strip()
    if rr.returncode != 0 or not out:
        print("SSH stderr:", _decode_stderr(rr.stderr)[:500]); sys.exit(1)
    if out.startswith("ERR"):
        print(out); sys.exit(1)
    try:
        start = out.index("{")
        data = json.loads(out[start:])
    except ValueError as e:
        print("JSON parse error:", e, out[:500]); sys.exit(1)

    print(f"BALANCE: {data['balance']}  EQUITY: {data['equity']}")
    # Group close deals (entry==1) by day, track position pnl
    pos = {}
    for rw in data["rows"]:
        pid = rw["pid"]
        if pid not in pos:
            pos[pid] = {"sym": "", "open": "", "close": "", "pnl": 0.0}
        if rw["entry"] == 0:
            pos[pid]["open"] = rw["time"]
        if rw["entry"] == 1:
            pos[pid]["close"] = rw["time"]
            pos[pid]["pnl"] = rw["profit"]
    from collections import defaultdict
    days = defaultdict(lambda: {"pnl": 0.0, "n": 0})
    for pid, p in pos.items():
        if p["close"] and p["pnl"] != 0:
            day = "2026-" + p["close"].split()[0].replace("/", "-")
            days[day]["pnl"] += p["pnl"]
            days[day]["n"] += 1
    print("\nDAY TOTALS (closed positions, BJT):")
    for d in sorted(days):
        print(f"  {d}: n={days[d]['n']:3d}  pnl={days[d]['pnl']:+.2f}")
    print(f"\nTOTAL PnL (08-01..now): {sum(v['pnl'] for v in days.values()):+.2f}")

if __name__ == "__main__":
    main()
