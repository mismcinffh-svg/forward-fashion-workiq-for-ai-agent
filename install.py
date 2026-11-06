"""Register the Work IQ MCP server in WorkBuddy's mcp.json.

Merges into the existing mcpServers object — never overwrites other servers.
Creates the file if it does not exist.

Usage:  python install.py
"""
import json
import os
import sys

HOME = os.path.expanduser("~")
MCP_JSON = os.path.join(HOME, ".workbuddy", "mcp.json")
HERE = os.path.dirname(os.path.abspath(__file__))
BRIDGE = os.path.join(HERE, "workiq-bridge.cmd")


def main():
    if not os.path.exists(BRIDGE):
        print(f"[!] bridge launcher not found: {BRIDGE}")
        return 1

    if os.path.exists(MCP_JSON):
        with open(MCP_JSON, encoding="utf-8") as f:
            raw = f.read().strip()
        config = json.loads(raw) if raw else {}
    else:
        config = {}

    servers = config.setdefault("mcpServers", {})

    entry = {
        "type": "stdio",
        "command": BRIDGE,
        "args": [],
        "timeout": 600,
    }

    if "work-iq" in servers:
        print("[i] work-iq already present — updating its entry")
    servers["work-iq"] = entry

    os.makedirs(os.path.dirname(MCP_JSON), exist_ok=True)
    with open(MCP_JSON, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"[OK] work-iq registered in {MCP_JSON}")
    print()
    print("Next steps (in the WorkBuddy app):")
    print("  1. Fully quit WorkBuddy (system tray icon -> Quit), then reopen it")
    print("     (WorkBuddy only reads mcp.json at startup)")
    print("  2. Sidebar -> Connectors -> Custom Connectors (top right)")
    print("  3. Find 'work-iq' -> click Trust")
    print("  4. Status changes to Enabled")
    print("  5. Open a NEW chat and try:")
    print("       List all available tools under the work-iq connector")
    return 0


if __name__ == "__main__":
    sys.exit(main())
