"""MSAL-based sign-in for the independent Work IQ app (Path C).

Replaces the device-code flow with an MSAL public-client PKCE login, the same
mechanism m365-buddy uses:

  1. First run: browser opens, the user signs in once, a refresh token is
     written to the MSAL token cache.
  2. Every later run: acquire_token_silent() redeems the cached refresh
     token. No browser, no consent prompt, no re-authorisation.

The cache lives at ~/.workbuddy/workiq/msal_token_cache.bin by default and can
be relocated with the WORKIQ_HOME environment variable.

The token cache is the credential: it holds a refresh token with the signed-in
user's Work IQ access. It must never be committed or shared.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

# --- configuration ---------------------------------------------------------

WORKIQ_API_APP_ID = "fdcc1f02-fc51-4226-8753-f668596af7f7"
TENANT = "b6c387dd-da7e-4491-8acd-e340f707a637"
AUTHORITY_HOST = f"https://login.microsoftonline.com/{TENANT}"

# The independent Work IQ app's client id. Override with WORKIQ_CLIENT_ID so
# the same code works before and after the app registration exists.
CLIENT_ID = os.environ.get("WORKIQ_CLIENT_ID", "").strip()

WORKIQ_SCOPES = [
    f"{WORKIQ_API_APP_ID}/WorkIQAgent.Ask",
    f"{WORKIQ_API_APP_ID}/WorkIQ.Read",
    f"{WORKIQ_API_APP_ID}/WorkIQ.Act",
]

_RESERVED_SCOPES = {"offline_access", "openid", "profile"}

_lock = threading.Lock()
_cached_token = None
_cached_expiry = 0


def workiq_home() -> Path:
    base = os.environ.get("WORKIQ_HOME")
    if base:
        return Path(base)
    return Path.home() / ".workbuddy" / "workiq"


def cache_path() -> Path:
    return workiq_home() / "msal_token_cache.bin"


def creds_path() -> Path:
    return workiq_home() / "client_id.txt"


def resolve_client_id() -> str:
    """Client id precedence: env var > user copy > packaged copy."""
    if CLIENT_ID:
        return CLIENT_ID
    candidates = [
        creds_path(),
        Path(__file__).resolve().parent / "client_id.txt",
    ]
    for cp in candidates:
        if cp.exists():
            value = cp.read_text(encoding="utf-8").strip()
            if value:
                return value
    cp = creds_path()
    raise SystemExit(
        "Work IQ client id not configured.\n"
        "Run setup.cmd, or set WORKIQ_CLIENT_ID, or write the id to:\n"
        f"  {cp}")


def save_client_id(client_id: str) -> None:
    workiq_home().mkdir(parents=True, exist_ok=True)
    creds_path().write_text(client_id.strip() + "\n", encoding="utf-8")


def _load_cache():
    from msal import SerializableTokenCache

    cache = SerializableTokenCache()
    cp = cache_path()
    if cp.exists():
        try:
            cache.deserialize(cp.read_text(encoding="utf-8"))
        except OSError:
            pass
    return cache


def _save_cache(cache) -> None:
    if getattr(cache, "has_state_changed", False):
        workiq_home().mkdir(parents=True, exist_ok=True)
        cp = cache_path()
        cp.write_text(cache.serialize(), encoding="utf-8")
        try:
            os.chmod(cp, 0o600)
        except OSError:
            pass


def _app(cache):
    import msal

    return msal.PublicClientApplication(
        resolve_client_id(), authority=AUTHORITY_HOST, token_cache=cache)


def get_token(*, allow_interactive: bool = True) -> str:
    """Return a valid Work IQ access token.

    Preference order:
      1. Silent  — cached refresh token, no browser, no prompt.
      2. Interactive — browser PKCE login, only when no usable cache exists.

    Once the user has signed in once, path 1 always succeeds, so the browser
    never reappears on later calls.
    """
    global _cached_token, _cached_expiry

    with _lock:
        now = time.time()
        if _cached_token and now < _cached_expiry - 120:
            return _cached_token

        cache = _load_cache()
        app = _app(cache)
        scopes = [s for s in WORKIQ_SCOPES if s not in _RESERVED_SCOPES]

        accounts = app.get_accounts()
        result = None
        if accounts:
            result = app.acquire_token_silent(scopes, account=accounts[0])

        if not result:
            if not allow_interactive:
                _save_cache(cache)
                raise RuntimeError(
                    "No cached Work IQ credentials. Sign in once with: "
                    "python signin.py")
            result = app.acquire_token_interactive(
                scopes, prompt="select_account")

        _save_cache(cache)

        if not result or "access_token" not in result:
            err = (result or {}).get("error_description") \
                or (result or {}).get("error") or str(result)
            raise RuntimeError(f"Failed to obtain Work IQ token: {err}")

        _cached_token = result["access_token"]
        _cached_expiry = now + int(result.get("expires_in", 3600))
        return _cached_token


def sign_in_interactive() -> dict:
    """Force a fresh interactive sign-in (used by setup)."""
    cache = _load_cache()
    app = _app(cache)
    for account in app.get_accounts():
        app.remove_account(account)
    _save_cache(cache)

    scopes = [s for s in WORKIQ_SCOPES if s not in _RESERVED_SCOPES]
    result = app.acquire_token_interactive(scopes, prompt="select_account")
    _save_cache(cache)
    if not result or "access_token" not in result:
        err = (result or {}).get("error_description") \
            or (result or {}).get("error") or str(result)
        raise RuntimeError(f"Interactive sign-in failed: {err}")
    return result


def describe() -> dict:
    """Report cache state without touching the network."""
    cp = cache_path()
    info = {
        "client_id": resolve_client_id(),
        "cache_path": str(cp),
        "cache_exists": cp.exists(),
        "home": str(workiq_home()),
    }
    if cp.exists():
        cache = _load_cache()
        app = _app(cache)
        accounts = app.get_accounts()
        info["accounts"] = [a.get("username") for a in accounts]
    return info


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(json.dumps(describe(), ensure_ascii=False, indent=2))
    elif cmd == "login":
        r = sign_in_interactive()
        print("signed in, expires_in =", r.get("expires_in"))
    elif cmd == "token":
        t = get_token()
        print("token length:", len(t))
    else:
        print("usage: workiq_auth.py [status|login|token]")
