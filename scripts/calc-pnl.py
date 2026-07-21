import re, json, os

def calc_pnl(log_path):
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
            # Buy closes shorts: PnL = (sell_price - buy_price) * lots * 100
            while rem > 0 and sell_q:
                s = sell_q[0]
                match = min(rem, s['lots'])
                pnl = (s['price'] - d['price']) * match * 100
                total_pnl += pnl
                wins += 1 if pnl >= 0 else 0
                losses += 1 if pnl < 0 else 0
                rem -= match
                if match >= s['lots']:
                    sell_q.pop(0)
                else:
                    sell_q[0]['lots'] -= match
            if rem > 0:
                buy_q.append({'lots': rem, 'price': d['price']})
        else:
            # Sell closes longs: PnL = (sell_price - buy_price) * lots * 100
            while rem > 0 and buy_q:
                b = buy_q[0]
                match = min(rem, b['lots'])
                pnl = (d['price'] - b['price']) * match * 100
                total_pnl += pnl
                wins += 1 if pnl >= 0 else 0
                losses += 1 if pnl < 0 else 0
                rem -= match
                if match >= b['lots']:
                    buy_q.pop(0)
                else:
                    buy_q[0]['lots'] -= match
            if rem > 0:
                sell_q.append({'lots': rem, 'price': d['price']})
    
    tt = wins + losses
    wr = round(wins / tt * 100, 2) if tt > 0 else 0
    return {'trades': tt, 'pnl': round(total_pnl, 2), 'winRate': wr, 'deals': len(deals)}

# Process all July logs
dates = ['20260706','20260707','20260708','20260709','20260710',
         '20260713','20260716','20260717','20260720']

results = {}
for d in dates:
    path = f'/tmp/{d}.log'
    if os.path.exists(path):
        r = calc_pnl(path)
        if r:
            date_key = f'{d[:4]}-{d[4:6]}-{d[6:8]}'
            results[date_key] = r
            print(f"{date_key}: {r['trades']} trades, PnL=${r['pnl']:>8}, WR={r['winRate']:5}%  (deals={r['deals']})")
        else:
            print(f"{d}: no trades")

total = sum(r['pnl'] for r in results.values())
print(f"\nTotal PnL (July): ${total:.2f}")
