#!/usr/bin/env python3
"""Wait for the latest Deploy to GitHub Pages run to finish, then verify live data JSON."""
import json
import subprocess
import time
import urllib.request

REPO = "williamlinknight/fusiongold-ea-site"
RUN_ID = "30642044855"


def get_token():
    url = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True, text=True
    ).stdout.strip()
    if "@" in url and "://" in url:
        auth = url.split("://")[1].split("@")[0]
        if ":" in auth:
            return auth.split(":", 1)[1]
    return None


def api(path):
    token = get_token()
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hermes-cron",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=30) as resp:
        return json.load(resp)


def main():
    # Poll run status
    deadline = time.time() + 300
    status = None
    conclusion = None
    while time.time() < deadline:
        run = api(f"/actions/runs/{RUN_ID}")
        status = run.get("status")
        conclusion = run.get("conclusion")
        print(f"[{time.strftime('%H:%M:%S')}] status={status} conclusion={conclusion}", flush=True)
        if status == "completed":
            break
        time.sleep(15)

    if status != "completed":
        print("TIMEOUT waiting for run to complete")
        return 1
    if conclusion != "success":
        print(f"DEPLOY FAILED: {conclusion}")
        return 1
    print("DEPLOY SUCCESS")

    # Verify live site data JSON
    time.sleep(10)
    req = urllib.request.Request(
        "https://williamlinknight.github.io/fusiongold-ea-site/data/ea-status.json",
        headers={"User-Agent": "hermes-cron"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=30) as resp:
        live = json.load(resp)
    print(f"Live updated: {live.get('updated')}")
    print(f"Live balance: {live.get('account', {}).get('balance')}")
    print(f"Live dayPnL: {live.get('account', {}).get('dayPnL')}")
    print(f"Live cumulativePnL: {live.get('account', {}).get('cumulativePnL')}")
    print(f"Live tradeHistory days: {len(live.get('tradeHistory', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
