"""Read last N bytes of the EA log. Try UTF-16-LE encoding."""
import os
logpath = r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\010E047102812FC0C18890992854220E\MQL5\Logs\20260723.log"
size = os.path.getsize(logpath)
chunk = 20000
with open(logpath, 'rb') as f:
    f.seek(max(0, size - chunk))
    data = f.read()

# Try different encodings
for enc in ['utf-16-le', 'utf-8', 'gbk', 'latin-1']:
    try:
        text = data.decode(enc, errors='replace')
        lines = text.split('\n')
        matching = [l for l in lines if any(kw in l for kw in ['ADX=', 'posCnt=', 'HEARTBEAT', 'BUY ', 'canBuy='])]
        if matching:
            print(f"Encoding {enc}: {len(lines)} lines, {len(matching)} matching")
            for m in matching[-8:]:
                print(f"  {m.strip()[:200]}")
            break
    except Exception as e:
        print(f"Encoding {enc}: {e}")
