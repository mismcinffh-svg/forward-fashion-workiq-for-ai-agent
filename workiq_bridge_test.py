"""End-to-end test: launch the bridge as a subprocess and drive it over stdio.

Runs initialize -> tools/list -> one live tool call, proving the whole chain
(token renewal -> hosted endpoint -> tool execution) works.

Requests are sent one at a time with a short pause, because the MCP session
id is only established after initialize completes.

Usage:  python workiq_bridge_test.py
"""
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def find_python():
    candidate = os.path.expanduser(r"~\.buddy-365\venv\Scripts\python.exe")
    if os.path.exists(candidate):
        return candidate
    return sys.executable


def main():
    bridge = os.path.join(HERE, "workiq_bridge.py")
    if not os.path.exists(bridge):
        print(f"[!] bridge not found: {bridge}")
        return 1
    sys.path.insert(0, HERE)
    import workiq_auth
    try:
        auth_info = workiq_auth.describe()
    except SystemExit as e:
        print(f"[!] {e}")
        return 1
    if not auth_info["cache_exists"]:
        print("[!] MSAL token cache missing - run setup.cmd first")
        return 1

    print("=" * 66)
    print("  Work IQ bridge end-to-end test")
    print("=" * 66)

    proc = subprocess.Popen(
        [find_python(), bridge],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
        bufsize=1, cwd=HERE)

    received = {}

    def reader():
        for line in proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") is not None:
                received[msg["id"]] = msg

    threading.Thread(target=reader, daemon=True).start()

    def send(payload, wait=6.0):
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()
        deadline = time.time() + wait
        while time.time() < deadline:
            if payload.get("id") in received:
                time.sleep(0.6)
                return received[payload["id"]]
            time.sleep(0.2)
        return received.get(payload.get("id"))

    try:
        init = send({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "workbuddy-test", "version": "1.0"}},
        })
        if not init or "result" not in init:
            print("\n[FAIL] initialize failed")
            return 2
        res = init["result"]
        info = res.get("serverInfo", {})
        print(f"\ninitialize  -> protocol={res.get('protocolVersion')} "
              f"server={info.get('name')} {info.get('version')}")

        send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
             wait=2)

        tools = send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        if not tools or "result" not in tools:
            print("[FAIL] tools/list failed")
            return 3
        tool_list = tools["result"].get("tools", [])
        print(f"tools/list  -> {len(tool_list)} tools")
        for t in tool_list:
            print(f"    - {t['name']}")

        call = send({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "list_agents", "arguments": {}},
        }, wait=25.0)

        ok = False
        print()
        if call and "result" in call:
            result = call["result"]
            agents = None
            sc = result.get("structuredContent")
            if isinstance(sc, dict) and isinstance(sc.get("result"), list):
                agents = sc["result"]
            if agents is None:
                # Work IQ returns the agent list as a JSON string in content[0].text
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        try:
                            parsed = json.loads(block.get("text", ""))
                        except json.JSONDecodeError:
                            continue
                        if isinstance(parsed, list):
                            agents = parsed
                            break
            if isinstance(agents, list):
                print(f"live call   -> list_agents returned {len(agents)} agents")
                for a in agents[:8]:
                    print(f"    - {a.get('name')}  ({a.get('provider')})")
                ok = True
            else:
                print("live call   -> unexpected shape:", str(result)[:250])
        else:
            print("live call   -> failed:", str(call)[:300])

        print()
        if ok:
            print("=== PASS: bridge works end to end ===")
            return 0
        print("=== bridge reachable but live call failed ===")
        return 4
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
