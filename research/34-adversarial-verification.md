# Adversarial verification of the three #34 claims

**Date of all checks: 2026-07-26.** Everything below was read from primary sources — the
`modelcontextprotocol/python-sdk` and `modelcontextprotocol/typescript-sdk` git trees at named
refs, the `modelcontextprotocol/modelcontextprotocol` spec repo via `gh api`, the PyPI registry,
and the installed Claude Code binary. `research/macos-spike-interface.md` was read only to learn
what was asserted; it is not cited as evidence for anything.

Where a code read alone would have left room for doubt, I ran the code. Four live probes are
reported (§5); they are the strongest evidence in this document and two of them contradict the
prior research.

**Pinned refs used throughout**

| Ref | Commit | Date |
|---|---|---|
| python-sdk `v1.28.1` | `777b8d06710c140e3606b0d4598e2aa48546c266` | 2026-06-26 |
| python-sdk `v2.0.0b2` | `2713b53b127afc094dc97d6067df9f69b647661c` | 2026-07-14 |
| python-sdk `main` | `dcd9c1ee9fcb0d4acdfb4403a83b20a8bb550039` | 2026-07-26 11:45 +0100 |
| typescript-sdk `main` | `1e1392e3f91583884fe82a0b4b91335875c3fba6` (tag `@modelcontextprotocol/client@2.0.0-beta.5`) | 2026-07-21 |
| spec repo `main` | fetched via `gh api` | 2026-07-26 |
| Claude Code | `/home/mark/.local/share/claude/versions/2.1.220`, build 2026-07-24T22:17:45Z | installed |

---

## 1. Claim 1 — "SDK v1.28.1 matches PRD §7.5 exactly"

### Verdict: **CONFIRMED** (all four sub-assertions, plus the stateless consequence, verified — the last one empirically)

**`_client_params` is instance state.** `python-sdk` `v1.28.1`, `src/mcp/server/session.py`:

- L76 `class ServerSession(BaseSession[...])`
- L86 `    _client_params: types.InitializeRequestParams | None = None`
- L108–109
  ```python
  def client_params(self) -> types.InitializeRequestParams | None:
      return self._client_params  # pragma: no cover
  ```
- L180, inside `_received_request`'s `case types.InitializeRequest(params=params):` branch:
  `self._client_params = params`

`ServerSession.__init__` (L88–103) takes `stateless: bool = False` and sets
`self._initialization_state = InitializationState.Initialized if stateless else ...NotInitialized`.
It never touches `_client_params`, which therefore stays at its class-level `None` unless an
`initialize` request actually arrives on that session object.

**`mcp.server.fastmcp.FastMCP` exists at that tag.** `git ls-tree v1.28.1 src/mcp/server/` lists a
`fastmcp/` directory containing `server.py`. Confirmed.

**Stateless mode really does produce `client_params is None` at `tools/call`.**
`v1.28.1` `src/mcp/server/streamable_http_manager.py`, `_handle_stateless_request` (L168–215):

```python
logger.debug("Stateless mode: Creating new transport for this request")
http_transport = StreamableHTTPServerTransport(
    mcp_session_id=None,      # L185
    ...
)
...
await self.app.run(read_stream, write_stream,
                   self.app.create_initialization_options(), stateless=True)  # L197-202
...
await http_transport.terminate()  # L215
```

A fresh transport, a fresh `ServerSession(stateless=True)`, and a teardown, per HTTP request.

**Probe A (see §5) confirms it on the wire**, against `mcp==1.28.1` installed from PyPI, using the
SDK's own `streamablehttp_client`:

```
stateful  -> client_params.clientInfo=probe-client/9.9.9
stateless -> client_params=None
```

PRD §7.5 (`PRD.md:1088`) and the §13.2 row at `PRD.md:1704` describe the shipped v1.28.1 code
correctly, mechanism and consequence.

### Is v1.28.1 the version the project would build against today?

Two separate answers, and the second one is the live issue.

- **v1.28.1 is the current stable.** PyPI `mcp` `info.version` = `1.28.1`. It is also the newest
  `v1.*` tag in the repo, and the `v1.x` branch is still maintained (`c0c5a9d6`, 2026-07-25).
- **It will not be the version `uv add mcp` resolves after 2026-07-28.** `python-sdk` `main`
  `README.md:21`: *"Stable v2 is targeted for 2026-07-28, alongside the spec release."* And
  `README.md:19`: *"If your package depends on `mcp`, add a `<2` upper bound to your version
  constraint (for example `mcp>=1.27,<2`) **before the stable release lands**."*

So claim 1 holds today and holds for as long as Tome pins `<2` — but "the version this project
would build against" is a decision that has not been made and, if left unmade for two more days,
resolves to 2.x by default. See §4.

**Also worth knowing:** `v1.28.1` `src/mcp/types.py:27` sets `LATEST_PROTOCOL_VERSION = "2025-11-25"`,
and `grep 2026-07-28` over the whole `v1.x` branch `src/` returns nothing. A 1.x server does not
speak the 2026-07-28 protocol at all. That is what makes claim 1 durable under a `<2` pin — and it
is also the cost of that pin.

---

## 2. Claim 2 — "On `main` (2.0.0b2), `client_params` has moved to a `Connection` object"

### Verdict: **PARTIALLY CONFIRMED.** Every mechanical assertion is true of `main`. The parenthetical "(2.0.0b2)" is materially wrong: the published 2.0.0b2 does *not* contain the optional-`clientInfo` behaviour, and on 2.0.0b2 a `clientInfo`-less request is **rejected**, not served with `client_params = None`.

### What is true on `main` (`dcd9c1ee`, 2026-07-26)

**`ServerSession` is a per-request proxy forwarding to `Connection`.** `src/mcp/server/session.py`:

- L3 (module docstring): *"A per-request proxy built by the kernel for each inbound request."*
- L41 `self._connection = connection`
- L44–46
  ```python
  def client_params(self) -> types.InitializeRequestParams | None:
      return self._connection.client_params
  ```
- L49–56, `client_capabilities`: *"Prefer this over `client_params.capabilities`: on 2026-07-28+
  the request envelope declares capabilities while client info stays optional, so capabilities can
  be present without `client_params`."*

**`Connection` is always present.** `src/mcp/server/connection.py:2-3` (module docstring):
*"Always present on `Context` (never `None`), even in stateless deployments."* Field declaration at
L150–156 carries the spec citation: *"settable on its own for the modern envelope, where
capabilities are required but client info is optional (spec PR #3002) — capability checks must not
depend on the peer having identified itself."*

**`from_envelope`'s both-present condition — the prior reading is exactly right.**
`src/mcp/server/connection.py:236-247`:

```python
info = _typed(Implementation, client_info)
capabilities = _typed(ClientCapabilities, client_capabilities)
client_params = None
if info is not None and capabilities is not None:
    client_params = InitializeRequestParams(
        protocol_version=protocol_version,
        capabilities=capabilities,
        client_info=info,
    )
connection = cls(outbound, protocol_version=protocol_version, client_params=client_params)
connection.client_capabilities = capabilities
connection.initialized.set()
```

`client_params` ends as `None` when client info is absent *or malformed* (`_typed` swallows
`ValidationError` and returns `None` — docstring L74–80: *"A missing, null or mis-shaped value
falls through to `ValidationError` and is treated as not supplied so the request still routes"*).
Note the asymmetry the prior research did not state: a **malformed** `clientInfo` also yields
`client_params = None`, silently, with the request still served.

**Something else does surface client info separately from `client_params`.** Yes —
`Connection.client_capabilities` (set unconditionally at L246, independent of `client_params`), and
`ServerSession.client_capabilities` forwarding to it. That is capabilities, not identity: there is
no second channel carrying the client's *name*. If `client_params` is `None`, identity is gone.

### What is false about "(2.0.0b2)"

`main` is **19 commits ahead of `v2.0.0b2`**, and two of those commits are the ones the claim
depends on:

| Commit | Date | Subject |
|---|---|---|
| `837ef904` | 2026-07-23 | Align with spec #3002: optional clientInfo, serverInfo in result `_meta` (#3143) |
| `00a70148` | 2026-07-24 | Serve the 2026-07-28 protocol over stdio: decide the era from the opening request (#3152) |

At `v2.0.0b2`, `src/mcp/shared/inbound.py:407-415` reads all three envelope keys with **subscript,
not `.get()`**:

```python
try:
    meta = body["params"]["_meta"]
    protocol_version = meta[PROTOCOL_VERSION_META_KEY]
    client_info = meta[CLIENT_INFO_META_KEY]
    client_capabilities = meta[CLIENT_CAPABILITIES_META_KEY]
except (KeyError, TypeError):
    return InboundLadderRejection(code=INVALID_PARAMS, message="params._meta must carry the
        reserved protocol-version, client-info and client-capabilities envelope keys")
```

On `main` (`src/mcp/shared/inbound.py:420-426`) that became:

```python
if missing := [key for key in (PROTOCOL_VERSION_META_KEY, CLIENT_CAPABILITIES_META_KEY) if key not in meta]:
    return InboundLadderRejection(...)
protocol_version: Any = meta[PROTOCOL_VERSION_META_KEY]
client_info: Any = meta.get(CLIENT_INFO_META_KEY)
```

Also absent from `v2.0.0b2`: `Connection.client_capabilities` and `ServerSession.client_capabilities`
(both added by `837ef904`). Both quotations the prior research attributed to "main, which
corresponds to the `2.0.0b2` prerelease" — the `#3002` comment and the `client_capabilities`
docstring — are **post-b2 text**. They exist; they were not in the published beta.

**Probes B and C (§5) demonstrate the difference on real stdio pipes.** Same server code, same
hand-written 2026-07-28 envelope, only the SDK version differs:

```
mcp==2.0.0b2 (PyPI)      WITHOUT clientInfo -> ERROR {'code': -32602, 'message': 'Invalid request parameters'}
mcp @ main (dcd9c1ee)    WITHOUT clientInfo -> client_params=None client_capabilities=ClientCapabilities(...)   [request SUCCEEDS]
```

### Does the refactor break §7.5's mechanism, or preserve it?

**Neither — and this is the distinction the prior research collapsed.** It *obsoletes* the
mechanism and *replaces the failure mode with a different one*.

- §7.5's mechanism (per-session state set once at `initialize`) survives only on the **legacy era**.
  `main` `src/mcp/server/runner.py:714-751` (`_serve_legacy_stream`) builds one
  `Connection.for_loop(...)` for the stream and the handshake populates it. **Probe D** confirms:
  a 2025-11-25 `initialize` + `tools/call` over stdio on `main` returns
  `client_params=claude-code/9.9`.
- On the **modern era** there is no per-session state to lose, because identity rides every
  request. `main` `src/mcp/server/runner.py:752-798` (`_serve_modern_stream`) builds a **fresh
  `Connection.from_envelope(...)` per inbound request** — on stdio. The prior research's §3.3
  statement that *"On stdio the SDK builds exactly one connection object for the process's whole
  lifetime"* was true of `serve_loop`, and is no longer true of the path `MCPServer.run(transport="stdio")`
  actually takes since `00a70148` (2026-07-24, two days ago).
- So the prior research's "stateless-mode `None` was engineered away" is **half right**: the
  *stateless-mode* `None` is gone (there is no stateless flag to set wrong). A *new* `None` was
  engineered in, reachable on every transport, and not under the server's control.

The consequence for the PRD is therefore not "§7.5's reason reads as stale". It is: **§7.5's reason
is obsolete on 2.x, and the risk it was guarding against reappears from a different direction that
no server-side configuration choice can close.**

### Transport-independence

**Verified, same code path.** `Connection.from_envelope` is the sole constructor on the modern
path for both transports:

- stdio / duplex: `src/mcp/server/runner.py:778` inside `_serve_modern_stream`
- streamable HTTP: `src/mcp/server/_streamable_http_modern.py:391` (and `:242` for the
  schema-resolving `tools/list` walk), plus `src/mcp/server/streamable_http_manager.py:228`
- in-process: `src/mcp/server/runner.py:855` (`modern_on_request`)

`_streamable_http_modern.py:223-225` even mirrors the optionality on the outbound side:
```python
if verdict.client_info is not None:
    # Optional key: a conforming pair-only caller omits it rather than sending null.
    meta[CLIENT_INFO_META_KEY] = verdict.client_info
```

Probes B–D all ran over **real stdio subprocess pipes**, so the risk is demonstrated on the
transport the spike selected, not inferred from the HTTP path.

---

## 3. Claim 3 — "Draft protocol revision 2026-07-28 makes client info optional (spec PR #3002)"

### Verdict: **CONFIRMED**, with one correction of emphasis and one date the prior research did not surface

**PR #3002 is real, merged, and does exactly this.**
`gh api repos/modelcontextprotocol/modelcontextprotocol/pulls/3002`:

```json
{"number":3002,"title":"feat(schema): add optional serverInfo response metadata and make clientInfo optional",
 "state":"closed","merged":true,"merged_at":"2026-07-16T02:16:05Z","created_at":"2026-07-02T17:45:09Z",
 "base":"main","changed_files":17}
```

**The schema diff** (`schema/draft/schema.ts`, from the PR's own patch):

```diff
-  "io.modelcontextprotocol/clientInfo": Implementation;
+  "io.modelcontextprotocol/clientInfo"?: Implementation;
```
with the doc comment changed from *"Identifies the client software making the request. **Required.**"*
to *"Clients **SHOULD** include this field on every request unless specifically configured not to
do so."*

**The prose diff** (`docs/specification/draft/basic/index.mdx`), the per-request `_meta` table:

```diff
-| `io.modelcontextprotocol/clientInfo`  | `Implementation` | Yes | Client name and version |
+| `io.modelcontextprotocol/clientInfo`  | `Implementation` | No  | Client name and version |
```
`clientCapabilities` stays `Yes`. So "capabilities required, client info optional" is exact.

**The revision label is right.** `schema/draft/schema.ts:30`:
`export const LATEST_PROTOCOL_VERSION = "2026-07-28";`

**Which revision directory?** `draft` — and this is a small correction. There is **no
`2026-07-28` directory** in the spec repo yet: `docs/specification/` and `schema/` both list
`2024-11-25 / 2025-03-26 / 2025-06-18 / 2025-11-25 / draft`. The change landed on `draft`, which
*declares itself* as `2026-07-28`.

**Current released revision.** `https://modelcontextprotocol.io/specification/versioning`, fetched
2026-07-26: *"The **current** protocol version is [**2025-11-25**](/specification/2025-11-25/)."*
The prior research is right that 2026-07-28 is not yet current.

**Transport-independent — verified in the spec text, not inferred.**
`docs/specification/draft/basic/transports/stdio.mdx`, "Request Metadata":

> All request metadata for the stdio transport is carried inline in the JSON-RPC message body. The
> protocol version, per-request capabilities, and **optional client identity** live in
> `_meta.io.modelcontextprotocol/*`; the method name and arguments live where JSON-RPC puts them.
> There is no header layer.

**At the current released revision, `clientInfo` is still required.** `schema/2025-11-25/schema.ts:261`:
`clientInfo: Implementation;` (non-optional, inside `InitializeRequest.params`). Mirrored in the
python SDK at `src/mcp-types/mcp_types/v2025_11_25/__init__.py:1982`:
`client_info: Annotated[Implementation, Field(alias="clientInfo")]`.

### The date the prior research did not surface

`blog/content/posts/2026-05-21-mcp-2026-07-28-rc.md`, "Release Timeline and Validation":

> The release candidate is locked as of **May 21, 2026**. The final specification will be published
> on **July 28, 2026**.

and in the lede:

> The release candidate is available today and the final specification ships on **July 28, 2026**.

**2026-07-28 is two days from today.** The prior research's framing — *"the versioning page still
lists 2025-11-25 as current, so 2026-07-28 is draft"* — is literally true and practically
misleading. It is a draft with a published ship date inside this week, matched by a Python SDK
stable-v2 target on the same date and a TypeScript SDK already at `2.0.0-beta.5`.

---

## 4. Optional in the schema vs. absent in practice

This is the angle that most changes the ticket's urgency, and it cuts **against** panic.

**The spec still SHOULDs it, twice.** `docs/specification/draft/basic/index.mdx` (post-#3002):
*"Clients **SHOULD** include `io.modelcontextprotocol/clientInfo` on every request unless
specifically configured not to do so."*

**No official SDK client can omit it without being explicitly rewritten.**

| Client | Evidence | Can it omit `clientInfo`? |
|---|---|---|
| python-sdk `main` | `src/mcp/client/session.py:65` `DEFAULT_CLIENT_INFO = types.Implementation(name="mcp", version="0.1.0")`; L382 `self._client_info = client_info or DEFAULT_CLIENT_INFO`; L129 and L691 stamp `meta[CLIENT_INFO_META_KEY] = client_info` unconditionally | **No.** Omitting it yields the literal string `mcp`, not absence. |
| typescript-sdk `2.0.0-beta.5` | `packages/client/src/client/client.ts:632-634` — `constructor(private _clientInfo: Implementation, options?: ClientOptions)`, a **required positional argument**; `packages/core-internal/src/wire/codec.ts:129` `readonly clientInfo: Implementation` (non-optional in `OutboundEnvelopeMaterial`); `rev2026-07-28/codec.ts:132` stamps it into every outbound envelope | **No.** |
| Claude Code 2.1.220 | The installed binary constructs the TS-SDK v2 `Client` with a hard-coded literal: `new Client({name:"claude-code", title:"Claude Code", version: <consts>.VERSION ?? "unknown", description:"Anthropic's agentic coding tool", websiteUrl:…}, {capabilities:{}})`. (`class lMt extends V2r{constructor(e,t){super(t); this._clientInfo=e, …}` matches the TS-SDK v2 `Client` signature exactly.) | **No.** Not configurable; not conditional. |
| Claude Desktop | **Not checked** — no macOS host here, no bundle to read. It ships the same TS SDK; the constructor makes omission impossible without a fork. Inference, not verification. This is the spike's checklist item M4 and it is still open. | Presumed no. |

**Note the TS SDK's asymmetry, which is the whole shape of the risk.** Its *server* already accepts
the absence (`rev2026-07-28/codec.ts:61-66`: *"`clientInfo` is NOT here: spec PR #3002 demoted it to
SHOULD, so a request without it is accepted"*, with `REQUIRED_ENVELOPE_KEYS` holding only
protocolVersion and clientCapabilities) while its *client* cannot produce it. Both SDKs are
permissive on receive and unconditional on send. That is deliberate, and it means
**"permitted to be absent" is real and "will be absent" is not, for any client Tome will actually
see.**

**A genuine bonus fact the ticket does not have.** The same PR added, to `basic/index.mdx`:

> `io.modelcontextprotocol/clientInfo` and `io.modelcontextprotocol/serverInfo` are self-reported by
> the sender and are not verified by the protocol. They are **intended for display, logging, and
> debugging**. Implementations **SHOULD NOT** use them to change the behavior of the client or
> server, and **SHOULD NOT** rely on them for security decisions.

`source` is a provenance column read for display and audit, and `PRD.md:1564` already scopes it as
*"client type only … Not device"*. That lands inside the spec's blessed use and outside its
prohibition — as long as nothing downstream branches on `source`. Worth checking `PRD.md:322`'s
fallback-judgement signal against that sentence, since it is one step from behaviour.

---

## 5. The probes

Four runs, all on this Fedora box, 2026-07-26. Scripts under
`/tmp/claude-1000/-home-mark-Projects-tome/238b5b88-8f97-4dad-b2d7-f0896e28d204/scratchpad/`.

**Probe A — `mcp==1.28.1` from PyPI, streamable HTTP, FastMCP, SDK's own client.**
A tool returning `ctx.session.client_params`, served once with `stateless_http=False` and once
with `True`:
```
stateful  -> client_params.clientInfo=probe-client/9.9.9
stateless -> client_params=None
```
→ PRD §7.5's consequence is real on the stable line.

**Probe B — `mcp==2.0.0b2` from PyPI, real stdio subprocess, hand-written 2026-07-28 envelope.**
```
WITH clientInfo    -> client_params=claude-desktop/1.2.3 client_capabilities='NO-SUCH-ATTR'
WITHOUT clientInfo -> ERROR {'code': -32602, 'message': 'Invalid request parameters'}
```
→ Three findings at once: (i) the published beta already serves the modern per-request envelope
over stdio; (ii) it **requires** `clientInfo`; (iii) `ServerSession.client_capabilities` does not
exist on it. `import mcp.server.fastmcp` on this install raises `ModuleNotFoundError` and
`from mcp.server.mcpserver import MCPServer` succeeds — the rename is in the shipped package, not
just on `main`.

**Probe C — `mcp @ git+…@dcd9c1ee` (`main`), same server, same envelopes.**
```
WITH clientInfo    -> client_params=claude-desktop/1.2.3 client_capabilities=ClientCapabilities(...) session_id='NO-ATTR'
WITHOUT clientInfo -> client_params=None            client_capabilities=ClientCapabilities(...) session_id='NO-ATTR'
```
→ **The exact failure the ticket fears, reproduced.** A fully-served, non-error `tools/call` over
stdio with no client identity available to the handler.

**Probe D — same `main` build, legacy 2025-11-25 handshake over stdio** (`initialize` +
`notifications/initialized` + `tools/call`):
```
LEGACY 2025-11-25 stdio -> client_params=claude-code/9.9 ...
```
→ The legacy era on 2.x preserves §7.5's mechanism intact. Era, not transport, is the variable.

---

## 6. What the prior research overstated, understated, or got wrong

**Materially wrong**

1. **"`main` … corresponds to the `2.0.0b2` prerelease."** `main` is 19 commits ahead of the
   `v2.0.0b2` tag, and the two commits that make claim 2's key assertions true (`837ef904`
   2026-07-23, `00a70148` 2026-07-24) both post-date it. Every #3002-related quotation in §3.3 is
   post-b2 text presented as describing the published beta. On the actual b2, a `clientInfo`-less
   request is rejected with `-32602` (Probe B). This is the same failure pattern the task brief
   warned about: a confident version number attached to evidence read from a different ref.

2. **"On stdio the SDK builds exactly one connection object for the process's whole lifetime …
   There is no per-request session construction on this path."** True of `serve_loop`
   (`runner.py:467-497`), which is what was read. Not true of the path `MCPServer.run(transport="stdio")`
   takes: `serve_dual_era_loop` routes a modern opening request to `_serve_modern_stream`, which
   calls `Connection.from_envelope(...)` **per request** (`runner.py:778`). §3.3's *"The failure
   mode §7.5 guards against is structurally unreachable on stdio"* is therefore false on the 2.x
   modern era.

3. **"the SDK is already implementing it, and clients will follow"** — as a description of
   `2.0.0b2`, no. As a description of `main`, yes. The distinction matters because b2 is the thing
   a person can install today.

**Overstated**

4. **"a period of `clientInfo`-less captures is a permanent hole in provenance."** Presented as a
   forecast; it is a possibility with no identified cause. Both official SDK clients make
   `clientInfo` structurally unomittable, Claude Code hard-codes it, and the spec SHOULDs it. The
   prior research asserted "clients will follow" without checking a single client. §4 checks four.

5. **"§7.5's … *reason* is version-specific and will read as stale against 2.x."** Understates it in
   one direction and overstates it in another. The reason is not merely stale — the mechanism is
   *gone* on the modern era, replaced by a per-request envelope. But the recommendation attached to
   it ("be stateful") was never load-bearing on stdio anyway.

**Understated**

6. **The ship date.** "2026-07-28 is draft" is correct and buries the fact that the final spec
   publishes **2026-07-28** (RC blog, "locked as of May 21, 2026 … final … published on July 28,
   2026") and that stable python-sdk 2.0 targets the same day (`README.md:21`). Two days out.

7. **The upper-bound instruction.** `python-sdk` `main` `README.md:19` explicitly tells dependants
   to add `<2` *before* the stable release lands. Tome has no dependency file at all (see §7), so
   there is nothing carrying that bound.

8. **The malformed-`clientInfo` case.** `_typed` (`connection.py:74-86`) degrades a mis-shaped
   client info to `None` *silently*, and the request still routes. So `client_params is None` has
   two causes on 2.x, not one, and the second is a client bug rather than a client choice.

**Correct and worth saying so cleanly**

9. `from_envelope`'s both-present condition, the `Connection`-always-present docstring, the
   `ServerSession`-as-proxy description, the `#3002` and `client_capabilities` quotations (as
   descriptions of `main`), the FastMCP→MCPServer rename, the versioning page still reading
   2025-11-25, and every element of claim 1 — all verified accurate against the refs where they
   actually live.

---

## 7. Does the project pin anything?

**No. There is no dependency statement of any kind.** `git ls-files` in
`/home/mark/Projects/tome` (branch `spike/macos-target`, HEAD `ba7a9e4`) returns 26 files: three
top-level Markdown documents and `research/`. **There is no `pyproject.toml`, no `uv.lock`, no
`requirements.txt`, and no `src/`.** The only Python in the repo is `research/ladder-probe/*.py`,
an unrelated enrichment experiment.

`PRD.md` names the toolchain (`PRD.md:992`: *"Python 3.13+ on uv, with a uv-managed interpreter
pinned in the repo"*) and mentions `uv sync --frozen` in the deploy sequence, but **states no `mcp`
version constraint anywhere** — `grep -n "mcp>=\|mcp==\|1\.28" PRD.md` is empty.

So the "claim 2 may be true but inert" hypothesis is **not available**. Nothing is pinned, because
nothing exists to pin it in. Whichever `mcp` the first `uv add` resolves is the one Tome gets, and
after 2026-07-28 that is 2.x by default.

---

## 8. How urgent is this actually?

Separating the two risks the ticket runs together:

**Risk 1 — `source is None` because of a protocol change: LOW, and low for a checkable reason.**
Nothing in the evidence produces a `clientInfo`-less request from any client Tome will meet. Both
official SDKs make it structurally unomittable; Claude Code 2.1.220 hard-codes `"claude-code"`; the
spec SHOULDs it; the SDKs' permissiveness is receive-side only. The prior research's "clients will
follow" is unsupported by any client it examined. The residual exposure is a *malformed* (not
absent) `clientInfo` — a client bug, silently degraded to `None` by `_typed`.

**Risk 2 — the ground under §7.5 moves within the week: HIGH, and it is a dependency-management
risk, not a protocol one.** Three dates converge:

- **2026-07-28 (2 days):** final spec published; stable `mcp` 2.0 targeted the same day.
- **The day Tome's `pyproject.toml` is first written:** with no `<2` bound, `uv add mcp` after that
  date resolves 2.x. On 2.x: `mcp.server.fastmcp.FastMCP` does not exist (Probe B —
  `ModuleNotFoundError`), `ServerSession` is a per-request proxy, and `client_params` can legally be
  `None`.
- **First capture:** the point after which the raw layer's immutability makes any provenance
  mistake permanent.

**So the ticket's premise — "must be settled before the first capture" — is right, but for a
different reason than it states.** It is not that clients are about to stop identifying themselves.
It is that:

1. Tome pins nothing, and the default resolution flips in two days;
2. on the 2.x line the handler must read `client_params` defensively because the type is
   `InitializeRequestParams | None` and `None` is now a *served* outcome rather than a
   misconfiguration — the difference between a `None` that means "you set `stateless=True`" (which
   the PRD can simply refuse to do) and a `None` that means "the peer declined to say", which no
   server-side setting can prevent;
3. PRD §7.5's stated *reason* for statefulness (`PRD.md:1088`) becomes factually wrong the moment
   Tome is on 2.x, and §13.2's row at `PRD.md:1704` with it. Not stale — wrong. Neither should
   survive into implementation unedited.

Practically: the decision that must precede first capture is **the version bound**, and then the
one-line handling of `client_params is None`. The provenance-hole scenario is the tail risk that
handling covers, not the thing driving the deadline.

*(What `source` should record when `client_params` is `None`, and whether the column should exist
at all, are out of scope here and are the human's call.)*

---

## 9. Things the ticket does not anticipate

1. **Era, not transport, decides which mechanism applies on 2.x.** The same stdio server serves
   §7.5's one-connection model to a 2025-11-25 client (Probe D) and a per-request-envelope model to
   a 2026-07-28 client (Probe C), chosen by the client's *first frame*
   (`runner.py:599-641`, `serve_dual_era_loop`: *"The client's first request decides the
   connection's protocol era, once"*). Tome's `source` handling must be correct under both
   simultaneously, and the server does not get to choose.

2. **`session_id` is `None` on stdio, full stop.** `main` `src/mcp/server/context.py:82-88`:
   *"The transport's session id for this connection, when one exists. … **`None` on stdio and
   stateless HTTP**."* On the modern path it is worse than absent-by-default — `Connection.from_envelope`
   takes no `session_id` parameter at all (`connection.py:211-217`), so there is nowhere to inject
   one per connection. `PRD.md:322`'s fallback-judgement signal ("*`search_raw` immediately after
   `search_entities` in the same session is a relevance judgement*") has **no session grain to hang
   on** under 2.x-modern-over-stdio: every request is its own connection object. A server-minted
   process-lifetime UUID still works, but it must be minted by Tome in module scope, not read from
   anything the SDK provides — and on the modern era it is a *process* id, which for Claude Desktop
   is app-launch-to-quit, not a conversation. The prior research's §3.4 verdict ("survives, with a
   server-minted id replacing a transport-supplied one") reached the right answer from the legacy
   path's reasoning; on the modern path the grain question is worse than it recorded.

3. **`clientInfo` now carries more than name+version.** Claude Code 2.1.220 sends
   `title: "Claude Code"`, `description`, and `websiteUrl` alongside `name`/`version`. If `source`
   stores only `name`, that is a deliberate narrowing worth recording rather than an accident.
   It also confirms `name` is the stable machine-readable field and `title` the display one —
   relevant to checklist item M4.

4. **`mcp` 1.x cannot speak 2026-07-28 at all.** `v1.28.1` `src/mcp/types.py:27` caps at
   `2025-11-25`, and the whole `v1.x` branch has zero occurrences of `2026-07-28`. Pinning `<2` is
   the clean way to keep claim 1 true indefinitely — but it also means that when Claude Desktop or
   Claude Code opens with a modern envelope, a 1.x Tome will refuse it. The `<2` pin buys stability
   with a client-compatibility clock attached. That trade is not in the ticket.

5. **The result envelope now carries `serverInfo` too.** PR #3002's other half adds
   `io.modelcontextprotocol/serverInfo` to every result's `_meta` (SHOULD). `main`
   `src/mcp/server/runner.py:393` `_stamp_server_info` does this automatically. Tome will be
   advertising its own name and version to the client on every response, by default. Harmless, but
   it is an outbound identity disclosure that nothing in the PRD's egress reasoning (§1.2/§1.3)
   currently mentions.

6. **A malformed `clientInfo` is indistinguishable from an absent one** at the handler
   (`connection.py:74-86` + `:236-239`). Any sentinel scheme should not assume `None` means "the
   client chose anonymity".

---

## 10. Verdict summary

| # | Claim | Verdict |
|---|---|---|
| 1 | SDK v1.28.1 matches PRD §7.5 exactly, incl. stateless → `client_params is None` | **CONFIRMED** — code at `v1.28.1` + Probe A. Caveat: v1.28.1 is current stable *today*; stable 2.0 targets 2026-07-28 and nothing in Tome pins `<2`. |
| 2 | On `main` (2.0.0b2), `client_params` moved to `Connection`; always present; `from_envelope` both-present condition | **PARTIALLY CONFIRMED** — every mechanical assertion true at `main` `dcd9c1ee`; **"(2.0.0b2)" is wrong** — the published beta requires `clientInfo` and rejects its absence with `-32602` (Probe B). Refactor *obsoletes* §7.5's mechanism on the modern era rather than preserving it; the prior "engineered away" reading is half right. |
| 3 | Draft 2026-07-28 makes client info optional (spec PR #3002), independent of transport | **CONFIRMED** — PR #3002 merged 2026-07-16; `schema/draft/schema.ts` `Implementation` → `Implementation?`; `basic/index.mdx` table Required Yes→No; `stdio.mdx` "optional client identity"; `LATEST_PROTOCOL_VERSION = "2026-07-28"`. Corrections: it lives in `draft/`, there is no `2026-07-28/` directory yet; released revision is still 2025-11-25; **the final ships 2026-07-28, two days from this check**. |
| — | Any real client omits `clientInfo` | **REFUTED for every client checked** (python-sdk, typescript-sdk, Claude Code 2.1.220); **UNVERIFIED for Claude Desktop** — no host available; spike checklist M4 remains open. |
