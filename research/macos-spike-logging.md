# macOS spike — logging, retention, and the leak invariant

Research date: 2026-07-26. Spike: [#32](https://github.com/markdlabrecque/tome/issues/32), Agent 4 of 5.
Sections owned: **§7.10** (Observability), **§7.11** (the journald namespace and its retention), **§7.12** (the leak tripwire), **§8.3**'s scoped purge, **§5.10** (the `warnings` channel).
Background decision: [#26](https://github.com/markdlabrecque/tome/issues/26) (journald retention vs. retraction reach), which rests on [#23](https://github.com/markdlabrecque/tome/issues/23) Finding C.

**This is a thought experiment. Nothing here changes `PRD.md`.** Every example below is synthetic; no natural key, real or plausible, appears anywhere in this file.

**Claim status.** Every substantive claim is tagged **[documented]** (stated in a primary source, quoted or cited), **[measured]** (someone ran it and reported the number — none of it by me, since I am on Linux), or **[assumed]** (reasoned inference, explicitly not verified). The PRD's own standard, and §13.3 exists because it was not always met.

---

## Summary — the prediction held, but not for the reason the ticket gave

The spike ticket predicted this was the most damaged area and the one most likely to produce a **breaks** verdict. **It held.** But the damage does not fall where the hypotheses expected, and the failure is sharper and more interesting than "macOS has no `LogNamespace=`".

The one-sentence version:

> **On macOS unified logging, "bounded retention" and "checkable invariant" are each individually reachable and jointly unreachable, and there is no scoped purge at any setting.** The remediation loop §7.12 closes cannot be closed.

The three knobs macOS actually offers are per-subsystem and documented — that part of hypothesis 2 is **wrong** — but none of them is a retention bound:

| What §7.11/§7.12 needs | macOS mechanism | Result |
|---|---|---|
| Tome's log lines are persisted so a daily scan has something to scan | `Persist: Info` per subsystem **[documented]** | ✅ works — and *increases* what is on disk |
| Retention of those lines is bounded to a stated number of days | *nothing* — eviction is **size-driven, system-wide** **[documented]** | ❌ no bound exists, in either direction |
| Nothing from Tome ever reaches disk | `persist:off` per subsystem **[documented]** | ✅ works — and makes the tripwire structurally impossible |
| Purge Tome's log lines only | *nothing* — `log erase` takes `--all` or `--ttl`, no predicate **[documented]** | ❌ the only purge is the whole Mac's log |

And two findings that are worse than the ticket anticipated, because they are about the *ordinary* path rather than the exotic one:

1. **The retention gradient is inverted relative to leak risk.** Apple's own table: Info is *not* persisted; Error and Fault are **[documented]**. §7.10's carve-out exists precisely because the exception path — Postgres's `ON CONFLICT` `DETAIL` line, Ollama's error path — is where an unowned string can carry a Natural Key. On macOS those land at Error/Fault, in the `Special` store, which is the **longest-retained** thing on the box **[documented]**. Tome's content-free INFO narrative, meanwhile, evaporates from memory in minutes. macOS keeps exactly the lines invariant C is least able to police and discards the ones it is most confident about.

2. **Postgres cannot be brought inside any Tome-scoped bound at all.** §7.11's flat, asterisk-free statement — *"Including it means the bound covers every process that can touch memory content"* — depends on `LogNamespace=` being settable on a distro-packaged unit via a drop-in. On macOS, Homebrew's Postgres formula sets `log_path`/`error_log_path` to `<prefix>/var/log/postgresql@NN.log` **[documented, from the formula]**, a single plain file with no rotation and no retention. The one process that can emit a Natural Key writes to an **unbounded** store, forever. That is not a decade; it is no bound at all.

**The honest answer is hypothesis 4, and it is not a consolation prize.** Tome writing plain files under its own control, rotated by `logging.handlers.TimedRotatingFileHandler(when='midnight', backupCount=30)`, reproduces §7.11's two knobs *exactly* — `MaxFileSec=1day` is `when='midnight'`, `MaxRetentionSec=30day` is `backupCount=30` — with **zero** host facilities, identically on both targets. The scoped purge becomes `rm` plus a truncate, which is **strictly more complete** than `journalctl --namespace=tome --rotate --vacuum-time=1s`, because a plain-file purge has no "vacuum skips active files" caveat to work around. And Postgres joins the bound by pointing `log_directory` at the same place, which needs no host cooperation on either target.

**Yes, this is better on Fedora too, and that is the finding that outlives the macOS question.** The costs are real (§6 below itemises them honestly, including two that are not obvious) but they are smaller than they look, because §7.11 *already* accepted that `journalctl -u tome-enrich` returns nothing. The operator already has to learn a non-default incantation. `tail -F /var/lib/tome/log/tome-enrich.log` is not a harder one.

### Per-section verdicts

| Section | If unified logging is kept | If Tome writes its own files |
|---|---|---|
| **§7.10** Observability — invariant C, `log_exception()`, `configure_logging()` | **Survives unchanged.** The rule is code-level and ports without edit. Its *rationale* strengthens. | **Survives unchanged.** |
| **§7.10** "stdlib logging to stdout, captured automatically, no timestamp in the format" | **Breaks.** launchd has no journald-equivalent stdout capture; it has `StandardOutPath`, which is a file **[documented + measure item]**. And a file needs the timestamp back. | **Survives with a substitute** — an explicit handler and an explicit timestamp. Same edit either way. |
| **§7.11** The namespace and its 30-day privacy bound | **Breaks — no acceptable substitute.** No per-subsystem retention exists. `persist:off` is retention-zero but kills §7.12. Postgres cannot be enclosed. | **Survives with a native substitute that is exact rather than approximate.** |
| **§7.11** The whole-box 4 GB *capacity* drop-in | **Dissolves.** It was justified entirely by Ollama's journal volume; on macOS Ollama logs to `~/.ollama/logs/server.log` **[documented, Ollama's own troubleshooting doc]** and is not in the unified log at all. | Dissolves, same reason. |
| **§7.12** The leak tripwire | **Breaks.** Not because of process substitution — that hypothesis is **killed** — but because `lines_scanned` is structurally ~0 at the default persist level, and the one setting that fixes it is the one that removes the bound. | **Survives with a substitute that is cheaper and wider** — `grep -rFf <(psql …)` over a directory, with Postgres's log inside it. |
| **§8.3** The scoped purge | **Breaks.** `log erase` is global. Firing it spends the entire machine's diagnostic history — the blunt variant §8.3 already rejected when it cost only 30 days of *Tome's* history. | **Survives, improved.** Scoped exactly, reaches the active file, no rotate dance. Bounded by APFS local snapshots (§6.4). |
| **§8.3** "Retraction owes journald nothing, and this is structural" | **Loses one of its two legs.** The argument is (a) per-entry deletion is impossible *and* (b) residue ages out in 30 days. On macOS (b) is false. The sentence must be restated or the conclusion withdrawn. | **Survives**, and (a) inverts — per-entry deletion in a text file is trivially possible, so the "structural, not declined" framing becomes "declined, on cost". A wording change, not a decision change. |
| **§5.10** The `warnings` channel | **Loses a producer.** Six become five: the tripwire row has no producer, and the table's only operator-cleared persistent warning disappears with it. | **Survives unchanged**, all six producers intact. |

---

## 1. How the unified log actually stores and evicts

Establishing this first, because both hypothesis 2 and hypothesis 3 turn on it and the popular understanding is wrong in both directions.

### 1.1 The persistence table is Apple's, and it is the load-bearing fact

From Apple's *Generating Log Messages from Your Code* **[documented]**:

> The system stores all messages in memory initially, and it writes messages with more severe log levels to disk.

| Log level | Persisted to disk | Apple's note |
|---|---|---|
| Debug | **No** | "verbose information during development" |
| Info | **Only when collected with the `log` tool** | "helpful, but not essential" |
| Notice (Default) | **Yes, up to a storage limit** | "essential for troubleshooting" |
| Error | **Yes, up to a storage limit** | — |
| Fault | **Yes, up to a storage limit** | — |

And, in the same document:

> Normally, the system stores debug and info messages only in memory, but you can write info messages to disk using the `log` command-line tool. For the other message types, the system compresses the messages and writes them to the on-disk data store. **When that data store exceeds a predefined size, the system purges old messages to make room for new ones.**

That last sentence is Apple stating, in a primary source, that eviction is **size-driven, not time-driven**. There is no `MaxRetentionSec` because there is no time axis in the policy at all.

### 1.2 The stores, and their sizes

The on-disk layout is `/private/var/db/diagnostics/` plus `/private/var/db/uuidtext/`, and it splits by entry class **[documented in the `log` man page's `--file`/archive handling; the folder breakdown and sizes are from Howard Oakley's *Inside the Unified Log* series, which is careful secondary work rather than a primary source — treat the numbers as [measured] by him, not by Apple]**:

| Store | Holds | Reported behaviour |
|---|---|---|
| `Persist/` | the bulk of Default-level entries | tracev3 files ≤ ~10.5 MB each, folder held to a **~520–530 MB target**, so ~50 files. Coverage reported as **8–12 hours on a constantly-running Mac**, days on one that sleeps |
| `Special/` | **Fault and Error entries** | 2.0–2.1 MB files, "progressively weeded", purged **by type and content rather than size**; entries here "may last considerably longer" — reported elsewhere as up to ~29 days |
| `Signpost/` | performance signposts | purged slower than Persist, faster than Special |
| `HighVolume/` | — | "seldom if ever used" |
| whole of `/var/db/diagnostics` | — | ~1–2 GB total |

Two consequences that matter directly:

- **The retention *floor* is unpredictable and can be very short.** 8–12 hours is well inside the window §7.11 calls "the gap between something breaking and you noticing it". A laptop that sleeps a lot lands somewhere between that and weeks, driven by *other software's* log volume, not Tome's. **[assumed]** that a laptop with Ollama, Xcode, and a browser on it sits at the noisy end.
- **The retention *ceiling* is unbounded in the sense that matters for privacy.** No policy says "gone by day 30". If the machine goes quiet for a month, a month-old line is still there. #26's whole point was that "until rotation" is not a bound; on macOS "until the Persist folder fills" is the same class of non-bound, just with a different constant.

### 1.3 There is no `logd` size knob

**[documented, negatively]** — Apple documents no user-facing control over the Persist target, and Oakley states flatly that there is "no option to increase [the size limits] to allow logs to be retained for longer". Nor to *decrease* them. The `log` man page has no such option; the MDM payload (§2.2) has no such key.

### 1.4 One thing that improves: the capacity problem dissolves

§7.11's whole-box `SystemMaxUse=4G` drop-in is **not a privacy decision** — the PRD says so explicitly — and is justified "entirely by Ollama's ~20k lines/day". On macOS, Ollama's own troubleshooting documentation says **[documented]**:

> Find the logs on **Mac** by running the command: `cat ~/.ollama/logs/server.log`

Ollama on macOS writes a plain file in the user's home directory and never touches unified logging. The Windows section of the same doc shows `server.log` plus numbered `server-#.log` archives, so Ollama **[assumed]** rotates its own file. Either way, the capacity pressure that justified the whole-box cap does not exist on this target. That row of §7.11 **dissolves** — the problem is absent, not solved differently.

(It is replaced by a smaller question that belongs to Agent 5 / Agent 3: `~/.ollama/logs/server.log` sits inside the home directory and therefore inside Time Machine's default scope. §7.11's measurement — all 160,988 Ollama journal lines read, no prompts or responses at default verbosity — should be **re-run against `server.log`** before assuming it carries no memory content, because it is a different code path from the systemd unit's stderr.)

---

## 2. Hypothesis 2 — "there is no `LogNamespace=` equivalent"

**Verdict: half wrong, and the half that is wrong does not help.**

There *is* a per-subsystem configuration mechanism, it is documented by Apple, and it is finer-grained than journald's namespaces (subsystem *and* category, versus journald's per-unit namespace assignment). What it cannot express is a retention bound.

### 2.1 What `log config` actually offers

From `man 1 log` **[documented, verbatim]**:

```
log config [--reset | --status] [--mode mode(s)]
    [--subsystem name [--category name]] [--process pid]
```

with:

```
--mode mode(s)   Will enable given mode.  Modes include:
                 level: {off | default | info | debug}
                 The level is a hierarchy, e.g. debug implies debug, info,
                 and default.
                 persist: {off | default | info | debug}
                 The persist mode is a hierarchy, e.g. debug implies debug,
                 info, and default.
```

Two orthogonal hierarchies. `level` controls what is **captured into memory**; `persist` controls what is **written from memory to disk**. Both are settable per subsystem, per category, or system-wide. Changes take effect immediately and are recorded into logging profiles **[documented]**.

The persistent form is a plist, and Apple documents it directly in *Customizing Logging Behavior While Debugging* **[documented, verbatim]**:

> You can also override the logging behavior of a specific subsystem by creating and installing a logging configuration profile property list file in the `/Library/Preferences/Logging/Subsystems/` directory. Name the file using an identifier string, in reverse DNS notation […]

```xml
<dict>
    <key>DEFAULT-OPTIONS</key>
    <dict>
        <key>Level</key>
        <dict>
            <key>Enable</key>
            <string>Info</string>
            <key>Persist</key>
            <string>Inherit</string>
        </dict>
    </dict>
    <key>server-connections</key>
    <dict>
        <key>Level</key>
        <dict>
            <key>Enable</key>
            <string>Debug</string>
            <key>Persist</key>
            <string>Inherit</string>
        </dict>
    </dict>
</dict>
```

Apple documents exactly two keys inside `Level` (`Enable`, `Persist`) and exactly four values (`Inherit`, `Default`, `Info`, `Debug`). **No retention key appears in Apple's documentation of this file.**

So the analogue of `LogNamespace=tome` + `/etc/systemd/journald@tome.conf` is:

| Fedora | macOS | Equivalent? |
|---|---|---|
| `LogNamespace=tome` on a unit | `os_log_create("com.example.tome", …)` — a *subsystem string chosen by the code*, not by the service manager | **Better in one way, worse in another.** Finer-grained (per category), but it is a property of the *process's own logging calls*, not of the service definition — so it cannot be imposed on a third-party binary. This is precisely why Postgres cannot be enclosed (§4.4). |
| `/etc/systemd/journald@tome.conf` | `/Library/Preferences/Logging/Subsystems/com.example.tome.plist` | Same shape, different contents |
| `MaxRetentionSec=30day` | — | **No equivalent** |
| `MaxFileSec=1day` | — | **No equivalent, and the concept does not apply** — tracev3 files are shared across all subsystems, so file-granularity rotation cannot be per-subsystem |
| `SystemMaxUse=1G` | — | **No equivalent**; the ~520 MB Persist target is global and unadjustable |

### 2.2 The MDM payload confirms the gap from the other direction

Apple publishes the schema for every configuration-profile payload in the `apple/device-management` repository. `mdm/profiles/com.apple.system.logging.yaml`, in full **[documented, verbatim]**:

```yaml
payloadkeys:
- key: Processes
  type: <dictionary>
  content: Not to be used.
- key: Subsystems
  type: <dictionary>
  content: A dictionary enabling the logging level for subsystems. See `Customizing
    Logging Behavior While Debugging` for more details about the format of the dictionary.
- key: System
  type: <dictionary>
  content: This dictionary has one key, `Enable-Private-Data`. Setting that value
    to `true` enables private data logging for the entire system.
```

The subkeys of `Subsystems` are literally `ANY: <any>`, content `TBD`. Apple's *managed-device* surface for logging is three keys: don't-use, a pointer to the level document, and a global privacy override. **There is no fleet-management mechanism for log retention on macOS.** If one existed, it would be here.

### 2.3 The `TTL` key — the one genuine lead, and it does not survive scrutiny

Apple's *own* subsystem plists under `/System/Library/Preferences/Logging/Subsystems/` contain a `TTL` dictionary that Apple's developer documentation does not mention. `com.apple.TimeMachine.plist` reportedly carries `TTL` with `Default: 30` and `Debug: 10` **[measured, by Der Flounder, on macOS 15.4.1 — over 900 Apple subsystems enumerated]**. Oakley describes the key as "the period for which log entries are retained", configured through logging profiles **[documented, secondary]**.

If `TTL` were a settable *maximum*, hypothesis 2 would be dead and §7.11 would port. Four reasons it almost certainly is not:

1. **It is a floor-raiser, not a ceiling.** A `TTL: 30` on TimeMachine only means something if the *default* is shorter than 30 days — which §1.2 establishes it is, by a wide margin. A key whose observed use is "keep this longer than normal" is an extension mechanism. **[assumed, but strongly indicated]**
2. **`log erase --ttl` names TTL data as a distinct store.** The man page **[documented, verbatim]**: `--all` "Deletes main log datastore, and inflight log data **as well as time-to-live data (TTL)**, and the fault and error content"; `--ttl` "Deletes time-to-live log content." If TTL were a retention *policy* on ordinary entries, there would be nothing separate to erase. It reads as a side-channel that holds TTL-marked entries beyond ordinary attrition.
3. **Apple does not document it, in either the developer guide or the MDM schema.** Building §7.11's privacy bound — the section whose whole argument is *"you cannot argue that window is harmless, because by construction you do not know what is in it"* — on an undocumented plist key would be substituting one unknown for another. That is a worse trade than the Fedora status quo, not a better one.
4. **Even if it worked downward, it would not close §8.3.** TTL is a passive expiry, not a purge. The remediation loop needs an operator action that takes effect *now*.

**Recommendation: do not chase `TTL`.** It is a cheap measure-on-the-machine item (§9, item 4) and worth ten minutes of curiosity, but the design must not depend on the answer.

### 2.4 The finding that actually matters: the two goals are jointly unreachable

Setting aside TTL, the reachable configurations are:

| Configuration | Retention of Tome's lines | Can §7.12's tripwire run? | Post-hoc debugging |
|---|---|---|---|
| default (`persist: default`) | ERROR/FAULT → `Special`, longest-lived store, weeks. INFO → **memory only, minutes** | Only against the ERROR/FAULT lines. `lines_scanned` ≈ 0 for the ordinary path | Errors yes, narrative no |
| `persist: info` | everything, until the global size attrition takes it — **8 hours to weeks, unpredictable, unbounded above** | ✅ yes, fully | ✅ yes |
| `persist: off` | **none — nothing reaches disk** | ❌ **structurally impossible** — `log show` reads the datastore; there is nothing to read | ❌ none |

`persist: off` is a genuinely attractive answer to #26 taken alone: it is a *harder* privacy guarantee than `MaxRetentionSec=30day`, because the residue window collapses from 30 days to the in-memory ring. If #26 had been decided on macOS, `persist:off` would have been the obvious ruling.

But #26 did not stop at bounding. It went on to §7.12, and §7.12's argument is explicit about why:

> **The strong argument for automating was never the dataset** […] It is **regression detection**: a `uv sync` pulling a FastMCP that starts logging tool arguments is a leak no manual week-one check can see, by construction.

Under `persist:off`, that leak still *happens* — FastMCP's `DEBUG` line with the full `capture_entry` text is still constructed, still handed to the logging system, still sits in the in-memory ring, and is still visible to anyone running `log stream` at that moment — and **nothing can ever detect it**. You have traded a bounded, checkable residue for an unbounded, unmeasurable blind spot. §7.12 anticipated the shape of this: *"`lines_scanned` is why it is numbers and not a boolean — a check that scans nothing and finds nothing looks identical to a passing check."* Under `persist:off`, the check scans nothing **permanently, by design**.

So: **bounded (`persist:off`) or checkable (`persist:info`), not both.** On Fedora, `LogNamespace=tome` delivers both simultaneously and that is the entire content of #26's unlock. **This is the "breaks" verdict, and it is a clean one.**

---

## 3. Hypothesis 3 — "the scoped purge may have no equivalent"

**Verdict: confirmed, without qualification.**

`man 1 log`, in full **[documented, verbatim]**:

```
log erase [--all] [--ttl]
```

> **erase** — Delete selected log data from the system. If no arguments are specified, the main log datastore and inflight log data will be deleted.
> `--all` — Deletes main log datastore, and inflight log data as well as time-to-live data (TTL), and the fault and error content.
> `--ttl` — Deletes time-to-live log content.

"Selected" is a misnomer. There is **no `--predicate`, no `--subsystem`, no `--process`, no `--start`/`--end`** on `erase`. Contrast `log show`, `log stream` and `log stats`, all three of which take `--predicate`. The asymmetry is deliberate: reading is filterable, deleting is not.

There is also no lesser-hammer alternative:

- **Delete the tracev3 files by hand?** They are shared across every subsystem on the machine, in a proprietary undocumented format **[documented — Apple ships no format spec; the format is only reachable through Apple's closed tools, which is why third-party parsers like `mandiant/macos-UnifiedLogs` exist as reverse-engineering projects]**. Deleting one file removes Tome's lines *and* everything else written in the same window. That is `log erase` with extra steps and a corruption risk.
- **Rewrite a tracev3 file with Tome's entries removed?** No writer exists, Apple or otherwise.
- **`log collect` a filtered archive and swap it in?** `log collect` produces a `.logarchive` bundle for *reading*; it is not a datastore replacement, and its filters are `--start`/`--last`/`--size`, not predicates.

So the only remediation available is `sudo log erase --all`, which deletes the entire Mac's log — every subsystem, every process, the fault and error content, and TTL data. Evaluated against §8.3's own reasoning, this fails on exactly the ground §8.3 already used to reject something milder:

> **`retract_entry` does not fire it automatically** — that is the already-rejected blunt variant, spending 30 days of operational history to remove content invariant C says is not there.

If spending **30 days of Tome's own history** was too blunt to fire automatically, spending **the whole machine's diagnostic history** is too blunt to fire at all — including manually, on a laptop where that history is the only record of why Wi-Fi dropped, why a kernel extension misbehaved, or why the last panic happened.

**Consequence for §7.12 and §5.10.** The loop is:

> leak detected → persistent warning → operator runs the purge → next day's check reads zero → warning clears.

On macOS unified logging, step 3 has no acceptable action. The warning is persistent and **has no clearing condition** — the operator would have to wait out an eviction window they cannot predict or bound. A persistent warning with no clearing action is worse than no warning: §5.10's own design note is that persistent warnings are reserved for *cheap fixes*, precisely to avoid "alarm fatigue that would poison the genuine stuck-work channel along with it". A permanently-lit tripwire warning does exactly that poisoning.

That is the second half of the "breaks" verdict, and it damages a section (§5.10) that would otherwise have ported for free.

---

## 4. Hypothesis 1 — invariant C survives; its enforcement may not

**Verdict: the invariant survives unchanged. Its *stated* enforcement survives. Its *checked* enforcement breaks. And a native enforcement mechanism that looked like it might replace the check turns out to be structurally unavailable to Python — a genuinely interesting near-miss.**

### 4.1 The rule itself ports without a character changed

> **No text derived from a Raw Entry, and no Natural Key, ever reaches a log line — only ids, entity types, counts, durations, confidences, reason codes and model tags.**

Nothing in this sentence names a host facility. `log_exception()` — emit `type(exc).__name__` plus a curated message, never `str(exc)`, never psycopg's `diag.message_detail` — ports unchanged. `configure_logging()` — pin all non-`tome` loggers to `WARNING`, with the one-time third-party audit — ports unchanged, and the FastMCP-logs-tool-arguments hazard it exists for is host-independent. The identifier scheme (`raw_entry_id` + `entity_type` + `entity_id`) ports unchanged, including the observation that retraction makes the id dangle.

**§7.10's rejection of a hash also ports unchanged**, but with one macOS footnote worth recording rather than acting on. §7.10 rejects hashing on the grounds that coarse Person/Project keys are "perhaps 20 bits against a wordlist" and "a hash brute-forced in seconds is worse than plaintext, because it *looks* like protection". macOS offers a primitive that is not the thing §7.10 rejected: `%{mask.hash}` **[documented]** —

> The inclusion of the `mask.hash` option replaces the generic redaction text with a hash value that is **unique for the current process**. The mask value corresponds to the redacted value, but doesn't provide any identifying information about that value.

A per-process salt defeats the wordlist attack §7.10 named, and it preserves the correlation property (same key → same mask within a run) that a plaintext-free log otherwise loses. It is a real answer to a real objection. It is also **unusable here** for the reason in §4.3, and it would be reopening a closed decision on its merits, which this spike may not do. Recorded only so nobody rediscovers it as a novelty.

### 4.2 The native enforcement that almost exists

This is the part where macOS looks, briefly, much better than Fedora.

Apple **[documented, verbatim]**:

> By default, the system doesn't redact integer, floating-point and Boolean values, but **it does redact the contents of dynamic strings and complex dynamic objects.**

Read that against invariant C's allow-list: *"only ids, entity types, counts, durations, confidences, reason codes and model tags"*. Ids, counts, durations and confidences are integers and floats — **not redacted**. Everything else — every dynamic string, which is exactly the class a Natural Key or a Raw-Entry fragment belongs to — is **redacted at write time**, and the redaction is a *non-write*: the value never enters the store, so it is not recoverable later.

That is invariant C, enforced by the operating system, at the point of writing, by default. journald has no analogue and could not have one — it is a byte-stream sink with no notion of which parts of a line are literal and which are interpolated.

If that worked, §7.12 would not need to exist. The tripwire is a *check* precisely because C is *asserted*; a structurally-enforced C converts the check from load-bearing to belt-and-braces, and the whole §7.11/§7.12/§8.3 chain relaxes.

### 4.3 It does not work, and the reason is exact

os_log's privacy model is a **compile-time** property of the format string. The redaction decision is made by the compiler from the literal `%{public}s` / `%{private}s` / bare `%s` in the source, not at runtime from the value. Python has no compile-time format strings in the C sense.

`pyoslog` — the only maintained Python binding to os_log, and the one a Python service would realistically use — states this in its own README **[documented, verbatim, primary]**:

> All the pyoslog methods have the same signatures as their native versions, *except* for where a method requires a `format` parameter. **The `os_log` system requires a constant (static) format specifier, and it is not possible to achieve this via Python. As a result, all instances of format strings use `"%{public}s"`, and all messages are converted to a string before passing to the native methods.**

Every Python log line is one dynamic string, and it must be marked `%{public}s` or it would render as a single `<private>` with no content at all. **The privacy model is not weakened by pyoslog; it is bypassed entirely, and it has to be.** Writing a bespoke ctypes binding instead does not help — the constraint is os_log's, not pyoslog's.

So: **hypothesis 1's optimistic branch is killed.** macOS's structural enforcement of invariant C is real, is better than anything journald offers, and is unreachable from Tome's stack. C stays asserted-and-checked, exactly as on Fedora — and the check is the thing that breaks.

### 4.4 Postgres: the enclosure fails, and this is the worst single finding

§7.11, quoted in full because every clause of it fails differently:

> **Postgres is in the namespace** because it is the one remaining process that can emit a Natural Key (§7.10's `DETAIL`). Including it means the bound covers *every* process that can touch memory content, statable flatly with no asterisk about `ON CONFLICT`. **Also set `logging_collector=off`** so Postgres logs to stderr → journald → the namespace; if left on, PG writes files under the data dir instead — a *third* log store, outside journald, outside every bound here, and outside the dumps.

On macOS:

- **`LogNamespace=` has no launchd counterpart, and could not.** Tome's subsystem string is chosen inside Tome's own `os_log_create` call. There is no way for a service manager to say "this other process's output belongs to my subsystem", because unified logging has no ingestion path from a foreign process's stderr at all.
- **Homebrew's Postgres already writes a plain file.** From `Formula/p/postgresql@17.rb` **[documented, verbatim from the formula]**:
  ```ruby
  def postgresql_log_path
    var/"log/#{name}.log"
  end
  # …
  service do
    log_path f.postgresql_log_path
    error_log_path f.postgresql_log_path
  end
  ```
  `brew services` renders those into the launchd plist's `StandardOutPath`/`StandardErrorPath`. So Postgres's stderr — including the `ON CONFLICT` `DETAIL: Key (entity_type, natural_key)=(…) already exists.` line — goes to `<HOMEBREW_PREFIX>/var/log/postgresql@17.log`. One file. **No rotation configured by the formula, no size cap, no age cap.** The "third log store, outside journald, outside every bound" that §7.11 explicitly set `logging_collector=off` to avoid is, on macOS, *the default and the only option*.
- **Therefore `logging_collector=off` inverts.** On macOS, `logging_collector=**on**` is the correct setting, because Postgres's own collector is the *only* thing on this target that can bound the Postgres log: `log_rotation_age`, `log_rotation_size`, `log_filename` with a rotating pattern, and `log_truncate_on_rotation=on` together give exact, stated retention. A closed decision reverses under the host change — recorded as a finding for the synthesis, not as a change.
- **`log_parameter_max_length_on_error=0` ports unchanged.** It is a Postgres GUC, host-independent, and it is doing more work on this target, not less.

**Net:** on macOS with unified logging, §7.11's asterisk-free sentence becomes *"the bound covers Tome's own subsystem, on a retention policy it does not control, and does not cover the one process most likely to emit a Natural Key, which writes to an unbounded file."* #26's finding was that natural keys persist ~a decade. On macOS-with-unified-logging the corresponding statement is worse: **for the Postgres path, forever.**

Note that this failure is *not* fixed by any unified-logging configuration. It is fixed by §6 — put Tome's logs in files and point Postgres's collector at the same directory — and that fix is available on Fedora too, where it removes §7.11's dependence on being able to add a `LogNamespace=` drop-in to a distro-packaged unit.

### 4.5 The stdout capture assumption

§7.10 says: *"**stdlib `logging` to stdout**, captured by journald automatically, no timestamp in the format (journald adds one)."*

launchd does not do this. `man 5 launchd.plist` **[documented]** describes `StandardOutPath` as "what **file** should be used for data being sent to stdout when using stdio(3)" — a path, not a sink. Apple's *Creating Launch Daemons and Agents* shows the same **[documented, verbatim]**:

```xml
<key>StandardOutPath</key>
<string>/var/log/myjob.log</string>
```

and warns *"Do not change `stdio` to point to `/dev/null`. Include the `StandardOutPath` or `StandardErrorPath` keys in your daemon's configuration property list file instead"* — which only makes sense if the default is discard-or-worse rather than capture-into-a-system-log.

I could not find an Apple sentence stating the default when the keys are omitted **[the man page is silent; secondary sources split between "/dev/null" and "system.log", the latter almost certainly describing pre-10.12 ASL behaviour]**. **This is measure item 1 in §9** and it takes two minutes: a `ProgramArguments` of `/bin/echo hello`, no `StandardOutPath`, then `log show --last 1m --predicate 'process == "echo"'`.

Whatever the answer, the design consequence is the same and is not in doubt: **there is no route from Python's stdout into a *named subsystem*.** Even in the best case where stdout is captured, it would be captured with no subsystem, no category, and therefore outside every per-subsystem control in §2. To get a subsystem you must call `os_log_create`, which means pyoslog, which means §4.3.

Two smaller riders:

- **"No timestamp in the format" inverts.** journald stamps every line. A file does not. The formatter must add `%(asctime)s` back. Trivial, but it is a line in §11.8's build obligations that changes.
- **`SyslogIdentifier=` per unit has no launchd key.** The substitute is the os_log *category* (if unified logging) or the filename (if files). Either works; this is Agent 3's territory but the resolution differs by which logging answer wins.

---

## 5. Hypothesis 5 — the tripwire's mechanics

**Verdict: the two properties the hypothesis worried about both survive. The tripwire breaks for a different reason.**

### 5.1 Process substitution — hypothesis killed

§7.12's `<(psql …)` is not a macOS problem.

- **zsh** is the default login and interactive shell on macOS from Catalina onward **[documented, Apple Support HT208050]**, and supports `<(…)`.
- **`/bin/bash` 3.2.57** ships with macOS **[documented]** and supports `<(…)`; process substitution has been in bash since 2.0.
- Both rely on `/dev/fd`, which Darwin provides.
- **The real constraint is symmetric across hosts and already applies.** `<(…)` is a shell feature, and neither `systemd`'s `ExecStart=` nor launchd's `ProgramArguments` runs a shell — both `exec` directly. So on *both* targets the tripwire must be invoked as `/bin/zsh -c '…'` (or `/bin/bash -c '…'`), or live in a script. That is a fact about service managers, not about macOS.

The "never writes a keys file" property — the one §7.12 cares about, given "a public repo one `git add -A` away from publishing exactly the artifact ruled out permanently" — **survives intact**.

### 5.2 Counts only — survives

`keys_checked`, `keys_suppressed`, `lines_scanned`, `hits` are all shell arithmetic over stdout. Nothing in unified logging forces content into the record. `log stats --predicate '…'` **[documented]** would even give a cheap `lines_scanned` without decoding message bodies.

One genuinely macOS-specific hazard, and it is benign here: `log show` renders redacted fields as the literal string `<private>`. Since pyoslog marks everything `%{public}s` (§4.3), nothing Tome writes is ever redacted, so `<private>` cannot silently swallow a hit. Worth knowing; not a problem.

A hazard that is **not** macOS-specific but is worth naming because the tripwire runs unattended on both targets: `grep -Ff` with a pattern file containing a **blank line** matches *every* line. If `select natural_key from entities` ever returns an empty string, `hits` becomes `lines_scanned` and the persistent warning fires forever. Guard with `psql -At -c "select natural_key from entities where natural_key <> ''"` or a `grep -v '^$'` in the substitution. Same on Fedora; recorded here because it is the kind of thing a port re-exposes.

### 5.3 The actual break: `lines_scanned` is structurally zero

The read side is fine mechanically. The man page gives us **[documented, verbatim]**:

```
log show --predicate 'subsystem == "com.example.my_subsystem"'
log show --last 1d --info --style compact
```

So the direct translation of §7.12 is:

```sh
log show --last 1d --info --style compact \
  --predicate 'subsystem == "com.example.tome"' \
  | grep -Ff <(psql -At -c "select natural_key from entities where natural_key <> ''")
```

This runs. It does not work, for the reason in §1.1 and §2.4: at the default persist level, **Tome's INFO narrative was never written to disk**, so `--last 1d` returns only whatever ERROR/FAULT lines were emitted — typically none on a healthy day. `lines_scanned` reads 0 or single digits, permanently. §7.12 named this exact failure mode as the reason the check reports numbers instead of a boolean; on macOS it becomes the steady state.

Setting `persist: info` fixes `lines_scanned` and is the only configuration in which the tripwire is meaningful — and it is the configuration with no retention bound and no purge. §2.4 again.

### 5.4 Three secondary costs of scanning the unified log

Recorded because they would surface in week one and are all avoided by §6.

1. **`log show` is expensive.** An unfiltered `log show --last 1h` "can return millions of entries and take minutes to complete" **[measured, secondary]**; a subsystem predicate helps a great deal but the tool still decodes the whole datastore window to apply the filter. §7.12 chose daily cadence explicitly to avoid "a journal scan every 15 minutes to find nothing"; on macOS even the daily scan is a multi-minute, multi-core operation on a laptop that may be on battery. Contrast a `grep` over a ~3 MB directory of text (§6.1), which is milliseconds.
2. **The scan cannot see Postgres.** §4.4. On Fedora, `LogNamespace=tome` on `postgresql.service` put the `DETAIL` line *inside the scanned namespace* — the tripwire's most valuable single target. On macOS, that line is in a Homebrew file the predicate cannot reach. The tripwire would have to grep that file separately, at which point you are already running the file-based design for half the problem.
3. **The store is swept into `sysdiagnose`.** A `.logarchive` inside a sysdiagnose bundle is "the contents of the two folders `/var/db/diagnostics` and `/var/db/uuidtext`" **[documented, secondary but consistent across sources]**, and sysdiagnose bundles are routinely generated and *sent to Apple* during support interactions. This is a genuinely new consideration with no Fedora analogue: on the current target, journald content leaves the box only if Mark carries it off. On macOS, anything in Tome's subsystem has a routine, one-keystroke path off the machine. It touches §1.3's named egress exceptions, which were reasoned against a tailnet and did not contemplate a diagnostic-bundle path. **A log store under Tome's own control in a non-standard location is not swept up.** Flagging for Agent 2 / synthesis.

---

## 6. Hypothesis 4 — abandon the system logger

**Verdict: yes, and the recommendation is not target-specific. This is the finding that outlives the macOS question.**

### 6.1 The two journald knobs have an exact, host-free reproduction

§7.11's bound is two directives, and §7.11 is emphatic that both are load-bearing:

> **`MaxFileSec=1day` is load-bearing — without it the retention number is fiction.** `MaxRetentionSec=` deletes whole **files**, not entries, so at the default `MaxFileSec=1month` a month-spanning file is deleted only once its *newest* entry is 30 days old: an effective bound near **60 days**.

That is precisely the semantics of Python's own rotating handler:

```python
logging.handlers.TimedRotatingFileHandler(
    "/var/lib/tome/log/tome-enrich.log",
    when="midnight",     # ≡ MaxFileSec=1day
    backupCount=30,      # ≡ MaxRetentionSec=30day
    utc=True,
)
```

Same two-knob structure, same file-granularity semantics, same coupling — and stdlib, so no dependency, no host facility, no distro packaging, no `LogNamespace=` drop-in on a unit Tome does not own, and identical behaviour on Fedora and macOS. `backupCount` is a *count of files* and `when` fixes one file per day, so the product is exact rather than approximate. It is arguably a cleaner statement of §7.11's intent than the journald pair, because the coupling that §7.11 has to explain in a paragraph is structural in the API.

The host-native alternative also exists on both sides if it is ever wanted — `newsyslog.conf(5)` on macOS **[documented]** takes `count` and `when` fields with exactly this meaning (`$D0` for daily, `count` for how many archives survive), and `logrotate` does the same on Fedora. **Neither is needed**, and both would reintroduce a host dependency for no gain. Note in passing: macOS's *plain-file* rotation facility is more expressive about retention than its *system logger* is, which is a strange thing to be true and is a small piece of evidence that Apple does not consider the unified log a retention-managed store at all.

**Volume sanity check [assumed, arithmetic not measurement].** Under invariant C the namespace is, in §7.11's word, "quiet": roughly 10 lines per enrichment run at ~100 bytes, 96 runs/day → ~100 KB/day → **~3 MB for the whole 30-day window**. A `SystemMaxUse=1G` equivalent is not needed; a free-space guard is not needed. This also re-confirms §7.11's observation that size-based rotation could never rescue the bound, on either target.

### 6.2 The purge becomes better than the one §8.3 specifies

Fedora today:

```sh
journalctl --namespace=tome --rotate --vacuum-time=1s
```

with §8.3's caveat that `--rotate` is *required, not optional*, "because vacuum skips active files".

Files:

```sh
rm -f /var/lib/tome/log/*.log.*        # rotated archives
: > /var/lib/tome/log/tome-enrich.log  # and the active file, in place
```

Two differences, both improvements:

- **It reaches the active file.** journald's vacuum cannot, which is why the rotate dance exists. Truncating an open file in place is atomic from the reader's point of view and does not disturb the running handler's fd.
- **It is exactly scoped, with nothing else in the blast radius.** Same as the journald form on Fedora, and *categorically* better than `log erase --all` on macOS.

§8.3's sentence *"Retraction owes journald nothing, and this is structural rather than declined"* needs restating under this design, and the restatement is a wording change rather than a decision change. The current argument has two legs: (a) per-entry deletion in journald does not exist, and (b) under invariant C there is nothing there anyway and residue ages out in 30 days. With files, leg (a) inverts — per-entry deletion in a text file is a `sed -i`, so it becomes *possible* and must be **declined on cost and coherence** rather than dismissed as impossible. Leg (b) is unchanged and is the one carrying the weight. The conclusion survives; the justification loses its cheapest sentence. Worth writing down because it is the sort of thing that quietly rots.

### 6.3 What is actually lost — itemised, including the two non-obvious ones

| Lost | Real cost | Mitigation |
|---|---|---|
| `journalctl -u tome-enrich` / `log stream` / Console integration | **Smaller than it looks.** §7.11 already accepts that `journalctl -u tome-enrich` returns nothing and that the working form is `journalctl --namespace=tome -u tome-enrich`, and puts that in the runbook. The operator already pays a non-default incantation. | `tail -F /var/lib/tome/log/tome-enrich.log` — arguably the more familiar incantation, not the less |
| Structured metadata / indexed fields (`_PID`, `_SYSTEMD_UNIT`, boot id; subsystem/category/activity) | **Already declined.** §7.10 rejected `structlog`, rejected the journal binding, and states that per-entry queryability lives in `enrichment_events`, with journald carrying only "the operational narrative". A narrative does not need indexed fields. | Format string carries level, logger name, pid |
| **Automatic capture of a hard crash** | **Real, and the one genuine loss.** A `logging` handler lives inside the process. A segfault, a `SIGKILL` from memory pressure, or anything written to stderr outside `logging` (a bare traceback, a C-library warning) bypasses it. journald catches all of that for free because it owns the pipe. | Two-part: point the unit's stderr at a file **in the same bounded directory** (`StandardError=append:/var/lib/tome/log/tome-enrich.stderr` on systemd; `StandardErrorPath` on launchd — both give the same result), and install a `sys.excepthook` routing through `log_exception()`. **Note the tension honestly:** a raw traceback in that stderr file can carry a Natural Key, which is exactly the carve-out's territory — so that file must be inside the rotation and inside the tripwire's scan, not outside them. On macOS, `ReportCrash` still writes `/Library/Logs/DiagnosticReports/*.ips` regardless, so *crash* capture specifically is not lost on that target. |
| **A store that survives Tome's own disk being full or its directory being wrong** | Minor but real: journald is somebody else's problem; a self-managed directory is Tome's. A permissions or path mistake silently loses logging, and there is no second place it lands. | `0700`, owned by `tome`, created by `make deploy`, and a startup assertion that the directory is writable. §7.12's `lines_scanned` is already the sentinel that would catch a silently-empty store — its value here goes up, not down |
| journald's Forward Secure Sealing | Not used, not relevant single-user | — |

### 6.4 What macOS specifically adds, that Fedora does not

Three new obligations for a plain-file store on the hypothetical target. All are cheap; none is optional; two would be easy to miss.

1. **Spotlight will index it.** `mds` indexes file *contents* in user-accessible locations. A leaked Natural Key in a log file would become a durable entry in the Spotlight index — a second store, outside the rotation, outside the purge, that the tripwire cannot see. Mitigation is one file: drop `.metadata_never_index` in the log directory, or `mdutil -i off` on the path. **[documented mechanism; applicability to the specific chosen path is [assumed] and is measure item 6.]**
2. **APFS local snapshots bound the purge's promise.** Apple **[documented, Apple Support 102154]**: Time Machine "saves one snapshot of your startup disk approximately every hour, and keeps it for 24 hours", automatically removing them "when space is needed on the disk or when they are older than 24 hours". A file deleted at 14:00 still exists inside the 13:00 snapshot. So on macOS, the purge's guarantee weakens from *"gone now"* to **"gone from the live filesystem now, and from local snapshots within 24 hours"**. This does **not** break the loop — the next day's tripwire greps live files and correctly reads zero — but it makes the promise a 24-hour one, and that is a sentence §8.3 would need. It is precisely parallel to §8.3's existing "removes content from the live store immediately, and from backups within 7 days", so the PRD already has the idiom for it. Note this hits `log erase --all` too: it is not more complete, only more destructive.
3. **Placement must dodge iCloud and Time Machine.** If the log directory landed under `~/Documents` or `~/Desktop` with Desktop & Documents Folder syncing on, Tome's operational log would sync to iCloud — an egress path §1.3 never contemplated. Keep it outside the home directory (Agent 3 and Agent 5 own the placement decision; this is the constraint from my side), and exclude it from Time Machine explicitly.

Fedora has no counterpart to any of the three. This is a small, concrete data point for the synthesis's portability-boundary question: *operational plumbing did not port for free even in the direction that was supposed to be host-agnostic* — writing a text file acquired three host-specific obligations.

### 6.5 Is it better on Fedora too? Yes — argued, with the counter-case stated

The case for:

- **The retention bound stops depending on a facility Tome does not own.** §7.11's design needs a `LogNamespace=` drop-in on `postgresql.service` — a distro-packaged unit. That works today and is a legitimate use of a drop-in, but it is a dependency on Fedora's packaging that a package update can disturb and that has to be re-verified after every major PG upgrade. `log_directory` pointed at Tome's own directory has no such dependency and is a Postgres GUC, i.e. it ports to macOS unchanged (§4.4).
- **One store, one bound, one purge, one scan.** Today the tripwire scans a journald namespace; the Postgres file case is *prevented* by `logging_collector=off` rather than *covered*. With files, `grep -rFf <(psql …) /var/lib/tome/log/` covers Tome and Postgres in the same command, and `lines_scanned` is a real number over a real corpus.
- **The purge gets strictly more complete** (§6.2 — it reaches the active file, which journald's cannot).
- **The check gets cheap.** ~3 MB of text versus a journald namespace scan today, versus a multi-minute `log show` on macOS. Cheap enough that "explicitly not after every incremental run" could be revisited — though it should not be, because §7.12's reasoning for daily cadence was about signal, not cost.
- **It removes an asymmetry the PRD already flags as awkward.** §7.11 has to spend a paragraph explaining why `MaxRetentionSec` alone is a fiction without `MaxFileSec`. The `when`/`backupCount` pair does not need the explanation.

The case against, stated fairly:

- **It is a change to a closed decision's implementation on a target where the current answer works.** #26 is closed, it is correct for Fedora, and "works" is a high bar to clear. This spike may not reopen it on the merits — so this belongs in the synthesis's *decisions-that-would-need-re-deciding* list, as a re-decision prompted by evidence, not as a change.
- **It gives up the crash-capture property**, which is the only thing on the loss list that is not already accepted or already paid (§6.3). The mitigation is sound but is new code (`sys.excepthook`) and a new file in the rotation, and it puts raw tracebacks — the highest-risk strings in the system — inside Tome's store rather than someone else's.
- **It adds a directory Tome must own correctly**, with mode, ownership, a deploy step, and an exclusion from `pg_dump`'s reach and from any future backup scope (§8.2 excludes `/opt/tome`; a log directory under `/var/lib/tome/` would need naming).
- **"Better on both targets" is a claim about a target that does not exist yet.** Its Fedora half stands on its own; its macOS half is only load-bearing if the spike goes anywhere.

**On balance: the plain-file design wins on every criterion #26 itself used to decide — boundedness, statable-without-an-asterisk coverage, purgeability, and checkability — and loses on one criterion #26 did not weigh (crash capture) with a mitigation that is real but not free.** That is a strong enough result to state plainly, which the ticket asked for.

---

## 7. Load-bearing PRD sentences that stop being true

Collected separately because these are the specific edits a port would force, and because two of them are the kind of sentence that stays in a document long after it stops being accurate.

| § | Sentence | What happens |
|---|---|---|
| 7.10 | "stdlib `logging` to stdout, captured by journald automatically, no timestamp in the format (journald adds one)" | **False on macOS.** No automatic capture; a file needs the timestamp back |
| 7.11 | "journald retention is per-namespace, not whole-box. […] So this was never a decision about the machine." | **Inverts.** On macOS the retention policy *is* whole-box and unadjustable — #23's original framing, which #26 disproved for Fedora, is correct for macOS |
| 7.11 | "Including it means the bound covers *every* process that can touch memory content, statable flatly with no asterisk about `ON CONFLICT`." | **False.** Postgres is structurally outside any Tome-scoped bound; §4.4 |
| 7.11 | "Also set `logging_collector=off`" | **Reverses** to `on`, for the same reason the original said `off`: keep the key-bearing line inside a bounded store |
| 7.11 | "residue ages out of the namespace within 30 days" | **No such number exists.** 8 hours to weeks, driven by other software's volume |
| 7.11 | Whole-box `SystemMaxUse=4G` capacity drop-in | **Dissolves** — Ollama is not in the unified log on macOS |
| 7.12 | "This gives the scoped purge a trigger, closing the loop" | **The loop cannot close.** No scoped purge exists |
| 8.3 | "Retraction owes journald nothing, and this is structural rather than declined" | **Loses a leg.** Under unified logging, clause (b) is false; under files, clause (a) inverts to "declined" |
| 8.3 | The scoped purge command itself | **No equivalent** under unified logging; **improved** under files |
| 5.10 | "The journald leak tripwire found a hit — **persistent**, cleared by the scoped purge" | **Producer disappears** under unified logging; six warnings become five, and the table loses its only operator-cleared persistent entry |
| 12.3 | "#23: 'bounding journald retention is a decision about the whole machine' — **False, and that was the unlock.**" | **Target-specific.** The correction is right for Fedora and wrong for macOS. If a second target is ever taken, this row needs a host column |
| 13.2 | "The leak tripwire needs a collision allowlist and cannot see retracted keys" | **Survives, and gains a third clause on macOS:** it also cannot see Postgres |

---

## 8. Verdicts, restated

**§7.10 — Observability.** **Splits.** Invariant C, the carve-out, `log_exception()`, `configure_logging()`, the identifier scheme and the hash rejection all **survive unchanged**; they are code-level and name no host facility. The *transport* sentence — stdout captured automatically, no timestamp — **survives with a native substitute** (an explicit handler, an explicit timestamp), and that substitute is the same edit whether the destination is os_log or a file. The `SyslogIdentifier=` line **survives with a substitute** (category or filename).

**§7.11 — The namespace and its retention.** **Breaks (no acceptable substitute)** on unified logging: no per-subsystem retention exists in either direction, the one setting that gives retention-zero destroys §7.12, and Postgres cannot be enclosed at all. **Survives with a native substitute** if Tome writes its own files, and the substitute is *exact* where the journald original needed a paragraph of explanation. The whole-box capacity drop-in **dissolves** independently.

**§7.12 — The leak tripwire.** **Breaks** on unified logging. Not on the grounds the hypothesis proposed — process substitution and counts-only both survive cleanly, and that half of hypothesis 5 is **killed** — but because `lines_scanned` is structurally near-zero at the default persist level, the setting that fixes it removes the bound, the scan cannot reach Postgres, and the scan is expensive enough to be a real cost on a battery-powered machine. **Survives with a substitute that is cheaper and wider** under the file design.

**§8.3's scoped purge.** **Breaks** on unified logging: `log erase` has no scoping of any kind, and the only available action is one §8.3's own reasoning already rejected in a much milder form. **Survives, improved** under the file design, with a new 24-hour APFS-snapshot caveat that fits the guarantee idiom §8.3 already uses.

**§5.10 — The `warnings` channel.** **Survives unchanged as a mechanism** — it is an MCP return value and has no host coupling. But under unified logging it **loses one of six producers**, and specifically the only one whose persistence is cleared by an operator action. That is collateral damage from §8.3, not a defect in §5.10. Under the file design it survives with all six intact.

**Overall: the ticket's prediction held.** This is the most damaged area I would expect any of the five agents to report, and it produces a genuine **breaks** verdict — but only on the assumption that the port keeps using the system logger. **The verdict is contingent, and the contingency is the recommendation.** If Tome logs to its own files, every section in my scope survives, several improve, and the improvement is available on the current target today.

---

## 9. Measure on the actual MacBook

Ordered by value-per-minute. Items 1–3 are the ones where reading has genuinely run out.

1. **Does launchd stdout reach the unified log at all?** `ProgramArguments = [/bin/echo, tome-probe-0001]`, no `StandardOutPath`, `launchctl bootstrap` it, then `log show --last 2m --info --predicate 'process == "echo"'`. Settles §4.5, which no source I found states plainly. ~2 min.
2. **What is the real Persist coverage on *this* machine?** `log show --last 30d --style compact 2>/dev/null | head -1` gives the oldest surviving entry; `sudo du -sh /var/db/diagnostics/*` gives the split. This is the single number that says whether unified logging's *de facto* retention is 8 hours or 3 weeks on a real M4 Pro laptop — and it is the number #26 would have needed. ~1 min.
3. **How long does a realistic tripwire scan take?** `time log show --last 1d --info --style compact --predicate 'subsystem == "com.apple.TimeMachine"' | wc -l`, on battery, watching `powermetrics`. If this is minutes and watts, it settles §5.4's first point empirically rather than by citation. ~5 min.
4. **Does a user-set `TTL` shorten anything?** Write `/Library/Preferences/Logging/Subsystems/com.example.probe.plist` with `DEFAULT-OPTIONS → Level → {Enable: Info, Persist: Info}` and a `TTL` of `{Default: 1}`, emit tagged lines for a few days, and see whether they vanish at 24 h or ride the ordinary attrition. The only way to resolve §2.3, and the design must not depend on the answer. ~4 days elapsed, ~10 min of work.
5. **Confirm `persist:off` really produces nothing on disk.** `sudo log config --mode "persist:off" --subsystem com.example.probe`, emit, then `log show --last 5m --info --predicate 'subsystem == "com.example.probe"'`. Confirms the §2.4 table's third row is real rather than inferred from the man page. ~3 min.
6. **Does Spotlight index the intended log path?** Write a file containing a unique synthetic token to the candidate directory, wait, `mdfind tome-probe-0002`. Settles §6.4 item 1 for the specific path. ~2 min.
7. **Confirm the Homebrew Postgres log file and its growth.** `ls -la $(brew --prefix)/var/log/`, and check whether anything rotates it. Confirms §4.4's "unbounded" from the machine rather than from the formula. ~1 min.
8. **Read `~/.ollama/logs/server.log` the way §7.11 read the journal.** The 160,988-line audit that concluded "no prompts, no responses at default verbosity" was against the systemd unit's stderr. The macOS app is a different code path and the conclusion should not be assumed to transfer. ~15 min.
9. **`grep -Ff <(…)` under BSD userland**, invoked the way a launchd job would invoke it (`/bin/zsh -c`). Expected to pass; cheap to confirm rather than assume. ~1 min.

---

## 10. What I could not settle, and where I may be wrong

- **`TTL` semantics are genuinely unresolved.** My reasoning that it is an extension rather than a bound rests on three indirect signals (Apple's own 30-day value on a subsystem whose default retention is much shorter; `log erase --ttl` treating TTL content as a separate store; Apple documenting the key nowhere). All three are consistent with the opposite reading — that TTL is a hard per-entry expiry and Apple's 30 is simply a long one. **If TTL is a settable ceiling, §7.11 ports and my §2 verdict softens from "breaks" to "survives with an undocumented native substitute"** — which would still be a poor foundation for a privacy bound, but a different verdict. Measure item 4.
- **Persist-folder coverage numbers are Oakley's, not Apple's.** The ~520–530 MB target, the ~50 files, the 8–12 hours are careful measurement by a reliable third party, not a documented contract. Apple documents only "a predefined size" and "purges old messages". The *direction* of the finding (size-driven, unbounded in time, unadjustable) is documented; the *magnitudes* are secondary.
- **The `Special`-folder retention figure (up to ~29 days) is the weakest number in this document.** It appears in secondary sources with no Apple confirmation, and the mechanism is described as "by type and content" rather than by any stated rule. The claim I actually rely on — *Error and Fault are retained longer than Default, which is retained longer than Info* — is solid and comes from Apple's own persistence table. The specific ceiling is not.
- **I have not verified pyoslog against the current macOS release.** Its README, source and Handler mapping are current on `main` and the `%{public}s` constraint is architectural rather than versioned, so I am confident in the conclusion. But the package itself is one maintainer's, and adopting it would be adding exactly the class of dependency §7.10 declined for `python3-systemd`. That is an argument against unified logging that I have deliberately *not* leaned on, because it is about the dependency rather than the mechanism.
- **I did not evaluate a hybrid** — Tome's narrative to files, plus a handful of high-level lifecycle events to os_log for Console visibility. It is a coherent design and it is the one I would expect a macOS-native developer to propose. I omitted it because it reintroduces an unbounded, unpurgeable store for the sake of ergonomics, and invariant C's discipline gets harder, not easier, when there are two sinks with different rules. Worth a paragraph in the synthesis if anyone wants it.
- **`log_parameter_max_length_on_error=0` and the exact set of Postgres logging GUCs needed under `logging_collector=on`** were not worked through. That is a small piece of §11.8 that would need writing, and it overlaps Agent 5's Postgres-installation finding.

---

## Sources

Primary:
- [`man 1 log`](https://www.manpagez.com/man/1/log/) — full synopsis, `config --mode` level/persist hierarchies, `erase --all`/`--ttl`, predicate keys and examples. Also mirrored at [keith.github.io/xcode-man-pages/log.1.html](https://keith.github.io/xcode-man-pages/log.1.html)
- [`man 5 launchd.plist`](https://www.manpagez.com/man/5/launchd.plist/) — `StandardOutPath`/`StandardErrorPath` as file paths
- [`man 5 newsyslog.conf`](https://keith.github.io/xcode-man-pages/newsyslog.conf.5.html) — `count`/`size`/`when` fields
- Apple, [Generating Log Messages from Your Code](https://developer.apple.com/documentation/os/generating-log-messages-from-your-code) — the persistence-by-level table, size-driven purge, the privacy defaults, `%{public}`/`%{private}`/`%{mask.hash}`
- Apple, [Customizing Logging Behavior While Debugging](https://developer.apple.com/documentation/os/customizing-logging-behavior-while-debugging) — `/Library/Preferences/Logging/Subsystems/`, `DEFAULT-OPTIONS`, `Level`/`Enable`/`Persist`, the four values
- Apple, [Logging](https://developer.apple.com/documentation/os/logging) — supersession of ASL/Syslog
- Apple, [`apple/device-management` — `mdm/profiles/com.apple.system.logging.yaml`](https://github.com/apple/device-management/blob/release/mdm/profiles/com.apple.system.logging.yaml) — the complete MDM payload schema
- Apple, [Creating Launch Daemons and Agents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
- Apple, [About Time Machine local snapshots](https://support.apple.com/en-us/102154) — hourly, kept 24 hours
- Apple, [Use zsh as the default shell on your Mac](https://support.apple.com/en-us/HT208050)
- [pyoslog README](https://github.com/simonrob/pyoslog) and [`pyoslog/handler.py`](https://raw.githubusercontent.com/simonrob/pyoslog/main/pyoslog/handler.py) — the `%{public}s` constraint, verbatim; the Python-level → `OS_LOG_TYPE_*` mapping
- [Homebrew `Formula/p/postgresql@17.rb`](https://github.com/Homebrew/homebrew-core/blob/master/Formula/p/postgresql%4017.rb) — `postgresql_log_path`, `log_path`/`error_log_path`
- [Ollama `docs/troubleshooting.mdx`](https://github.com/ollama/ollama/blob/main/docs/troubleshooting.mdx) — `~/.ollama/logs/server.log` on Mac

Secondary (careful, but not Apple):
- Howard Oakley, [Inside the Unified Log 1: Goals and architecture](https://eclecticlight.co/2025/09/23/inside-the-unified-log-1-goals-and-architecture/), [3: Log storage and attrition](https://eclecticlight.co/2025/09/29/inside-the-unified-log-3-log-storage-and-attrition/), [How does macOS keep its log?](https://eclecticlight.co/2026/02/23/how-does-macos-keep-its-log/), [How long does the log keep entries?](https://eclecticlight.co/2026/03/12/how-long-does-the-log-keep-entries/), [Controlling what's written to the unified log](https://eclecticlight.co/2020/06/26/controlling-whats-written-to-the-unified-log/), [Control what gets written to the log](https://eclecticlight.co/2026/04/30/control-what-gets-written-to-the-log/), [Explainer: sysdiagnose and logarchives](https://eclecticlight.co/2026/06/27/explainer-sysdiagnose-and-logarchives/)
- Rich Trouton (Der Flounder), [Accessing subsystem logging configurations used by the macOS unified logging on macOS Sequoia](https://derflounder.wordpress.com/2025/05/05/accessing-subsystem-logging-configurations-used-by-the-macos-unified-logging-on-macos-sequoia/) — the `TTL` key observed in Apple's own subsystem plists
- [mosen, Configuration Profiles documentation — Unified Logging](https://mosen.github.io/profiledocs/payloads/logging.html) — community-documented profile keys including `TTL`, beyond Apple's published schema
- [mandiant/macos-UnifiedLogs](https://github.com/mandiant/macos-UnifiedLogs) — evidence that the tracev3 format is proprietary and only reverse-engineered
