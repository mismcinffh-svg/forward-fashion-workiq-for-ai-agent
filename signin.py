"""Sign in to Work IQ with the independent app (MSAL / PKCE browser login).

First run: the default browser opens, you sign in with your own Microsoft
account once, and the refresh token is cached.

Later runs: silent. The cached refresh token is redeemed without opening a
browser and without asking for consent again.

Usage:
  python signin.py            # sign in (interactive if needed)
  python signin.py --status   # show cache state, no network call
  python signin.py --check    # verify the token works against the MCP endpoint
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import workiq_auth  # noqa: E402

MCP_URL = "https://workiq.svc.cloud.microsoft/mcp"


def check_endpoint(token):
    """Call the hosted MCP endpoint with the token to prove it is usable."""
    import urllib.error
    import urllib.request

    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                   "clientInfo": {"name": "workbuddy-signin", "version": "1.0"}},
    }).encode()
    req = urllib.request.Request(MCP_URL, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, resp.read(800).decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(600).decode(errors="replace")
    except Exception as e:
        return None, str(e)[:300]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "login"

    if mode == "--status":
        print(json.dumps(workiq_auth.describe(), ensure_ascii=False, indent=2))
        return 0

    print("=" * 70)
    print("  Work IQ sign-in")
    print("=" * 70)

    try:
        info = workiq_auth.describe()
    except SystemExit as e:
        print(f"[!] {e}")
        return 1
    print(f"  client id : {info['client_id']}")
    print(f"  cache     : {info['cache_path']}")
    print(f"  cached    : {'yes' if info['cache_exists'] else 'no'}")
    print()

    print("[*] acquiring token (silent if a cached session exists)…")
    try:
        token = workiq_auth.get_token(allow_interactive=True)
    except Exception as e:
        print(f"[!] {e}")
        return 2
    print(f"[OK] token acquired (length {len(token)})")

    if mode == "--check":
        print("\n[*] verifying against the Work IQ MCP endpoint…")
        code, body = check_endpoint(token)
        print(f"    HTTP {code}")
        print(f"    {body[:400]}")
        if str(code) == "200":
            print("\n=== SUCCESS: token works against the hosted endpoint ===")
            return 0
        print("\n=== token obtained but endpoint check failed ===")
        return 3

    print("\n=== SUCCESS: signed in ===")
    print("The session is cached; later calls are silent and never reopen")
    print("the browser.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
