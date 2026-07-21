import re, json

def calc_all_logs():
    dates = ['20260706','20260707','20260708','20260709','20260710',
             '20260713','20260716','20260717','20260720']
    results = {}
    
    for d in dates:
        try:
            with open(f'/tmp/{d}.log', 'rb') as f:
                text = f.read().decode('utf-16-le', errors='replace')
        except:
            continue
        
        deals = []
        for line in text.split('\n'):
            m = re.search(r'deal #\d+ (\w+) ([\d.]+) XAUUSD at ([\d.]+) done', line)
            if m:
                deals.append({'dir': m.group(1), 'lots': float(m.group(2)), 'price': float(m.group(3))})
        
        if not deals:
            continue
        
        buy_q = []
        sell_q = []
        total_pnl = 0.0
        wins = 0
        losses = 0
        
        for deal in deals:
            rem = deal['lots']
            if deal['dir'] == 'buy':
                while rem > 0 and sell_q:
                    s = sell_q[0]
                    match = min(rem, s['lots'])
                    pnl = (deal['price'] - s['price']) * match * 100
                    total_pnl += pnl
                    if pnl >= 0:
                        wins += 1
                    else:
                        losses += 1
                    rem -= match
                    if match >= s['lots']:
                        sell_q.pop(0)
                    else:
                        sell_q[0]['lots'] -= match
                if rem > 0:
                    buy_q.append({'lots': rem, 'price': deal['price']})
            else:
                while rem > 0 and buy_q:
                    b = buy_q[0]
                    match = min(rem, b['lots'])
                    pnl = (deal['price'] - b['price']) * match * 100
                    total_pnl += pnl
                    if pnl >= 0:
                        wins += 1
                    else:
                        losses += 1
                    rem -= match
                    if match >= b['lots']:
                        buy_q.pop(0)
                    else:
                        buy_q[0]['lots'] -= match
                if rem > 0:
                    sell_q.append({'lots': rem, 'price': deal['price']})
        
        tt = wins + losses
        wr = round(wins / tt * 100, 2) if tt > 0 else 0
        date_key = f'{d[:4]}-{d[4:6]}-{d[6:8]}'
        results[date_key] = {
            'trades': tt,
            'pnl': round(total_pnl, 2),
            'winRate': wr
        }
        print(f"{date_key}: {tt} trades, PnL=${round(total_pnl,2)}, WR={wr}%")
    
    return results

r = calc_all_logs()
print(f"\nTotal PnL: ${sum(v['pnl'] for v in r.values()):.2f}")
