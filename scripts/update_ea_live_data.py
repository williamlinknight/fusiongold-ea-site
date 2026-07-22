#!/usr/bin/env python3
"""
update_ea_live_data.py — MT5 Account History 版
SSH into VPS → run Python script using MetaTrader5 API → update public/data/ea-status.json
Run via cron: Mon-Fri 19:30 BJT + daily 07:20 BJT
"""
import json, subprocess, os, sys
from datetime import datetime

VPS_HOST = "43.162.99.220"
VPS_USER = "Administrator"
VPS_PASS = "Kingfisher@12"
REPO_DIR = os.path.expanduser("~/Desktop/fusiongold-ea-site")
DATA_PATH = os.path.join(REPO_DIR, "public", "data", "ea-status.json")
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"

# Python script that runs ON the VPS via MT5 API
MT5_SCRIPT = r"""
import MetaTrader5 as mt5, json, sys
from datetime import datetime, timezone

try:
    mt5.initialize(path="C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe")
    acc = mt5.account_info()
    if not acc:
        sys.exit(1)

    # Get ALL deals from July 13 onward
    deals = mt5.history_deals_get(datetime(2026, 7, 13), datetime.now())
    pos = {}
    for d in deals:
        pid = d.position_id
        if pid not in pos:
            pos[pid] = {
                "sym": d.symbol, "tp": "BUY" if d.type == 0 else "SELL",
                "lt": float(d.volume), "pnl": 0.0, "ct": ""
            }
        if d.entry == 1:
            pos[pid]["pnl"] = round(d.profit, 2)
            pos[pid]["ct"] = str(d.time)

    # Closed trades only
    closed = [p for p in pos.values() if p["pnl"] != 0]
    closed.sort(key=lambda x: x["ct"], reverse=True)

    # Daily aggregation
    dn = {}
    for t in closed:
        day = datetime.fromtimestamp(int(t["ct"])).strftime("%Y-%m-%d")
        dn.setdefault(day, {"pnl": 0.0, "cnt": 0, "win": 0})
        dn[day]["pnl"] += t["pnl"]
        dn[day]["cnt"] += 1
        if t["pnl"] > 0:
            dn[day]["win"] += 1

    # Last 10 trades
    last10 = []
    for t in closed[:10]:
        dt = datetime.fromtimestamp(int(t["ct"]))
        last10.append({
            "time": dt.strftime("%m/%d %H:%M"),
            "type": t["tp"], "lots": t["lt"], "pnl": t["pnl"]
        })

    # Build tradeHistory with cumulative
    total = sum(t["pnl"] for t in closed)
    dh, cum = [], 0
    for k in sorted(dn.keys()):
        v = dn[k]
        wr = round(v["win"] / v["cnt"] * 100, 1) if v["cnt"] > 0 else 0
        cum += round(v["pnl"], 2)
        dh.append({
            "date": k, "pnl": round(v["pnl"], 2),
            "trades": v["cnt"], "winRate": wr,
            "cumulative": round(cum, 2)
        })

    # Current day PnL
    today_key = datetime.now().strftime("%Y-%m-%d")
    day_pnl = round(dn.get(today_key, {}).get("pnl", 0), 2)

    # Try to get current session/market status from last heartbeat in log
    session_status = "WAITING"

    out = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M BJT"),
        "note": "MT5 Account History from 2026-07-13",
        "account": {
            "balance": round(acc.balance, 2),
            "equity": round(acc.equity, 2),
            "dayPnL": day_pnl,
            "dayPnLPercent": round(day_pnl / (acc.balance - day_pnl) * 100, 2) if (acc.balance - day_pnl) > 0 else 0,
            "cumulativePnL": round(cum, 2),
            "positions": 0,
            "status": "RUNNING"
        },
        "session": {"status": session_status, "cooldown": 0},
        "market": {"adx": 0, "adxHard": 20, "spread": 0, "maxSpread": 50},
        "signal": {"bull": 0, "bear": 0, "h4Buy": "N", "h4Sell": "N", "canBuy": "N", "canSell": "N", "need": 3},
        "risk": {"aggRisk": 0, "maxRisk": round(acc.balance * 0.04, 2), "dailyLossLimit": False, "consecutiveLossPause": False},
        "lastTrades": last10,
        "tradeHistory": dh
    }
    print(json.dumps(out, ensure_ascii=False))
    mt5.shutdown()
except Exception as e:
    print(f"ERR:{e}")
    try: mt5.shutdown()
    except: pass
"""


def ssh_python(python_code: str) -> str:
    """Run Python code on the VPS via cmd, return stdout."""
    # Write script to VPS as a temp file, then run it
    script_path = r"C:\Users\Administrator\Desktop\_ea_updater.py"

    # Escape for shell: replace single quotes, newlines, etc.
    # Using echo with cmd /V for delayed expansion to handle special chars
    # Build command to write file then run it
    cmd_parts = [
        f'cmd /c echo import MetaTrader5 as m,json,datetime > {script_path}',
        f'echo m.initialize(path=r"C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe") >> {script_path}',
        f'echo a=m.account_info() >> {script_path}',
        f'echo g=m.history_deals_get(datetime.datetime(2026,7,13),datetime.datetime.now()) >> {script_path}',
        # ... build each line
    ]
    # Too complex. Better: write the script via PowerShell as base64 then run it.

    # Alternative: write with powershell out-file
    import base64
    b64 = base64.b64encode(python_code.encode("utf-16-le")).decode()
    pwsh_cmd = (
        f"powershell -Command \""
        f"$d=[System.Convert]::FromBase64String('{b64}'); "
        f"[System.Text.Encoding]::Unicode.GetString($d) | "
        f"Out-File -FilePath {script_path} -Encoding utf8 -Force; "
        f"&'{PYTHON}' {script_path}"
        f"\""
    )
    full_cmd = f"sshpass -p '{VPS_PASS}' ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=30 {VPS_USER}@{VPS_HOST} {pwsh_cmd}"
    r = subprocess.run(full_cmd, shell=True, capture_output=True, timeout=120)
    out = r.stdout.decode("utf-8", errors="replace")
    err = r.stderr.decode("utf-8", errors="replace")
    if r.returncode != 0:
        print(f"SSH stderr: {err[:500]}")
    return out.strip()


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Updating EA live data (MT5 API)...")

    result = ssh_python(MT5_SCRIPT)
    if not result or result.startswith("ERR"):
        print(f"❌ MT5 API failed: {result}")
        # Fallback to log-based update
        print("⚠️  Falling back to log-based update...")
        _fallback_update()
        return

    # Parse JSON output from VPS
    try:
        # Find the JSON in the output (might have debug info before it)
        json_start = result.index("{")
        new_data = json.loads(result[json_start:])
    except (ValueError, json.JSONDecodeError) as e:
        print(f"❌ JSON parse error: {e}")
        print(f"Raw output: {result[:500]}")
        return

    # Merge with existing data (preserve fields MT5 API doesn't provide)
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH) as f:
            existing = json.load(f)
        # Merge session/market/signal/risk from existing data
        for section in ["session", "market", "signal", "risk"]:
            if section in existing and section in new_data:
                new_data[section] = {**existing[section], **new_data[section]}

    # Also try to get live session/market data from log for the heartbeat fields
    try:
        _merge_heartbeat_data(new_data)
    except Exception:
        pass

    # Write updated data
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w") as f:
        json.dump(new_data, f, indent=2, ensure_ascii=False)

    acct = new_data.get("account", {})
    print(f"✅ Updated: Balance=${acct.get('balance','?')} PnL=${acct.get('dayPnL','?')}")
    print(f"   Last {len(new_data.get('lastTrades',[]))} trades | {len(new_data.get('tradeHistory',[]))} trading days")
    print(f"   File: {DATA_PATH}")


def _merge_heartbeat_data(data):
    """Merge live session/market data from today's EA log (for ADX/spread/status)."""
    today_str = datetime.now().strftime("%Y%m%d")
    log_path = (
        r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal"
        r"\010E047102812FC0C18890992854220E\MQL5\Logs"
    )
    cmd = (
        f"powershell -Command \"Get-Content '{log_path}\\{today_str}.log' "
        f"| Select-String 'HEARTBEAT|posCnt.*ADX' -Tail 2 2>$null"
        f"\""
    )
    full = f"sshpass -p '{VPS_PASS}' ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=30 {VPS_USER}@{VPS_HOST} {cmd}"
    r = subprocess.run(full, shell=True, capture_output=True, timeout=15)
    out = r.stdout.decode("utf-8", errors="replace")
    if not out.strip():
        return

    import re
    for line in out.split("\n"):
        if "HEARTBEAT" in line:
            s = re.search(r"Status=(\w+)", line)
            if s and s.group(1) in ("RUNNING", "WAITING", "HALTED"):
                data["account"]["status"] = s.group(1)
            p = re.search(r"Positions=(\d+)", line)
            if p:
                data["account"]["positions"] = int(p.group(1))
        if "ADX=" in line:
            a = re.search(r"ADX=([\d.]+)", line)
            if a:
                data["market"]["adx"] = float(a.group(1))
            sp = re.search(r"spread=([\d.]+)/([\d.]+)", line)
            if sp:
                data["market"]["spread"] = float(sp.group(1))
                data["market"]["maxSpread"] = float(sp.group(2))
            ss = re.search(r"session=(\w+)", line)
            if ss:
                data["session"]["status"] = ss.group(1)
            cd = re.search(r"cooldown=(\d+)", line)
            if cd:
                data["session"]["cooldown"] = int(cd.group(1))


def _fallback_update():
    """Old log-based fallback if MT5 API fails."""
    import re
    today_str = datetime.now().strftime("%Y%m%d")
    log_path = (
        r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal"
        r"\010E047102812FC0C18890992854220E\MQL5\Logs"
    )
    cmd = (
        f"powershell -Command \"Get-Content '{log_path}\\{today_str}.log' "
        f"| Select-String 'HEARTBEAT' -Tail 1 2>$null\""
    )
    full = f"sshpass -p '{VPS_PASS}' ssh -T -o StrictHostKeyChecking=no -o ConnectTimeout=30 {VPS_USER}@{VPS_HOST} {cmd}"
    r = subprocess.run(full, shell=True, capture_output=True, timeout=15)
    out = r.stdout.decode("utf-8", errors="replace")
    if not out.strip():
        print("Fallback also failed — keeping existing data")
        return

    data = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH) as f:
            data = json.load(f)

    line = out.strip().split("\n")[-1]
    b = re.search(r"Balance=([\d.]+)", line)
    e = re.search(r"Equity=([\d.]+)", line)
    d = re.search(r"DayPnL=\$?(-?[\d.]+)", line)
    if b and e and d:
        data["account"] = data.get("account", {})
        data["account"]["balance"] = float(b.group(1))
        data["account"]["equity"] = float(e.group(1))
        data["account"]["dayPnL"] = abs(float(d.group(1)))  # fallback can't tell direction
        data["account"]["status"] = "RUNNING"
        data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M BJT")

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"⚠️ Fallback updated: Balance=${data.get('account',{}).get('balance','?')}")


if __name__ == "__main__":
    main()
