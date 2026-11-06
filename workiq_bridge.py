"""Work IQ MCP bridge — independent-app edition (Path C).

Speaks MCP over stdio to WorkBuddy and forwards to the Microsoft-hosted
Work IQ endpoint.

Authentication
--------------
Tokens come from the MSAL token cache managed by workiq_auth.py. After the
user signs in once in a browser, the cached refresh token is redeemed
silently — the bridge never opens a browser and never asks for consent.
If the cache is missing or expired, the bridge reports that setup.cmd must
be run again; interactive login is never triggered during normal task calls.

Portability notes
-----------------
* No hard-coded user paths: the script resolves its own directory.
* The tenant id can be overridden with the WORKIQ_TENANT environment variable.
* The MSAL cache location can be overridden with WORKIQ_HOME.

The token cache holds a refresh token with the signed-in user's Work IQ
access — never commit it, never send it over chat, never share it.
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TENANT = os.environ.get("WORKIQ_TENANT", "b6c387dd-da7e-4491-8acd-e340f707a637")
MCP_URL = "https://workiq.svc.cloud.microsoft/mcp"

_lock = threading.Lock()
_cached_token = None
_cached_expiry = 0
_session_id = None
_protocol_version = None


def log(m):
    print(f"[work-iq] {m}", file=sys.stderr, flush=True)


def get_token(force=False):
    """Return a valid access token, renewing silently through the MSAL cache."""
    global _cached_token, _cached_expiry
    with _lock:
        now = time.time()
        if not force and _cached_token and now < _cached_expiry - 120:
            return _cached_token

        import workiq_auth

        try:
            token = workiq_auth.get_token(allow_interactive=False)
        except Exception as e:
            log(f"silent token acquisition failed: {str(e)[:200]}")
            log("run setup.cmd to sign in again; no browser was opened")
            raise

        _cached_token = token
        _cached_expiry = now + 3600
        return token


def parse_sse(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                try:
                    out.append(json.loads(payload))
                except Exception:
                    pass
        elif line.startswith("{"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def forward(payload):
    """Forward one JSON-RPC message upstream and print the response to stdout."""
    global _session_id, _protocol_version
    try:
        token = get_token()
    except Exception as e:
        print(json.dumps({
            "jsonrpc": "2.0",
            "id": payload.get("id"),
            "error": {"code": -32000, "message": f"Work IQ token unavailable: {str(e)[:200]}"},
        }), flush=True)
        return

    # The MCP-Protocol-Version header MUST match the body params.protocolVersion,
    # otherwise the server rejects with -32020. Mirror whatever the client sends.
    if payload.get("method") == "initialize":
        client_version = (payload.get("params") or {}).get("protocolVersion")
        if client_version:
            _protocol_version = client_version

    body = json.dumps(payload).encode()
    req = urllib.request.Request(MCP_URL, data=body, method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if _protocol_version:
        req.add_header("MCP-Protocol-Version", _protocol_version)
    if _session_id:
        req.add_header("Mcp-Session-Id", _session_id)

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            sid = resp.headers.get("Mcp-Session-Id")
            if sid:
                _session_id = sid
            text = resp.read().decode(errors="replace")
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        ctype = e.headers.get("Content-Type", "") if e.headers else ""
        sid = e.headers.get("Mcp-Session-Id") if e.headers else None
        if sid:
            _session_id = sid
        log(f"upstream HTTP {e.code}: {text[:300]}")
        if payload.get("id") is not None:
            print(json.dumps({
                "jsonrpc": "2.0", "id": payload.get("id"),
                "error": {"code": -32000, "message": f"upstream HTTP {e.code}: {text[:300]}"},
            }), flush=True)
        return
    except Exception as e:
        log(f"upstream connection error: {str(e)[:200]}")
        if payload.get("id") is not None:
            print(json.dumps({
                "jsonrpc": "2.0", "id": payload.get("id"),
                "error": {"code": -32000, "message": f"upstream error: {str(e)[:200]}"},
            }), flush=True)
        return

    if "text/event-stream" in ctype:
        messages = parse_sse(text)
    else:
        messages = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except Exception:
                    print(line, flush=True)

    for msg in messages:
        if msg.get("id") == 1 and isinstance(msg.get("result"), dict):
            negotiated = msg["result"].get("protocolVersion")
            if negotiated:
                _protocol_version = negotiated
                log(f"negotiated MCP protocolVersion = {negotiated}")

    for msg in messages:
        print(json.dumps(msg, ensure_ascii=False), flush=True)


def main():
    log("starting: Work IQ MCP bridge -> " + MCP_URL)
    try:
        get_token(force=True)
    except Exception as e:
        log(f"startup token acquisition failed: {str(e)[:200]}")
        log("the bridge will retry on the first request")

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log(f"ignoring non-JSON line: {raw[:120]}")
            continue
        forward(msg)
    log("stdin closed, exiting.")


if __name__ == "__main__":
    main()
