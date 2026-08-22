#!/usr/bin/env python3
"""Probe: dump ALL balance/credit operations (type 2/3) + daily balance chain from MT5."""
import json, subprocess, sys, tempfile, os, time

VPS_HOST = "43.162.99.220"
VPS_USER = "Administrator"
VPS_PASS = "Kingfisher@12"
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
VPS_SCRIPT = r"C:\Users\Administrator\Desktop\_probe_balance.py"
SSH_OPTS = "-o StrictHostKeyChecking=no -o ConnectTimeout=30"
SSH_BASE = f"sshpass -p '{VPS_PASS}' ssh -T {SSH_OPTS} {VPS_USER}@{VPS_HOST}"

MT5_SCRIPT = r"""import MetaTrader5 as mt5, json, sys
from datetime import datetime, timezone, timedelta
SERVER_UTC_OFFSET = 3
BJT_UTC_OFFSET = 8
TZ_FIX = timedelta(hours=BJT_UTC_OFFSET - SERVER_UTC_OFFSET)

def _to_bjt(ts_int):
    return datetime.fromtimestamp(int(ts_int), tz=timezone.utc) + TZ_FIX

try:
    mt5.initialize(path="C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe")
    acc = mt5.account_info()
    deals = mt5.history_deals_get(datetime(2026, 7, 1), datetime(2027, 1, 1)) or []
    rows = []
    for d in deals:
        if d.type in (2, 3):  # balance / credit operations
            rows.append({
                "time": _to_bjt(d.time).strftime("%m/%d %H:%M"),
                "type": d.type,
                "profit": round(d.profit, 2),
                "comment": str(d.comment)
            })
    rows.sort(key=lambda r: r["time"])
    print(json.dumps({
        "balance": round(acc.balance, 2),
        "ops": rows
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
        print("JSON parse error:", e, out[:800]); sys.exit(1)
    print("CURRENT BALANCE:", data["balance"])
    print("BALANCE OPS (type 2=balance, 3=credit):")
    for o in data["ops"]:
        print(f"  {o['time']} type={o['type']} profit={o['profit']:+.2f} comment={o['comment']}")

if __name__ == "__main__":
    main()
