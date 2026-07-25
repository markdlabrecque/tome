# MCP remote transport over Tailscale — research findings

Research for [issue #9](https://github.com/markdlabrecque/tome/issues/9), child of the "Tome: memory-keeper PRD" map (issue #1). Question: what is the current state of the MCP remote-transport story for a self-hosted, single-user server reachable over Tailscale rather than local stdio, and is a Tailscale-only (no app-level auth) security model workable?

Sources are primary: the official MCP specification (modelcontextprotocol.io), the modelcontextprotocol GitHub org (typescript-sdk, python-sdk), and Anthropic's own docs for Claude Code (code.claude.com) and Claude/Claude Desktop (claude.com/docs, support.claude.com). Research date: 2026-07-25; the spec's "current" version as of this writing is **2025-11-25**.

## 1. Transport options in the MCP spec today

The spec currently defines exactly two standard transports: **stdio** and **Streamable HTTP**. ("The protocol currently defines two standard transport mechanisms for client-server communication: 1. stdio ... 2. Streamable HTTP" — [Transports, spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)).

**Streamable HTTP is the current network transport**, and it explicitly *replaces* the older transport: "This replaces the HTTP+SSE transport from protocol version 2024-11-05. See the backwards compatibility guide below." ([same page](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)). The old transport is referred to throughout as "the **deprecated** HTTP+SSE transport (from protocol version 2024-11-05)" in the Backwards Compatibility section of the current spec. So: **SSE-only transport is legacy/deprecated**, not the current recommendation — confirmed independently by Claude Code's own docs, which state outright: "The SSE (Server-Sent Events) transport is deprecated. Use HTTP servers instead, where available." ([code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp)).

Key mechanics of Streamable HTTP relevant to a self-hosted server:
- A single HTTP endpoint (e.g. `https://example.com/mcp`) handles both POST (client→server messages) and GET (optional server-initiated SSE stream) — [Transports spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
- **Session management is optional and server-chosen.** A server *may* assign a session ID at initialize time via a session-ID header on the `InitializeResult` response; if it does, the client must echo that header on every subsequent request. Note a naming/casing change between spec revisions worth flagging for version-mismatch debugging: the 2025-06-18 spec used header name `Mcp-Session-Id`; the current 2025-11-25 spec renamed it to `MCP-Session-Id` ([2025-06-18 Transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports) vs [2025-11-25 Transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)).
- **Resumability** (via SSE `id` + client `Last-Event-ID` header) is a MAY, not a MUST — servers aren't required to support reconnection/redelivery at all.
- **Security warning baked into the spec itself**: servers "MUST validate the `Origin` header ... to prevent DNS rebinding attacks," "SHOULD bind only to localhost (127.0.0.1) rather than all network interfaces (0.0.0.0)" when running locally, and "SHOULD implement proper authentication for all connections" ([Transports spec, Security Warning](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)). This last point is a `SHOULD`, not a `MUST` — see §3 below on why a Tailscale-only model is defensible against it.
- **Protocol version negotiation**: clients must send an `MCP-Protocol-Version` header on every HTTP request after initialization; if absent, servers should assume the old `2025-03-26` version for backwards compatibility. Mismatched/invalid versions get a `400 Bad Request` ([Transports spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)). Version strings are just dates: "the last date backwards incompatible changes were made" — clients/servers may support multiple versions but must agree on exactly one per session ([Versioning](https://modelcontextprotocol.io/specification/versioning)).

## 2. How Claude Code and Claude Desktop actually connect to a remote server

This is where the two products diverge significantly, and it matters a lot for a Tailscale-only deployment.

### Claude Code — connects directly, runs locally, ideal for Tailscale

Claude Code is a local CLI process. When you register a remote server, Claude Code itself opens the HTTP connection from the machine it's running on — there is no cloud intermediary. Syntax, straight from the docs:

```bash
# Streamable HTTP (current, recommended)
claude mcp add --transport http <name> <url>
claude mcp add --transport http notion https://mcp.notion.com/mcp

# With an auth header (works fine for a shared/static credential, or omit entirely for Tailscale-only trust)
claude mcp add --transport http secure-api https://api.example.com/mcp \
  --header "Authorization: Bearer your-token"

# SSE — explicitly called out as deprecated by Claude Code's own docs
claude mcp add --transport sse <name> <url>
```
([code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp))

This writes a JSON entry like:
```json
{ "mcpServers": { "stripe": { "type": "http", "url": "https://mcp.stripe.com" } } }
```
into `~/.claude.json` (user/local scope) or `.mcp.json` (project scope) — same docs. Note a documented gotcha: `type` also accepts `streamable-http` as an alias for `http` since that's the name the spec itself uses, so server-provided config snippets work unmodified; but a JSON entry with a `url` and *no* `type` field is silently treated as a (broken) stdio server, with Claude Code reporting an explicit configuration-error message (behavior changed slightly across versions — pre‑v2.1.202 gave a more confusing `command: expected string, received undefined` error) — [code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp).

Because Claude Code runs on the same device you'd have joined to your tailnet, a Streamable HTTP server reachable only via its Tailscale IP/MagicDNS name is directly reachable with **no bridge process needed** — you just `claude mcp add --transport http memory-keeper https://<tailscale-hostname>/mcp`.

### Claude Desktop — two entirely different remote paths, only one of which works over Tailscale

This is the critical finding for this ticket. Claude Desktop has **two separate mechanisms** for "remote" MCP, and they are not interchangeable:

1. **Custom Connectors** (Settings → Connectors → "Add custom connector"), Anthropic's officially documented way to add a remote MCP server to Claude Desktop/claude.ai. This is **cloud-mediated**: "Claude connects to your remote MCP server from Anthropic's cloud infrastructure, rather than from your local device," and explicitly, "your MCP server must be reachable over the public internet from Anthropic's IP ranges." Private-network servers are called out as unsupported: "Servers hosted on a private corporate network, behind a VPN, or blocked by a firewall won't connect, even if you can reach them from your own machine" ([support.claude.com — Get started with custom connectors](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp); general connector docs at [claude.com/docs/connectors/custom/remote-mcp](https://claude.com/docs/connectors/custom/remote-mcp)). **This path is a non-starter for a Tailscale-only server** unless you additionally expose it to the public internet (e.g. Tailscale Funnel) and allowlist Anthropic's IP ranges — which defeats the "Tailscale-only, no public exposure" premise of this ticket.

2. **`claude_desktop_config.json`** (Settings → Developer → Edit Config), the same local-process mechanism used for local stdio servers. Anthropic's own quickstart for this file only documents `command`/`args` stdio entries (e.g. the filesystem server via `npx`) — [modelcontextprotocol.io/docs/develop/connect-local-servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers). There is **no documented native `url`/`type: http` entry for this config file** in Anthropic's docs; community reporting (a maintainer response in a modelcontextprotocol GitHub discussion) confirms Claude Desktop's config-file path is stdio (and, separately, a less-complete SSE) only, and that the practical workaround for remote HTTP here is a small local stdio↔HTTP bridge process, most commonly the community `mcp-remote` npm package, run via `npx`:
   ```json
   {
     "mcpServers": {
       "memory-keeper": {
         "command": "npx",
         "args": ["mcp-remote", "https://<tailscale-hostname>/mcp"]
       }
     }
   }
   ```
   ([GitHub discussion modelcontextprotocol/modelcontextprotocol#1940](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/1940); config path itself documented at [modelcontextprotocol.io/docs/develop/connect-local-servers](https://modelcontextprotocol.io/docs/develop/connect-local-servers)). Because `mcp-remote` is spawned locally by Claude Desktop and makes its outbound HTTP request from the user's own device — which is on the tailnet — **this path does reach a Tailscale-only server**, unlike the Custom Connectors path. `mcp-remote` is a community project, not an Anthropic-maintained one, so treat it as a pragmatic bridge rather than a blessed long-term primary-source solution.

**Bottom line for this ticket**: Claude Code can talk to a Tailscale-only Streamable HTTP server natively with a one-line `claude mcp add`. Claude Desktop's *official* remote-server UI (Custom Connectors) cannot reach a Tailscale-only server at all because the connection is proxied through Anthropic's cloud and requires public-internet reachability; Desktop can only reach it by going through `claude_desktop_config.json` with a local stdio→HTTP bridge (`mcp-remote` or equivalent).

## 3. Authentication/session handling and whether Tailscale-only is a sane pattern

The MCP spec has a **separate, optional** authorization spec layered on top of the HTTP transport, and it is explicit that it's optional:

> "Authorization is **OPTIONAL** for MCP implementations. When supported: Implementations using an HTTP-based transport **SHOULD** conform to this specification. Implementations using an STDIO transport **SHOULD NOT** follow this specification, and instead retrieve credentials from the environment." — [Authorization spec, 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)

So there is no spec requirement to implement OAuth for an HTTP MCP server; it's a documented, optional layer you can simply not build. When implemented, the spec's authorization model is a fairly heavyweight OAuth 2.1 resource-server flow: MCP servers act as an OAuth 2.1 resource server, MUST implement OAuth 2.0 Protected Resource Metadata (RFC 9728), and rely on a (possibly separate) Authorization Server implementing OAuth 2.0 Authorization Server Metadata (RFC 8414) and, ideally, Dynamic Client Registration (RFC 7591) — same spec page. None of that is required if you simply don't advertise a `WWW-Authenticate`/protected-resource-metadata response; a server that never returns 401 with that header effectively opts out of the whole OAuth dance, and per the spec that's a legitimate configuration ("Authorization is OPTIONAL").

The transport spec's own Security Warning is the closest thing to a caveat against no-auth deployments, and it is phrased as a `SHOULD`, not a `MUST`: "Servers **SHOULD** implement proper authentication for all connections" — [Transports spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports). The other two bullets in that same warning (validate `Origin` header against DNS-rebinding; bind to localhost rather than 0.0.0.0 "when running locally") are the two protections that matter practically for a Tailscale deployment:
- **Origin validation is a MUST**, independent of the auth question — this guards against a browser-based DNS-rebinding attack that could hit the server from an unrelated web page even inside a private network, so the memory-keeper server should still validate `Origin`/`Host` even though it's Tailscale-only.
- **Binding**: "bind only to localhost" is guidance for a *local* deployment; for this ticket's use case the server intentionally needs to bind to the Tailscale interface (or `0.0.0.0` with Tailscale/firewall as the sole ingress path) rather than pure localhost, since the whole point is network reachability from other tailnet devices. Tailscale's own network-level ACLs are exactly the kind of access control that substitutes for the "authentication" the spec recommends — the spec doesn't say authentication has to be *application-level* OAuth, just that connections should be authenticated somehow, and network-layer (WireGuard-authenticated tailnet membership + Tailscale ACLs) is a legitimate substitute for a single-user personal server. This isn't something the primary sources bless explicitly as "sane for Tailscale," because the spec is transport/protocol-focused and silent on deployment topology — but nothing in the spec requires app-level auth, and the origin-validation MUST is the one piece of hardening worth keeping regardless.

Practical implication for the memory-keeper server: skip OAuth entirely (no `WWW-Authenticate`/Protected Resource Metadata responses needed), keep `Origin` header validation in the server implementation regardless (cheap, and it's a MUST independent of the auth decision), and bind the HTTP listener to the Tailscale interface/tailnet IP rather than 0.0.0.0-with-no-firewall.

## 4. Known limitations / gotchas / maturity caveats today

- **Reconnection/resumability is optional, not guaranteed.** The spec only says servers "MAY" support resumable streams via SSE event IDs + `Last-Event-ID`; a server that doesn't implement this will simply drop in-flight streaming responses on disconnect, requiring the client to retry/re-initialize — [Transports spec, Resumability and Redelivery](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports). Don't assume a naive server implementation survives a laptop sleep/wake or a brief Tailscale route flap without a client-side retry.
- **Multiple concurrent clients**: the transport is explicitly designed for it ("the server operates as an independent process that can handle multiple client connections" — same spec page), but *stateful* session handling (the optional session-ID mechanism) is server-implementation-defined; for a genuinely single-user personal server this is low-risk, but if you ever run Claude Code + Claude Desktop simultaneously against the same server, make sure the server implementation doesn't assume a single global session.
- **Stateless-mode memory leak in the official Python SDK**: `modelcontextprotocol/python-sdk` issue #756 reported that the `StreamableHTTPSessionManager`'s stateless-mode task group never exits, and its internal task list grows unboundedly with every request, leaking memory over the life of a long-running process ([python-sdk#756](https://github.com/modelcontextprotocol/python-sdk/issues/756)). The issue is tracked as resolved/closed in the SDK's tracker, but it's a concrete reminder that Streamable HTTP server-side implementations (in either official SDK) are still young enough to have this class of bug; a long-lived personal server process should be restarted periodically or monitored for memory growth until you've confirmed your SDK version is past this fix.
- **Claude Desktop does not natively speak Streamable HTTP via its config file** (see §2) — this is arguably the single biggest practical gotcha for this ticket, since the natural assumption ("just put a `url` field in `claude_desktop_config.json`") doesn't work; you need the `mcp-remote` bridge (or write/vendor an equivalent) and accept a third-party (non-Anthropic) dependency in the client-side chain for Desktop specifically. Claude Code has no such gap.
- **Version-header casing/negotiation drift across spec revisions**: the session-ID response header was renamed from `Mcp-Session-Id` (2025-06-18) to `MCP-Session-Id` (2025-11-25) between spec revisions ([2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports), [2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)). Since HTTP headers are case-insensitive this is unlikely to break real implementations, but it's a sign the HTTP transport surface is still shifting between revisions — pin/track the SDK and spec version you build against, and expect small breaking changes if you jump SDK major versions.
- **SSE-only servers are legacy**: if any tooling/example you copy from still shows a bare SSE endpoint (`.../sse`) rather than a unified `/mcp` endpoint, that's the deprecated 2024-11-05 shape — both the spec and Claude Code's docs steer you away from it now ([Transports spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports); [code.claude.com/docs/en/mcp](https://code.claude.com/docs/en/mcp)).

## Summary / recommendation

- Build the memory-keeper server on **Streamable HTTP** (current transport; SSE-only is deprecated).
- For **Claude Code**: `claude mcp add --transport http memory-keeper https://<tailscale-hostname>/mcp` works directly, no bridge needed, since Claude Code runs locally on a tailnet-joined device.
- For **Claude Desktop**: do **not** use the built-in "Custom Connectors" UI — it proxies through Anthropic's cloud and requires public-internet reachability, which a Tailscale-only server doesn't have. Instead use `claude_desktop_config.json` with a local stdio→HTTP bridge (`mcp-remote` pointed at the Tailscale URL), the same pattern used for any local stdio server, since that bridge runs on the tailnet-joined device itself.
- **Tailscale-only, no app-level auth is a defensible v1 choice**: MCP's OAuth-based authorization layer is explicitly optional in the spec, so skipping it isn't a spec violation. Keep the transport's `Origin`-header validation (a MUST, independent of the auth decision) and bind the HTTP listener to the tailnet interface rather than an unfirewalled `0.0.0.0`.
- Budget for two immaturity risks regardless of the above: (1) reconnection is only a MAY in the spec, so expect to handle drops in the client; (2) at least one real memory-leak bug has existed in the official Python SDK's stateless HTTP mode, so monitor a long-running process until you're confident your SDK version is past it.
