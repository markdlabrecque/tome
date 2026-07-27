# macOS spike — service management and the laptop duty cycle

Research date: 2026-07-26. Spike ticket: **#32**. Branch: `spike/macos-target`.

**Area:** Agent 3 of 5. Sections owned: **§7.3** (unit inventory), **§7.6** (deployment), **§7.9** (storage placement and clock), **§4.8** (cadence, idle path, and staleness alarms), **§7.10** (observability — the service-management half; §7.11/§7.12 retention and the tripwire belong to Agent 4).

**Target under test:** MacBook, M4 Pro, 48 GB unified memory, macOS 26.x, launchd, APFS, FileVault, single machine, single user, no tailnet. The machine **sleeps, moves, and runs on battery**.

---

## 0. Evidence conventions, and one thing to read first

The PRD's standard (§13.3 exists because it was not always met) is that a claim states how it is known. This document uses four labels:

| Label | Means |
|---|---|
| **Documented** | Stated in a primary source — an Apple man page, Apple developer documentation, an Apple header, or CPython's own docs. Quoted where load-bearing. |
| **Reported** | Stated in a credible secondary source (Apple Developer Forums answers from Apple staff, long-standing Mac-admin references) and corroborated across at least two, but not in a primary spec. |
| **Reasoned** | An inference this document makes from documented facts. Sound or not, **nobody has run it.** |
| **Arithmetic** | A number derived from PRD-measured figures. Not a measurement of the new host. |

> **Read this before using anything below.** **Nothing in this document is measured.** There is no MacBook attached to this research; every claim about how the target behaves is documented, reported, or reasoned. Section 11 lists what a two-hour session on the actual machine would settle better than any amount of reading, and several of the items there could change conclusions in section 6.

**Coordination.** Agent 5 owns how Postgres is installed (Homebrew / Postgres.app / container). That choice determines the service-management story below, so §2.4 states the conclusions **conditionally on each route** rather than picking one. Agent 2 owns whether the MCP server has an HTTP edge at all; if stdio transport wins, `tome-mcp` stops being a service — §2.3 and §2.6 state both branches.

---

## 1. Summary

### 1.1 Per-section verdicts

| Section | Verdict | One-line reason |
|---|---|---|
| **§7.3** unit inventory — *the seven units* | **Survives with a native substitute, and shrinks** | Seven systemd objects become **four or five** launchd jobs (launchd has no separate timer object). Tome owns **two or three** of them. |
| **§7.3** — *system-not-user, on a hard constraint* | **Dissolves** | The constraint was cross-domain ordering. On macOS both Postgres and Tome live in the **same** domain (`gui/$UID`), so there is no domain to cross. The hard constraint evaporates — and takes its accepted costs (`sudo`, no notification bus) with it. |
| **§7.3** — *ordering and binding* | **Breaks, with an acceptable application-level substitute** | launchd has **no dependency model at all** — Apple's own words. `After=`/`Requires=`/soft-vs-hard is unexpressible. The substitute is connection retry in the application, which is what Apple documents you should do. |
| **§7.6** deployment — `/opt/tome` | **Survives unchanged, literally** | `/opt` is a firmlink on macOS. The path ports character-for-character. |
| **§7.6** — *the SELinux constraint* | **Dissolves, and a different constraint appears elsewhere** | `restorecon` and home-directory labelling have no analogue. TCC, plist ownership rules, and Background Task Management are real constraints but they bind on **different things** — and they do **not** make a dev-checkout deploy structurally impossible the way SELinux did. |
| **§7.9** storage placement | **Survives with a native substitute** | A path-for-path remap. The only interesting choice is Tome's own state directory, and it is unconstrained because none of the candidates is TCC-protected. |
| **§7.9** *clock* | **Dissolves** | The entire RTC / `set-local-rtc` / Windows-registry paragraph exists because of the dual boot. There is no dual boot and macOS keeps the RTC in UTC. The two *obligations* it created survive (one becomes vacuous, one gains a new cause). |
| **§4.8** cadence — *the ~15 min monotonic timer, no `Persistent=`* | **Survives with a native substitute, and the deliberate choice is the default** | `StartInterval` drops missed intervals across sleep and across a still-running job — documented, and exactly what `no Persistent=` plus the advisory lock were arranged to achieve. The design got what it asked for for free. |
| **§4.8** — *`OnBootSec≈5min`* | **Unexpressible; purpose served by an approximation** | launchd has no start-delay key. `StartInterval` without `RunAtLoad` delays the first firing by one interval, which serves the same purpose more coarsely. |
| **§4.8** — *the two cheap checks* | **Survives unchanged** | Advisory lock and pending-count are database facts. Nothing about the host touches them. And the section's shape is what makes the duty-cycle fix cheap — see §1.3. |
| **§4.8** — *staleness measured against uptime* | **Breaks. Silently, and with the sign flipped.** | See §1.4. **The highest-value finding in this document.** |
| **§7.10** observability — *stdout captured by the logger automatically* | **Breaks** | launchd routes a job's stdout **nowhere** unless told to. Apple's guidance is `StandardOutPath` (a plain file) or `os_log`. The zero-configuration capture that made §7.10's design cheap does not exist. |
| **§7.10** — *invariant C, the identifier scheme, the run shape* | **Survives unchanged** | Code-level rules. The host is not involved. |
| **§7.10** — *`SyslogIdentifier=` per unit* | **Survives with a weaker substitute** | Process name, or an `os_log` subsystem/category pair. |
| **§4.1 / §7.7** — *not owned, but broken by the duty cycle* | **Flagged for synthesis** | Full mode is 5–50 hours of work on a machine whose lid closes. §4.1's degradation contract ("`search_entities` errors for the duration") is calibrated in hours and becomes calibrated in **calendar weeks**. See §6.10. |

### 1.2 The one-paragraph answer on hypothesis 1

**launchd cannot express what systemd expressed — but the thing systemd was expressing has mostly ceased to exist.** §7.3 chose system units because a systemd *user* manager cannot order against `postgresql.service`. On macOS there is no such split: under the most likely install route Postgres is itself a **user** LaunchAgent in `gui/$UID`, the same domain Tome's jobs would live in. The domain mismatch dissolves. What does *not* dissolve is ordering itself — launchd has no ordering primitive whatsoever, by design ("launchd has no explicit dependency model", `man launchd.plist`). The failure mode this produces is **benign and self-healing**: `tome-mcp` started before Postgres fails its connection, exits, and `KeepAlive={SuccessfulExit: false}` restarts it after `ThrottleInterval` (10 s default) — which is `Restart=on-failure` with a floor. The honest fix is a connection retry loop in the application, which is exactly what Apple's own documentation tells you to build. **Net: the constraint is gone, the mechanism is gone, and the outcome is the same.**

### 1.3 The duty-cycle answer — the genuinely new question

Stated as plainly as I can:

1. **In steady state the problem is smaller than the hypothesis assumes.** At §1.5's 20 entries/day and §1.5's ~18 s/entry, enrichment is **~6 minutes of GPU work per day**, arriving as bursts of one or two entries (~18–36 s) roughly every fifteen minutes. That is not "an 18 s GPU burn while you type" as a continuous condition; it is a handful of sub-minute events per day.
2. **One structural fact removes most of the remaining fear.** On-device, **capture and enrichment share a duty cycle.** A backlog cannot accumulate while the machine is asleep, because you cannot capture into a sleeping machine either — capture is manual (§1.2) and the only client is on this machine. The "wake the laptop, get ambushed by three hours of queued work" scenario **cannot occur**. The desktop could accumulate a backlog while you were in Windows and a remote client kept capturing; the laptop cannot.
3. **No resource lever exists, and §7.7's reasoning for why that is acceptable ports verbatim.** `ProcessType`, `Nice`, `LowPriorityIO` all act on the enrichment runner, which is a thin HTTP client that is mostly blocked on a socket — the identical objection §7.7 already raised against cgroup limits. `ProcessType=Background` on Apple Silicon confines a process to E-cores at near-idle frequency; applied to the runner it throttles JSON parsing and Postgres writes and touches the GPU work not at all. Reaching the GPU work means throttling *Ollama*, which also throttles the interactive capture-embedding path — again §7.7's exact objection. **The only lever available is *when* to run, not *how hard*.**
4. **Therefore: gate, do not throttle — and gate narrowly.** §4.8 already has the right shape: "two cheap checks, in order, before any model is loaded." The recommendation is a **third check of exactly that kind**, not a new mechanism:
   - **Thermal:** skip the tick if `NSProcessInfo.thermalState` is `serious` or `critical`. Cheap, documented, and the only thermal signal a userland job can read.
   - **Battery, conditionally:** skip if on battery **and** below a floor (say 20%). Not "skip on battery" flat — see below.
5. **AC-gating incremental runs is rejected, on the PRD's own reasoning.** §4.8 rejected a nightly cadence because it "guarantees the 'I told Tome this an hour ago and it can't find it' failure." Gating on AC recreates that failure exactly, for whoever works unplugged. And the arithmetic does not support it: ~6 minutes/day of GPU at an assumed ~30 W package delta is roughly **3 Wh/day** against a ~72 Wh battery — under 5% of a charge (*Arithmetic*, and the 30 W figure is Agent 1's to correct).
6. **AC-gating `full` mode is warranted and free.** Full mode is operator-initiated, rare, CLI-gated, and 5–50 hours long. Refusing to start one on battery costs nothing and prevents the only genuinely bad power outcome.
7. **Idle-gating is rejected on the same reasoning as nightly.** It makes the latency from capture to enrichment unbounded and unpredictable, which is precisely what §4.8 spent a decision avoiding. macOS's native "when idle" facility, **XPC Activity**, is disqualified more strongly still — see §6.5.
8. **The one knob worth naming that the PRD does not have:** a **per-tick entry cap**. A 30-entry capture session produces ~9 minutes of continuous GPU. Capping the batch at, say, 5 entries per firing turns that into six 90-second bursts spaced fifteen minutes apart. This is the only *scheduling* lever that shapes burst length, it costs two lines in the runner loop, and it trades against latency. Named as a finding, not proposed as a decision.

**The hypothesis is therefore half-killed.** Enrichment does *not* need AC-gating, idle-gating, or thermal-gating as a class. It needs one cheap thermal check, one conditional battery-floor check, and an AC precondition on full mode. §7.7's sentence "*the machine is assumed not in use during enrichment*" is indeed false on this target and must be struck — but almost everything §7.7 concluded *from* that sentence stands anyway, because it stood "independently of that" (§7.7's own words) and because the knobs it declined are still not connected to the contended resource.

### 1.4 The staleness alarm — it breaks, and the sign flips

**§4.8's staleness alarm inverts on this host. This is a real, silent, high-value finding.**

§4.8: *"Staleness is measured against uptime, not wall-clock age. The machine is dual-booted and sometimes off, so a wall-clock alarm would fire every time it returns from Windows when nothing is wrong."*

The alarm works on the desktop because **uptime is a good proxy for "how long the machine has had the opportunity to run enrichment."** On the Fedora box the machine is either up (opportunity) or powered off in Windows (uptime resets to zero at the next boot, suppressing the alarm).

On a MacBook that proxy fails in both directions at once:

- **Documented:** `uptime` and `sysctl kern.boottime` on macOS are derived from the wall-clock instant of boot. **Sleep does not reset them and does not pause them.** A Mac slept nightly for a month reports a month of uptime.
- **Documented:** `StartInterval` **drops** every firing that would have occurred during sleep — *"If the system is asleep during the time of the next scheduled interval firing, that interval will be missed due to shortcomings in kqueue(3)"* (`man launchd.plist`).

Put together: a laptop can report three weeks of uptime while having been awake for perhaps forty hours of it and having fired the timer accordingly. The guard clause "*only alarm once the system has been up longer than the threshold*" **never suppresses anything**, because uptime on a machine that never reboots is always above any threshold worth setting. The alarm degrades into the pure wall-clock alarm §4.8 explicitly rejected — and it fires on the exact physical situation it was built to excuse: *the machine wasn't running, so of course no work happened.* On the desktop that situation reads as `uptime = 0` (quiet). On the laptop the same situation reads as `uptime = 3 weeks` (loud). **Same fact, opposite signal.**

And it lands, as §4.8 warns, "on the one channel that has to stay quiet enough to be trusted."

**The substitute is cheap, documented, and portable — and it improves the Fedora box too.** Replace *uptime* with *awake time*:

| Host | Clock | Documented semantics |
|---|---|---|
| macOS | `CLOCK_UPTIME_RAW` (`time.CLOCK_UPTIME_RAW`, macOS ≥ 10.12) | *"increments monotonically … but that does not increment while the system is asleep"* (`man clock_gettime`); CPython: *"not incremented while the system is asleep."* |
| Linux | `CLOCK_MONOTONIC` (`time.CLOCK_MONOTONIC`) | CPython documents `CLOCK_BOOTTIME` as *"Identical to CLOCK_MONOTONIC, except it also includes any time that the system is suspended"* — i.e. `CLOCK_MONOTONIC` excludes suspend. |

Both are "seconds this machine has been awake since boot." The alarm becomes:

```
awake_now  - awake_at_last_successful_run  >  threshold     (same boot session)
awake_now                                  >  threshold     (boot session changed)
```

Cost: **one extra stored value** — the awake-clock reading at each successful run, alongside `last_successful_run_at` — plus a boot-session identifier so a reboot invalidates it (`sysctl -n kern.boottime` on macOS, `/proc/sys/kernel/random/boot_id` on Linux). One column on `enrichment_runs`, or one row in a small state table.

Two things make this more than a patch:

- **It is the semantics §4.8 actually wanted all along.** "Has the machine had a chance to run?" is an awake-time question, and it was only ever answered with boot-uptime because on a machine that powers off rather than sleeps the two coincide.
- **It composes exactly with the timer.** `StartInterval` is a kqueue timer, which also does not advance during sleep. So the alarm threshold and the timer interval are denominated in *the same clock*. "No successful run in N awake-seconds against a 900-awake-second timer" is a statement you can reason about; "no successful run in N wall-seconds" is not.

**Residual uncertainty, flagged honestly:** one secondary source encountered during this research claims `CLOCK_UPTIME_RAW` can go *backwards* across a long sleep on battery (macOS standby / hibernation writing RAM to disk). I could not confirm this in any primary source and the issue I traced it to did not in fact say it. **Measure it** (§11, item M5). If true, the alarm needs the same "tolerate a value in the past/future" tolerance §4.8 already applies to `last_successful_run_at` — which is a two-line defence, not a design change.

### 1.5 Hypotheses: what survived contact

| # | Hypothesis as written | Outcome |
|---|---|---|
| 1 | *launchd cannot express what systemd expressed* | **Confirmed on the mechanism, killed on the consequence.** launchd's ordering story is not "weaker still" — it is *absent by design*. But the constraint that forced system units evaporates, the failure is benign and self-healing, and Apple documents the application-level fix as the intended pattern. |
| 2 | *The enrichment timer becomes a user-facing problem* | **Half-killed.** Steady-state load is ~6 min/day in sub-minute bursts, and backlog cannot accumulate because capture and enrichment share a duty cycle. AC/idle/thermal gating as a class is **not** warranted; two cheap pre-flight checks and an AC precondition on full mode are. §7.7's rejection of resource limits ports verbatim and is still right. |
| 3 | *Sleep breaks the timer's semantics* | **Killed.** `StartInterval` drops missed intervals across sleep and across a running job — which is *precisely* what "no `Persistent=`" plus the advisory-lock skip were built to produce. The deliberate choice survives **as the default**. The inversion is available (`StartCalendarInterval` coalesces missed firings on wake) and is the right choice for the **backup** timer, which today is `Persistent=`-less only incidentally. |
| 4 | *Sleep may silently break the staleness alarm* | **Confirmed, and worse than stated.** It does not merely break; the signal inverts. §1.4. |
| 5 | *§7.6's SELinux constraint has a macOS analogue* | **Complicated.** `/opt` ports literally (it is a firmlink), `restorecon` has no analogue and needs none, and TCC does **not** reproduce the "structurally impossible" property — Tome touches no TCC-protected location. The real analogues are elsewhere and smaller: plist ownership rules, Background Task Management letting the user silently switch the agent off, and Apple DTS advising that daemons live inside app bundles. |
| 6 | *LaunchAgent vs LaunchDaemon is the shape of the whole decision* | **Confirmed, and it is the cleanest decision in the area.** LaunchAgent, on five independent grounds, and it *refunds* two accepted costs the PRD is currently paying (§3). |

---

## 2. §7.3 — the unit inventory

### 2.1 What launchd is, in systemd terms

Four differences matter before anything else.

**One object per job.** systemd's `.service` + `.timer` pair is one launchd plist. `StartInterval` and `StartCalendarInterval` are *keys on the job*, not separate schedulable entities. This is why seven systemd objects become four or five launchd jobs — three of the seven are timers and drop-ins.

**Domains, not a user/system split with a wall between them.** `launchctl` targets `system`, `user/<uid>`, `gui/<uid>`, `login/<asid>`, or `pid/<pid>` (*Documented*, `man launchctl`). The system domain "manages the root Mach bootstrap and is considered a privileged execution context"; a `gui/<uid>` domain is created "when the user logs in at the GUI." Crucially for §7.3: a job in `gui/$UID` sits alongside every other job in `gui/$UID`, including Homebrew's — there is no "you cannot see the system manager's units" boundary of the kind §7.3 hit.

**No dependency model.** *Documented*, `man launchd.plist`: *"Unlike many bootstrapping daemons, launchd has no explicit dependency model. Interdependencies are expected to be solved through the use of IPC."* Apple's *Daemons and Services Programming Guide* is more expansive: *"The `launchd` daemon was designed to remove the need for dependency ordering among daemons"* and *"Because `launchd` registers the sockets and file descriptors used by all daemons before it launches any of them, daemons can be launched in any order."*

**No drop-ins.** systemd's `.d/` override mechanism, which §7.3 uses for `postgresql.service` and `ollama.service` (both units Tome does not own), has **no launchd equivalent.** To change a key on Homebrew's Postgres or Ollama plist you edit the plist in place — a file Homebrew owns and will overwrite on upgrade. *(Reasoned.)* This is a real, unglamorous loss: §7.3's whole "Tome, via a drop-in" ownership column becomes "Tome, by patching someone else's file, reapplied after every `brew upgrade`." The mitigation is to stop using Homebrew's generated plist and ship a Tome-owned one with a different label — which trades the drift for divergence from `brew services`.

### 2.2 The primitive-by-primitive translation

*All launchd claims in this table are* **Documented** *from `man launchd.plist` / `man launchctl` unless marked otherwise.*

| systemd, as §7.3 uses it | launchd | Verdict |
|---|---|---|
| `After=` / `Requires=` (hard) | — | **No equivalent.** Solve in the application. |
| `After=` / `Wants=` (soft) | — | **No equivalent**, and nothing to lose: soft ordering is the absence of a constraint, which launchd gives you by default. |
| `Type=oneshot` | implicit — a job that runs and exits | Free. |
| `Type=simple` long-lived | `KeepAlive=true` | Free. |
| `Restart=on-failure` | `KeepAlive={SuccessfulExit: false}` | Native substitute. **Note:** *"Rapidly exiting jobs are throttled"*; `ThrottleInterval` defaults to 10 s, so the restart floor is 10 s. |
| `.timer`, monotonic, `OnUnitActiveSec=15min` | `StartInterval=900` | Native substitute. See §4. |
| absence of `Persistent=` | `StartInterval`'s documented drop-on-sleep | **Identical, by default.** |
| `Persistent=true` | `StartCalendarInterval` coalescing on wake | Native substitute — the right shape for `tome-backup`. |
| `OnBootSec=5min` | — | **Unexpressible.** Approximated: `StartInterval` without `RunAtLoad` delays the first firing by one interval. |
| `EnvironmentFile=/etc/tome/tome.env` | `EnvironmentVariables` (an inline plist dict) | **Degrades.** launchd has no environment-*file* reader. §7.8's `tome.env` must be read by Tome's own code. See §8.3. |
| `User=` / `Group=` | `UserName` / `GroupName` | **System domain only** — *"This key is only applicable for services that are loaded into the privileged system domain."* Under a LaunchAgent the job simply runs as you, which is what you want. |
| `WorkingDirectory=` | `WorkingDirectory` | Free. |
| `SyslogIdentifier=` | — | Process name, or an `os_log` subsystem/category. |
| `LogNamespace=` | — | Agent 4. No equivalent. |
| `IPAddressDeny=` / `IPAddressAllow=` | — | Agent 2 / issue #28. No equivalent (already known). |
| `RuntimeMaxSec=` (run-duration cap) | — | **No equivalent.** `ExitTimeOut` only governs SIGTERM→SIGKILL on *stop*. |
| `systemctl start / stop / restart` | `launchctl bootstrap` / `bootout` / `kickstart -k` | Free. |
| `systemctl enable / disable` | `launchctl enable` / `disable` (persistent across reboots) | Free. |
| `systemd-analyze verify` | `plutil -lint` | **Degrades** — syntax only, no semantic validation. |
| `systemctl status` (narrative + last log lines) | `launchctl print <target>` (state + last exit code, **no log excerpt**) | **Degrades.** See §9.4. |

Two launchd features with no systemd counterpart worth naming, because they change what is possible rather than merely how it is spelled:

- **Socket activation as the *default* answer to ordering.** launchd holds the listening socket and starts the job on first connection (`Sockets`, `launch_activate_socket(3)`). This is why Apple can say daemons may launch in any order. It would solve `tome-mcp` → Postgres cleanly *if Postgres were socket-activated by launchd* — which it is not under any install route (§2.4). The mechanism exists and is unavailable. *(Reasoned.)*
- **`LaunchEvents`** — IOKit-matching and notification-matching launch triggers. Relevant to duty-cycle gating in principle (a power-source change is observable this way); dismissed in §6.3 as more machinery than a `pmset` call in the pre-flight.

### 2.3 The hard constraint: what actually happens if `tome-mcp` starts before Postgres

§7.3's constraint was *"a systemd user manager cannot express ordering against system units."* Two separate questions fall out of it on macOS.

**Does the constraint reproduce?** No. Under the Homebrew route (the likely one), Postgres is a **user LaunchAgent in `gui/$UID`** — the same domain Tome's jobs would occupy. There is no privileged domain to order against, so the specific impossibility §7.3 hit **does not exist here.** (*Documented*, `brew services`: "By default, services run as your user in `~/Library/LaunchAgents/`.") §7.3's stated reason for choosing system units is void on this target.

**Does the ordering *problem* go away?** No — it gets worse, because launchd cannot order *anything*. But the failure is benign, for three reasons:

1. **`tome-mcp` is `Restart=on-failure` today.** Its launchd translation, `KeepAlive={SuccessfulExit: false}`, produces: start → cannot reach Postgres → non-zero exit → launchd restarts after ≥10 s → succeeds once Postgres is listening. Worst case at login is a handful of restart cycles over a minute. *(Reasoned from documented `KeepAlive` and `ThrottleInterval` semantics.)*
2. **Postgres is a hard dependency but a *local* one.** Both are on the same machine on loopback; the window is the difference between two login-triggered job starts, i.e. seconds.
3. **Apple documents the application-level fix as the intended design**, not as a workaround. A connection retry with backoff at startup — which a single-user tool should arguably have anyway — closes the window entirely and removes the restart churn from the log.

**But there is a wrinkle §7.3 would notice.** `tome-mcp` is deliberately **soft** on Ollama and **hard** on Postgres, and that asymmetry is load-bearing: it is what keeps a broken Ollama from blocking capture (§4.5). launchd cannot express either side, so **the asymmetry has to move into the code.** Today it is legible in a unit file that an operator can read; there it becomes a property of a connection-setup function. That is a genuine loss of legibility, not of behaviour, and it should be recorded as such rather than shrugged off — §7.3's soft/hard distinction is one of the more carefully-argued lines in the section.

Similarly, `tome-enrich`'s **hard** dependency on both Postgres and Ollama becomes: the runner's pre-flight checks fail, it logs and exits non-zero, and the next `StartInterval` firing retries. **This is already how §4.8 works** — *"The timer* is *the retry mechanism"* — so for the runner the loss is nil. *(Reasoned.)*

**If Agent 2 concludes stdio transport wins, this entire subsection dissolves:** Claude Desktop / Claude Code spawn the MCP server as a child process on demand, launchd is not involved, ordering is the client's problem, and `tome-mcp` is not a job at all.

### 2.4 Conditional on how Postgres is installed (Agent 5's call)

| Route | What supervises Postgres | Domain | Starts at | Effect on §7.3 |
|---|---|---|---|---|
| **Homebrew** `postgresql@18` via `brew services` | launchd, from `~/Library/LaunchAgents/homebrew.mxcl.postgresql@18.plist` | `gui/$UID` | login | **Best case.** Same domain as Tome's jobs. `launchctl print` sees it. Still no ordering, but the *shape* of §7.3 ports. Cost: Homebrew owns the plist; Tome has no drop-in mechanism to modify it. |
| **Homebrew with `sudo brew services`** | launchd, from `/Library/LaunchDaemons/` | `system` | boot | **Reintroduces §7.3's original problem in mirror image** — Tome's agents in `gui/$UID` cannot order against a system-domain job either. But since launchd cannot order *at all*, this costs nothing extra. Postgres running before login is a real benefit only if something needs it before login; on-device, nothing does. |
| **Postgres.app** | A GUI application supervising the postmaster | not a launchd job in the ordinary sense | when the app is launched (login item, if configured) | **Worst case for service management.** Tome's availability becomes contingent on a GUI app the user can quit from the Dock, with no `launchctl` visibility and no restart supervision Tome can reason about. It also means Postgres is not running during a `gui` session where the app failed to launch, with no signal. |
| **Container** (Docker Desktop / OrbStack / Apple `container`) | A VM supervisor, itself a user-session app or agent | varies | when the VM host starts | **Adds a supervision layer and a sleep hazard.** The VM is suspended with the host; on wake, clock skew inside the guest and reconnection behaviour are both unknowns this document cannot resolve. Also puts a filesystem boundary between Postgres and the dumps, which is Agent 5's problem. |

**The conclusion is the same under all four:** launchd cannot order, so ordering must be solved in Tome's code. What the route changes is (a) whether `launchctl` can *see* Postgres at all — it cannot under Postgres.app — and (b) how much of §7.3's "Tome, via a drop-in" ownership column survives. **Recommendation for the synthesis: the Homebrew user-agent route is the only one that keeps §7.3 recognisable.** Postgres.app is the route that would force §7.3 to be rewritten rather than ported.

### 2.5 Ollama

Ollama on macOS ships two ways: the `.dmg` desktop app (a menu-bar item, started as a **Login Item**) and `brew install ollama` (a Homebrew-generated **LaunchAgent**). *(Reported, corroborated across the Ollama macOS docs and Homebrew's service docs.)*

Two consequences for §7.3:

- **The Homebrew agent is the one that resembles today's `ollama.service`.** The desktop app is a Login Item, and there is a reported ordering hazard — *"Login Items in System Settings can launch before Launch Agents, which means that Ollama in the menu bar may not see the host settings"* — i.e. environment set by an agent may not reach a Login-Item-launched Ollama. Since §7.7 pins `OLLAMA_HOST`, `OLLAMA_GPU_OVERHEAD`, keep-alive, and `OLLAMA_NUM_PARALLEL` through a Tome-owned drop-in, and **launchd has no drop-in**, this matters: §7.7's configuration mechanism has to be re-sited. *(Reasoned.)*
- **§1.4's "hand-installed, owned by no package, no unattended upgrade path" is fixable here.** Homebrew gives Ollama a package manager and an upgrade path, which is a small unambiguous gain. It also means `brew upgrade` can replace the plist under Tome, which is the same small loss noted in §2.1.

### 2.6 The new inventory

**Branch A — Agent 2 concludes an HTTP edge is still needed:**

| launchd job | Owner | Type | Replaces |
|---|---|---|---|
| `homebrew.mxcl.postgresql@18` | Homebrew | `KeepAlive`, login | `postgresql.service` (+ its Tome drop-in) |
| `homebrew.mxcl.ollama` | Homebrew | `KeepAlive`, login | `ollama.service` (+ its Tome drop-in) |
| `dev.tome.mcp` | Tome | `KeepAlive={SuccessfulExit:false}` | `tome-mcp.service` |
| `dev.tome.enrich` | Tome | `StartInterval=900` | `tome-enrich.service` **+** `tome-enrich.timer` |
| `dev.tome.backup` | Tome | `StartCalendarInterval` (daily) | `tome-backup.service` **+** `tome-backup.timer` |

**Five jobs, three of them Tome's.** Seven → five is not a simplification of the system; it is the disappearance of the timer object.

**Branch B — Agent 2 concludes stdio:** drop `dev.tome.mcp`. **Four jobs, two of them Tome's**, and Tome's launchd surface is reduced to two scheduled batch jobs. If that branch holds, §7.3 is barely a section any more, and — worth saying plainly — **§7.3's soft-vs-hard-on-Ollama argument, its `sudo` cost, and its notification-bus cost all disappear with it**, because they were all consequences of `tome-mcp` being a supervised long-lived service.

**Verdict on §7.3: survives with a native substitute, and shrinks.** The hard constraint that produced it dissolves. Its ordering guarantees break and are replaced by application-level retry. Its accepted costs (`sudo`, no notification bus) are refunded. Its "via a drop-in" ownership model has no equivalent and is the one thing that genuinely worsens.

---

## 3. LaunchAgent vs LaunchDaemon

Hypothesis 6 said this is the shape of the whole decision. It is, and it is not close.

### 3.1 The two options

*All rows* **Documented** *from Apple's Daemons and Services Programming Guide and `man launchctl`, except where marked.*

| | **LaunchAgent** (`~/Library/LaunchAgents`, `gui/$UID`) | **LaunchDaemon** (`/Library/LaunchDaemons`, `system`) |
|---|---|---|
| Apple's definition | *"A user agent is essentially identical to a daemon, but is specific to a given logged-in user and executes only while that user is logged in."* | Runs independent of login. |
| Runs as | the logged-in user | root, or `UserName` |
| Available before login | no | yes |
| Survives logout | no | yes |
| Survives screen lock | **yes** — lock does not end the Aqua session (*Reported*) | yes |
| User session access (notifications, `osascript`, keychain) | yes | no |
| TCC prompts possible | yes, in principle | **no** — silently denied (*Reported*, corroborated by Apple staff answers) |
| Plist ownership | owned by the loading user; not group- or world-writable; mode 600 or 400 | owned by root; same write restriction |
| Needs `sudo` to install / edit / start | **no** | yes |
| Visible in System Settings › Login Items & Extensions | yes — **and the user can switch it off** (*Documented*, Ventura+ BTM) | yes — same |
| FileVault interaction | none — the user has already unlocked to log in | starts after pre-boot unlock; nothing runs while the machine sits at the FileVault prompt (*Reasoned*) |

### 3.2 The recommendation: LaunchAgent, on five grounds

1. **The only consumer is in the user session.** Claude Desktop and Claude Code run as the user. A memory-keeper with no remote clients has nothing to serve when nobody is logged in. §7.3's own §10 note that a system unit "has no clean route to the desktop notification bus" is the tell: the design has always wanted to be closer to the session.
2. **It matches how Postgres and Ollama will actually be installed.** Homebrew defaults to `~/Library/LaunchAgents`. Choosing a daemon means Tome is in a different domain from its dependencies for no benefit.
3. **It refunds §7.3's accepted cost.** *"Editing units and reading `journalctl` needs `sudo`"* — an agent needs none. Deploy, restart, inspect, all unprivileged.
4. **It refunds the deferred fix in §10.3 / §13.2.** *"The `warnings` channel is dead if the MCP server fails to start … Desktop notifications are the deferred fix."* An agent in the user session can post a notification with one `osascript -e 'display notification …'` call or `UNUserNotificationCenter`. On the desktop this needed a bridge out of a system unit; here it is free. **This is a genuine capability the move buys**, and it is the natural home for the staleness alarm and the leak tripwire's persistent warning. (Caveat: notification *permission* is itself a TCC-adjacent grant that attaches to the posting binary — see §7.3 below and measure item M8.)
5. **TCC.** An agent can at least *ask*; a daemon is denied without a prompt. Tome should never need to ask (§7.2), but the option costing nothing is worth having.

### 3.3 What choosing an agent costs

- **Nothing runs before login.** No backup, no enrichment, no MCP server. On a single-user on-device tool this is correct behaviour, not a cost — but it means "I rebooted and left it" produces no work at all, which is a new operational fact worth writing down.
- **Background Task Management is a new, silent off-switch.** *Documented:* since Ventura, every third-party LaunchAgent appears in **System Settings › General › Login Items & Extensions**, and the user can toggle it off, which disables the job without deleting the plist. Installing it also produces a *"Background items added"* notification. There is **no systemd analogue for a UI that silently disables your service**, and combined with §9.4's weak failure signal this is a plausible "why has nothing enriched for a week" story with no log line anywhere. It should be on the runbook, and `get_enrichment_status` arguably ought to be able to say "the agent is not loaded" — which `launchctl print gui/$UID/dev.tome.enrich` can answer in one call.
- **Apple is deprecating the hand-written-plist pattern.** *Reported:* `SMAppService` is the modern registration API, it expects helpers to live **inside an app bundle**, and Apple DTS's current advice for daemons hitting file-access problems is *"The simplest solution is to put your daemon inside an app bundle."* Nothing forces this today. It is a direction-of-travel risk for a design that expects to live for years.

**Verdict: LaunchAgent, unambiguously.** This is the one place in this area where the macOS target is straightforwardly better than the Fedora one.

---

## 4. §4.8 — the timer, across sleep

### 4.1 What `StartInterval` does, verbatim

> *"This optional key causes the job to be started every N seconds. If the system is asleep during the time of the next scheduled interval firing, that interval will be missed due to shortcomings in kqueue(3). If the job is running during an interval firing, that interval firing will likewise be missed."*
> — `man launchd.plist` (*Documented*)

Note the historical wrinkle, because it matters for how much to trust this: *(Reported)* the 10.9 man page described the **opposite** behaviour (fire on wake, coalescing missed intervals); the text above appeared in 10.11 and has been stable since. So the current documentation is a deliberate correction, not an omission — which raises confidence in it. It should still be measured (§11, M2), because a documented behaviour that reversed once can reverse again.

### 4.2 Hypothesis 3 is killed: the deliberate choice survives *as the default*

§4.8's two scheduling decisions were:

- **monotonic, no `Persistent=`** — do not replay missed firings after downtime;
- **skip if the advisory lock is held** — a long run plowing through timer windows is normal operation, not a failure.

`StartInterval` gives **both**, in one key, with no configuration:

| §4.8's intent | systemd expression | launchd |
|---|---|---|
| Missed firings during downtime are not replayed | omit `Persistent=` | **documented default**: missed during sleep → dropped |
| A firing during a live run is a no-op | fire anyway; the runner takes the lock, fails, exits at debug level | **documented default**: *"If the job is running during an interval firing, that interval firing will likewise be missed"* — launchd never spawns it |

The second row is a small **improvement**: the wasted process spawn, the 0.17 s warm import, and the debug-level "skipped" line all disappear for the common in-run case. §4.8's advisory-lock check remains necessary — a CLI `--reembed`, an MCP `trigger_enrichment`, and a timer firing can still collide — but it stops being the *routine* path.

**So: "the deliberate 'no `Persistent=`' choice survives" — not merely survives, but is what you get by default and cannot easily opt out of.** The hypothesis that sleep breaks the timer's semantics is killed. Sleep does exactly what the design wanted.

### 4.3 The inversion is available, and `tome-backup` should probably take it

> *"Unlike cron which skips job invocations when the computer is asleep, launchd will start the job the next time the computer wakes up. If multiple intervals transpire before the computer is woken, those events will be coalesced into one event upon wake from sleep."*
> — `man launchd.plist`, `StartCalendarInterval` (*Documented*)

That is `Persistent=true` with automatic coalescing, and it is the correct semantics for the **daily backup**, which today is a plain `daily` timer. On a desktop that is on at some point most days, a plain daily timer is fine. On a laptop that is asleep at 03:00 every night, a `StartInterval=86400` backup would drift and skip; `StartCalendarInterval` fires once on the next wake. **This is a case where the host change makes a decision *better*, and it is free.** (*Reasoned* from the two documented behaviours.)

The one thing to watch: coalescing means a wake after a week produces **one** backup, not seven — which is what you want, and worth stating so nobody later "fixes" it.

### 4.4 `OnBootSec≈5min` has no expression

launchd has no start-delay key. Three approximations, none exact:

- **`StartInterval=900` with `RunAtLoad` absent** — first firing one interval after load. Serves `OnBootSec`'s purpose (don't pile onto login) more coarsely, at 15 min instead of 5. Apple's own guidance supports omitting `RunAtLoad`: *"This key should be avoided, as speculative job launches have an adverse effect on system-boot and user-login scenarios."*
  **Caveat (needs measuring, §11 M1):** whether a `StartInterval` job fires immediately on load or after one full interval is not stated unambiguously in the man page, and secondary sources disagree.
- **`XPC_ACTIVITY_DELAY`** — exact, but requires adopting XPC Activity wholesale, which §6.5 rejects.
- **A `sleep 300` in the program's own startup** — ugly, and holds a process for five minutes to do nothing.

**Take the first.** `OnBootSec` was never load-bearing; it exists so the runner does not compete with boot. A 15-minute first delay does that better.

### 4.5 The two cheap checks

Both survive untouched — they are database queries. The **shape** of §4.8 is what makes the duty-cycle answer cheap: it already establishes "cheap read-only checks, in order, before any model is loaded" as the idiom for deciding not to work. §6.9's recommendation is a third check in that same list, not a new mechanism. **§4.8 anticipated the extension point without knowing it.**

**Verdict on §4.8 (cadence): survives with a native substitute, and the substitute is closer to the intent than the original.**
**Verdict on §4.8 (staleness alarm): breaks — see §1.4.**

---

## 5. The duty cycle: sizing the problem before solving it

### 5.1 The arithmetic

From §1.5 and §4.1 (*Arithmetic*, on PRD-measured inputs — Agent 1 owns whether ~18 s/entry survives the move to Metal, and it may not):

| Quantity | Value | Source |
|---|---|---|
| Capture rate | ~20 entries/day | §1.5 |
| Extraction cost | ~18 s/entry | §1.5 (and §13.3: *"recorded as unverified"*) |
| **Steady-state GPU work** | **~360 s/day ≈ 6 min/day** | derived |
| Timer firings per 24 h if never asleep | 96 | 900 s |
| Entries per firing, average | ~0.2 | derived |
| **Typical burst length** | **~18–36 s** (1–2 entries) | derived |
| A heavy capture session (30 entries in one sitting) | ~9 min of continuous GPU | derived |
| Full re-derivation | 5 h @1k, 25 h @5k, **50 h @10k** | §1.5, §4.1 |

**The steady state is not a duty-cycle problem.** Six minutes a day, delivered in sub-minute bursts, on a machine with 12 CPU cores and a GPU that is idle the rest of the time, is not something a user notices except as fan noise on a heavy day. If the hypothesis had said "an 18 s burn while you type" as a *continuous* condition it would be wrong by two orders of magnitude.

### 5.2 The observation that removes most of the rest

**Capture and enrichment now share a duty cycle.** This is the service-management echo of the spike ticket's central observation ("the only consumer sleeps with the server"), and it is what defuses the laptop case:

- Capture is **manual** (§1.2) and comes through the MCP tool surface (§5.1), whose only client is on this machine.
- A sleeping machine cannot be captured into.
- Therefore **the queue cannot grow while the timer is not firing.**

Contrast the Fedora box, where an iPhone or MacBook on the tailnet could capture into a running server while the desktop was in Windows — precisely the case §4.8's uptime-based staleness alarm was defending against. **On-device, that case does not exist.** The pathological "wake up and get ambushed" scenario the hypothesis worries about is structurally impossible.

What *can* still happen:
- **A heavy capture session** — 30 entries into a conversation, then you keep working. ~9 minutes of GPU spread over the next few ticks, or all at once depending on how the batch is bounded. This is the only realistic annoyance, and §6.9 names the knob for it.
- **Recovery after a long stretch of `resolution_required` or failed runs.** Bounded by the same capture rate.
- **A full run.** §6.10 — and this one is genuinely bad.

### 5.3 What actually gets worse, which the hypothesis does not mention

**Unified memory makes model residency a user-visible cost, in a way VRAM never was.** On the Fedora box, `qwen3:14b`'s 10 GB lives in VRAM — a separate pool the user cannot otherwise spend. On an M4 Pro, that 10 GB is *the same 48 GB* the user's browser, editor and Claude Desktop are drawing from. §7.7's decisions — shorten the global keep-alive, unload `qwen3:14b` explicitly at the end of every run, pin only the 275 MB embedder — were made "for crash behaviour"; **on this host they become the primary user-experience lever**, and their justification strengthens considerably. That is Agent 1's number to size, but it belongs in the duty-cycle story because the fix is a *residency* decision, which is service-management-shaped. *(Reasoned.)*

---

## 6. The duty cycle: what macOS actually offers, and what to use

### 6.1 The full inventory of available levers

| Lever | What it is | Reaches the GPU work? | Verdict |
|---|---|---|---|
| `ProcessType=Background` | launchd key → background QoS (9) → **E-cores only, near-idle frequency** on Apple Silicon | **No** | Wrong knob — §6.2 |
| `Nice` | launchd key → `nice(3)` | **No** | Wrong knob |
| `LowPriorityIO` / `LowPriorityBackgroundIO` | launchd keys → throttled filesystem I/O | **No** | Wrong knob (and the runner does almost no I/O) |
| `StartInterval` | when the job runs | n/a | **The only real lever** |
| XPC Activity (`xpc_activity_register`) | DAS-scheduled work with idle/battery/screen-sleep criteria | indirectly, by deferring | Disqualified — §6.5 |
| `IOPSGetProvidingPowerSourceType` / `pmset -g ps` | read the current power source | n/a | **Usable as a pre-flight check** — §6.6 |
| `NSProcessInfo.thermalState` | read the system thermal pressure (`nominal`/`fair`/`serious`/`critical`) | n/a | **Usable as a pre-flight check** — §6.8 |
| `ioreg -c IOHIDSystem` → `HIDIdleTime` | ns since last human input | n/a | Available, but idle-gating is rejected — §6.7 |
| `caffeinate` / `IOPMAssertionCreateWithName` | hold off idle sleep | n/a | Useful for full mode only, and **cannot beat a lid close** — §6.10 |
| `LaunchEvents` + notify matching | start a job on a power-source change | n/a | Over-engineered for a `pmset` call in a pre-flight |
| Metal/GPU priority | — | — | **No user-settable equivalent found.** Ollama exposes nothing. This is the missing knob, and it is missing on both hosts. |

### 6.2 Why the launchd resource knobs are the wrong ones — §7.7's argument, ported verbatim

§7.7 rejected CPU/memory/IO limits with a sentence that turns out to be host-independent:

> *"the knobs are not connected to the contended resource. The enrichment runner is a thin client that hands prompts to Ollama and waits, so limits on it would throttle a process that is mostly idle; limits on `ollama.service` would also throttle the interactive capture-embedding path; and VRAM has no cgroup control."*

Substitute launchd's knobs and Apple's scheduler and it reads identically:

- **On the runner:** `ProcessType=Background` confines the process to E-cores at near-idle clock (*Documented* by Apple: QoS influences P/E placement; *Reported*: background-QoS threads are E-core-only, and low-QoS E-core work runs near ~1050 MHz). Applied to a process that spends 18 s per entry blocked on an HTTP socket, this throttles JSON parsing and Postgres writes and does **nothing at all** to the GPU work. It would make Tome slower while making the machine no more responsive. **Strictly negative.**
- **QoS does not propagate over HTTP.** macOS propagates QoS across XPC and dispatch; a plain HTTP request to a separate long-lived daemon does not carry it. Ollama's work runs at Ollama's QoS regardless of the runner's. *(Reasoned — worth confirming, §11 M6.)*
- **On Ollama:** setting `ProcessType=Background` on the Ollama agent *would* reach the GPU work — and would also throttle the interactive capture-embedding path that §4.5's 5 s budget depends on. **The identical objection, unchanged.**
- **The escape hatch §7.7 already named** — two Ollama server processes, since visible devices and configuration are per server process — becomes affordable at 48 GB (Agent 1's territory): a background-QoS instance for enrichment, a normal-QoS instance for capture embedding. §7.7 rejected the two-instance split as mechanical overhead for a capacity problem. Here it would be the *only* way to buy a resource lever. **Named as a finding; the memory cost of two resident copies is Agent 1's number.**

**Conclusion: §7.7's resource-limit rejection survives the host change intact, and for the same reason. What does not survive is the sentence it sat next to.**

### 6.3 The sentence that must be struck

> *"No idle-gating either — the machine is assumed not in use during enrichment, and the settings above stand independently of that."* — §7.7

The first clause is false on this target. The second clause is **true**, and this is the part worth noticing: §7.7 hedged its own assumption, and the hedge holds. Every specific setting in §7.7 stands on VRAM/residency reasoning, not on the machine being idle. So striking the assumption invalidates **no decision in §7.7** — it invalidates only the *absence* of a gating decision, which is what §6.9 supplies.

### 6.4 What "AC power" costs to check

*Documented:* `IOPSGetProvidingPowerSourceType(IOPSCopyPowerSourcesInfo())` returns one of `kIOPMACPowerKey` ("AC Power"), `kIOPMBatteryPowerKey` ("Battery Power"), `kIOPMUPSPowerKey`. From Python this is a `pyobjc`/`ctypes` call, or — with no dependency at all — `pmset -g ps`, whose first line is `Now drawing from 'AC Power'` (*Reported*, corroborated across several admin references, and stable for many years). Battery percentage comes from the same output.

Cost: one `subprocess` call, single-digit milliseconds, no privileges, no framework dependency. **It fits §4.8's "cheap check" budget with room to spare.**

### 6.5 XPC Activity: the native "run when idle and plugged in" facility, and why it is disqualified

This is the closest thing macOS has to what the hypothesis asks for, so it deserves a real look before rejection. *Documented*, from `xpc/activity.h`:

| Key | Documented meaning |
|---|---|
| `XPC_ACTIVITY_INTERVAL` | *"the desired time interval (in seconds) of the activity. The activity will not be run more than once per time interval."* |
| `XPC_ACTIVITY_DELAY` | *"the number of seconds to delay before beginning the activity."* |
| `XPC_ACTIVITY_GRACE_PERIOD` | *"the number of seconds to allow as a grace period before the scheduling of the activity becomes more aggressive."* |
| `XPC_ACTIVITY_PRIORITY_MAINTENANCE` | *"maintenance priority … intended for user-invisible maintenance tasks such as garbage collection or optimization."* |
| `XPC_ACTIVITY_PRIORITY_UTILITY` | *"utility priority … intended for user-visible tasks such as fetching data from the network, copying files, or importing data."* |
| `XPC_ACTIVITY_ALLOW_BATTERY` | *"whether the activity should be allowed to run while the computer is on battery power."* |
| `XPC_ACTIVITY_REQUIRE_SCREEN_SLEEP` | *"whether the activity should only be performed while the primary screen is in sleep mode."* |
| `XPC_ACTIVITY_REQUIRE_BATTERY_LEVEL` | *"an integer percentage of minimum battery charge required to allow the activity to run."* |

That is, quite precisely, "run only on AC, only when the screen is asleep, only above N% battery, at maintenance priority, roughly every 15 minutes." It is the facility Apple's own maintenance work uses.

**It is disqualified on §4.8's own reasoning, three times over:**

1. **The grace-period model makes latency unbounded.** `XPC_ACTIVITY_INTERVAL` is *"will not be run more than once per time interval"* — a ceiling on frequency, not a floor. The Duet Activity Scheduler decides when, and under load or on battery it can defer for hours. §4.8 rejected a *nightly* cadence because it "guarantees the 'I told Tome this an hour ago and it can't find it' failure." An unpredictable cadence is worse than a nightly one: at least nightly is legible.
2. **`XPC_ACTIVITY_REQUIRE_SCREEN_SLEEP` means enrichment happens only when you are not looking** — which, on a machine that sleeps when the screen sleeps, means it happens approximately never.
3. **It is not a launchd.plist key.** Adopting it means the runner becomes a resident daemon that registers activities and blocks, rather than a `oneshot` that exits. That inverts the process model §4.8 depends on ("With a `oneshot` runner fired by a timer, no `Restart=` is needed"), and re-opens the crash-loop-backoff question §4.8 says it *dissolved*. It is also documented only in a header, not in Apple's developer documentation, and would need `pyobjc` or a C shim from Python.

**Kill it.** It is the right facility for Spotlight indexing and the wrong one for a memory-keeper whose product requirement is "captured now, findable soon."

### 6.6 AC-gating: no for incremental, yes for full

**Incremental — rejected.** Two reasons:

- **It recreates the failure §4.8 spent a decision avoiding.** Anyone working unplugged in a coffee shop captures a note and it stays `pending` until they get home. §4.8: *"Captures made in one session are enriched by the next firing."* AC-gating breaks that sentence for the exact situation the laptop exists for.
- **The arithmetic does not justify it.** ~6 min/day of GPU. Assuming a ~30 W package delta during generation (*Assumed* — Agent 1 should replace this), that is ~3 Wh/day against a battery in the ~70 Wh class: **under 5% of a charge, for a full day's enrichment.** Gating that away buys almost nothing and costs the product's main latency guarantee.

**A battery *floor* — accepted.** "Skip if on battery and below 20%" is a different and much weaker claim: it protects the one case where the user actually cares (running out), costs nothing when it passes, and defers work by at most one tick once you plug in. Recommend this, not AC-gating.

**Full mode — AC required.** Refuse to *start* a full run on battery. Free, obviously right, and it removes the worst outcome. Whether to *abort* an in-flight full run on unplug is a harder call and probably no: §4.1's per-entry transactions mean a run can be stopped at any time and resumed, so the honest behaviour is to stop cleanly at the next entry boundary and let the timer resume when power returns.

### 6.7 Idle-gating: rejected, and the tools noted anyway

Rejected for the same reason as nightly and as XPC Activity: it makes capture-to-findable latency unbounded, which is the one thing §4.8 refused to trade.

For completeness, the tools do exist: `ioreg -c IOHIDSystem` exposes `HIDIdleTime` in nanoseconds since the last human input, readable with a one-line `awk` (*Reported*, widely used; with a *Reported* caveat that it has behaved inconsistently on some Apple Silicon models, which is itself an argument against relying on it). CoreGraphics' `CGEventSourceSecondsSinceLastEventType` is the framework equivalent.

One free half-measure worth naming, since it costs nothing: **a LaunchAgent keeps running while the screen is locked** — lock does not end the Aqua session (*Reported*). So the common "step away, screen locks, machine stays awake on AC" window is already available to enrichment with no configuration at all. Whether the machine actually stays awake there depends on the user's `pmset` settings, which is an operator fact, not a design one.

### 6.8 Thermal-gating: one signal, and it is worth taking

There is no launchd thermal key and no way to ask macOS to throttle a job thermally. What exists is a **readable** signal: `NSProcessInfo.processInfo.thermalState`, returning `nominal` / `fair` / `serious` / `critical`, with a matching notification. *(Documented in Apple's Foundation documentation; not independently verified for this spike beyond that, so treat the exact enum spelling as needing a check.)*

Reading it costs one `pyobjc` call. Skipping the tick at `serious` or above is the honest thermal answer: it does not prevent Tome from being the thing that *caused* the thermal pressure, but it stops Tome from being the thing that *sustains* it while you are trying to compile something. On a fanned M4 Pro this may fire approximately never, which is fine — a check that never fires costs nothing and documents the intent.

### 6.9 The recommendation, in §4.8's own idiom

§4.8 today:

> *Every firing does two cheap checks* **in order, before any model is loaded**:
> 1. Try the advisory lock, non-blocking. If it cannot be acquired, exit immediately.
> 2. Check `pending_count` and the un-embedded count. Exit without loading any model if there is nothing to do.

The macOS shape adds a third of the same kind:

> 3. **Check the machine's willingness to work.** Exit at debug level, counting as a skip and not a failure, if any of:
>    - `thermalState` is `serious` or `critical`;
>    - on battery **and** below a configured floor (starting value 20%);
>    - **for `full` mode only**: not on AC.

Three properties make this the right shape rather than a bolt-on:

- **It reuses the skip path that already exists.** §4.8 already establishes that a skipped firing is *"normal operation, logged at debug level, and* **must not** *count as a failed run or touch `last_successful_run_at`."* A power skip is the same class of event as a lock skip. Nothing new needs inventing — including, importantly, the interaction with the staleness alarm.
- **It is read-only and sub-millisecond**, so §4.8's "idle cost is one query" claim survives roughly intact.
- **It puts the values in `tome.env`** (§7.8's dividing line: *"things measured against something that can move under you"*) and in §13.4's starting-points table, where an unmeasured number belongs.

**And one further knob, named but not proposed: a per-tick entry cap.** The only genuinely user-visible burst is a heavy capture session. A cap converts one 9-minute burst into six 90-second ones. It costs latency for the tail of the batch and it needs a decision about interaction with §4.1's "run scope is fixed at start". Worth a ticket if the synthesis goes anywhere; not worth deciding here.

### 6.10 The real duty-cycle casualty: full mode

**This is the finding in this area that most deserves the synthesis's attention, and it is not in the hypothesis list.**

Three facts, each individually fine:

1. **A full run is 5–50 hours** (§1.5, §4.1), growing with the corpus and reaching ~36 h within a year.
2. **A closed lid sleeps the machine, unconditionally.** *Reported*, consistently: `caffeinate`'s assertions hold off *idle* sleep, but a lid close is an explicit hardware-path sleep request and no assertion overrides it. Clamshell operation requires external power **and** an external display.
3. **`search_entities` errors for the entire duration of a full run** (§4.1), returning *"entity layer rebuilding, 1,240/5,000 processed; use `search_raw`."*

On the Fedora box, (3) is a contract measured in hours — unpleasant but comprehensible, and the operator chose it. On a MacBook, 50 hours of *awake* time is **two to four calendar weeks** of ordinary laptop use. §4.1's degradation contract silently changes units.

Everything else about full mode ports fine — §4.1's crash recovery is genuinely free (*"Each entry commits atomically … a crashed run leaves the remainder plainly `pending`"*), so sleep interruption is a non-event and the run resumes on the next tick. **It is the degradation window, not the interruption, that breaks.**

This is not mine to decide, but the options are worth naming for the synthesis:
- **Do full runs plugged in with the lid open and `caffeinate -i`,** accepting a multi-day operation rather than a multi-week one.
- **Revisit build-alongside-then-swap,** which §4.1 considered and rejected *"for the simpler schema"* — a decision made when the wipe window was hours. At weeks, the atomic-flip design's cost/benefit is materially different. **Flag this as a decision the host change may reopen**, per the spike's own rule that only host-invalidation is admissible.
- **Accept it,** on the grounds that full runs are rare and `search_raw` is a real fallback. Defensible; but "the primary retrieval surface is down for a fortnight" should be written down as such rather than inherited from a section that meant "for an afternoon."

---

## 7. §7.6 — deployment

### 7.1 `/opt/tome` ports literally

*Documented:* `/opt` is one of the standard firmlinks listed in `/usr/share/firmlinks`, alongside `/Applications`, `/Users`, `/private`, `/usr/local` and `/Volumes`. A firmlink bidirectionally merges a path on the read-only signed System volume with the writable Data volume, so **`/opt` is writable with `sudo` and needs no `/etc/synthetic.conf` entry.** (Homebrew's Apple Silicon prefix `/opt/homebrew` is the everyday proof.)

So `/opt/tome`, root-owned, readable by the running user, with `/opt/tome/.venv` from `uv sync --frozen`, ports **character for character**. That is a pleasant and slightly surprising result: the most Fedora-looking line in §7.6 is the one that needs no change.

### 7.2 The SELinux constraint dissolves; nothing replaces it in that position

§7.6's argument was: SELinux Enforcing + `/home/mark` at `0700` labelled `user_home_dir_t` makes running service code out of the dev checkout **structurally impossible**, and `restorecon` is mandatory because copied files carry home labels.

On macOS:
- There is **no mandatory-access-control label on files** that would refuse execution by path provenance. No `restorecon`, and nothing to restore.
- **A LaunchAgent runs as the user**, so `/Users/<you>` at `0700` is no obstacle at all — it is the agent's own home.
- Consequently **running out of the dev checkout is entirely possible on macOS**, where it was impossible on Fedora. §7.6's *reason* evaporates.

`/opt/tome` should still be the answer, but the argument has to be rebuilt on different ground: separating deployed code from an editable working tree, and keeping the deploy atomic and reviewable. That is a *preference* argument where Fedora had a *constraint* argument, and the PRD should say so rather than porting the sentence.

### 7.3 Where the macOS constraints actually are

Four of them. None makes anything impossible; together they are a different, more diffuse set of rules.

**(a) TCC, and it probably never binds.** *Documented/Reported:* TCC protects `~/Desktop`, `~/Documents`, `~/Downloads`, iCloud Drive, third-party cloud folders, removable volumes, network volumes and Time Machine backups. **A daemon cannot be prompted** — with no user session, TCC denies silently (corroborated by multiple Apple Developer Forums threads including Apple staff answers). An agent *can* prompt, but granting Full Disk Access to a bare CLI binary is reported to be unreliable in current macOS: *"Granting Full Disk Access to a CLI tool as a Launch Daemon does not work on MacOS 26.2. I was unable to add the binary neither using `+` button or by dragging the binary to the Prefpane."* Apple DTS's current advice is *"The simplest solution is to put your daemon inside an app bundle."*

  **But Tome touches none of those locations.** Code in `/opt/tome`, state in `/opt/tome/var` or `/usr/local/var/tome`, Postgres in Homebrew's prefix — nothing TCC guards. **So the constraint is real, documented, and inert — provided the placement decision in §8 is made deliberately rather than by accident.** The trap is putting the dev checkout in `~/Documents/Projects/tome`, which *would* make the agent silently unable to read its own code. That is the honest analogue of the SELinux footgun: same shape (a placement choice with a silent failure), different location, and easier to avoid.

**(b) Plist ownership.** *Documented*, Apple: *"Daemons and agents that are installed globally must be owned by the root user. Agents installed for the current user must be owned by that user. All daemons and agents must not be group writable or world writable. (That is, they must have file mode set to 600 or 400.)"* This belongs in `make deploy`.

**(c) Background Task Management.** §3.3 — the user can silently disable the agent from System Settings. No systemd analogue. Belongs in the runbook and arguably in `get_enrichment_status`.

**(d) The quarantine attribute.** `com.apple.quarantine` is the nearest structural cousin to an SELinux label: an extended attribute that travels with a file and changes what the system will let you do with it. It is applied by LaunchServices-aware downloaders (browsers), not by `curl`, `pip` or `uv`, so it should be **inert** for a `uv sync --frozen` deploy (*Reasoned*). `xattr -dr com.apple.quarantine /opt/tome` is the `restorecon` analogue if it is ever needed. Cheap insurance; low expected value.

**SIP** is worth a sentence only to dismiss it: it protects `/System`, `/bin`, `/sbin`, `/usr` (excluding `/usr/local`) and Apple-signed processes. Tome writes to none of them.

### 7.4 The deploy sequence, rewritten

```
launchctl bootout gui/$UID/dev.tome.enrich          # stop scheduling AND any live run
  → rsync code to /opt/tome
  → uv sync --frozen
  → plutil -lint  on every plist                     # replaces systemd-analyze verify (syntax only)
  → chown/chmod the plists to 0600, owner = $USER    # launchd refuses otherwise
  → tome-migrate                                     # pg_dumps first, replays the retraction ledger
  → launchctl kickstart -k gui/$UID/dev.tome.mcp     # restart; omit entirely under stdio
  → launchctl bootstrap gui/$UID ~/Library/LaunchAgents/dev.tome.enrich.plist
```

Differences worth naming:

- **`restorecon` is gone**, with nothing in its slot. The classic Fedora footgun does not have a macOS twin.
- **No `sudo` anywhere** (except the initial `mkdir /opt/tome`), because everything is in the user domain. §7.3's accepted cost is refunded here too.
- **`bootout` is more violent than `systemctl stop <timer>`.** systemd's stop-the-timer leaves an in-flight run alone; `bootout` unloads the job *and* terminates the running instance (SIGTERM, then SIGKILL after `ExitTimeOut`). §7.6 already accepts this — *"a deploy is a scheduled crash"* — and §4.1's per-entry transactions make it safe. But the sentence *"The timer is stopped first … stopping the timer removes the case rather than relying on recovery"* becomes **false**: on launchd you cannot separate the timer from the job, so the deploy now *does* rely on recovery. §7.6's carefully-argued belt-and-braces reduces to braces. Worth stating.
- **Editing a plist requires `bootout` + `bootstrap`,** not a `daemon-reload` equivalent. Not a burden, but a different verb.
- **`plutil -lint` is a much weaker gate than `systemd-analyze verify`** — it checks that the XML parses, not that the job makes sense. A misspelled key is silently ignored by launchd. This is a real, permanent loss of a safety net.

**Verdict on §7.6: survives with a native substitute. The path ports unchanged; the constraint that justified it dissolves and must be re-argued; the deploy sequence ports with one genuine loss (`plutil -lint` ≠ `systemd-analyze verify`) and one genuine gain (no `sudo`).**

---

## 8. §7.9 — storage placement and clock

### 8.1 The path table, per Postgres route

*(Conditional on Agent 5. Homebrew paths are* **Documented** *by Homebrew's own prefix conventions; the Tome rows are* **Reasoned** *recommendations.)*

| §7.9 today | Homebrew route | Postgres.app route | Container route |
|---|---|---|---|
| `/var/lib/pgsql/data`, `chattr +C` | `/opt/homebrew/var/postgresql@18` | `~/Library/Application Support/Postgres/var-18` | inside a volume | 
| `/var/lib/tome/` | `/opt/tome/var/` | same | same |
| `/var/lib/tome/dumps/` | `/opt/tome/var/dumps/` | same | same |
| `/var/lib/tome/backups/`, `0700`, owned by `tome` | `/opt/tome/var/backups/`, `0700`, owned by **`$USER`** | same | same |
| `/opt/tome/` code + venv, root-owned | **unchanged** | unchanged | unchanged |
| `/etc/tome/tome.env` | `/opt/tome/etc/tome.env` (see §8.3) | same | same |

Notes:

- **`chattr +C` has no APFS equivalent** — Agent 5's, flagged in the spike ticket, not restated here.
- **The `tome` system user disappears** under a LaunchAgent: the job runs as `$USER`. §7.9's `0700`-owned-by-`tome` becomes `0700`-owned-by-you, which is a *weaker* separation (you can read your own backups without effort, where `tome`-owned meant `sudo`). On a single-user on-device machine that separation was buying very little; but it *was* buying something, and it is gone. **Say so rather than silently dropping it.** FileVault is Agent 5's counterweight.
- **The alternative to `/opt/tome/var` is `~/Library/Application Support/Tome/`**, which is the idiomatic macOS location for a user agent's state and is not TCC-protected. Two arguments against it here: it entangles Tome's data with Time Machine's default backup set in ways Agent 5 should decide deliberately, not by placement default; and it splits code (`/opt`) from data (`~/Library`) where today they are neighbours. Recommend keeping them adjacent under `/opt/tome`, and letting Agent 5 override on durability grounds — that is their section.

### 8.2 The clock paragraph dissolves entirely

§7.9's clock discussion is:
- `RTC in local TZ: yes` needs fixing;
- fix it on the **Windows** side via `HKLM\…\RealTimeIsUniversal`;
- then `timedatectl set-local-rtc 0`;
- NTP becomes a correction rather than a crutch.

**Every clause is dual-boot-specific.** There is no Windows, macOS keeps the hardware clock in UTC with no user-facing option to do otherwise, and `timed`/`sntp` synchronise against `time.apple.com` by default. **Verdict: dissolves.** Nothing replaces it. (Whether Apple's time service is a §1.3 named egress exception is Agent 2's restatement, not mine.)

The two **obligations** the paragraph created behave differently:

- **"The server compares the incoming `captured_at` against its own clock and flags a wild disagreement."** *Survives, but becomes vacuous* — client and server are the same machine, so a wild disagreement is impossible by construction. **Keep it anyway.** It costs nothing, and it is the seam that lets a second device back in later without re-deriving the argument. Recording it as "vacuous on this target, retained deliberately" is more honest than deleting it.
- **"Tolerate a future-dated `last_successful_run_at`."** *Survives, and gains a new and more frequent cause.* On Fedora the cause was a backwards clock correction after boot. On a laptop it is a backwards correction after **wake**, which happens far more often — every wake in a new timezone or after a long sleep is a candidate. So the tolerance goes from a rare-case defence to a routine one. And if the staleness alarm moves to an awake clock (§1.4), that clock needs its **own** monotonicity tolerance, for the unconfirmed standby-reset behaviour in §11 M5.

### 8.3 `EnvironmentFile=` has no launchd equivalent — a §7.8 consequence I own the mechanism for

§7.8 puts `/etc/tome/tome.env` behind systemd's `EnvironmentFile=`. launchd has only `EnvironmentVariables`, an **inline plist dictionary**. There is no file-reading directive.

Three options, and the third is right:

1. **Inline the config into each plist.** Rejected: the plist is also the deploy artifact, the config would be triplicated across three jobs, and §7.8's epoch fingerprint reads *named keys from `tome.env`* (§7.8) — it cannot read a plist without redefining what it fingerprints.
2. **A shell wrapper that sources the file and `exec`s Python.** Works, adds a process, and puts config parsing in shell.
3. **Tome reads `tome.env` itself at startup.** ~15 lines, or `python-dotenv`. Keeps §7.8's file, its format, its fingerprint semantics, and its dividing line between `tome.env` and code, all unchanged.

**What is lost either way:** with `EnvironmentFile=`, systemd fails the unit if the file is missing, before a line of Tome's code runs. Under option 3 that guarantee moves into Tome's startup path — which is fine, but it is now Tome's job to fail loudly rather than start with defaults. **Worth a build obligation.** (`/opt/tome/etc/tome.env` rather than `/etc/tome/` because `/etc` on macOS is a symlink into `/private/etc`, works fine, but is not where a user-domain agent's config belongs; and keeping config next to code keeps the deploy one directory.)

**Verdict on §7.9: storage placement survives with a native substitute (a path remap plus the loss of the dedicated service user); clock dissolves, with both of its obligations surviving — one vacuously, one with a new and more frequent trigger.**

---

## 9. §7.10 — observability, the service-management half

*(§7.11 retention, §7.12 the tripwire, and the invariant-C enforcement question are Agent 4's. This section covers only how a launchd job's output reaches anywhere, which is the mechanism §7.10 depends on.)*

### 9.1 The zero-configuration capture does not exist

§7.10's design rests on one sentence: *"**stdlib `logging` to stdout**, captured by journald automatically."* That is what makes §7.10 cheap — no logging framework, no journal binding, no `structlog`, no `python3-systemd`.

On launchd there is **no automatic capture.** Apple's own guidance offers two routes and no third:

- **`StandardOutPath` / `StandardErrorPath`**, which map the job's stdout/stderr to **a plain file**. *Documented*, with the example `/var/log/myjob.log`.
- **`os_log`**, which Apple recommends for daemons: *"such programs log to the system logging facility, which is currently `<os/log.h>`."*

If neither is set, the output goes nowhere useful. (*Reported*, consistently: `/dev/null`. The launchd man page is silent, which is itself telling — this is the one gap in the primary sources here, and it is worth a two-minute check on the machine, §11 M7.)

### 9.2 The two routes, costed

**Route A — `StandardOutPath` to a file.** Python's `logging` to stdout works unchanged, so §7.10's format decision, its identifier scheme, its `log_exception()` and `configure_logging()` functions all port untouched. What appears is a rotation obligation — and macOS *has* a native answer: **`newsyslog`**, driven by `/etc/newsyslog.conf` and `/etc/newsyslog.d/*.conf`, run periodically by a system LaunchDaemon (*Reported*, corroborated: `com.apple.newsyslog`, on a `StartCalendarInterval`). Its per-file config expresses `count` (how many archives to keep), `size`, and `when` (a rotation hour or elapsed-hours trigger). **That is a per-file size bound *and* a per-file time bound *and* a retention count — the three things §7.11 needs.** Handing this to Agent 4 as the most promising native substitute for `journald@tome.conf`'s `MaxRetentionSec` / `MaxFileSec` / `SystemMaxUse` triple.

**Route B — `os_log`.** Better integrated (`log show`, `log stream`, Console.app, sysdiagnose capture), but three problems for §7.10 specifically:
- **Level semantics fight the design.** *Reported*: `default` and above are persisted to disk; `info` and `debug` are memory-resident and weeded quickly. §7.10's operational narrative is written at INFO. Mapping it to `os_log`'s `default` level to make it survive means every routine line is a "default" event — which works, but inverts the level scheme.
- **Retention is not controllable the way §7.11 needs it.** *Reported:* a Mac left running may retain only the last ~20 hours of persisted entries, and the eviction is volume-driven and global. §7.11's *"MaxRetentionSec=30day"* has no per-subsystem analogue; **and note the failure direction is toward too-short, not too-long**, which is the safe direction for a privacy bound and the wrong direction for debugging. Agent 4's call.
- **It needs a binding.** Python has no stdlib `os_log`; you need `pyoslog`, `pyobjc`, or a `ctypes` shim — which is exactly the "no journal binding" simplification §7.10 chose to avoid. (`syslog(3)` is bridged into the unified log on modern macOS and Python *does* have a stdlib `syslog` module — a possible middle path, unverified, §11 M9.)

**Reading strongly toward Route A**, which is also the direction Agent 4's brief anticipates ("*the honest answer may be to stop using the system logger*"). The service-management half of that answer is: **it is barely a downgrade, because `newsyslog` is a real facility and `StandardOutPath` costs one plist key.**

### 9.3 `SyslogIdentifier=`

No equivalent. Under Route A, one file per job gives the same disambiguation for free (arguably better). Under Route B, an `os_log` subsystem/category pair (`dev.tome` / `enrich`) is the idiomatic form and also gives `log show --predicate 'subsystem == "dev.tome"'` — which is the closest thing macOS has to `journalctl --namespace=tome -u tome-enrich`, though without the retention property that made the namespace worth having.

### 9.4 The new problem: a launchd job fails quietly

`systemctl status tome-enrich` gives you state, last start, exit code, **and the last ten log lines**, in one command. `launchctl print gui/$UID/dev.tome.enrich` gives state and last exit status with **no log excerpt** — you then go find the log yourself. And a plist rejected at `bootstrap` fails with famously terse errors (`Load failed: 5: Input/output error`).

Stack this against two facts already in the PRD and it compounds:
- §13.2: *"The `warnings` channel is dead if the MCP server fails to start."*
- §3.3 above: **Background Task Management can silently disable the agent from a System Settings toggle.**

**On this host, "Tome has quietly stopped working" has more entry points and fewer signals than on Fedora.** That is a real regression and it should be recorded as an accepted risk rather than discovered later.

**The counterweight is genuine and belongs in the same paragraph:** a LaunchAgent is *in* the user session, so the desktop-notification fix that §10.3 defers becomes a one-line `osascript` call. **The design goes from "the quiet-failure problem is hard to fix" to "the quiet-failure problem is worse, and the fix is now trivial."** Net, that is probably an improvement — but only if the fix is actually taken, which makes §10.3's deferral harder to justify on this target than on Fedora.

**Verdict on §7.10: the stdout-capture mechanism breaks and has an acceptable native substitute (`StandardOutPath` + `newsyslog`); everything code-level survives unchanged; `SyslogIdentifier=` degrades; and the section acquires a new, unlisted weakness — quiet failure — alongside a newly-cheap fix for it.**

---

## 10. Cross-cutting: what the synthesis should carry from this area

1. **The portability boundary, tested here.** The spike frames the boundary as *data/durability stays host-agnostic; operational plumbing may use native facilities freely because it gets replaced wholesale.* This area is almost entirely plumbing, and the prediction mostly held — but with one important correction: **§4.8's staleness alarm looked like plumbing and was not.** "Measure staleness against uptime" is a *semantic* decision that reaches into the data layer (it needs a stored value alongside `last_successful_run_at`) and it silently inverted on the new host. The boundary's failure mode is not "plumbing was expensive to replace"; it is **"something that looked like plumbing turned out to encode a host assumption in a place the data layer depends on."** That is a sharper statement than the one the boundary currently makes, and this area is the evidence for it.
2. **`no Persistent=` is the counter-example that proves the boundary right.** A carefully-reasoned systemd choice turned out to be launchd's inescapable default. Zero porting cost for a decision that took a ticket to make.
3. **Two accepted costs are refunded** (§13.2 rows): `sudo` for unit editing, and no route to the desktop notification bus. Both are consequences of *system* units, which this target does not need.
4. **Three things get worse and are not currently accepted risks:** no drop-in mechanism for third-party services; `plutil -lint` in place of `systemd-analyze verify`; and quiet failure with BTM as a new silent off-switch.
5. **One decision may be reopened by the host, not on its merits:** §4.1's rejection of build-alongside-then-swap for full mode, because the degradation window changes units from hours to weeks (§6.10).

---

## 11. Measure on the actual MacBook — this area's checklist

Ordered by how much a conclusion above depends on them.

| # | Question | How | Depends on it |
|---|---|---|---|
| **M1** | Does a `StartInterval` job fire **immediately on load**, or after one full interval? | A plist with `StartInterval=60`, no `RunAtLoad`, appending a timestamp; `bootstrap` and watch. | §4.4 — whether `OnBootSec`'s purpose is served. |
| **M2** | Does `StartInterval` really **drop** intervals across sleep? Count firings across a lid-close of a known duration. | Same job; sleep 20 min; count lines. | **§1.4 and §4.2 — the two biggest conclusions here.** |
| **M3** | Does `uptime` / `kern.boottime` advance across sleep as documented? | `sysctl -n kern.boottime` and `uptime` before and after a 20-minute sleep. | §1.4. |
| **M4** | Does `CLOCK_UPTIME_RAW` **pause** across sleep and stay monotonic? | `python3 -c "import time; print(time.clock_gettime(time.CLOCK_UPTIME_RAW))"` before/after. | §1.4 — the substitute. |
| **M5** | Does `CLOCK_UPTIME_RAW` survive **standby/hibernation** (long sleep on battery) without going backwards? | Same, across a multi-hour sleep on battery below 50%. | §1.4's residual uncertainty. |
| **M6** | Does `ProcessType=Background` on the runner change Ollama's GPU behaviour at all? (It should not.) | Time a run with and without; watch with `powermetrics`. | §6.2 — confirms §7.7's argument ports. |
| **M7** | Where does a launchd job's stdout go with **no** `StandardOutPath`? `/dev/null`, or the unified log? | A job that prints a unique token; `log show --last 5m \| grep`. | §9.1 — the one gap in the primary sources. |
| **M8** | Can a LaunchAgent post a user notification via `osascript`, and what grant does it need? | One-line agent; observe. | §3.2 ground 4 and §9.4's counterweight. |
| **M9** | Does Python's stdlib `syslog` module reach the unified log, and at what persisted level? | `python3 -c "import syslog; syslog.syslog('token')"`; `log show`. | §9.2 Route B's cost — Agent 4 also wants this. |
| **M10** | What does `brew services start postgresql@18` actually generate — domain, `KeepAlive`, `UserName`, data dir? | `cat ~/Library/LaunchAgents/homebrew.mxcl.postgresql@18.plist`; `launchctl print gui/$UID/...`. | §2.4 — Agent 5's input to §2. |
| **M11** | Does `tome-mcp` starting before Postgres actually recover on the `KeepAlive` restart, and in how long? | Bootstrap both at once from a cold login; count restarts. | §2.3 — "the failure is benign." |
| **M12** | Actual package power draw during one 18 s enrichment call. | `sudo powermetrics --samplers cpu_power,gpu_power`. | §6.6's ~3 Wh/day arithmetic — the assumed 30 W is the weakest number in this document. |
| **M13** | Does an enrichment run **survive** a sleep/wake in the middle of an Ollama HTTP call and a live Postgres session (advisory lock intact)? | Trigger a run, sleep 10 min mid-run, wake, watch. | §6.10's "sleep interruption is a non-event." |
| **M14** | Does `NSProcessInfo.thermalState` ever leave `nominal` on this machine under an enrichment run? | `pyobjc` read during a full run. | §6.8 — whether the thermal check is worth its line. |

**M2, M3 and M4 together settle §1.4 in under an hour**, and §1.4 is the finding this area most wants confirmed before anyone acts on it.

---

## 12. Honest uncertainty

- **Nothing here is measured.** Section 11 exists because that is not a small caveat.
- **`ProcessType=Background` → E-cores-only is *Reported*, not *Documented*.** Apple documents that QoS influences P/E placement; the categorical "background QoS never runs on a P core" comes from a credible secondary source. The conclusion in §6.2 does not depend on the strong form — the weak form (background QoS is meaningfully deprioritised) is enough — but the sentence should not be quoted as Apple's.
- **QoS does not propagate over a plain HTTP call to a separate daemon** is *Reasoned*. If it somehow does, §6.2's conclusion strengthens rather than weakens (the knob would then work), so the error direction is benign — but it would change the recommendation.
- **Whether `launchd` throttles or complains about a `StartInterval` job that exits in 18 ms** (the idle tick) is untested. `ThrottleInterval` governs *respawn*, not interval firings, so it should be a non-issue at 900 s; at a much shorter interval it would not be.
- **The `~3 Wh/day` figure in §6.6 rests on an assumed 30 W package delta** that nobody measured, on a chip nobody profiled, for a call whose duration Agent 1 may revise substantially. It is the weakest quantitative claim in this document and the recommendation against AC-gating leans on it. If Agent 1 finds the M4 Pro takes ~60 s/entry rather than ~18 s, the daily figure triples and the recommendation deserves re-examination.
- **`NSProcessInfo.thermalState`'s exact API surface from Python** was not verified beyond Apple's Foundation documentation existing.
- **The Postgres.app and container routes are sketched, not researched.** Agent 5 owns them; §2.4's rows for those two are the least supported in this document.
- **Apple's direction of travel toward `SMAppService` and app-bundled helpers** is *Reported* and is a multi-year risk, not a current constraint. It is mentioned because a design meant to last should know about it, not because it changes anything today.

---

## Sources

Primary — Apple man pages and headers:
- [`launchd.plist(5)`](https://keith.github.io/xcode-man-pages/launchd.plist.5.html) — `StartInterval`, `StartCalendarInterval`, `KeepAlive`, `ThrottleInterval`, `ProcessType`, `Nice`, `LowPriorityIO`, `LowPriorityBackgroundIO`, `LaunchEvents`, `RunAtLoad`, `StandardOutPath`, `Sockets`, `UserName`, `EnvironmentVariables`, `ExitTimeOut`, and "launchd has no explicit dependency model"
- [`launchd.plist(5)`, mirrored](https://leancrew.com/all-this/man/man5/launchd.plist.html) — used to confirm the verbatim `StartInterval` / `StartCalendarInterval` sleep text
- [`launchctl(1)`](https://keith.github.io/xcode-man-pages/launchctl.1.html) — domains, `bootstrap`/`bootout`/`kickstart`/`enable`/`disable`/`print`, plist ownership
- [`clock_gettime(3)`](https://keith.github.io/xcode-man-pages/clock_gettime.3.html) — `CLOCK_UPTIME_RAW` *"does not increment while the system is asleep"*
- [`xpc/activity.h`](https://github.com/jceel/libxpc/blob/master/xpc/activity.h) — XPC Activity criteria and priorities
- [`IOPowerSources.h`](https://github.com/opensource-apple/IOKitUser/blob/master/ps.subproj/IOPowerSources.h) — `IOPSGetProvidingPowerSourceType`, `kIOPMACPowerKey`
- [`IOPSGetProvidingPowerSourceType`, Apple Developer Documentation](https://developer.apple.com/documentation/iokit/iopowersources_h/1810316-iopsgetprovidingpowersourcetype)
- [`XPC_ACTIVITY_REQUIRE_SCREEN_SLEEP`](https://developer.apple.com/documentation/xpc/xpc_activity_require_screen_sleep) and [`XPC_ACTIVITY_ALLOW_BATTERY`](https://developer.apple.com/documentation/xpc/xpc_activity_allow_battery), Apple Developer Documentation

Primary — Apple developer documentation and forums:
- [Creating Launch Daemons and Agents](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html) — agent vs daemon, plist placement and ownership, *"designed to remove the need for dependency ordering"*, `StandardOutPath`, on-demand guidance
- [Apple Developer Forums thread 118508 — daemons unable to access files or folders](https://developer.apple.com/forums/thread/118508) — TCC and daemons; Apple DTS: *"The simplest solution is to put your daemon inside an app bundle"*; the macOS 26.2 report that FDA cannot be granted to a bare CLI binary
- [Apple Developer Forums thread 23361 — launchd StartInterval changed behavior in 10.11?](https://developer.apple.com/forums/thread/23361) — the 10.9 → 10.11 documentation reversal
- [Optimize for Apple Silicon with performance and efficiency cores](https://developer.apple.com/news/?id=vk3m204o) — QoS influences P/E core placement

Primary — CPython:
- [`time` module documentation](https://docs.python.org/3/library/time.html) — `CLOCK_UPTIME_RAW` (macOS ≥ 10.12), `CLOCK_MONOTONIC`, `CLOCK_BOOTTIME` *"identical to CLOCK_MONOTONIC, except it also includes any time that the system is suspended"*

Secondary, corroborated:
- [How macOS depends on firmlinks — The Eclectic Light Company](https://eclecticlight.co/2023/07/22/how-macos-depends-on-firmlinks/) — the `/usr/share/firmlinks` list including `/opt`
- [Creating root-level directories and symbolic links on macOS Catalina — Der Flounder](https://derflounder.wordpress.com/2020/01/18/creating-root-level-directories-and-symbolic-links-on-macos-catalina/) — read-only System volume, `/etc/synthetic.conf`
- [Explainer: Permissions, privacy and TCC — The Eclectic Light Company](https://eclecticlight.co/2025/11/08/explainer-permissions-privacy-and-tcc/) — the TCC-protected location list
- [Inside the Unified Log 3: Log storage and attrition — The Eclectic Light Company](https://eclecticlight.co/2025/09/29/inside-the-unified-log-3-log-storage-and-attrition/) and [Control what gets written to the log](https://eclecticlight.co/2026/04/30/control-what-gets-written-to-the-log/) — persist levels, ephemeral vs persisted, retention magnitudes
- [How macOS schedules background activities](https://eclecticlight.co/2023/01/21/how-macos-schedules-background-activities/) and [What is Quality of Service, and how does it matter?](https://eclecticlight.co/2025/05/09/what-is-quality-of-service-and-how-does-it-matter/) — background QoS and E-core confinement
- [Login and Background Item Management in macOS Ventura 13 — n8felton](https://n8felton.wordpress.com/2022/10/24/login-and-background-item-management-in-macos-ventura-13/) — BTM, Login Items & Extensions, the "background item added" notification
- [Starting and stopping background services with Homebrew — thoughtbot](https://thoughtbot.com/blog/starting-and-stopping-background-services-with-homebrew) — `brew services` generates `~/Library/LaunchAgents/homebrew.mxcl.*.plist`; `sudo` variant uses `/Library/LaunchDaemons`
- [Why caffeinate does not work with the lid closed](https://clamshell.dev/guides/why-caffeinate-does-not-work-lid-closed) — lid close is a hardware sleep path no assertion overrides
- [`newsyslog(8)`, macOS](https://www.unix.com/man_page/osx/8/newsyslog/) and [Using macOS newsyslog to Rotate Service Logs](https://patelhiren.com/blog/macos-newsyslog-openclaw-logs/) — `/etc/newsyslog.d`, `count`/`size`/`when`, driven by `com.apple.newsyslog`
- [A launchd Tutorial](https://www.launchd.info/) — general launchd reference; `StandardOutPath` debugging guidance
- [Detect how long a user has been idle — jbranchaud/til](https://github.com/jbranchaud/til/blob/master/mac/detect-how-long-a-user-has-been-idle.md) and [Inactivity and Idle Time on OS X — DssW](https://www.dssw.co.uk/blog/2015-01-21-inactivity-and-idle-time/) — `ioreg -c IOHIDSystem` / `HIDIdleTime`
- [`pmset` reference — DssW](https://www.dssw.co.uk/reference/pmset/) and [pmset-drawing-ac-power](https://github.com/SixArm/pmset-commands/blob/master/pmset-drawing-ac-power) — `pmset -g ps`, `Now drawing from 'AC Power'`
- [Setting Up Ollama as a Background Service on macOS](https://medium.com/@anand34577/setting-up-ollama-as-a-background-service-on-macos-66f7492b5cc8) and [ollama-brew-service-setup](https://github.com/ntrlmt/ollama-brew-service-setup) — Ollama as a Homebrew LaunchAgent vs the desktop Login Item
