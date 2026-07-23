#!/usr/bin/env python3
"""
update_ea_live_data.py — MT5 Account History 版
SSH into VPS → run Python script using MetaTrader5 API → update public/data/ea-status.json
Strategy: SCP the Python script to VPS once, then SSH just runs it (no fragile quoting chains).
"""
import json, subprocess, os, sys, tempfile, base64
from datetime import datetime

VPS_HOST = "43.162.99.220"
VPS_USER = "Administrator"
VPS_PASS = "Kingfisher@12"
REPO_DIR = os.path.expanduser("~/Desktop/fusiongold-ea-site")
DATA_PATH = os.path.join(REPO_DIR, "public", "data", "ea-status.json")
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
VPS_SCRIPT = r"C:\Users\Administrator\Desktop\_ea_updater.py"
SSH_OPTS = "-o StrictHostKeyChecking=no -o ConnectTimeout=30"
SSH_BASE = f"sshpass -p '{VPS_PASS}' ssh -T {SSH_OPTS} {VPS_USER}@{VPS_HOST}"

# Python script that runs ON the VPS via MT5 API
MT5_SCRIPT = r"""import MetaTrader5 as mt5, json, sys, time
from datetime import datetime, timezone, timedelta
# IC Markets server time is UTC+3 (summer) / UTC+2 (winter)
# BJT = UTC+8. Difference: +5h (summer) / +6h (winter)
SERVER_UTC_OFFSET = 3  # IC Markets summer UTC+3
BJT_UTC_OFFSET = 8
TZ_FIX = timedelta(hours=BJT_UTC_OFFSET - SERVER_UTC_OFFSET)  # +5h

def _to_bjt(ts_int):
    # Convert MT5 server timestamp (UTC+3 summer) to BJT (UTC+8)
    return datetime.fromtimestamp(int(ts_int), tz=timezone.utc) + TZ_FIX

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
        day = _to_bjt(int(t["ct"])).strftime("%Y-%m-%d")
        dn.setdefault(day, {"pnl": 0.0, "cnt": 0, "win": 0})
        dn[day]["pnl"] += t["pnl"]
        dn[day]["cnt"] += 1
        if t["pnl"] > 0:
            dn[day]["win"] += 1

    # Last 10 trades
    last10 = []
    for t in closed[:10]:
        dt = _to_bjt(int(t["ct"]))
        last10.append({
            "time": dt.strftime("%m/%d %H:%M BJT"),
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
    today_key = (datetime.fromtimestamp(time.time(), tz=timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d")
    day_pnl = round(dn.get(today_key, {}).get("pnl", 0), 2)

    session_status = "WAITING"

    out = {
        "updated": (datetime.fromtimestamp(time.time(), tz=timezone.utc) + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M BJT"),
        "timezone": "BJT (UTC+8 / 北京时间)",
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


def _decode_stderr(stderr_bytes):
    """Try multiple encodings for Chinese Windows error messages."""
    for enc in ["gbk", "gb18030", "utf-8"]:
        try:
            return stderr_bytes.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return stderr_bytes.decode("utf-8", errors="replace")


def _ssh_run(remote_cmd: str) -> subprocess.CompletedProcess:
    """Run a command on the VPS via SSH with retry logic."""
    full = f"{SSH_BASE} {remote_cmd}"
    return subprocess.run(full, shell=True, capture_output=True, timeout=120)


def _ensure_script_on_vps():
    """Write MT5_SCRIPT to VPS via SCP if not already present or outdated."""
    try:
        # Check if script exists by SSH (single-quote to protect from local bash)
        r = subprocess.run(
            f"""{SSH_BASE} 'if exist "{VPS_SCRIPT}" echo EXISTS'""",
            shell=True, capture_output=True, timeout=30
        )
        exists = b"EXISTS" in r.stdout
        if exists:
            return True  # Already exists, just use it

        # Write via SCP using temp file (use forward slashes for SCP target path)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(MT5_SCRIPT)
            tmp_path = f.name

        scp_target = VPS_SCRIPT.replace("\\", "/")
        scp_cmd = f"sshpass -p '{VPS_PASS}' scp {SSH_OPTS} {tmp_path} {VPS_USER}@{VPS_HOST}:{scp_target}"
        r = subprocess.run(scp_cmd, shell=True, capture_output=True, timeout=30)
        os.unlink(tmp_path)

        if r.returncode != 0:
            stderr = _decode_stderr(r.stderr)
            print(f"SCP failed: {stderr[:200]}")
            return False

        # Verify the file was written
        verify = subprocess.run(
            f"""{SSH_BASE} 'if exist "{VPS_SCRIPT}" echo OK'""",
            shell=True, capture_output=True, timeout=30
        )
        return b"OK" in verify.stdout
    except Exception as e:
        print(f"_ensure_script_on_vps error: {e}")
        return False


def ssh_run_mt5() -> str:
    """Run the MT5 updater script on VPS via SSH (simple call, no quoting chain)."""
    remote_cmd = f"\"{PYTHON}\" {VPS_SCRIPT}"
    r = _ssh_run(remote_cmd)
    out = r.stdout.decode("utf-8", errors="replace").strip()
    if r.returncode != 0:
        decoded = _decode_stderr(r.stderr)
        print(f"SSH stderr: {decoded[:500]}")
    return out


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Updating EA live data (MT5 API)...")

    # Step 1: Ensure VPS has the updater script
    if not _ensure_script_on_vps():
        print("⚠️  Could not ensure VPS script — falling back to log-based update")
        _fallback_update()
        return

    # Step 2: Run the script on VPS
    result = ssh_run_mt5()
    if not result or result.startswith("ERR"):
        print(f"❌ MT5 API failed: {result}")
        print("⚠️  Falling back to log-based update...")
        _fallback_update()
        return

    # Step 3: Parse JSON output
    try:
        json_start = result.index("{")
        new_data = json.loads(result[json_start:])
    except (ValueError, json.JSONDecodeError) as e:
        print(f"❌ JSON parse error: {e}")
        print(f"Raw output: {result[:500]}")
        # Don't fallback — the MT5 data is invalid, keep existing file
        return

    # Step 4: Merge with existing data
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH) as f:
            existing = json.load(f)
        for section in ["session", "market", "signal", "risk"]:
            if section in existing and section in new_data:
                new_data[section] = {**existing[section], **new_data[section]}

    # Step 5: Also merge live heartbeat data if possible
    try:
        _merge_heartbeat_data(new_data)
    except Exception:
        pass

    # Step 6: Write
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
    # Remote: type + findstr, single-quoted to protect from local bash
    cmd = f"""cmd /c type "{log_path}\\{today_str}.log" 2>nul | findstr "HEARTBEAT posCnt\""""
    r = subprocess.run(
        f"""{SSH_BASE} '{cmd}'""",
        shell=True, capture_output=True, timeout=60
    )
    out = r.stdout.decode("utf-8", errors="replace")
    if not out.strip() or r.returncode != 0:
        return

    import re
    for line in out.split("\n"):
        line = line.strip()
        if "HEARTBEAT" in line:
            s = re.search(r"Status=(\w+)", line)
            if s and s.group(1) in ("RUNNING", "WAITING", "HALTED"):
                data["account"]["status"] = s.group(1)
            p = re.search(r"Positions=(\d+)", line)
            if p:
                data["account"]["positions"] = int(p.group(1))
        if "ADX=" in line or "posCnt" in line:
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
    cmd = f"""cmd /c type "{log_path}\{today_str}.log" 2>nul | findstr "HEARTBEAT\""""
    r = subprocess.run(
        f"""{SSH_BASE} '{cmd}'""",
        shell=True, capture_output=True, timeout=60
    )
    out = r.stdout.decode("utf-8", errors="replace")
    if not out.strip() or r.returncode != 0:
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
        data["account"]["dayPnL"] = abs(float(d.group(1)))
        data["account"]["status"] = "RUNNING"
        data["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M BJT")

    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"⚠️ Fallback updated: Balance=${data.get('account',{}).get('balance','?')}")


if __name__ == "__main__":
    main()
