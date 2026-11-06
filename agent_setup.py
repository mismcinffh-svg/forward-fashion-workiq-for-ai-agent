"""Non-interactive installer entry point for AI agents.

The script handles dependency installation, browser sign-in, endpoint
verification and WorkBuddy MCP registration. It never calls pause and never
prints access tokens. The only interactive step is the user's first Microsoft
365 browser sign-in. Use --no-interactive for a silent validation run.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIREMENTS = HERE / "requirements.txt"


def ensure_dependencies():
    try:
        import msal  # noqa: F401
        return
    except ImportError:
        print("[1/4] Installing the Microsoft authentication library (MSAL)...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)
        ])


def main():
    no_interactive = "--no-interactive" in sys.argv
    try:
        ensure_dependencies()
        sys.path.insert(0, str(HERE))
        import install
        import signin
        import workiq_auth

        client_id = workiq_auth.resolve_client_id()
        print(f"[2/4] WorkIQ for Agent client: {client_id}")
        print("[3/4] Acquiring a token and checking Work IQ...")
        if not no_interactive:
            print("      If a browser opens, sign in with YOUR company account.")
        token = workiq_auth.get_token(allow_interactive=not no_interactive)
        status, body = signin.check_endpoint(token)
        if str(status) != "200":
            print(f"[X] Work IQ endpoint returned HTTP {status}: {body[:300]}")
            return 2
        print("      Work IQ endpoint check: HTTP 200")

        print("[4/4] Registering the work-iq connector in WorkBuddy...")
        result = install.main()
        if result != 0:
            return result

        summary = {
            "status": "installed",
            "client_id": client_id,
            "workiq_http_status": status,
            "connector": "work-iq",
            "interactive_sign_in_allowed": not no_interactive,
            "next": [
                "Fully restart WorkBuddy",
                "Open Connectors > Custom Connectors",
                "Find work-iq and select Trust",
                "Start a new chat",
            ],
        }
        print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"[X] Agent setup failed: {str(exc)[:1000]}")
        print("    Resolve the reported dependency, sign-in, assignment or network issue,")
        print("    then run agent_setup again. No access token was printed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
