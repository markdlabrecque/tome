# #34 addendum: what the pinned `mcp` 1.x line does with a client that fails to identify itself

Run 2026-07-27, Fedora box, `mcp` 1.28.1 from PyPI, Python 3.14.6, real stdio pipes,
hand-written 2025-11-25 frames. Instrument: `probe.py` + `srv.py` in this directory,
re-runnable with the two commands in `probe.py`'s docstring.

## Why this run exists

[`../34-adversarial-verification.md`](../34-adversarial-verification.md) established that on
1.28.1 **stateless mode** yields `client_params is None` (Probe A) and that on `mcp` `main` a
`clientInfo`-less request is **served** with `client_params=None` (Probe C). Neither arm asked the
question §9.4's `NULL` handling actually turns on: **on the pinned line, can a client produce a
missing or junk `source`?** Probe B answered it for `2.0.0b2`, not for 1.x.

Without this, "`NULL` means Tome is misconfigured, not that a client chose anonymity" rests on
reading `InitializeRequestParams.clientInfo` as a required pydantic field. That inference is
correct but it is an inference, and #34 exists because an inference of exactly that shape was
wrong last time.

## Result

```
mcp 1.28.1 | python 3.14.6

well-formed (control)    -> SERVED -> ['client_params=probe-client/9.9.9']
clientInfo key omitted   -> initialize REJECTED -32602 Invalid request parameters
clientInfo: null         -> initialize REJECTED -32602 Invalid request parameters
clientInfo: {}           -> initialize REJECTED -32602 Invalid request parameters
wrong types              -> initialize REJECTED -32602 Invalid request parameters
extra keys only          -> initialize REJECTED -32602 Invalid request parameters
name empty string        -> SERVED -> ['client_params=/1']
name whitespace only     -> SERVED -> ['client_params=   /1']
```

`InitializeRequestParams.model_fields` on the same install: `clientInfo` **required = True**,
alongside `protocolVersion` and `capabilities`; `task` and `meta` optional.
`LATEST_PROTOCOL_VERSION = 2025-11-25`.

## What it settles

1. **On the pin, a missing or mis-shaped `clientInfo` never reaches Tome.** It is refused at the
   handshake with `-32602`, not degraded. This is the opposite of `main`'s behaviour, where `_typed`
   silently turns a mis-shaped payload into `None` and serves the request. So the 2.x finding that a
   malformed payload is indistinguishable from an absent one **does not apply while pinned** — and
   becomes true the moment the pin lifts.

2. **`client_params is None` at capture time therefore indicts Tome, not the client** — stateless
   mode enabled, or the pin crossed. That is what licenses handling it as a `WARNING`-level health
   signal rather than a caller-facing one.

3. **One junk value does get through, and it is new.** `{"name": "", "version": "1"}` and
   `{"name": "   ", ...}` both pass validation and are **served**, so `clientInfo.name` can be an
   empty or whitespace-only string. Pydantic constrains the field's presence and type, never its
   content. Neither the ticket nor the prior verification anticipated this: every reachable-junk
   analysis stopped at `None`.

   Consequence, folded into §9.4: an empty or whitespace-only `name` is treated as **absent** —
   `NULL`, same warning. It is the absence case, not an exception to storing real names verbatim.
   No client Tome will meet does this (Desktop sends `claude-ai`, Claude Code `claude-code`), which
   is exactly why it would have been discovered in an immutable row rather than in a probe.

## Limits

- 1.28.1 only. The pin is `>=1.28,<2`, so a later 1.x could in principle tighten or loosen
  validation; re-run this on any bump, as with the `num_batch` ceiling probe (§6.4).
- stdio only. The validation lives in the shared `types.py` model rather than in a transport, so
  the streamable-HTTP edge should behave identically — **not** separately confirmed here.
- It probes the SDK's acceptance of frames, not any real client's behaviour. Which clients send
  what is #33 Gate A's evidence, not this run's.
