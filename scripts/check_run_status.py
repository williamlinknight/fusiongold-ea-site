#!/usr/bin/env python3
"""Check latest GitHub Actions run status for the repo (uses token from git remote URL)."""
import json
import subprocess
import urllib.request

def get_token():
    url = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        capture_output=True, text=True
    ).stdout.strip()
    # Format: https://user:token@github.com/owner/repo.git
    if "@" in url and "://" in url:
        auth = url.split("://")[1].split("@")[0]
        if ":" in auth:
            return auth.split(":", 1)[1]
    return None

def main():
    token = get_token()
    req = urllib.request.Request(
        "https://api.github.com/repos/williamlinknight/fusiongold-ea-site/actions/runs?per_page=5",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "hermes-cron",
        },
    )
    # Disable proxies entirely: macOS system proxy points at a dead local proxy,
    # and env http_proxy/all_proxy also reference it. Direct connection works.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=30) as resp:
        data = json.load(resp)
    for r in data.get("workflow_runs", []):
        print(
            r["id"], r["name"], "|", r["status"],
            "|", r["conclusion"],
            "|", r["head_sha"][:7],
            "|", r["created_at"],
        )

if __name__ == "__main__":
    main()
