#!/usr/bin/env python3
"""One-shot probe: read VPS Expert logs 20260812..20260821 (UTF-16-LE),
dump HEARTBEAT lines to verify the 08-14 $3000 reset balance chain."""
import json, subprocess, sys, tempfile, os, time

VPS_HOST = "43.162.99.220"
VPS_USER = "Administrator"
VPS_PASS = "Kingfisher@12"
PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"
VPS_SCRIPT = r"C:\Users\Administrator\Desktop\_probe_logs.py"
SSH_OPTS = "-o StrictHostKeyChecking=no -o ConnectTimeout=30"
SSH_BASE = f"sshpass -p '{VPS_PASS}' ssh -T {SSH_OPTS} {VPS_USER}@{VPS_HOST}"

MT5_SCRIPT = r"""import json, os, glob
LOG_DIR = r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\010E047102812FC0C18890992854220E\MQL5\Logs"
out = {}
for day in ["20260812","20260813","20260814","20260815","20260817","20260818","20260819","20260820","20260821"]:
    p = os.path.join(LOG_DIR, day + ".log")
    if not os.path.exists(p):
        out[day] = "NO_FILE"
        continue
    size = os.path.getsize(p)
    lines = []
    try:
        with open(p, "rb") as f:
            f.seek(max(0, size - 60000))
            data = f.read()
        text = data.decode("utf-16-le", errors="replace")
        for ln in text.split("\n"):
            if "HEARTBEAT" in ln or "Balance" in ln and "=" in ln:
                lines.append(ln.strip())
    except Exception as e:
        out[day] = f"ERR:{e}"
        continue
    out[day] = lines[-12:] if lines else "NO_HEARTBEAT"
print(json.dumps(out, ensure_ascii=False))
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
    try:
        start = out.index("{")
        data = json.loads(out[start:])
    except ValueError as e:
        print("JSON parse error:", e, out[:800]); sys.exit(1)
    for day in sorted(data):
        print(f"=== {day} ===")
        v = data[day]
        if isinstance(v, list):
            for ln in v:
                print("   ", ln[:180])
        else:
            print("   ", v)

if __name__ == "__main__":
    main()
