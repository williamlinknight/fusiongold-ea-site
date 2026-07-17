#!/usr/bin/env python3
"""
update_ea_live_data.py
SSH into VPS → extract EA status → update public/data/ea-status.json
Run via cron: Mon-Fri 19:30 BJT
"""
import json, subprocess, os, sys, re
from datetime import datetime

VPS_HOST = "43.162.99.220"
VPS_USER = "Administrator"
VPS_PASS = "Kingfisher@12"

LOG_PATH = (
    r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal"
    r"\010E047102812FC0C18890992854220E\MQL5\Logs"
)
REPO_DIR = os.path.expanduser("~/Desktop/fusiongold-ea-site")
DATA_PATH = os.path.join(REPO_DIR, "public", "data", "ea-status.json")

TODAY = datetime.now().strftime("%Y%m%d")

def ssh(cmd):
    """Run a command on the VPS via sshpass."""
    full = f"sshpass -p '{VPS_PASS}' ssh -o ConnectTimeout=10 {VPS_USER}@{VPS_HOST} "
    full += f'"powershell -Command \\"{cmd}\\""'
    r = subprocess.run(full, shell=True, capture_output=True, text=True, timeout=15)
    return r.stdout, r.stderr, r.returncode

def parse_heartbeat(line):
    """Extract balance, equity, dayPnL, positions from HEARTBEAT line."""
    b = re.search(r"Balance=([\d.]+)", line)
    e = re.search(r"Equity=([\d.]+)", line)
    d = re.search(r"DayPnL=\$?(-?[\d.]+)", line)
    p = re.search(r"Positions=(\d+)", line)
    s = re.search(r"Status=(\w+)", line)
    return {
        "balance": float(b.group(1)) if b else None,
        "equity": float(e.group(1)) if e else None,
        "dayPnL": float(d.group(1)) if d else None,
        "positions": int(p.group(1)) if p else None,
        "status": s.group(1) if s else None,
    }

def parse_scan(line):
    """Extract ADX, spread, session, canBuy/canSell etc."""
    s = re.search(r"session=(\w+)", line)
    sp = re.search(r"spread=([\d.]+)/([\d.]+)", line)
    a = re.search(r"ADX=([\d.]+)", line)
    cb = re.search(r"canBuy=(\w)", line)
    cs = re.search(r"canSell=(\w)", line)
    bb = re.search(r"bull=(\d+)", line)
    be = re.search(r"bear=(\d+)", line)
    h4b = re.search(r"h4Buy=(\w)", line)
    h4s = re.search(r"h4Sell=(\w)", line)
    agg = re.search(r"aggRisk=\$?([\d.]+)", line)
    maxr = re.search(r"\$?([\d.]+) ADX=", line)  # fallback for max risk
    cooldown = re.search(r"cooldown=(\d+)", line)
    return {
        "session": s.group(1) if s else None,
        "spread": float(sp.group(1)) if sp else None,
        "maxSpread": float(sp.group(2)) if sp else None,
        "adx": float(a.group(1)) if a else None,
        "canBuy": cb.group(1) if cb else None,
        "canSell": cs.group(1) if cs else None,
        "bull": int(bb.group(1)) if bb else None,
        "bear": int(be.group(1)) if be else None,
        "h4Buy": h4b.group(1) if h4b else None,
        "h4Sell": h4s.group(1) if h4s else None,
        "aggRisk": float(agg.group(1)) if agg else None,
        "cooldown": int(cooldown.group(1)) if cooldown else None,
    }

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Updating EA live data...")
    
    # 1) Get today's log from VPS
    cmd = f"Get-Content '{LOG_PATH}\\{TODAY}.log' | Select-String 'HEARTBEAT|P&L|OrderSend.*lots|posCnt|canBuy|連'"
    out, err, code = ssh(cmd)
    if code != 0 or not out.strip():
        print("WARNING: Could not fetch VPS data, using fallback")
        return  # Keep existing data file
    
    lines = out.strip().split("\n")
    
    # 2) Extract heartbeat (last one)
    hb_lines = [l for l in lines if "HEARTBEAT" in l]
    scan_lines = [l for l in lines if "posCnt=" in l and "ADX=" in l]
    pnl_lines = [l for l in lines if "P&L" in l]
    
    # Load existing data
    data = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH) as f:
            data = json.load(f)
    
    # Update account info from last heartbeat
    if hb_lines:
        hb = parse_heartbeat(hb_lines[-1])
        if hb["balance"]:
            data["account"] = data.get("account", {})
            data["account"]["balance"] = hb["balance"]
            data["account"]["equity"] = hb["equity"]
            data["account"]["dayPnL"] = hb["dayPnL"]
            data["account"]["positions"] = hb["positions"]
            data["account"]["status"] = hb["status"]
    
    # Update market info from last scan
    if scan_lines:
        sc = parse_scan(scan_lines[-1])
        if sc["adx"]:
            data["session"] = data.get("session", {})
            data["session"]["status"] = sc["session"]
            data["session"]["cooldown"] = sc["cooldown"]
            data["market"] = data.get("market", {})
            data["market"]["adx"] = sc["adx"]
            data["market"]["spread"] = sc["spread"]
            data["market"]["maxSpread"] = sc["maxSpread"]
            data["signal"] = data.get("signal", {})
            data["signal"]["bull"] = sc["bull"]
            data["signal"]["bear"] = sc["bear"]
            data["signal"]["canBuy"] = sc["canBuy"]
            data["signal"]["canSell"] = sc["canSell"]
            data["signal"]["h4Buy"] = sc["h4Buy"]
            data["signal"]["h4Sell"] = sc["h4Sell"]
    
    # Update timestamp
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M BJT")
    data["updated"] = now_str
    
    # Write data file
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Updated: Balance=${data.get('account',{}).get('balance','?')}")
    print(f"   File: {DATA_PATH}")

if __name__ == "__main__":
    main()
