"""#34: what `mcp` 1.x does with a missing, malformed, or empty `clientInfo`.

Closes the gap Probe A in `../34-adversarial-verification.md` left open: that probe
established stateless -> `client_params is None` on 1.28.1, but never asked what the
pinned line does with a *client* that fails to identify itself.

Run:
    uv venv .v && VIRTUAL_ENV=$PWD/.v uv pip install 'mcp==1.28.1'
    ./.v/bin/python probe.py

Drives `srv.py` over real stdio pipes with hand-written 2025-11-25 frames, using the
same interpreter it is run with -- so the arms and the server always agree on version.
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SRV = os.path.join(HERE, "srv.py")


def run(client_info, omit=False):
    p = subprocess.Popen(
        [sys.executable, SRV],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1,
    )
    params = {"protocolVersion": "2025-11-25", "capabilities": {}}
    if not omit:
        params["clientInfo"] = client_info

    def send(obj):
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def read(timeout=10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = p.stdout.readline()
            if line:
                return json.loads(line)
            if p.poll() is not None:
                return None
        return None

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": params})
    init = read()
    call = None
    if init is not None and "result" in init:
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "whoami", "arguments": {}}})
        call = read()
    p.stdin.close()
    try:
        p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.kill()

    if init is None:
        return "no response; server exited"
    if "error" in init:
        return f"initialize REJECTED {init['error']['code']} {init['error']['message']}"
    if call is None:
        return "initialize ok; tools/call got no response"
    if "error" in call:
        return f"initialize ok; tools/call error {call['error']}"
    texts = [c.get("text") for c in call["result"].get("content", [])]
    return f"SERVED -> {texts}"


CASES = [
    ("well-formed (control)", {"name": "probe-client", "version": "9.9.9"}, False),
    ("clientInfo key omitted", None, True),
    ("clientInfo: null", None, False),
    ("clientInfo: {}", {}, False),
    ("wrong types", {"name": 123, "version": []}, False),
    ("extra keys only", {"foo": "bar"}, False),
    ("name empty string", {"name": "", "version": "1"}, False),
    ("name whitespace only", {"name": "   ", "version": "1"}, False),
]

if __name__ == "__main__":
    import importlib.metadata as md
    print(f"mcp {md.version('mcp')} | python {sys.version.split()[0]}\n")
    for label, ci, omit in CASES:
        print(f"{label:24s} -> {run(ci, omit)}")
