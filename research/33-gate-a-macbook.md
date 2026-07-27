# Gate A — transport verification on the MacBook (issue #33)

Run date: 2026-07-26 (evening, local), MacBook Pro (M4 Pro, macOS Darwin 27.0.0).
Hands-on, on-machine. Nothing committed; all test artefacts removed (see Cleanup).

## Verdict

**Gate A PASSES for the decided shape.** One server module, two entry points —
`transport="stdio"` for Claude Desktop, the same module run as a long-lived
loopback HTTP process for Claude Code — works on this machine, and both clients
reconnect reliably across a restart of the client.

One material hazard was found that reshapes the *supervision* story, not the
transport choice: **Claude Desktop never restarts a stdio MCP server that dies.**
See "Hazard 1".

## Result matrix

| Client | Transport | Result | Evidence |
|---|---|---|---|
| Claude Code 2.1.219 | stdio | **PASS** | `claude mcp list` → Connected; `whoami` tool round-tripped in 5 separate headless sessions |
| Claude Code 2.1.219 | loopback HTTP (`claude mcp add --transport http http://127.0.0.1:8931/mcp`) | **PASS** | `whoami` round-tripped in 8 separate client processes against one server PID |
| Claude Desktop 1.24012.9 | stdio | **PASS** | 3 app launches, 3 clean `initialize` + `tools/list`/`prompts/list`/`resources/list` round trips |
| Claude Desktop | HTTP | **N/A — not attempted** | manifest v0.3 exposes no `url` field; confirmed the config schema only accepts `command`/`args`/`env` |

"Across a restart of the client" was actually exercised, not assumed:
Claude Desktop was quit with `osascript -e 'quit app "Claude"'` and relaunched
**three times**; Claude Code was exercised as **eight separate `claude -p`
processes** (each is a full client lifecycle).

### Environment / pins

- `mcp` resolved and tested against: **1.28.1** (constraint `mcp>=1.28,<2`).
  Full transitive set includes `pydantic 2.13.4`, `starlette 1.3.1`,
  `uvicorn 0.51.0`, `httpx 0.28.1`, `sse-starlette 3.4.6`.
- Python 3.12, project managed with `uv`.
- Server entry points used: `python server.py stdio` and
  `python server.py http --port 8931` (FastMCP `transport="streamable-http"`,
  host pinned to `127.0.0.1`).
- MCP protocol version negotiated by **both** clients: `2025-11-25`.
- Claude Code here is **2.1.219**, not the 2.1.220 the brief cited. The
  hard-coded clientInfo behaviour is identical.

## The per-session vs per-launch question (Desktop)

**Answer: ONE SERVER PER APP LAUNCH, not per session.**

Evidence, all empirical:

1. **The server appears before any conversation exists.** Within ~1 s of
   `open -a Claude`, and before any chat window was interacted with, the process
   tree already showed the server spawned and initialized. Desktop's own
   `~/Library/Logs/Claude/mcp.log` records a single
   `Server started and connected successfully` per launch.
2. **Process ancestry ties lifetime to the Electron main process, not a
   renderer:**
   ```
   43883  .venv/bin/python3 server.py stdio
   43882  /opt/homebrew/bin/uv run --directory <dir> python server.py stdio
   43881  /Applications/Claude.app/Contents/Helpers/disclaimer /opt/homebrew/bin/uv run ...
   43880  /Applications/Claude.app/Contents/MacOS/Claude        <- ppid 1
   ```
   The MCP client lives in Claude's main process. Sessions are renderer-level;
   the server is not.
3. **Opening additional chat windows spawns nothing.** Four `open
   "claude://claude"` deep links across two launches produced **zero** additional
   server processes and **zero** additional `initialize` handshakes. A polling
   loop sampling `pgrep` every 3 s for ~10 minutes never observed more than the
   one server pair.
4. **Exactly one `initialize` per launch, three launches:**
   ```
   23:17:10  pid 32150  {"name":"claude-ai","version":"0.1.0"}
   23:19:17  pid 34624  {"name":"claude-ai","version":"0.1.0"}
   23:30:20  pid 43883  {"name":"claude-ai","version":"0.1.0"}
   ```

**Consequences.**

- Cold start on Desktop lands on **app launch**, not on the first capture of each
  session. Desktop boots the server while the user is still looking at the
  window; by the time a capture is possible the server is warm. This is
  *better* than the ticket's worst case.
- **Grain of a Tome-minted process UUID under Desktop is per-app-launch.** One
  UUID will span every conversation in that launch. If capture provenance needs
  session granularity, the process UUID cannot supply it — Desktop gives the
  server no session identity at all (see clientInfo below: no session id, no
  conversation id, nothing distinguishing one chat from another). Session grain
  would have to come from the tool call payload, i.e. from the model, which is
  not trustworthy as an identifier.

**Contrast — Claude Code stdio is per-session.** Each `claude -p` invocation
spawned a fresh server PID (29171, 29488, 30048, 30449, 30682, 31027 …), each
reporting `uptime_s` of ~4–6 s at the moment of the tool call. Every Claude Code
session pays the full cold start on the stdio path.

**Contrast — Claude Code HTTP has no cold start at all.** One server process
(PID 29700, started 23:15:35) served **eight** separate client processes over
**944.5 s**. `uptime_s` reported by the tool climbed monotonically —
19.8 → 37.8 → 47.9 → … → 944.5 — while the PID never changed. Each client
session opens a new MCP session object against the same warm process
(`session_obj` differs, PID identical). This is the direct confirmation the
ticket asked for: **the loopback HTTP path has zero per-session cold start.**

## clientInfo — closing issue #34's checklist item M4

Captured by hooking `ServerSession._received_request` and logging the verbatim
`InitializeRequestParams` on every handshake, so the payload is what went over
the wire, not a reconstruction.

### Claude Desktop 1.24012.9 — **previously unverified, now closed**

```json
{"name": "claude-ai", "version": "0.1.0"}
```

Serialized with `exclude_none=False` to prove the absent fields are genuinely
absent:

```json
{"name": "claude-ai", "title": null, "version": "0.1.0",
 "websiteUrl": null, "icons": null}
```

Client capabilities:

```json
{"extensions": {"io.modelcontextprotocol/ui": {"mimeTypes": ["text/html;profile=mcp-app"]}}}
```

**Four things follow, and they matter more than the payload's size:**

1. **`version` is a placeholder, not the app version.** Desktop is 1.24012.9;
   it announces `0.1.0`. Any logic that reads clientInfo.version to gate
   behaviour, detect capability, or record provenance will record a constant
   that is also wrong.
2. **`name` is `claude-ai`, not `claude-desktop`.** It does not distinguish
   Desktop from claude.ai web or any other first-party surface that reuses the
   string. If Tome wants "which client captured this", `claude-ai` is not a
   sufficient answer, and it is not one that can be improved by asking the
   client.
3. **No `title`, no `websiteUrl`, no `description`, no `icons`** — the exact
   opposite of Claude Code, which hard-codes all five. So the two clients are
   trivially separable *today* (`claude-code` vs `claude-ai`), but only by name,
   and only for as long as the strings hold.
4. **No sampling and no roots capability.** Desktop advertises only the MCP-UI
   extension. A server cannot initiate anything toward Desktop — no sampling
   callback, no roots query, no elicitation. Claude Code, by contrast,
   advertises `{"elicitation": {}, "roots": {"listChanged": true}}`. Anything in
   the design that assumes the server can prompt the user must be Code-only.

### Claude Code 2.1.219 — confirms the hard-coding

```json
{"name": "claude-code",
 "title": "Claude Code",
 "version": "2.1.219",
 "websiteUrl": "https://claude.com/claude-code",
 "description": "Anthropic's agentic coding tool"}
```

Capabilities: `{"elicitation": {}, "roots": {"listChanged": true}}`.

Identical byte-for-byte over stdio and over HTTP — the transport does not
change what Claude Code announces. Unlike Desktop, `version` here **is** the
real client version and tracks the installed build.

## Hazards found

### Hazard 1 (material) — Desktop does not restart a dead stdio server

Killed the server with `kill -9` while Desktop stayed up. Desktop logged the
disconnect and then **did nothing**:

```
06:27:26 [info]  [gatea-stdio] Server transport closed
06:27:26 [info]  [gatea-stdio] Server transport closed unexpectedly, this is
                 likely due to the process exiting early. ...
06:27:26 [error] [gatea-stdio] Server disconnected. ...
06:27:26 [info]  [gatea-stdio] Client transport closed
```

The polling loop then recorded `procs=0` for **90 s continuously**. Opening a
new chat window (`claude://claude`) did **not** trigger a respawn — another
60 s at `procs=0`, no new log lines. Only quitting and relaunching the app
brought the server back.

There is no retry, no backoff, and no user-visible signal in the chat UI. Under
Desktop, a server that dies at 09:00 is simply unavailable until the user
happens to restart the app — which, on a machine that stays logged in for days,
could be a very long time. **This is a silent capture-availability hole, and it
is a property of the client, not of Tome.** Combined with the per-launch
finding, the exposure is: one crash costs the entire remainder of the app
launch.

Mitigation belongs in the server: the stdio entry point must not be able to die.
That means no unhandled exception escaping to the top level, no fatal path on a
Postgres connection failure (retry, per the ticket's launchd-has-no-dependency-
model note), and defensive handling of anything that could raise during
`initdb`-time or model-load-time work. Note this pushes in the same direction as
the ticket's existing "retry logic in code" conclusion, and for a second
independent reason.

### Hazard 2 (observed once, unreproduced) — silent death during the first launch

On the very first app launch of this run, the server process disappeared
somewhere between 23:17:11 and ~23:19:00 while Desktop's main process (31795)
stayed alive. `mcp.log` recorded **no** disconnect, **no** error, nothing after
the successful `tools/list` at 23:17:10.971. I attempted to reproduce it with
the same deep-link sequence on a later launch and could not; the server then ran
continuously for over 10 minutes across four new-window deep links.

I am recording it rather than explaining it away. It may have been an artefact
of the first-ever spawn of a new command (Desktop routes every MCP command
through `/Applications/Claude.app/Contents/Helpers/disclaimer`, present in all
three launches). It compounds Hazard 1: whatever killed it, Desktop never
noticed and never recovered.

### Hazard 3 (minor) — Desktop wraps every MCP command in a helper binary

Every spawn goes through `/Applications/Claude.app/Contents/Helpers/disclaimer`,
which sits between Claude and `uv`. Two implications: the `ppid` a Tome server
sees under Desktop is the wrapper, not Claude, so parent-process introspection
is not a reliable way to identify the host; and an approval/consent gate exists
on this path whose failure modes are undocumented and which is a plausible
source of Hazard 2.

### Hazard 4 (minor) — Claude Code spawns *all* configured stdio servers per session

Even a `claude -p` run that only allowlisted the HTTP tool still spawned the
stdio server (log shows a stdio `initialize` paired with every HTTP one). Under
Claude Code every session pays the cold start of every configured stdio server
whether or not it is used. This is a further argument for the HTTP entry point
on the Code side, independent of warm-start: it keeps Tome out of the
per-session spawn set entirely.

## What this means for the transport design

- **The decided shape holds.** No stdio-to-HTTP shim is needed and none was
  built. Desktop reaches the module over stdio directly; Claude Code reaches the
  same module over loopback HTTP as a long-lived process. The `mcp-remote`-shaped
  risk in PRD §13.2 is not reintroduced.
- **Desktop's cold start is cheaper than the ticket feared** — it lands at app
  launch, not first capture.
- **Desktop's crash recovery is worse than the ticket assumed** — there is none.
  The reliability requirement ("high reliability on capture") now rests on the
  stdio entry point being unkillable, because the client will not help.
- **A Tome-minted process UUID is per-app-launch under Desktop and per-session
  under Claude Code stdio.** Under Claude Code HTTP it is per-server-lifetime,
  spanning all sessions. Three different grains for the same identifier; the
  design should not assume one.
- **`clientInfo` is usable to tell Code from Desktop and useless for anything
  finer.** Desktop's version is a fixed `0.1.0` placeholder. Do not build
  provenance, gating, or telemetry on it.

## What was not covered

- Gate B (capture-path latency) — not part of this run.
- Desktop tool *invocation* from the chat UI. macOS did not grant `osascript`
  assistive access, so I could not type into Desktop, and I did not attempt to
  change that permission. What is proven for Desktop is the full JSON-RPC
  handshake plus `tools/list`, `prompts/list` and `resources/list` round trips —
  the client sent, the server answered, the client accepted, three launches
  running. The tool *execution* leg is unexercised under Desktop; it was
  exercised repeatedly under Claude Code on both transports.

## Cleanup performed

- `claude_desktop_config.json` restored from a verbatim byte copy;
  `diff` against the backup reports **IDENTICAL**, SHA-256
  `384932061b53f274fa44bad586356c7e2afcc1cddf555e71160a10bbebfe353a` both before
  and after. Note for the record: the file contained **no** `mcpServers` key at
  all before this run — Desktop's real connectors are configured elsewhere, not
  in this file. The key was added for the test and removed with the restore.
- `claude mcp remove gatea-stdio` / `gatea-http` (local scope, project
  `/Users/mark/Projects/tome`); `claude mcp list` shows no `gatea` entries.
- Long-lived HTTP process killed; nothing listening on 127.0.0.1:8931; `pgrep -f
  gatea` returns nothing.
- Claude Desktop restarted with the restored config and left running (pid 46158
  at time of writing).
- Nothing committed to git.
