#!/usr/bin/env python3
"""
day_deals.py — Dump deal-level MT5 Account History for a given BJT date.
SCP to VPS → run via MT5 Python API → print JSON rows (entry + exit deals).

Usage: python3 scripts/day_deals.py 2026-08-04
"""
import json, subprocess, sys, tempfile, os
from datetime import datetime

VPS_HOST = "43.162.99.220"
VPS_USER = "Administrator"
VPS_PASS = "Kingfisher@12"
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
VPS_SCRIPT = r"C:\Users\Administrator\Desktop\_day_deals.py"
SSH_OPTS = "-o StrictHostKeyChecking=no -o ConnectTimeout=30"
SSH_BASE = f"sshpass -p '{VPS_PASS}' ssh -T {SSH_OPTS} {VPS_USER}@{VPS_HOST}"

TARGET_DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")

# Runs ON the VPS. Query a wide range, filter by BJT date.
MT5_SCRIPT = r"""import MetaTrader5 as mt5, json, sys
from datetime import datetime, timezone, timedelta
SERVER_UTC_OFFSET = 3  # IC Markets summer UTC+3
BJT_UTC_OFFSET = 8
TZ_FIX = timedelta(hours=BJT_UTC_OFFSET - SERVER_UTC_OFFSET)  # +5h
TARGET = sys.argv[1] if len(sys.argv) > 1 else "2026-08-04"

def _to_bjt(ts_int):
    return datetime.fromtimestamp(int(ts_int), tz=timezone.utc) + TZ_FIX

try:
    mt5.initialize(path="C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe")
    acc = mt5.account_info()
    if not acc:
        sys.exit(1)
    # Wide window: day before through day after target (server time)
    from_ = datetime(2026, 1, 1)
    to = datetime(2027, 1, 1)
    deals = mt5.history_deals_get(from_, to) or []
    rows = []
    for d in deals:
        dt = _to_bjt(d.time)
        if dt.strftime("%Y-%m-%d") != TARGET:
            continue
        rows.append({
            "time": dt.strftime("%m/%d %H:%M"),
            "pid": d.position_id,
            "type": d.type,        # 0=Buy 1=Sell 2=CloseBuy 3=CloseSell
            "entry": d.entry,      # 0=open 1=close 2=reverse
            "volume": float(d.volume),
            "price": round(d.price, 2),
            "profit": round(d.profit, 2),
            "commission": round(d.commission, 2),
            "swap": round(d.swap, 2),
            "comment": str(d.comment),
            "reason": d.reason      # 1=SL 2=TP 3=SO 4=Client
        })
    rows.sort(key=lambda r: (r["pid"], r["time"]))
    print(json.dumps(rows, ensure_ascii=False))
    mt5.shutdown()
except Exception as e:
    print(f"ERR:{e}")
    try: mt5.shutdown()
    except: pass
"""


def _decode_stderr(stderr_bytes):
    for enc in ["gbk", "gb18030", "utf-8"]:
        try:
            return stderr_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return stderr_bytes.decode("utf-8", errors="replace")


def main():
    # 1. SCP the script (always overwrite so edits take effect)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(MT5_SCRIPT)
        tmp_path = f.name
    scp_target = VPS_SCRIPT.replace("\\", "/")
    scp_cmd = f"sshpass -p '{VPS_PASS}' scp {SSH_OPTS} {tmp_path} {VPS_USER}@{VPS_HOST}:{scp_target}"
    r = subprocess.run(scp_cmd, shell=True, capture_output=True, timeout=60)
    os.unlink(tmp_path)
    if r.returncode != 0:
        print("SCP failed:", _decode_stderr(r.stderr)[:300])
        sys.exit(1)

    # 2. Run on VPS with target date — retry with cooldown (VPS throttles rapid SSH)
    # Use forward slashes + single-quote the ENTIRE remote command (skill pitfall #1)
    py_fwd = PYTHON.replace("\\", "/")
    script_fwd = VPS_SCRIPT.replace("\\", "/")
    remote_cmd = f'"{py_fwd}" {script_fwd} {TARGET_DATE}'
    full = f"{SSH_BASE} '{remote_cmd}'"
    import time as _time
    r = None
    for attempt in range(4):
        r = subprocess.run(full, shell=True, capture_output=True, timeout=180)
        if r.returncode == 0 and r.stdout.strip():
            break
        if attempt < 3:
            _time.sleep(30 + attempt * 20)
    out = r.stdout.decode("utf-8", errors="replace").strip()
    if r.returncode != 0 or not out:
        print("SSH stderr:", _decode_stderr(r.stderr)[:500])
        sys.exit(1)
    if out.startswith("ERR"):
        print(out)
        sys.exit(1)
    try:
        start = out.index("[")
        data = json.loads(out[start:])
    except ValueError as e:
        print("JSON parse error:", e, out[:500])
        sys.exit(1)
    print(json.dumps(data, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
