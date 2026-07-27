# The interface, with no network — macOS on-device target

Research for the macOS retarget spike ([issue #32](https://github.com/markdlabrecque/tome/issues/32)), Agent 2 of 5. Question: what happens to Tome's *interface* — the HTTP edge, the networking policy, the client setup, and the egress exception list — if Tome stops being a server reachable across a tailnet and becomes an entirely on-device install on a single MacBook with no Tailscale and no network.

**Sections owned:** §1.3, §7.4, §7.5, §9 (all), the network rows of §13.2, and §10's mobile ruling.

**Direct predecessor:** [`research/mcp-remote-transport-tailscale.md`](./mcp-remote-transport-tailscale.md), which established the transport reasoning this document revisits. Where that document's findings still hold I say so and cite it; where they have moved I date the change.

**Research date: 2026-07-26.** Every "as of" statement below is as of that date. The MCP specification's current version is **2025-11-25**; a **2026-07-28** revision exists in draft and is already partly implemented in the Python SDK's main branch, which turns out to matter (§3.3).

---

## 0. Evidence labelling, and the one-paragraph answer

The PRD's standard is *measured / documented / assumed*, and §13.3 exists because that standard was not always met. I have no MacBook, so I have measured nothing on the target. To keep the standard honest without inflating it, I use four labels:

| Label | Means |
|---|---|
| **Documented** | Stated in a primary source — the MCP spec, Anthropic's own docs, Apple developer/platform documentation, Ollama's own docs. Cited and dated. |
| **Verified in source** | Read directly out of the shipped artifact — the Python SDK at a named tag, the npm registry, the GitHub API. This is measurement of an artifact, not of the target machine. |
| **Assumed** | Reasoned. Not confirmed by either of the above. Flagged inline every time. |
| **Measurable** | Settled faster by running something on the MacBook than by reading. Collected in §10. |

**The one-paragraph answer.** The load-bearing observation in the spike ticket holds for this area, and holds harder than the ticket puts it. §7.5, §7.4, §9.1–§9.3 and three of §13.2's four network rows do not need porting — they need **deleting**, because the problems they solve are artifacts of the server being reachable across a network. stdio is not a workaround for the absence of a network; it is the transport the MCP spec tells clients to prefer ("Clients **SHOULD** support stdio whenever possible"), and it is the only transport *both* Claude clients document for a server on the same machine. What survives is narrow and specific: `source` provenance survives on stdio (with a caveat that has nothing to do with the host change and everything to do with a draft spec revision), and §1.3's egress list survives in a form that is materially **weaker**, because the thing that bounded three of its four entries was `IPAddressDeny=` and macOS has no unit-level equivalent to it. That last point is the real cost of this section's move, and it is not small.

### Verdict summary

| Section | Verdict | One line |
|---|---|---|
| **§1.3** exception 1 (Tailscale signalling) | **Dissolves** | No tailnet, no coordination traffic. The exception that forced the constraint's non-literal reading is gone; the rule gets *closer* to literal. |
| **§1.3** exception 2 (NTP) | **Survives with a native substitute, on a new reason** | `timed` replaces `chronyd`. Its stated justification — drift breaks Tailscale handshakes and kills the only ingress — is void. It needs a different one, and there is one. |
| **§1.3** exception 3 (`uv sync`) | **Survives, half its bound removed** | Still human-initiated and outside any service. But "so §7.4's kernel-enforced deny is untouched" has no referent on macOS, because there is no kernel-enforced deny. |
| **§1.3** exception 4 (model weights) | **Must be restated per runtime; on Ollama it gets worse** | Ollama's macOS build **auto-downloads updates** (Ollama's own FAQ), which kills the "human-initiated, never automatic" half — the only bound it had left. An MLX/HuggingFace fetch could be *cleaner* than today, if acquisition is deliberate. |
| **§1.3** framing sentence | **Breaks** | "Three of the four are bounded by *where they run*" becomes **none of them are**. This is the biggest honest loss in my area. |
| **§7.4** (bind broadly, filter in kernel) | **Dissolves as a bind decision; breaks as an egress control** | Both premises (the `FedoraWorkstation` zone; the tailnet-address startup race) are gone. The honest minimum is **no listening socket at all**. But the two lines were doing a second job — kernel-enforced egress — and *that* has no acceptable substitute. |
| **§7.5** (the HTTP edge) | **Dissolves**, except the provenance mechanism | Starlette app, `GET /mcp` → 405, `Host` allowlist, the ~20-line suffix subclass, `json_response=True`, the DNS-rebinding reasoning, the "never hang" `mcp-remote` discovery argument: all gone. The stateful-session finding survives in restated form. The "no server-initiated SSE" door **opens** on stdio. |
| **§9.1** (which clients) | **Survives with a native substitute** | Same two clients. The reason iOS is excluded changes completely and the exclusion gets *stronger*. §13.3's flagged re-check comes back **still true** — and stops mattering. |
| **§9.2** (endpoint, per-device config, `mcp-remote`) | **Dissolves** | No endpoint, no URL, no TLS question, no bridge, no pinned dead dependency, no Node-version constraint. Replaced by two documented stdio config entries. |
| **§9.3** (Host allowlisting) | **Dissolves** on stdio; **shrinks to zero code** on loopback HTTP | With no HTTP surface there is no rebinding target. If loopback HTTP is chosen instead, the SDK now auto-configures exactly the right allowlist and the ~20-line subclass is unnecessary. |
| **§9.4** (provenance) | **Survives unchanged, and its accepted risk shrinks** | `source` still reads `clientInfo` at `initialize`. Its "not device" caveat becomes vacuous: there is one device. |
| **§13.2** `100.64.0.0/10` CGNAT row | **Dissolves** | No source-address filter, no CGNAT range, no bound socket. |
| **§13.2** `Host` allowlist coupling row | **Dissolves** | No allowlist, no addressing to be coupled to. |
| **§13.2** `mcp-remote` row | **Dissolves** | The dependency is not replaced, it is removed. Confirmed still untended: last publish 2026-02-05, last commit 2026-02-05, 142 open issues. |
| **§13.2** "server can never volunteer" row | **Inverts** — the door opens | stdio is duplex by construction; server→client notifications ride the same pipe. What closed the door becomes a product decision only, not a transport one. |
| **§13.2** "entries captured without device provenance can never gain it" | **Survives, defanged** | Still true. Costs nothing when there is exactly one device. |
| **§10.2** mobile/iOS ruled out permanently | **Survives; the basis is replaced and the ruling gets stronger** | It was structural against Tailscale-only ingress. It becomes structural against *no ingress at all* — a stricter fact, reached by a different route. |

**Hypotheses killed:** #2 partially (the "honest minimum" is not a loopback bind — it is no socket; but the hypothesis's claim that §7.4's justification is *void* understates it, because §7.4 was silently doing a second job that genuinely breaks). #3's first half survives but for a reason the hypothesis did not anticipate — the SDK has already refactored the mechanism the PRD describes, and a draft spec revision makes `client_params` optional independently of transport.

---

## 1. What current Claude clients actually support for a local MCP server on macOS

This is the re-check §13.3 explicitly demands: *"Claude Desktop's lack of native remote-MCP support — Verified at decision time; **re-check before building**."* §9.1 states the consequence of the re-check going the other way: *"if Desktop has since gained direct remote support, the bridge disappears and §9.2 collapses."*

**Finding, dated 2026-07-26: the fact is still true. Claude Desktop has not gained native remote-MCP support in its config file.** And §9.2 collapses anyway, for a different and better reason.

### 1.1 The spec's own preference

**Documented** ([Transports, spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), fetched 2026-07-26):

> The protocol currently defines two standard transport mechanisms for client-server communication:
> 1. stdio, communication over standard in and standard out
> 2. Streamable HTTP
>
> **Clients SHOULD support stdio whenever possible.**

That sentence is worth pausing on. The current architecture uses the transport the spec treats as the *network* case, for a deployment that is not networked. On the Mac target, Tome would be using the transport the spec tells clients to prefer, for exactly the topology it was designed for.

The stdio contract in full (same page):

> * The client launches the MCP server as a subprocess.
> * The server reads JSON-RPC messages from its standard input (`stdin`) and sends messages to its standard output (`stdout`).
> * Messages are individual JSON-RPC requests, notifications, or responses.
> * Messages are delimited by newlines, and **MUST NOT** contain embedded newlines.
> * The server **MAY** write UTF-8 strings to its standard error (`stderr`) for any logging purposes including informational, debug, and error messages.
> * The client **MAY** capture, forward, or ignore the server's `stderr` output and **SHOULD NOT** assume `stderr` output indicates error conditions.
> * The server **MUST NOT** write anything to its `stdout` that is not a valid MCP message.
> * The client **MUST NOT** write anything to the server's `stdin` that is not a valid MCP message.

Two clauses have consequences elsewhere in the PRD and I flag them now: the `stdout` prohibition, and the `stderr` allowance. See §7.3 below — the `stderr` clause is a genuine hazard for Invariant C and belongs on Agent 4's desk.

**The spec's Security Warning is scoped to the other transport.** It is introduced with the words *"When implementing Streamable HTTP transport:"* and only then lists the Origin-validation MUST, the localhost-bind SHOULD, and the authentication SHOULD. **None of the three applies to stdio.** This is the single sentence that deletes most of §7.5 and all of §9.3: those requirements are not being waived or traded away, they are out of scope for the transport.

The authorization spec is equally explicit that stdio is a different world (quoted in the predecessor document, [Authorization spec 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)): *"Implementations using an STDIO transport **SHOULD NOT** follow this specification, and instead retrieve credentials from the environment."* Tome has no credentials, so this is a no-op — but it confirms that the "no app-level auth" decision (§1.2) is not merely defensible on stdio, it is the spec's expectation.

### 1.2 Claude Code — stdio is a documented first-class option

**Documented** ([code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp), fetched 2026-07-26). Claude Code documents four transports — `stdio`, `http`, `sse` (deprecated), and `ws` — and stdio is one of three headline "Options" in the add flow:

> ### Option 3: Add a local stdio server
> Stdio servers run as local processes on your machine. They're ideal for tools that need direct system access or custom scripts.
> ```
> claude mcp add [options] <name> -- <command> [args...]
> ```

with the `--` convention documented explicitly: *"For stdio servers, the `--` (double dash) separates Claude's own options, such as `--transport`, `--env`, and `--scope`, from the command and arguments that run the server. Everything after `--` is passed to the server untouched."*

The JSON form, from the same page's `add-json` example, is `{"type":"stdio","command":"...","args":[...],"env":{...}}`, written into `~/.claude.json` (user/local scope) or `.mcp.json` (project scope). Plugin-config docs confirm the field set: *"`stdio` servers: `command`, `args`, `env`"*.

Four operational details from the same page that bear on Tome specifically:

- **`CLAUDE_PROJECT_DIR` is injected** into the spawned server's environment. Irrelevant to Tome, but it establishes that Claude Code sets environment on the child — the substitute for `EnvironmentFile=` (§7.8) if one is wanted.
- **"Stdio servers are local processes and are not reconnected automatically."** HTTP/SSE servers get five exponential-backoff reconnect attempts; stdio gets none. On a *network* transport that would be a downgrade. Here it is the correct behaviour: a local subprocess that died did not "disconnect", it crashed, and silently respawning it would hide the failure. Note the interaction with §13.2's *"the `warnings` channel is dead if the MCP server fails to start"* — see §7.2 below, where this actually improves.
- **Idle timeout: 30 minutes for stdio** (versus 5 for HTTP), and **no per-request timer at all** for stdio ("Stdio and WebSocket servers have no per-request timer"). The HTTP path has a 60-second first-byte timer by default. Tome's slowest tool call is a capture with an inline embed on a 5 s budget (§4.5), so neither binds — but the stdio path is the more forgiving of the two, and `trigger_enrichment` / a cold model load has more headroom on it.
- **Deprecation direction**: *"The SSE (Server-Sent Events) transport is deprecated. Use HTTP servers instead, where available."* Unchanged from the predecessor document.

**Verdict: Claude Code reaches an on-device Tome over stdio with one documented command and no bridge.** This was already true for HTTP over the tailnet; it is true here with less machinery.

### 1.3 Claude Desktop — two local paths, both stdio, no third

**Documented** ([modelcontextprotocol.io/docs/develop/connect-local-servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers), fetched 2026-07-26). Config file at `~/Library/Application Support/Claude/claude_desktop_config.json`; the only documented entry shape is `command` / `args` / `env`. There is still **no documented `url` or `type: "http"` field**. The page's own "Next steps" card sends you to Custom Connectors for anything remote, which is the cloud path.

**Desktop Extensions (`.mcpb` bundles) are the second local path, and they are also stdio.** The Claude help centre's current article on local MCP servers ([support.claude.com/en/articles/10949351](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop), "updated over 3 weeks ago") leads with them: *"Desktop extensions provide a streamlined way to install and manage local MCP servers through single-click installable packages."* The MCPB manifest specification (**version 0.3, last updated 2025-12-02**, [modelcontextprotocol/mcpb MANIFEST.md](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md)) defines `mcp_config` with `command`, `args`, `env` and `platform_overrides` — and **no url/http/remote option anywhere**. A bundle is a zip containing a local server plus a manifest describing how to execute it.

**Custom Connectors are still cloud-mediated, and the wording got broader.** From [support.claude.com/en/articles/11175166](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) (marked updated *this week* when fetched 2026-07-26):

> Claude connects to your remote MCP server from Anthropic's cloud infrastructure, rather than from your local device. **This is true across every Claude client, including claude.ai, Claude Desktop, Cowork, and the mobile apps.**

> your MCP server must be reachable over the public internet from Anthropic's IP ranges.

> Servers hosted on a private corporate network, behind a VPN, or blocked by a firewall won't connect, even if you can reach them from your own machine.

The predecessor document reached the same conclusion in July 2025; the current wording is more explicit and enumerates the clients. This is the sentence that kills mobile (§8) and it is now stated by Anthropic rather than inferred.

**Corroborating (community, not primary):** [anthropics/claude-code#37286](https://github.com/anthropics/claude-code/issues/37286), filed 2026-03-22, reports that putting a `url` field in `claude_desktop_config.json` causes Claude Desktop to **silently delete the entire `mcpServers` key** on startup, with no error. The reporter's config was `{"mcpServers": {"brain-mcp": {"url": "http://127.0.0.1:7677/mcp"}}}` — i.e. someone attempting exactly the loopback-HTTP shortcut this spike would consider. The issue was closed by a bot as out-of-repo, so it is unresolved rather than refuted. Treat it as a signal, not a fact: it is one report, but it is the *only* datapoint I found on Desktop's behaviour with `url`, and it points the same way as the documentation.

**Verdict: as of 2026-07-26, Claude Desktop's only paths to a server it did not reach through Anthropic's cloud are `claude_desktop_config.json` (stdio) and `.mcpb` (stdio).** The §13.3 re-check returns *unchanged*.

### 1.4 What this means for §9.1's premise

§9.1 opens: *"The server is already centrally hosted — one instance, Streamable HTTP on the tailnet, shared by every device. Nothing server-side is per-device; what is irreducibly per-device is client configuration."*

On the Mac target the sentence inverts in an interesting way. There is one *device*, so "per-device configuration" collapses to nothing. But there is no longer one *instance*: **stdio means each client spawns its own copy of the server.** That is a real architectural change and I treat it properly in §7.4 below rather than burying it here.

---

## 2. §7.4 — Networking: bind broadly, filter in the kernel

### 2.1 The bind decision dissolves; hypothesis 2 confirmed on that half

§7.4's decision rests on exactly two measured facts about the Fedora box, both recorded in §1.4:

1. *"`FedoraWorkstation` opens **every port from 1025–65535 inbound on `eno1`**, and `tailscale0` is in no zone. A `0.0.0.0` bind is therefore reachable from the physical LAN, unfirewalled."*
2. *"binding the tailnet address directly races... `tailscaled.service` is `Type=notify`, so systemd considers it started when the daemon signals ready — which precedes authenticating and precedes `tailscale0` acquiring its address."*

Neither exists on the target. There is no tailnet to race against and no tailnet address to bind. macOS's Application Firewall is a different animal entirely: **Apple documents it as inbound-only** ([Apple Platform Security, "Firewall security in macOS"](https://support.apple.com/guide/security/firewall-security-seca0e83763f/web)) — the configuration surface is *"Block all incoming connections, regardless of app"*, *"Automatically allow built-in software to receive incoming connections"*, and the downloaded-signed-software equivalent. Outbound filtering is absent from the feature. So the specific hazard §7.4 exists to neutralise — a broadly-bound port silently reachable because the distro's default zone opened the whole ephemeral range — has no macOS analogue either way: Apple's default is not "1025–65535 open", and its firewall would not be the mechanism if it were.

**The honest minimum is not a loopback bind. It is no listening socket at all.** On stdio, Tome's MCP server binds nothing. `lsof -i` shows it nowhere. The entire class of question — which interface, which source addresses, what does `ss -ltn` show — stops existing rather than getting a smaller answer. §7.4's own accepted caveat (*"the port remains bound broadly, so `ss -ltn` shows it listening on all interfaces even though policy blocks non-tailnet sources"*) evaporates with it.

For completeness, the loopback-HTTP alternative is real and I cost it in §5.3. It is strictly more machinery for no benefit that survives scrutiny.

### 2.2 The half hypothesis 2 missed: §7.4 was doing a second job, and that job breaks

§7.4 lists four things the shape buys, and the third is not about binding at all:

> **It filters both directions**, so these two lines make *no external egress* a **kernel-enforced property of the unit** rather than a claim about application behaviour.

§1.2 promotes that to a hard constraint — *"No Tome data leaves the machine ... Enforced in the kernel for the units (§7.4)"* — and §1.3 leans on it twice, once for the `uv sync` exception and once, at length, for the Ollama one. **This is the load-bearing half of §7.4 and it does not survive the move.** Restating it as "we don't need it, there's no network" is wrong: the machine has Wi-Fi, and `IPAddressDeny=any` was never about the machine's connectivity, it was about the *process's* capability.

**What macOS offers instead — the full honest list.**

| Mechanism | Granularity | Verdict as a substitute |
|---|---|---|
| **launchd plist** | — | **No equivalent key.** `launchd.plist` has `Sockets`, resource limits, and sandbox hooks; it has no address-policy property. *(Documented by absence in `man launchd.plist`; no primary source claims one exists.)* |
| **Application Firewall** (`socketfilterfw`) | Per-app, **inbound only** | Not applicable. Apple's own feature description covers incoming connections only. |
| **pf** (`pfctl`, `/etc/pf.conf`) | Packet-level, system-wide | Present and functional (macOS's pf derives from OpenBSD's). System-wide rules by address/port/protocol, not by process. **Filtering by `user`/`group` is unresolved** in the sources I found — one says translation rules cannot match on user, another says group filtering is possible. See §10, item M6: this is a two-minute `pfctl -nf` parse test on the machine, and if `user` works it is the closest thing to a real substitute. |
| **NetworkExtension content filter** (`NEFilterDataProvider`) | Per-flow, per-process | Technically the right shape. Requires a system extension and an Apple-granted entitlement, plus a signed app bundle to host it. Wildly disproportionate for two lines of unit config. |
| **App Sandbox** (`com.apple.security.network.client`) | Per-app, deny-by-default | Closest *conceptual* analogue: outgoing connections are denied unless the entitlement is claimed ([Apple: com.apple.security.network.client](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.network.client)). But it is all-or-nothing — there is no address allowlist — and it requires restructuring Tome into a signed, sandboxed app bundle. **Whether it also blocks loopback is unresolved** in the sources I found, and Tome needs loopback for Postgres and the inference runtime. Assumed-blocking would make it useless; assumed-permissive would make it a blunt but real seal. Needs checking (§10, M7). |
| **`sandbox-exec`** with `(deny network-outbound)` | Per-process, profile-driven | **The nearest true analogue**, and it composes with launchd trivially — wrap the executable in the plist's `ProgramArguments`. Reported working on macOS 15 with `(deny network-outbound)` and selective `(allow network-outbound (remote ip "localhost:5432"))`-style rules. **But Apple deprecated it in favour of App Sandbox, the profile language is undocumented, and Apple may remove it without warning in a point release.** Spending Tome's egress invariant on an undocumented deprecated tool trades a kernel guarantee for a guarantee that can vanish in a Tuesday update. |
| **Third-party (Little Snitch, LuLu)** | Per-app, prompt-driven | Real products that do this well. But they are user-prompt-driven rather than policy-as-code, they add a proprietary kernel-adjacent dependency to a system whose whole point is that it is self-hosted and inspectable, and a prompt is not an invariant. |

**Verdict on §7.4: dissolves as a bind decision, breaks as an egress control.** The bind half is not ported, it is deleted, and nothing is lost — the caveat it carried disappears with it. The egress half has no substitute at proportionate cost. `sandbox-exec` and possibly `pf`-by-user are the only candidates that could restore a kernel-level property, and both are worse than what they replace: one is deprecated and undocumented, the other is coarse and unconfirmed.

**One important interaction with stdio, which cuts the other way and must be said.** Under stdio, the MCP server is a subprocess of Claude Desktop or Claude Code, running as the logged-in user. So even if a `pf`-by-user or `sandbox-exec` seal were adopted, it could only cover the components launchd owns — the enrichment runner and the backup job. **The MCP server, the process that receives every raw entry text on the capture path, would be the one component outside the seal**, because its parent is a GUI app that legitimately needs the internet. On the Fedora box that process was the *most* sealed of the three (§7.4's block is written for it). That inversion is the sharpest single consequence of choosing stdio, and it is the price of deleting §7.5.

---

## 3. §7.5 — The HTTP edge

### 3.1 What dies, row by row

§7.5's table has six rows and every one of them is an obligation created by speaking HTTP. On stdio there is no HTTP.

| §7.5 requirement | Fate |
|---|---|
| **`GET /mcp` → 405** with an `Allow` header, because `streamable_http_app()` registers the route with no method restriction and GET would otherwise open an SSE stream | **Gone.** No route, no router, no method. |
| **Unknown paths → immediate 404** (Starlette default) | **Gone.** No paths. |
| **`Host` allowlist; absent `Origin` allowed, present-but-unallowlisted rejected** | **Gone.** No headers exist on stdio. |
| **The `*.tailc0e3c3.ts.net` suffix pattern → ~20-line `TransportSecuritySettings` subclass** | **Gone twice over** — no tailnet to name, and no middleware to subclass. |
| **A legible 403 naming the mismatch** (the SDK returns 421) | **Gone.** |
| **`json_response=True`** to leave no SSE streams | **Gone.** No response encoding choice; stdio is newline-delimited JSON-RPC by definition. |

The custom Starlette app itself — the thing §7.5 chose over `FastMCP.streamable_http_app()` precisely so *"the client obligations fall out of the framework instead of being hand-enforced"* — is not needed, because there are no client obligations to make fall out. The SDK's stdio entry point takes no `transport_security` argument at all.

**Verified in source** ([python-sdk, main, `src/mcp/server/mcpserver/server.py`](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/mcpserver/server.py)), the overload set makes the scoping explicit:

```python
@overload
def run(self, transport: Literal["stdio"] = ...) -> None: ...
@overload
def run(self, transport: Literal["sse"], ..., transport_security: TransportSecuritySettings | None = ...) -> None: ...
@overload
def run(self, transport: Literal["streamable-http"], ..., transport_security: TransportSecuritySettings | None = ...) -> None: ...
```

and `run_stdio_async` is four lines:

```python
async def run_stdio_async(self) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await self._lowlevel_server.run(read_stream, write_stream,
                                        self._lowlevel_server.create_initialization_options())
```

`TransportSecurityMiddleware` imports `starlette.requests.Request` and `starlette.responses.Response` and takes a `Request` in its only public method. It cannot be applied to stdio; there is nothing to apply it to.

**Two of §7.5's claims are still accurate for HTTP, and I checked rather than assuming, because they would matter if loopback HTTP were chosen** (§5.3). **Verified in source** in `src/mcp/server/transport_security.py` on main: the wildcard matcher is still port-only (`if allowed.endswith(":*")`, then a `host.startswith(base_host + ":")` test) — so §7.5's "the SDK's wildcards are **port-only** (`host:*`)" holds, and a suffix pattern would still need a subclass. And the status codes are still `421` for a Host mismatch and `403` for an Origin mismatch, matching §7.5's note that the SDK returns 421.

### 3.2 The "never hang" argument goes with the bridge

> **Never hang.** A 405 on GET sends `mcp-remote` down its longer discovery path (three `.well-known` probes rather than one) at each Desktop launch; on the tailnet a prompt 404 costs microseconds, but its 5–10 s per-probe timeout ceiling only bites against a server that hangs.

This whole paragraph is a statement about `mcp-remote`'s OAuth discovery behaviour. With the bridge gone (§4.2) there is no discovery, no probe, no ceiling. **Dissolves.**

The underlying engineering instinct — *never hang, fail fast and legibly* — is worth carrying forward as a principle, but it has no specific obligation attached to it on this target.

### 3.3 What survives: the forced-stateful finding, restated — and a hazard the host change did not cause

§7.5's most interesting paragraph is the one that is not about HTTP at all:

> **Sessions are stateful — forced, not chosen.** `_client_params` is per-`ServerSession` instance state, set only when `initialize` arrives on that session. Stateless mode builds a fresh transport and session *per request*, so a `tools/call` would arrive with `client_params is None`, **breaking `source`**.

**First: is the PRD's description of the SDK still accurate? Yes, for the version it would be built against.** **Verified in source** at tag [`v1.28.1`](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/session.py) — the current stable release, and the release line the PRD's other SDK claims were made against — `ServerSession` still carries `_client_params: types.InitializeRequestParams | None = None` as instance state, still assigns it in the `initialize` branch (`self._client_params = params`), and still exposes it via a `client_params` property. `mcp.server.fastmcp.FastMCP` still exists at that tag. §7.5 describes the shipped code correctly.

**Second: does stdio preserve the mechanism? Yes, and more cleanly than HTTP does.** On stdio the SDK builds exactly one connection object for the process's whole lifetime, from the single stdin/stdout stream pair. **Verified in source** in `src/mcp/server/runner.py` on main: `serve_loop` constructs `Connection.for_loop(dispatcher, session_id=session_id)` once per stream pair and hands it to `serve_connection`, which drives the dispatcher *"until the underlying channel closes."* There is no per-request session construction on this path and no stateless variant of it — stateless mode is a Streamable-HTTP concept (it exists to let an HTTP server avoid holding per-client state between POSTs). The failure mode §7.5 guards against is structurally unreachable on stdio. `source` works.

Note also what §7.5 called the two favourable side effects. The first — *"the SDK's reported memory leak was stateless-mode only, so this avoids it by construction"* — remains true and gets stronger: on stdio there is no stateless mode to avoid. The second — *"the session identity that makes the fallback judgement signal possible (§3.8) exists only because sessions are stateful"* — needs care, and I take it up in §3.4.

**Third, and this is the part the hypothesis did not anticipate: the mechanism the PRD describes has already been refactored in the SDK's next major line, and a draft spec revision threatens `source` on *every* transport.** This is not caused by the host change and would apply equally on Fedora — but it lands in my section, so I record it.

**Verified in source** on `main` (which corresponds to the `2.0.0b2` prerelease, published 2026-07-14 per the PyPI registry; stable is `1.28.1`):

- **`mcp.server.fastmcp` is renamed to `mcp.server.mcpserver`**, and `FastMCP` to `MCPServer`. There is no `fastmcp` directory in the main branch tree. §7.5, §11.5 and §7.1's references to FastMCP are correct today and will need a spelling change on the 2.x line. *(This is orthogonal to the spike and belongs in whatever ticket tracks SDK version drift — but somebody should know.)*
- **`client_params` has moved off `ServerSession` onto a `Connection` object.** `ServerSession` is now documented as *"A per-request proxy built by the kernel for each inbound request"* and its `client_params` property just forwards: `return self._connection.client_params`. `Connection`'s module docstring says it is *"Always present on `Context` (never `None`), even in stateless deployments."* So the specific failure §7.5 designed against — stateless mode producing `client_params is None` — has been engineered away on the 2.x line. **The conclusion (be stateful) is unaffected on stdio, where there is no choice to make. But the *reason* §7.5 gives is version-specific and will read as stale against 2.x.**
- **The real hazard is upstream of the SDK.** `Connection` carries this comment:

  > the modern envelope, where capabilities are required but client info is optional (spec PR #3002) — capability checks must not depend on the peer having identified itself.

  and `ServerSession.client_capabilities` carries:

  > Prefer this over `client_params.capabilities`: on **2026-07-28+** the request envelope declares capabilities while client info stays optional, so capabilities can be present without `client_params`.

  `Connection.from_envelope` only synthesises `client_params` when *both* client info and capabilities are present; otherwise it records capabilities alone and leaves `client_params` as `None`.

  **`source` reads `clientInfo`. If a client omits client info under the 2026-07-28 protocol, `source` is `None` on a perfectly valid, fully-initialised connection.** The [versioning page](https://modelcontextprotocol.io/specification/versioning) still lists **2025-11-25** as current, so 2026-07-28 is draft — but the SDK is already implementing it, and clients will follow.

  **This is a live risk to §9.4 and to the `source` column in `raw_entries`, and it is transport-independent.** It intersects badly with §13.2's *"Entries captured without device provenance can never gain it"*: raw is immutable, so a period of `clientInfo`-less captures is a permanent hole in provenance, not a bug that can be backfilled. **Recommended:** whatever `source` does when `client_params` is `None` should be decided deliberately — a sentinel value like `unknown` that is distinguishable from both clients, not a null and not a silent default — and it should be decided before first capture, not after. That is a PRD-level decision and I am flagging it, not making it.

### 3.4 §3.8's session identity on stdio — survives, with a changed grain

§3.8's fallback-judgement signal needs a session id: *"Sessions are stateful by force (§7.5), so the server has a session identity at every `tools/call`. ... `search_raw` immediately after `search_entities` in the same session **is** a relevance judgement."*

On stdio there is no `MCP-Session-Id` header and no session-id concept in the spec — the transport has none. **Verified in source**: `Connection` has a `session_id: str | None` field, and `serve_loop` passes through whatever the caller supplies; the streamable-HTTP manager supplies one, and the stdio path has nothing to supply. So the server would mint its own — a UUID at process start is sufficient and trivially correct.

**Is it the same grain?** Under HTTP, a session was one client's `initialize`-to-teardown lifecycle against a shared long-lived server. Under stdio, the *process* is the session, and the process's lifetime is the client's. For Claude Desktop that is roughly app-launch to app-quit. For Claude Code — **assumed, and worth checking (§10, M2)** — a stdio server is spawned per session, so the grain is per-`claude`-invocation, which is if anything *tighter* and better aligned to "the same conversation" than the HTTP session was.

There is a real gain here that is easy to miss. Under HTTP, "same session" was a property the server had to track across a shared process. Under stdio, **two different clients cannot share a session by accident**, because they are different processes. The §3.8 signal gets less noisy in one specific way: cross-client interleaving is structurally impossible.

**Verdict on §3.8's dependency: survives, with a server-minted id replacing a transport-supplied one.** No design change; the sentence "sessions are stateful by force (§7.5)" needs its cross-reference repointed, because the force is now the transport rather than a mode choice.

### 3.5 What *opens*: the no-server-initiated-SSE door

§7.5 closes a door knowingly:

> **No server-initiated SSE, ever.** ... Building the stream would mean per-client connection state plus event-ID replay for resumability, with no traffic on it. **The door this closes:** the server can never *volunteer* anything without a retrofit.

and §13.2 carries it as an accepted risk.

**On stdio that door is not closed. It was never a door.** The stdio channel is one bidirectional pipe pair; server→client messages need no second connection, no event IDs, no resumability machinery, no `GET` handler. **Verified in source**, `Connection`'s docstring is explicit about the shape:

> duplex modern transports (e.g. stdio) pass a notify-only wrapper around the dispatcher so server notifications ride the pipe while server-initiated requests stay refused.

So: **server-initiated notifications become free; server-initiated *requests* remain refused** on the modern path (the protocol forbids them there). Everything §7.5 said it would cost — per-client connection state, event-ID replay — was the cost of doing it over HTTP.

**This does not mean Tome should volunteer anything.** §1.6 is a product decision — *"v1 is answer-when-asked. Tome never volunteers content"* — and §10.5's rejected-surfaces reasoning stands on its own merits. But the accepted risk as written attributes the closed door to the transport, and on this target that attribution is false. **§13.2's "the server can never volunteer anything without a retrofit" row should be deleted or rewritten**, because the retrofit it warns about costs nothing here. The honest restatement is: *the door is closed by product decision, and the transport no longer holds it shut.*

Two downstream items this touches, both outside my sections, so I flag rather than rule:
- §13.2's *"the `warnings` channel is dead if the MCP server fails to start"*, whose deferred fix is desktop notifications (§10.3). Part of that gap — surfacing something to the user without a tool call in flight — is now transport-reachable.
- §7.3's *"a system unit has no clean route to the desktop notification bus"*. Under stdio the server is a child of a GUI app in the user's session, so the premise changes. Agent 3's territory.

**Verdict on §7.5: dissolves, with one paragraph surviving in restated form and one accepted risk inverting.**

---

## 4. §9 — Client setup

### 4.1 §9.1 — Which clients, and why iOS is not one

**Survives with a native substitute.** Same two clients: Claude Code and Claude Desktop. Both are documented to reach a local stdio server on macOS (§1.2, §1.3). Claude Desktop ships for macOS, so the §9.2 parenthetical *"MacBook only — Desktop does not ship for Linux"* stops being a caveat and becomes the ordinary case.

Three of §9.1's four claims need rewriting even though the verdict is the same:

- *"The server is already centrally hosted — one instance ... shared by every device"* — **false on the target.** One device, and *more than one instance* (§4.4).
- *"what is irreducibly per-device is client configuration"* — **vacuous.** One device. What is irreducibly per-*client* is client configuration, which is two JSON entries.
- *"Transport: Streamable HTTP. It is the current spec transport"* — **replaced.** Streamable HTTP is still the current *network* transport, but the spec's guidance for this topology is stdio, and Streamable HTTP is not a candidate for Claude Desktop without a bridge.

The iOS sentence is handled in §8.

### 4.2 §9.2 — Endpoint and per-device configuration: the largest single deletion

Every paragraph of §9.2 is contingent on there being a URL. Taken in order:

| §9.2 content | Fate |
|---|---|
| **"Plain HTTP over the tailnet. No TLS."** — justified because Tailscale is already WireGuard end-to-end | **Dissolves.** No wire. stdin/stdout between a parent and its child process; the pipe never leaves the kernel. The question "should this be encrypted" has no referent. |
| **The `tailscale cert` / ACME rejection** — direct outbound to Let's Encrypt is egress the constraint does not permit, and 90-day manual renewal is a silent-failure generator | **Dissolves, and takes a would-be egress path with it.** Worth logging as a small win in the §1.3 ledger: a path that was *considered and rejected* on egress grounds cannot even be proposed here. |
| **`mcp-remote` `--allow-http`** because "mcp-remote allows non-TLS only for literal localhost" | **Dissolves.** For the record, the PRD's reading of that behaviour is correct: **verified in source** in `mcp-remote`'s `src/lib/utils.ts`, the check is `if (!(url.protocol == 'https:' || isLocalhost || allowHttp))` → exit. So a loopback URL would need no flag, which matters only for the §5.3 alternative. |
| **The Claude Code one-liner** `claude mcp add --transport http tome http://odin.<tailnet>.ts.net:PORT/mcp` | **Replaced** by `claude mcp add tome -- <interpreter> <entrypoint>` (transport defaults to stdio; the `--` convention is documented). |
| **The Claude Desktop `mcp-remote` config block** | **Replaced** by a plain `command`/`args` entry — the same shape the official quickstart documents for the filesystem server. |
| **"The bridge cannot be centralized even in principle"** — Desktop launches its MCP connection as a stdio subprocess, so the bridge must be local | **Inverts into the solution.** The property that made the bridge un-centralisable is exactly the property that makes the bridge unnecessary: Desktop launches a local subprocess, and now the local subprocess *is* Tome. |
| **`mcp-remote` pinned to 0.1.38, the dead-repo reasoning, "target Node 20 or 22 LTS; avoid Node 26"** | **Dissolves entirely.** No npm dependency, no Node runtime in the chain, no version constraint on the Mac's Node. |
| **"A custom bridge is a documented fallback, not built"** — the seven-responsibility dumb pipe, framing bugs, spec-drift ownership, the `Mcp-Session-Id`→`MCP-Session-Id` rename | **Dissolves.** The fallback existed only in case `mcp-remote` failed. |

**The `mcp-remote` risk, re-dated before deleting it.** §13.2 records it as *"~5.5 months without commits at decision time, 99 open issues."* **Verified against the registry and the GitHub API, 2026-07-26:** latest published version is still `0.1.38`, published **2026-02-05T23:21:44Z**; the repository's last commit is **2026-02-05T23:20:22Z** (message: `0.1.38`); **142 open issues**; not archived. So the dependency has gone another ~5.7 months untended and accumulated ~43 more open issues. The accepted risk did not blow up, but it did not improve either — and on this target it is not mitigated, it is **removed**.

**Verdict on §9.2: dissolves.** In exchange for two config entries that are shorter than the ones they replace, the deployment sheds an untended third-party dependency, a pinned version, a runtime-version constraint on an unrelated toolchain, two live upstream bugs, a documented custom-bridge fallback, and a TLS decision. This is the cleanest result in the spike's interface area and it is not close.

### 4.3 §9.3 — Host allowlisting

**Dissolves on stdio.** §9.3's own framing states the dependency plainly: *"Why it matters once TLS is off the table. Tailscale controls which devices reach the box but cannot control what runs on an authorized device. A rebound page on the MacBook is a genuine tailnet peer making a same-origin request, invisible at the network layer — and `search_entities` would hand over the entire memory layer."*

The attack requires a browser able to resolve a hostname to the server's address and issue an HTTP request to it. With no listening socket, there is no address and no request. The defence is not weakened, replaced or traded — **the attack has no target.** Everything in §9.3 goes with it: the enumeration of legitimate spellings (FQDN, short name, tailnet v4/v6, `localhost`/`127.0.0.1`), the suffix pattern, the absent-`Origin`-allowed rule, the legible 403, and the residual coupling cost.

The finding underneath it — *"Neither client sends an `Origin` header at all. The SDK's `_commonHeaders()` sets only `Authorization`, `mcp-session-id` and `mcp-protocol-version`, and Node's `fetch` adds no `Origin` server-side"* — becomes moot rather than wrong. I did not re-verify it; it has no consequence on this target and re-verifying it would be research spent on a deleted section. **If the loopback-HTTP alternative (§5.3) is ever seriously considered, that claim must be re-checked**, because §9.3's whole "allow an absent Origin" rule depends on it.

**On loopback HTTP it would shrink to zero code rather than dissolving**, which is a genuinely useful finding for §5.3. **Verified in source**, the SDK now auto-configures the allowlist for a loopback bind (`src/mcp/server/mcpserver/server.py`):

```python
if transport_security is None and host in ("127.0.0.1", "localhost", "::1"):
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
    )
```

Since the allowlist for a loopback deployment contains no suffix patterns — only exact hosts with port wildcards, which is precisely what the SDK's port-only matcher handles — **the ~20-line subclass would not be needed either.** §9.3 on loopback HTTP costs one argument, or nothing at all if the default host is used. That is worth knowing, but it does not make loopback HTTP a better choice than stdio; it makes it a *cheaper bad choice*.

### 4.4 §9.4 — Provenance, and a consequence stdio introduces

**Survives unchanged.** `source` reads client type from `clientInfo` in the `initialize` payload; the `initialize` handshake is transport-independent, and §3.3 establishes it is recorded per-connection on stdio. The two clients remain distinguishable by name.

Two of §9.4's notes change:

- *"The bridge runs on the MacBook, so it does not obscure device identity — the server still sees the Mac's tailnet IP"* — **moot.** No bridge, no IP, and **one device**, which makes the entire "client type, not device" caveat vacuous rather than merely accepted. The accepted risk in §13.2 (*"Entries captured without device provenance can never gain it"*) stays literally true and stops costing anything, because there is no second device whose entries would have differed.
- The "genuinely new capability rather than a field lifted from a payload" argument against device provenance — **stronger.** Reading device identity would now mean reading nothing at all, since the answer is constant.

**Whether `source` still means anything with one device: yes, but it now means something narrower than it looks.** It never was device provenance; it was client provenance, and *client* still varies — Desktop and Code are genuinely different capture contexts with different agents, different conversation shapes and different capture habits. That distinction is what §5.11's tool descriptions and §4's extraction are ultimately calibrated against. Keeping `source` is cheap and it remains the only per-entry evidence of which surface a memory came in through.

**But stdio adds a new provenance hazard the PRD has never had to think about.** Under stdio, Tome is spawned by the client, so the process's parent, argv and environment are all client-supplied. `clientInfo` remains the right source — it is what the spec defines and what §9.4 already specifies — and the temptation to read the parent process instead should be resisted, because argv and environment are exactly the kind of thing §5.1 already prohibits agents from supplying. Worth one sentence in a rewritten §9.4: **`source` is read from the handshake, never inferred from the process.**

### 4.5 The consequence §9 does not currently have a place for: N clients means N servers

Under HTTP, §9.1's "one instance shared by every device" was literally true. Under stdio it is false: **each client launch spawns its own Tome process.** Claude Desktop spawns one per configured server per app launch; Claude Code spawns per session (**assumed** — §10, M2).

This is not a problem, but it is a change with five consequences, and the PRD currently has no section that would catch them:

1. **Postgres concurrency** — already handled. Multiple connections are Postgres's job, §4.6's advisory lock already exists for the runner, and `capture_entry` is a per-entry transaction.
2. **The pinned embedder** — §7.7 pre-warms `bge-m3` at MCP server start with `keep_alive=-1`. That now happens once per client launch. `keep_alive=-1` is daemon state, not per-caller state, so repeated warms are idempotent. **No conflict**, but the pre-warm's *lifecycle* detaches from anything long-lived: on the Fedora box it happened once at boot; here it happens whenever a human opens a client, and never if they don't. (If the runtime is MLX rather than Ollama, this changes shape entirely — Agent 1's territory.)
3. **Startup latency is now user-visible.** Every Claude Code session pays Tome's cold start: Python interpreter, imports, DB connect, and whatever the pre-warm costs. Under systemd this happened once at boot where nobody was watching. **Measurable (§10, M3)** and possibly the most likely thing to make the on-device version feel worse than the networked one.
4. **`tome-mcp.service` disappears as a unit**, and with it §7.3's *"`tome-mcp`: **hard** on Postgres, **soft on Ollama**"* ordering. There is nothing to order, because the process starts when a human opens a client — long after boot, by which time Postgres is either up or the process fails visibly at its first query. **This makes Agent 3's hardest question partly moot for one of the three units** and I flag it to them explicitly: launchd's weaker ordering story does not need to express `After=postgresql` for the MCP server, because the MCP server no longer starts at boot. The enrichment and backup jobs still do.
5. **The failure story improves.** §13.2 accepts that *"the `warnings` channel is dead if the MCP server fails to start"* and *"surfaces only as a Claude connection error: obvious that something is wrong, not what."* Under stdio the client owns the process, so the client sees the exit and captures its stderr. Claude Desktop writes it to `~/Library/Logs/Claude/mcp-server-<NAME>.log` and general connection failures to `~/Library/Logs/Claude/mcp.log` ([documented](https://modelcontextprotocol.io/docs/develop/connect-local-servers)); Claude Code shows the server as `failed` in `/mcp`. **"Obvious that something is wrong, not what" becomes "obvious that something is wrong, and the traceback is in a named file."** That is a real improvement to a real accepted risk.

But point 5 has a sting, and it is not mine to resolve:

**⚠ Hand-off to Agent 4 (logging / Invariant C).** The MCP spec permits the server to write logs to `stderr`, and Claude Desktop *captures stderr into a file it owns*, under `~/Library/Logs/Claude/`, with no retention policy Tome controls and no analogue to `journalctl --namespace=tome --rotate --vacuum-time=1s`. Invariant C — *"No text derived from a Raw Entry, and no Natural Key, ever reaches a log line"* — is a code-level rule and ports unchanged; but under stdio, **an unhandled exception whose traceback includes an entry's text would be written by the Python runtime to stderr and archived by Claude Desktop into a location outside Tome's purge scope**. On the Fedora box that traceback landed in the `tome` journald namespace with a 30-day bound and a scoped-purge remediation. This is a new leak surface created by the transport choice, not by macOS, and it argues for: stderr kept rigorously empty (no logging handler on it, `sys.excepthook` installed to write a redacted line only), with all real logging going to Tome-owned files. Agent 4 owns the design; I own having found the surface.

---

## 5. Restating the transport choice honestly

### 5.1 The three options

1. **stdio, no socket.** Each client spawns Tome. §7.4, §7.5, §9.2, §9.3 delete.
2. **Loopback Streamable HTTP.** One launchd-managed long-lived server on `127.0.0.1:PORT`. Claude Code connects with `claude mcp add --transport http tome http://127.0.0.1:PORT/mcp`. Claude Desktop **cannot** — it needs `mcp-remote` (no `--allow-http` required for a loopback URL, verified in §4.2).
3. **stdio shim in front of a long-lived loopback daemon.** A thin stdio↔HTTP process spawned by each client, forwarding to one server.

### 5.2 Why option 3 is named and rejected

Option 3 is `mcp-remote` reinvented, pointed at localhost. It reintroduces the bridge, the HTTP edge, the `Host` allowlist, the framing bugs §9.2 catalogued, and the spec-drift ownership — to buy back a single shared process. It is the worst of both and I raise it only so nobody proposes it as a compromise.

### 5.3 What loopback HTTP would actually cost

The one thing option 2 buys is **a single long-lived server process**: one cold start, one pre-warm, one place to look. Against that:

- **Claude Desktop keeps `mcp-remote`** — the untended dependency stays, with its swallowed-transport-error hang and its unconditional OAuth discovery probe. §13.2's row survives intact. This alone should decide it: the single most valuable deletion in this whole area is undone.
- **A listening socket exists again**, so the SDK's DNS-rebinding middleware is needed. It costs zero code (§4.3), but it is a live surface and a thing that can be misconfigured.
- **§7.5's Starlette-app reasoning partly returns** — `GET /mcp` → 405 and `json_response=True` are still worth having, because they are still cheap and the FastMCP default still opens an SSE stream on GET.
- **A boot-ordering problem returns.** A long-lived MCP server started by launchd must not accept connections before Postgres is up — which is precisely the constraint §7.3 called *hard* and which Agent 3 is investigating launchd's ability to express. stdio makes it disappear; loopback HTTP hands it back.
- **macOS Local Network Privacy** almost certainly does not apply to loopback — Apple's TN3179 defines a local network as *"an IP network associated with a broadcast-capable network interface. Such interfaces include Wi-Fi and Ethernet, but not cellular (WWAN) or VPN"*, and `lo0` is not broadcast-capable. **But TN3179 never uses the word "loopback"** (I checked the full text: zero occurrences), so the exemption is inferred from the definition and corroborated only by Apple DTS forum posts, not stated. That is a small unresolved risk that option 1 does not have at all. See §6.3.

**Recommendation: option 1, stdio.** The only argument for option 2 is process count, and process count is cheap; the argument against it is that it preserves the single dependency this section most wants to be rid of.

---

## 6. §1.3 — Named egress exceptions, restated

This is the section that gets *worse* on the move, and it should be stated first rather than last.

### 6.1 The framing sentence breaks

§1.3's second paragraph is the one that carries the weight:

> Each is human-initiated or carries no memory content; none is an automatic path out for Tome data. **Three of the four are bounded by *where they run*; the fourth is bounded only by nobody invoking it.**

"Bounded by where they run" means one thing and one thing only: `IPAddressDeny=any` on the Tome units (§7.4). §2.2 establishes there is no macOS equivalent at proportionate cost. So on the Mac target the sentence becomes: **none of them is bounded by where it runs; all of them are bounded by behaviour and convention.** §1.2's hard-constraint row — *"Enforced in the kernel for the units (§7.4)"* — loses its parenthetical and, with it, its verb.

**That is a real regression and I do not want to soften it.** The PRD's most rigorous move in this area was refusing to let "no external egress" stand as an unbacked claim and instead making it a kernel property for the code that touches raw text. That rigour does not port.

### 6.2 The counterweight, stated so the ledger is honest

Two things move the other way, and together they are substantial:

- **The exception list gets shorter and the rule gets closer to literal.** #15 §9's whole reason for restating "no external egress" as "no Tome data leaves" was that *Tailscale itself egresses, or there would be no tailnet*. Remove Tailscale and that argument disappears. The constraint can be stated closer to its literal form than it has ever been able to be. That is a rhetorical gain but also a real one: the exception that was *definitional* — the one that could never be argued with — is gone.
- **The MCP server has no listening socket and no reason to make any non-loopback connection.** The ingress surface goes to zero, and the egress surface of Tome's own code goes to "whatever it chooses to open", which is nothing. The enforcement got weaker; the thing being enforced got smaller.

Which of those dominates is a judgement for the synthesis, not for me. What I can say is that they are not the same kind of thing: the loss is a *guarantee*, and the gains are *surface reductions*. A smaller surface with no guarantee is not obviously better than a larger surface with one, and #28's own reasoning — which declined a seal on proportion while insisting the gap be *stated rather than papered over* — is the right precedent for how to write it up.

### 6.3 The four exceptions, one at a time

**1. Tailscale's own signalling — dissolves.** Deleted, not ported. Nothing to restate.

**2. NTP — survives with a native substitute, on a replaced justification.**

- *Substitute*: `chronyd` → **`timed`**, macOS's built-in time daemon since 10.13, configured via `systemsetup -setusingnetworktime` / `-setnetworktimeserver`, defaulting to `time.apple.com`. It is on by default and there is no per-process seal to exempt it from, which is moot since there is nothing to exempt it from.
- *The stated reason is void.* §1.3 justifies NTP as: *"Refusing it makes the RTC the sole authority, dual-boot drift becomes permanent, and a bad enough drift breaks Tailscale's handshakes and so takes down the only ingress path."* Every clause of that is Fedora-box-specific — no dual boot, no Tailscale handshakes, no ingress path to take down.
- *There is a replacement reason, and it is arguably stronger.* Raw is immutable (§1.2), so `captured_at` is written once and can never be corrected. §11.5 already requires the server to *"flag a `captured_at` that disagrees wildly with the server clock"*, and §4.8's staleness alarms and §8.5's 90-day `query_log` window are both clock-dependent. A drifting clock on a machine whose raw layer is append-only produces permanently wrong timestamps on the one table that cannot be fixed. **NTP survives on data-integrity grounds rather than reachability grounds** — and it carries no memory content, which is the test that actually matters.
- *A laptop-specific wrinkle worth flagging to Agent 3*: a machine that sleeps and wakes across timezones has a clock story a dual-boot desktop does not. Not mine.

**3. `uv sync` → PyPI — survives, with half its bound removed.**

The exception's shape test is intact: human-initiated, never automatic, run during a deploy. What is *not* intact is the clause #20 called *"a cleaner one"*: *"it runs as root **outside** the units, so §7.4's kernel-enforced `IPAddressDeny=any` on the running system is untouched."* On macOS there is no `IPAddressDeny=any` on the running system, so there is nothing for running-outside-the-units to leave untouched. **The exception survives on the human-initiated half alone.** Same verdict, half the argument.

**4. Model weights — must be restated per runtime, and on Ollama it gets materially worse.**

Per the coordinator's scope note, the inference runtime is not assumed to be Ollama. Both paths need covering, and they land very differently.

**Path A — Ollama on macOS. The exception survives in name and loses its last bound.**

#28's ruling has two halves. The *enforcement* half — sealed vs. unsealed, `IPAddressDeny=any` + `IPAddressAllow=localhost`, `systemctl set-property --runtime` applying with no restart, the reseal-self-heals-at-boot property, the BPF-drops-packets-so-a-sealed-pull-hangs failure mode — is **entirely systemd vocabulary and does not port**. There is no sealed/unsealed axis on macOS at all, so there is no decision to make and no trade to weigh. §7.7's careful "declined on proportion, not on the argument" reasoning has no macOS restatement; the seal is not declined, it is unavailable.

The *shape-test* half is worse than that. §1.3 item 4's surviving bound is: **"human-initiated and never automatic (#17: Ollama is hand-installed at `/usr/local/bin`, owned by no package, with no unattended upgrade path)."** That measured fact about the Fedora box is what made "human-initiated" true. **On macOS it is false. Documented, in Ollama's own FAQ ([docs.ollama.com/faq](https://docs.ollama.com/faq)): *"Ollama on macOS and Windows will automatically download updates."*** The macOS distribution is a menubar app that auto-starts at login and auto-downloads updates in the background; the user is prompted only to *restart* to apply one already fetched. There are multiple long-standing upstream requests to make this optional ([ollama/ollama#4498](https://github.com/ollama/ollama/issues/4498), [#11804](https://github.com/ollama/ollama/issues/11804)).

So on macOS, with the default Ollama distribution: the daemon has standing outbound access (no seal available), *and* it egresses on its own initiative without a human in the loop. **Both halves of the test fail.** §1.3's item 4 would have to say so, and #28's honest-statement precedent means it would have to say so plainly.

There is a partial mitigation and it belongs in the record: **Homebrew's `ollama` formula is CLI-only and does not carry the menubar app's auto-updater**, so installing that way restores the "no unattended upgrade path" property that #17 measured on Fedora. That is a real choice with a real consequence for §1.3, and it is exactly the kind of thing that gets decided by accident during setup and then relied on for a year. **If Ollama is the runtime, the install method is a §1.3-load-bearing decision, not a convenience.** (Note it also interacts with Agent 3's service story and Agent 5's data-directory question — Homebrew's formula runs under `brew services`/launchd, the app does not.)

One further Ollama-on-macOS note for whoever owns §7.7: environment configuration moves from a systemd drop-in to `launchctl setenv OLLAMA_HOST ...` (documented in the same FAQ), which is per-user-session global rather than per-unit. The default bind is documented as `127.0.0.1:11434` — so §7.7's *"the bind is pinned"* decision, which existed because a lost drop-in would leave Ollama on `0.0.0.0` behind an open firewalld zone, is **defended by the default** on macOS rather than by configuration. Smaller problem, different mechanism.

**Path B — MLX / HuggingFace. The exception could get genuinely cleaner, if acquisition is made deliberate.**

I am not researching MLX (Agent 1 owns it), but the *shape* of the egress is what §1.3 turns on, and the shape is different in a way that matters:

- Weights come from HuggingFace via `huggingface_hub`, which is **a library call inside whatever process makes it** — not a request handed to a long-lived daemon. That is structurally the `uv sync` shape, not the `ollama pull` shape.
- If model acquisition is an explicit operator step — a `make pull` target, an `hf download`, a documented setup command — then it is human-initiated, runs in the operator's own short-lived process, and is not a standing capability of any long-running service. **That would make it the cleanest exception on the list**, and the only one that clears both halves of #15/#20's test on the Mac target.
- **The failure mode to avoid is lazy download at load time.** If the serving code calls a loader that silently fetches a missing model, the fetch happens inside the long-lived process that receives every raw entry text — reproducing exactly the `ollama pull` shape #28 had to concede, and doing it *inside Tome's own code* rather than a third party's. That is worse, not better, because it would be Tome's own process holding the capability.

**Verdict: if MLX is chosen, §1.3's fourth exception should be written to require deliberate acquisition and to state that lazy auto-download is prohibited.** That is a one-line design constraint on the runtime integration and it converts the list's weakest entry into its strongest. It is a small but real point in the Mac target's favour — and it only materialises if someone writes it down before the code exists.

### 6.4 §1.3 as it would have to read

Not a proposal, a sketch of the shape, so the cost is legible:

- **Exceptions: two, or three.** NTP (`timed`); `uv sync` → PyPI; and model-weight acquisition, whose entry depends entirely on the runtime and its install method.
- **The bound: behavioural for all of them.** No entry can claim to be bounded by where it runs.
- **The gain to state alongside the loss:** the definitional exception is gone, the ingress surface is zero, and the rule can be stated closer to its literal form than the Fedora box ever permitted.
- **The candidate substitutes, named and costed rather than omitted:** `sandbox-exec` (deprecated, undocumented, could vanish), `pf` by user or group (unverified — §10, M6), App Sandbox (requires restructuring into a signed sandboxed bundle; loopback behaviour unverified). None is adopted here; all should be named, because #28's precedent is that an unstated gap is the only unacceptable outcome.

---

## 7. §13.2 — the network rows

| Row | Verdict |
|---|---|
| **`100.64.0.0/10` is CGNAT, so this is a source-address filter, not an interface filter** — "a LAN numbered inside 100.64/10 would pass. The port also remains bound broadly, so `ss -ltn` looks more open than policy allows" | **Dissolves.** No filter, no CGNAT range, no bound port. Delete. |
| **The `Host` allowlist is coupled to how the box is addressed** — "a device or tailnet rename is a rare, delayed breakage" | **Dissolves.** No allowlist. Delete. |
| **`mcp-remote` is an untended dependency, pinned to a dead repo** — swallowed transport errors, Node 26 OAuth-probe crash | **Dissolves.** The dependency is removed, not replaced. Re-dated before deletion (§4.2): still `0.1.38`, still last-touched 2026-02-05, now 142 open issues. Delete. |
| **The server can never volunteer anything without a retrofit** | **Inverts.** stdio is duplex; server→client notifications are free. Rewrite: the door is held shut by product decision (§1.6), not by transport. |
| **Entries captured without device provenance can never gain it** | **Survives, defanged.** Still literally true; costs nothing with one device. Keep, with the cost restated as zero. |
| *(new)* **`source` may be `None` under protocol 2026-07-28+** | **New row needed.** Client info becomes optional while capabilities stay required (spec PR #3002, already implemented in the SDK's 2.x line). Transport-independent; would apply on Fedora too. Raw is immutable, so a period of `clientInfo`-less captures is permanent. §3.3. |
| *(new)* **No component's egress is kernel-enforced** | **New row needed, and it is the heaviest one in this area.** §1.2's hard constraint downgrades from a kernel property to an application-behaviour property for *all three* Tome components, not just the inference daemon. §6.1. |
| *(new)* **The MCP server runs as the logged-in user, as a child of a GUI app** | **New row needed.** stdio removes the dedicated service account for the one component that handles every raw entry on the capture path, and places it outside any launchd-scoped seal. §2.2, §4.5. |
| *(new)* **Tome's stderr is archived by the client, outside Tome's retention control** | **New row needed — Agent 4's to word.** Claude Desktop captures MCP-server stderr into `~/Library/Logs/Claude/mcp-server-<NAME>.log`. Invariant C's *enforcement* now has a second destination with no bound and no scoped purge. §4.5. |

Net: **three network rows delete, one inverts, one is defanged, and four new ones appear.** The count barely moves; the character changes completely. What leaves is a set of risks about *reachability*; what arrives is a set of risks about *enforcement*.

---

## 8. §10 — the mobile ruling

§9.1: *"iOS/mobile is excluded structurally, not as a scoping choice. The Claude mobile app reaches MCP servers only through cloud-mediated connectors, which cannot see a Tailscale-only host. Exposing the server publicly is ruled out by the destination."* §10.2 promotes it to *ruled out permanently*: *"Structurally incompatible with Tailscale-only ingress, not a deferral."*

**Does moving to a laptop change the ruling's basis? Completely. Does it make mobile more or less reachable? Strictly less. The ruling gets stronger.**

**The basis today has two legs**, and each fails independently on the new target:

1. *"cloud-mediated connectors cannot see a Tailscale-only host"* — the premise names Tailscale. There is no Tailscale. The clause needs replacing, not porting.
2. *"Exposing the server publicly is ruled out by the destination"* — this leg survives untouched. It is a destination-level constraint, not a network-topology one.

**The replacement basis is stricter.** On the Fedora box, mobile was *one policy decision away* from working: publish the tailnet host to the public internet (Tailscale Funnel), allowlist Anthropic's IP ranges, and the Claude iOS app would connect. The PRD refused, but the refusal was a choice with a working alternative behind it. On the Mac target there is no such alternative, because there is nothing to publish: **stdio has no endpoint.** Making Tome mobile-reachable would mean first re-adding a network transport, then re-adding the entire HTTP edge (§7.5), then re-adding a rebinding defence (§9.3), then exposing it publicly — i.e. reversing four deletions before the destination-level refusal even comes into play.

**Anthropic's own wording now covers mobile explicitly**, which is worth having: *"Claude connects to your remote MCP server from Anthropic's cloud infrastructure, rather than from your local device. This is true across every Claude client, including claude.ai, Claude Desktop, Cowork, and the mobile apps"* ([support.claude.com/en/articles/11175166](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp), updated within the week of 2026-07-26). The 2025 version of this finding was inferred from a private-network exclusion clause; the 2026 version names the mobile apps. **The re-check strengthens the ruling.**

**One nuance that should be recorded rather than glossed.** The current setup's peers include an iPhone (§1.4). A tailnet-joined iPhone could not reach Tome — but a *future* client architecture in which the iOS app spawned or proxied a local connection was at least conceivable, and Tailscale kept the network path alive as an option. The on-device target closes that option at the topology level. **The ruling therefore stops being "ruled out permanently on a fact about connectors" and becomes "ruled out permanently on a fact about the deployment."** That is a stronger ruling on a narrower base: if the deployment ever changes back, the ruling's basis changes with it, whereas the connector fact was independent of deployment. §10.2's wording should reflect which fact it is standing on, because they have different lifespans.

**Verdict: survives, basis replaced, strength increased.** §9.1's sentence and §10.2's one-liner both need rewriting; neither verdict changes.

---

## 9. What is lost, collected in one place

The spike ticket asks for what is lost alongside what is deleted. Deletions are easy to celebrate; this is the honest column.

1. **Kernel-enforced egress, for all three components.** The largest loss in this area, by a distance. §1.2's hard constraint downgrades from a property to a claim. No proportionate substitute exists. *(§2.2, §6.1)*
2. **The dedicated service account for the MCP server.** Under stdio it runs as the logged-in user, as a child of a GUI app, with that user's full file access — and outside any launchd-scoped seal that might otherwise cover the enrichment and backup jobs. The component with the most sensitive data path becomes the least contained. *(§2.2, §4.5)*
3. **A stderr destination outside Tome's control.** Client-captured logs in `~/Library/Logs/Claude/` with no retention bound and no scoped-purge equivalent. A second home for anything Invariant C fails to catch. *(§4.5 — Agent 4)*
4. **One server instance.** Replaced by one per client launch. Cheap, but it moves cold-start latency into the user's line of sight and detaches the model pre-warm from any boot-time event. *(§4.5)*
5. **A rehearsed, measured set of defences.** §7.4 and §9.3 were argued out over three tickets against measured facts, and they are being deleted rather than replaced. That is correct — but it means the interface's security posture on the new target is *"there is no surface"*, which is only as strong as the claim that no surface ever reappears. The moment anyone adds a loopback listener for any reason, none of the deleted reasoning is there to catch it. **Worth carrying one sentence forward into whatever replaces §7.4: Tome binds no socket, and adding one reopens §7.5 and §9.3 in full.**
6. **The `ollama pull` exception's last bound**, if Ollama-on-macOS-via-the-app is the runtime. Auto-updates make it neither human-initiated nor sealed. *(§6.3)*
7. **The `mcp-remote` risk is removed, not managed** — which is a gain, but it is worth noticing that the PRD's careful analysis of *why the risk was acceptable* (80% OAuth machinery that never executes) was good work that now has no subject. No action; just an honest note that deletions retire reasoning as well as risk.

---

## 10. Try it on the MacBook — this section's checklist

Ordered by how much reading they would save.

| # | Item | Why it beats reading | Rough method |
|---|---|---|---|
| **M1** | **Does a `command`/`args` stdio entry in `claude_desktop_config.json` work on the current Desktop build?** | Everything in this document rests on it. It is documented, but documented-and-current is a five-minute check and §13.3 exists because a documented fact went stale. | Point a config entry at the official filesystem server; confirm it appears under Connectors and a tool call succeeds. |
| **M2** | **Does Claude Code spawn one stdio server process per session, or share one?** | Decides §3.4's session grain and §4.5's process count. I could not settle it from the docs and marked it assumed. | Open two `claude` sessions with the same stdio server configured; count processes. |
| **M3** | **Cold-start latency of the Tome stdio server.** | The most likely way the on-device version feels *worse* than the networked one, and it is now paid at every client launch. | Time interpreter + imports + DB connect + pre-warm, from a shell, once the stack exists. |
| **M4** | **What `clientInfo.name` do Claude Desktop and Claude Code actually send over stdio?** | `source`'s entire value depends on the two being distinguishable, and on the strings being stable enough to store. | Log the `initialize` params from a throwaway stdio server launched by each client in turn. Also confirms whether either omits client info (§3.3). |
| **M5** | **Does Claude Desktop capture stderr, and where exactly?** | Sizes the Invariant C exposure in §4.5 for Agent 4. | Have a throwaway stdio server write a marker to stderr; look for it under `~/Library/Logs/Claude/`. Check whether the file is ever rotated. |
| **M6** | **Does macOS `pf` accept `user` / `group` in a filter rule?** | The only candidate for a *kernel-enforced* per-account egress deny. Sources conflict; the parser settles it in one command. | `echo 'block drop out proto tcp from any to any user 501' \| sudo pfctl -nf -` and read the error, if any. |
| **M7** | **Does App Sandbox's `com.apple.security.network.client` gate loopback connections?** | Decides whether App Sandbox is a usable seal or useless (Tome needs loopback for Postgres and the runtime). | Minimal sandboxed signed binary, entitlement off, connect to `127.0.0.1`. |
| **M8** | **Does `sandbox-exec` with `(deny network-outbound)` plus a loopback allow still work on the installed macOS version?** | The nearest analogue to `IPAddressDeny=`; deprecated, so version-specific. | Run a trivial script under a profile; confirm loopback passes and an external host fails. |
| **M9** | **Does Local Network Privacy fire for a loopback-only process?** | Only relevant if the loopback-HTTP option is revived, but TN3179 never says the word "loopback" and the exemption is inferred. | Loopback-only client from a launchd *agent* (not daemon — TN3179 is explicit the daemon exemption doesn't extend to agents); watch for a prompt or a silent block. |
| **M10** | **Which Ollama install is present / would be used — the menubar app or the Homebrew formula?** | Directly decides whether §1.3's fourth exception can claim "human-initiated" at all. | Trivial to check; consequential to get wrong. Only applies if Ollama is the runtime. |

---

## 11. Decisions that would need re-deciding

Sized as tickets, for the synthesis's input to a possible fresh map. I have not scoped effort — only named the decision and what makes it a decision rather than a rewrite.

1. **Transport: stdio, and the standing prohibition that goes with it.** Not just "pick stdio" — the durable part is the rule that Tome binds no socket, and that adding one reopens §7.5 and §9.3 in full. Cheap to decide, load-bearing forever.
2. **§1.3 restated, with the enforcement downgrade stated plainly and the substitutes named-and-declined.** #28's precedent says the unacceptable outcome is an unstated gap, not a conceded one. Must cover: NTP's replaced justification, `uv sync`'s halved bound, and the runtime-conditional fourth entry.
3. **Model-weight acquisition must be deliberate.** A one-line constraint on the runtime integration — no lazy auto-download inside a long-lived process — that decides whether §1.3's weakest entry becomes its strongest. Depends on Agent 1's runtime finding. If Ollama: the install method (menubar app vs. Homebrew) is part of this decision.
4. **What `source` records when `client_params` is `None`.** Forced by draft protocol 2026-07-28 making client info optional. Must be settled *before first capture*, because raw is immutable. Not caused by the host change; surfaced by it.
5. **Where the MCP server's configuration comes from**, now that `EnvironmentFile=` and `/etc/tome/tome.env` (§7.8) have no launchd-spawned process to attach to. Options: an `env` block in each client's config (duplicated, client-owned, in the user's Library), or the server reading a Tome-owned file itself. The second is almost certainly right and should be written down as such.
6. **Whether any per-process egress seal is adopted at all** — `sandbox-exec`, `pf`-by-user, or nothing — and if nothing, that being a recorded decision rather than an omission. Blocked on M6/M8.
7. **Rewrite §9 as "client setup" rather than "per-device setup"**, with §9.1's central-hosting premise corrected, §9.2 replaced by two stdio entries, §9.3 deleted, and §9.4 gaining one sentence: `source` is read from the handshake, never inferred from the process.
8. **§10.2's mobile ruling re-based** onto the deployment fact, with the note that the new basis has a different lifespan than the old one.
9. **SDK version drift (out of scope for the spike, but discovered by it).** `mcp.server.fastmcp.FastMCP` → `mcp.server.mcpserver.MCPServer` on the 2.x line, plus the `Connection` refactor that makes §7.5's stateless-mode reasoning read as stale. Applies on either host.

---

## 12. Sources

**MCP specification (primary), all fetched 2026-07-26**
- [Transports, 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) — the two transports; "Clients SHOULD support stdio whenever possible"; the full stdio contract; the Streamable-HTTP-scoped Security Warning; session management.
- [Versioning](https://modelcontextprotocol.io/specification/versioning) — current version is 2025-11-25.
- [Authorization, 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization) — stdio implementations SHOULD NOT follow the authorization spec. *(via the predecessor document.)*

**Anthropic / Claude client documentation (primary), all fetched 2026-07-26**
- [Connect to local MCP servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers) — `claude_desktop_config.json` path and schema (command/args/env only); Claude Desktop log locations.
- [Connect to remote MCP servers](https://modelcontextprotocol.io/docs/develop/connect-remote-servers) — Custom Connectors as the documented remote path.
- [Claude Code — MCP](https://code.claude.com/docs/en/mcp) — `claude mcp add <name> -- <command>`; the `--` convention; `add-json` stdio shape; stdio not auto-reconnected; stdio idle/timeout semantics; SSE deprecated.
- [Get started with custom connectors (support.claude.com)](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) — cloud-mediated across every client including mobile; public-internet requirement; private/VPN/firewall exclusion.
- [Getting started with local MCP servers on Claude Desktop (support.claude.com)](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop) — Desktop Extensions as the current local path.
- [MCPB manifest spec, v0.3, updated 2025-12-02](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md) — `mcp_config` = command/args/env/platform_overrides; no url/http.

**Python MCP SDK (verified in source), read 2026-07-26**
- [`v1.28.1` `src/mcp/server/session.py`](https://github.com/modelcontextprotocol/python-sdk/blob/v1.28.1/src/mcp/server/session.py) — `ServerSession._client_params`, set at `initialize`; `mcp.server.fastmcp` present. Confirms §7.5's description of the current stable line.
- [`main` `src/mcp/server/connection.py`](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/connection.py) — `Connection`, `from_envelope`, `for_loop`; client info optional on 2026-07-28+ (spec PR #3002); stdio named as a duplex modern transport.
- [`main` `src/mcp/server/runner.py`](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/runner.py) — `serve_loop` builds one `Connection` per stream pair.
- [`main` `src/mcp/server/mcpserver/server.py`](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/mcpserver/server.py) — `MCPServer.run` overloads (no `transport_security` on stdio); `run_stdio_async`; the loopback auto-allowlist in `sse_app`/`streamable_http_app`.
- [`main` `src/mcp/server/transport_security.py`](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/server/transport_security.py) — Starlette-typed; port-only wildcards; 421 on Host, 403 on Origin.
- PyPI registry, `mcp` — stable `1.28.1`; `2.0.0b2` published 2026-07-14.

**`mcp-remote` (verified in source / registry), read 2026-07-26**
- npm registry — `latest` = `0.1.38`, published 2026-02-05T23:21:44Z; no later publish.
- GitHub API, `geelen/mcp-remote` — last commit 2026-02-05T23:20:22Z; 142 open issues; not archived.
- [`src/lib/utils.ts`](https://github.com/geelen/mcp-remote/blob/main/src/lib/utils.ts) — `if (!(url.protocol == 'https:' || isLocalhost || allowHttp))`, confirming loopback needs no `--allow-http`.

**Apple (primary), all fetched 2026-07-26**
- [TN3179: Understanding local network privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy) — "A local network is an IP network associated with a broadcast-capable network interface. Such interfaces include Wi-Fi and Ethernet, but not cellular (WWAN) or VPN."; "macOS automatically allows local network access by: Any daemon started by `launchd`; Any program running as root; Command-line tools run from Terminal or over SSH..."; "The exception for `launchd` daemons doesn't apply to `launchd` agents." **Contains no occurrence of "loopback".**
- [Apple Platform Security — Firewall security in macOS](https://support.apple.com/guide/security/firewall-security-seca0e83763f/web) — inbound-only feature set.
- [`com.apple.security.network.client` entitlement](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.network.client) — gates outgoing connections for sandboxed apps.
- [Apple Developer Forums thread 763753](https://developer.apple.com/forums/thread/763753) — DTS: "Daemons are not subject to LNP. Agents are."; the macOS 15.0 DNS bug, fixed in 15.1. *(Forum, not documentation — corroborating only.)*

**Ollama (primary), fetched 2026-07-26**
- [Ollama FAQ](https://docs.ollama.com/faq) — "Ollama on macOS and Windows will automatically download updates."; default bind `127.0.0.1:11434`; `launchctl setenv` for environment variables; models at `~/.ollama/models`.
- [ollama/ollama#4498](https://github.com/ollama/ollama/issues/4498), [#11804](https://github.com/ollama/ollama/issues/11804) — open requests to disable auto-update. *(Corroborating.)*

**Corroborating, explicitly not primary**
- [anthropics/claude-code#37286](https://github.com/anthropics/claude-code/issues/37286) (filed 2026-03-22, closed as out-of-repo) — a `url` field in `claude_desktop_config.json` silently strips the `mcpServers` key.
- Secondary reporting on `sandbox-exec` and macOS `pf` per-user filtering, used only to identify candidates; both are marked unverified and appear as M6/M8 in §10.

**Internal**
- [`research/mcp-remote-transport-tailscale.md`](./mcp-remote-transport-tailscale.md) — the direct predecessor.
- Issues [#32](https://github.com/markdlabrecque/tome/issues/32) (this spike), [#28](https://github.com/markdlabrecque/tome/issues/28) (the Ollama egress ruling), and `PRD.md` §1.2–§1.4, §3.8, §7.3–§7.5, §7.7, §9, §10, §11.5, §13.2–§13.3.

*All examples in this document are synthetic; `markdlabrecque/tome` is public.*
