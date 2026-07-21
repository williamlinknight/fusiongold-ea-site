#!/usr/bin/env python3
"""
EA Live data updater.
1. SCP log files from VPS
2. Calculate PnL via FIFO matching (local Python, proper UTF-16 LE)
3. Merge with historical data
4. Save to public/data/ea-status.json
"""
import json, os, subprocess, sys, re, datetime, tempfile, glob

NOW = datetime.datetime.now()
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE, "public", "data", "ea-status.json")
SCRIPT_DIR = os.path.join(BASE, "scripts")
TMP_DIR = "/tmp/ea-logs"

VPS = "Administrator@43.162.99.220"
VPS_LOGS = "C:/Users/Administrator/AppData/Roaming/MetaQuotes/Terminal/010E047102812FC0C18890992854220E/logs"

def scp_log(date_str):
    """Download one log file from VPS"""
    os.makedirs(TMP_DIR, exist_ok=True)
    local = os.path.join(TMP_DIR, f"{date_str}.log")
    if os.path.exists(local):
        return local  # already downloaded
    cmd = f'sshpass -p "Kingfisher@12" scp -v -o StrictHostKeyChecking=no "{VPS}:{VPS_LOGS}/{date_str}.log" {local}'
    try:
        subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if os.path.exists(local) and os.path.getsize(local) > 50:
            return local
    except: pass
    return None

def calc_pnl(log_path):
    """FIFO PnL calculation from UTF-16 LE log file"""
    with open(log_path, 'rb') as f:
        raw = f.read()
    try:
        text = raw.decode('utf-16-le')
    except:
        text = raw.decode('utf-8', errors='replace')
    
    deals = []
    for line in text.split('\n'):
        m = re.search(r'deal #\d+ (\w+) ([\d.]+) XAUUSD at ([\d.]+) done', line)
        if m:
            deals.append({'dir': m.group(1), 'lots': float(m.group(2)), 'price': float(m.group(3))})
    
    if not deals:
        return None
    
    buy_q, sell_q = [], []
    total_pnl, wins, losses = 0.0, 0, 0
    
    for d in deals:
        rem = d['lots']
        if d['dir'] == 'buy':
            while rem > 0 and sell_q:
                s = sell_q[0]
                match = min(rem, s['lots'])
                pnl = (d['price'] - s['price']) * match * 100
                total_pnl += pnl
                wins += 1 if pnl >= 0 else 0
                losses += 1 if pnl < 0 else 0
                rem -= match
                if match >= s['lots']: sell_q.pop(0)
                else: sell_q[0]['lots'] -= match
            if rem > 0: buy_q.append({'lots': rem, 'price': d['price']})
        else:
            while rem > 0 and buy_q:
                b = buy_q[0]
                match = min(rem, b['lots'])
                pnl = (d['price'] - b['price']) * match * 100
                total_pnl += pnl
                wins += 1 if pnl >= 0 else 0
                losses += 1 if pnl < 0 else 0
                rem -= match
                if match >= b['lots']: buy_q.pop(0)
                else: buy_q[0]['lots'] -= match
            if rem > 0: sell_q.append({'lots': rem, 'price': d['price']})
    
    tt = wins + losses
    wr = round(wins / tt * 100, 2) if tt > 0 else 0
    return {'trades': tt, 'pnl': round(total_pnl, 2), 'winRate': wr}

def load_existing():
    """Load existing data to preserve history"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f:
                return json.load(f)
        except: pass
    return None

def save_data(data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def main():
    # Step 1: Load existing data
    existing = load_existing()
    if existing:
        history = {h['date']: h for h in existing.get('tradeHistory', [])}
        balance = existing.get('account', {}).get('balance', 4797.07)
    else:
        history = {}
        balance = 4797.07
    
    # Step 2: Download recent logs (last 5 trading days) and calculate PnL
    dates_to_check = []
    for i in range(7):
        d = NOW - datetime.timedelta(days=i)
        dates_to_check.append(d.strftime('%Y%m%d'))
    
    new_data = False
    for d in dates_to_check:
        log_path = scp_log(d)
        if log_path:
            result = calc_pnl(log_path)
            date_key = f'{d[:4]}-{d[4:6]}-{d[6:8]}'
            if result and result['trades'] > 0:
                history[date_key] = result
                new_data = True
                print(f"{date_key}: {result['trades']} trades, PnL=${result['pnl']}, WR={result['winRate']}%")
    
    # Step 3: Build 30-day history
    output = []
    for i in range(30):
        d = (NOW - datetime.timedelta(days=29-i)).strftime('%Y-%m-%d')
        if d in history:
            output.append(history[d])
        else:
            output.append({'date': d, 'pnl': 0.0, 'trades': 0, 'winRate': 0})
    
    # Step 4: Determine today's PnL
    today_key = NOW.strftime('%Y-%m-%d')
    day_pnl = history.get(today_key, {}).get('pnl', 0.0) if today_key in history else 0.0
    
    # Step 5: Build and save
    data = {
        "updated": NOW.strftime("%Y-%m-%d %H:%M BJT"),
        "note": "Local Python FIFO (UTF-16 LE)",
        "account": {
            "balance": balance, "equity": balance,
            "dayPnL": day_pnl, "dayPnLPercent": 0.0,
            "positions": 0, "maxPositions": 4, "status": "WAITING"
        },
        "session": {"status": "WAITING", "cooldown": 0},
        "market": {"adx": 0, "adxHard": 20, "spread": 0, "maxSpread": 50},
        "signal": {"bull": 0, "bear": 0, "h4Buy": "N", "h4Sell": "N",
                   "canBuy": "N", "canSell": "N", "need": 3},
        "risk": {"aggRisk": 0, "maxRisk": 190.46,
                 "dailyLossLimit": False, "consecutiveLossPause": False},
        "lastTrades": [],
        "tradeHistory": output
    }
    
    save_data(data)
    
    total_pnl = sum(h.get('pnl', 0) for h in output)
    
    print(f"\nUPDATE_OK")
    print(f"Balance: ${balance}")
    print(f"Day PnL: ${day_pnl}")
    print(f"Total PnL (30d): ${total_pnl:.2f}")
    print(f"Trading days: {sum(1 for h in output if h['trades'] > 0)}")
    
    return 0

sys.exit(main())
