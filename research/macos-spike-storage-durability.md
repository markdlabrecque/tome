# Storage, durability and at-rest security if Tome targets a MacBook

Research date: 2026-07-26. Spike: [#32](https://github.com/markdlabrecque/tome/issues/32), Agent 5 of 5.
Sections owned: **§7.9**, **§8 (all)**, **§1.4's storage facts**, the **durability rows of §13.2**.
Background decision: [#19](https://github.com/markdlabrecque/tome/issues/19).

Hypothetical target: MacBook Pro, M4 Pro, 48 GB unified memory, macOS, APFS, FileVault presumed on, the only machine, no tailnet, no remote clients.

**Every claim below is tagged.** *Measured* means someone ran it and recorded the number. *Documented* means a primary source says it in as many words, and the source is cited. *Assumed* means it is a reasoned inference from documented facts and nobody has checked it. The PRD's own standard (§13.3), applied here because this section is where getting it wrong is least visible.

**Nothing in this document is measured on the target machine.** The MacBook is a tailnet peer of the Fedora box and was offline during this research; I did not attempt to reach it. Everything that would be settled faster by running a command on it is collected in [§13, Check on the actual MacBook](#13-check-on-the-actual-macbook).

---

## 0. Summary

The headline is real but smaller than the hypothesis assumed, and it arrives with three regressions the hypothesis did not anticipate.

**What genuinely improves:**

1. **At-rest exposure inverts.** On Apple silicon the internal volume is encrypted *before* FileVault is turned on; FileVault entangles the key with the user password. §8.7 does not survive as written — it dissolves and is replaced by its opposite. Exactly **one** argument in §8 was load-bearing on the unencrypted fact and genuinely loosens: **§8.5's characterisation of the 90-day `query_log` window as "a privacy dial"**. §8.3's retraction guarantee does *not* loosen, for a reason worth stating carefully — see §1.4.
2. **Off-machine backup flips from ruled-out to a solved problem, and this is the strongest single argument in my area.** Both facts that ruled it out — `nvme1n1` earmarked for Windows, no always-on tailnet peer — are properties of the Fedora box and simply do not exist on the target. Time Machine to an external disk turns *"a dead disk loses the store and its backups together"* from an accepted risk into a configuration step. It is not literally free (an external SSD, and it must be plugged in), but the reason the Fedora ritual was rejected — *"a mechanism nobody can rely on"* — does not transfer, because Time Machine is automatic, retains on a schedule, and reports its own failures.
3. **`chattr +C` needs no substitute.** APFS is copy-on-write for *metadata*; ordinary file-data overwrites are redirected only when a snapshot or clone pins the extents. There is no user-facing per-file exemption (Apple's `INODE_SNAPSHOT_COW_EXEMPTION` exists and Apple says do not set it), but at Tome's scale on NVMe the mitigation is not needed. This is the cleanest "does not matter here" in the spike.

**What gets worse, and was not in the hypothesis list:**

4. **PostgreSQL's default WAL sync on macOS does not flush the drive write cache.** Documented, in PostgreSQL's own reliability chapter: *"On macOS, write caching can be prevented by setting `wal_sync_method` to `fsync_writethrough`."* The default on Darwin is `open_datasync`. This is a **new build obligation** with a performance cost, and the PRD has never had to think about it because Linux `fdatasync` behaves differently.
5. **APFS does not checksum file data.** Confirmed against Apple's own APFS reference: metadata objects carry a Fletcher-64 `o_cksum`; `j_file_extent_val_t` has no checksum field. §8.2 explicitly leans on btrfs checksumming to withdraw the weekly restore-into-scratch: *"a dump that reads at all is reading its original bytes."* **That sentence is false on APFS.** The withdrawal survives on its other grounds, but one of its two legs is gone.
6. **Deleted content acquires a new residue window.** Time Machine's hourly APFS local snapshots pin freed blocks on the startup volume for up to 24 hours, and the Time Machine backup itself retains per its own schedule. §8.3's guarantee — *"removes content from the live store immediately, and from backups within 7 days"* — needs a clause it did not need on btrfs, where nothing snapshots by default. FileVault makes this tolerable; it does not make it untrue.

**Install route, decisively, for Agent 3: Homebrew `postgresql@18` (18.4, arm64 bottles) + `brew install pgvector` (0.8.5, built per-major against both @17 and @18), run by a launchd *agent* rather than a system daemon.** Reasoning and the launchd consequences in [§9](#9-how-postgres-gets-installed--agent-3s-input). The decisive fact against Postgres.app is that PostgreSQL's own download page describes it as *"Close the app, and the server shuts down"*; the decisive fact against a container is that it puts the store inside a Linux VM disk image that Docker Desktop **excludes from Time Machine by default**. Two Homebrew details Agent 3 needs and that also change §8.2 and §8.9: the formula is keg-only so the binaries are **`pg_dump-18`, `pg_dumpall-18`, `pg_restore-18`**, and a LaunchDaemon needs `--sudo-service-user=` or Postgres refuses to start as root.

**On the framing question — does Time Machine violate the portability boundary?** No, and the reason is precise: **Time Machine should carry `pg_dump` output, not the data directory.** Used that way it is a *transport* for a host-agnostic artifact, which is the opposite of marrying the store to a filesystem. Used the other way — snapshotting `PGDATA` and calling that the backup — it would be exactly the btrfs-snapshot coupling #19 rejected, in a new costume. The boundary holds, and the case sharpens it: the principle is not "never use a host facility", it is **"the recovery artifact must be host-agnostic; how it gets to a second disk need not be."**

### Per-section verdict table

| Section | Verdict | One-line reason |
|---|---|---|
| **§7.9 storage placement** | **Survives with a native substitute** | Paths translate cleanly; `/opt` and `/usr/local` are firmlinked to the writable Data volume. |
| **§7.9's `chattr +C` line** | **Dissolves** | No APFS equivalent exists and none is needed at this scale. Stated as a finding, not a shrug — see §5. |
| **§7.9 clock** | **Dissolves (the Windows half); survives (the server obligation)** | No dual-boot, no `RTC in local TZ`. The `captured_at` skew check becomes structurally unfireable but costs nothing to keep. |
| **§3.11's `chattr +C` row** | **Dissolves** | Same as above. Every other row in that table survives unchanged. |
| **§8.1 what each bound does not touch** | **Survives with an added clause** | The four statements remain true of *Tome's* bounds. A host mechanism (TM snapshots) now retains things Tome's bounds do not reach. |
| **§8.2 backups — mechanism** | **Survives unchanged** | `pg_dump -Fc` is exactly as right on macOS, and more so. |
| **§8.2 backups — destination** | **Reopens and flips** | Both ruling-out facts were Fedora-box facts. This is the spike's strongest durability finding. |
| **§8.2 space arithmetic** | **Survives** | Losing `compress=zstd:1` costs almost nothing — see §6. Free space is the thing to re-measure. |
| **§8.2 free-space guard** | **Survives with changed semantics** | Same coupling on APFS; "free" becomes ambiguous in a *new* way (purgeable snapshots) rather than ceasing to be ambiguous. |
| **§8.2 verification reasoning** | **Survives with one leg broken** | `pg_restore -f /dev/null` is unaffected. The btrfs-checksum reinforcement is void on APFS. |
| **§8.3 retraction** | **Survives; guarantee needs one new clause** | Mechanics are pure SQL and host-independent. The exposure window gains APFS local snapshots and the TM backup set. |
| **§8.4 neighbours' event payloads** | **Survives unchanged** | Entirely inside Postgres. Host-independent. |
| **§8.5 `query_log` 90 days** | **Survives; one of its two justifications dissolves** | The privacy-dial framing was load-bearing on no-LUKS. The judged-set sample-size argument is untouched and was always the calibrating one. |
| **§8.6 `enrichment_events` no pruning** | **Survives unchanged** | Capacity argument; capacity is not the binding constraint on either host. |
| **§8.7 encryption as a calibrating fact** | **Dissolves and inverts** | Needs rewriting from scratch, not porting. |
| **§8.8 version pinning** | **Survives, but its premise is runtime-contingent** | The "no unattended upgrade path" argument is an Ollama-on-Fedora fact. Under MLX/HF it changes shape — see §8. |
| **§8.9 restore procedure** | **Survives with substitutions** | RPM → Homebrew; one new step (locale provider) that the Fedora runbook never needed. |
| **§1.4 storage facts** | **All must be re-measured** | Every storage line in §1.4 is a fact about `nvme0n1`. None transfers. |
| **§13.2 durability rows** | **Two soften, one flips, three new rows appear** | Detailed in §12. |

---

## 1. What the PRD's at-rest fact actually holds up

Before asking what FileVault changes, it is worth being exact about what is currently resting on the absence of LUKS, because the hypothesis says *"several retention bounds were calibrated against a threat that no longer applies"* and that turns out to be **one bound, one framing, and two things that only look like they depend on it**.

§8.7 names four dependents in its own words:

> This does not change any decision above — it *calibrates* several. It is why retraction's threat model is agent reachability rather than forensics (§8.3); why the query log's window is a privacy dial doing real work (§8.5); why the journald bound matters *because* of it rather than instead of it (§7.11); and why the leak tripwire refuses to write a keys file (§7.12).

Taking them one at a time, and separating *what the argument concluded* from *what it needed the fact for*:

### 1.1 §8.5 — the query log window. Load-bearing. This one genuinely loosens.

§8.5's wording is unambiguous:

> **Capacity is irrelevant at any window** — a year costs 4–73 MB against 876 GB free — so **the window controls exactly one thing: how long a record of what you were searching for exists on a disk with no LUKS layer.** It is a privacy dial, stated as one.

That sentence is void on an encrypted volume. What remains is the *other* half of §8.5, which is the half that actually produced the number 90:

> **90 days is calibrated against the only real evidence available.** […] the target is **a few hundred real queries** […] even at a quiet 3/day, 90 days yields ~270.

So the value survives its own derivation intact; what dissolves is the *constraint from above*. On the Fedora box, 90 days was a compromise between "enough queries to build a judged set" (pressure to lengthen) and "how long search text sits unencrypted" (pressure to shorten). **On an encrypted volume only the first pressure exists.** That is a real gain: it removes any reason to shorten the window, and gives a clean argument for lengthening it if the judged set turns out to want more than a few hundred queries.

**Verdict: 90 days survives, its privacy framing dissolves, and the bound becomes free to grow.** This is the single clearest instance of the hypothesis being right.

### 1.2 §7.11 — the journald retention bound. Not mine, but the dependency is real.

Agent 4 owns §7.11 and §7.12. For the record from this side: the §8.7 clause *"why the journald bound matters because of it"* is the same structural argument as §8.5's — a time bound on plaintext residue, where the plaintext is unencrypted. It loosens for the same reason. But Agent 4's harder problem is that the *enforcement mechanism* (a `LogNamespace=` with `MaxRetentionSec=`) may have no macOS equivalent at all, and encryption does not help with that: an unbounded log is still an unbounded log, and invariant C's whole point is that natural keys should not be in it in the first place. **Encryption softens the consequence of a leak; it does nothing about the tripwire that detects one.** I flag this because it is the place where "FileVault fixes it" is most tempting and least true.

### 1.3 §7.12 — the tripwire refusing to write a keys file. Not load-bearing on encryption at all.

The tripwire refuses to persist a file of natural keys. §8.7 lists this as calibrated by the at-rest fact, but the reasoning does not actually need it: writing a file that is *nothing but* a distilled list of every subject in the store is a bad idea on an encrypted disk too, because it concentrates the most sensitive projection of the corpus into one artifact that is readable by anything running as the user on an unlocked machine — which is the threat model that survives FileVault. **Verdict: no loosening. The decision was over-attributed to the at-rest fact.**

### 1.4 §8.3 — retraction's threat model. This is where the hypothesis is subtly wrong.

The §8.3 sentence is:

> **The exposure is tolerable because on an unencrypted filesystem, retraction's threat model cannot be disk forensics** — the live database is equally exposed, so it never was. What retraction actually buys is that content stops being **reachable by an agent** through `search_raw`, stops feeding Entities, and stops surfacing in conversation. A dump file is none of those things.

Read carefully, this is not a bound calibrated *downward* by the missing encryption. It is an argument that a particular objection is **inadmissible**: you cannot complain that a dump leaks to disk forensics when the live database already does. Encryption removes the premise of that argument — and the conclusion **stays true anyway**, because agent reachability was always the *right* threat model for a memory-keeper whose only interface is an LLM. FileVault does not make retraction promise more; it makes the argument for the current promise cleaner, since "the live DB is equally exposed" stops being needed.

There is, however, a direction the hypothesis did not consider. §8.3's guarantee is:

> **Retraction removes content from the live store immediately, and from backups within 7 days.**

On btrfs with no snapshotting configured, "immediately" was very nearly literal at the filesystem layer — the PRD is already honest that Postgres leaves the old tuple in the heap until vacuum and the content persists in WAL. **On APFS under Time Machine, "immediately" gains a host-level exception the PRD has no clause for:** the hourly local snapshot pins the freed extents on the startup volume for up to 24 hours ([Apple, *About Time Machine local snapshots*](https://support.apple.com/en-us/102154) — *documented*), and if the data directory is included in Time Machine backups, the retracted bytes go to the backup disk and stay there per Time Machine's retention schedule, which is much longer than 7 days.

**This is a real regression, and it is one of the two strongest arguments for excluding `PGDATA` from Time Machine entirely** (the other is §3.3). With `PGDATA` excluded, the residue reduces to the 24-hour local-snapshot window, which is *shorter* than the 7 days the PRD already accepts, and it is encrypted. That is a defensible position; it is just not the position the PRD currently states.

**Verdict: §8.3's guarantee survives, but the statement of it needs an added clause naming the local-snapshot window. It does not loosen on FileVault, and its threat-model framing gets *more* defensible, not less.**

### 1.5 What FileVault does not do, stated so it is not overstated

- **It protects a powered-off machine.** Apple: *"FileVault… uses the AES-XTS data encryption algorithm to protect full volumes"*, all key handling in the Secure Enclave, *"encryption keys are never directly exposed to the CPU"*, and *"After a user turns on FileVault on a Mac, their credentials are required during the boot process."* ([Apple Platform Security, *Volume encryption with FileVault in macOS*](https://support.apple.com/guide/security/volume-encryption-with-filevault-sec4c6dc1b6e/web) — *documented*.)
- **It does nothing against a running or unlocked machine.** Apple's document is explicitly about data at rest and does not claim otherwise. Anything running as the user reads the store. Given the PRD's threat model is *agent reachability* in §8.3 and §7.12, **the threat FileVault addresses is largely orthogonal to the threat Tome's bounds address.** This is the correction the hypothesis asked for and it should be stated bluntly: *FileVault dissolves the accepted risk in §13.2 without loosening most of the bounds that risk was said to calibrate.*
- **It does not protect a sleeping machine by default.** A laptop with the lid closed keeps the volume key in memory. There is a `pmset` knob (`destroyfvkeyonstandby`) historically used to force the key out on standby; I could not confirm current Apple-silicon behaviour from a primary source and mark this **unverified**. Practically it means "closed lid on a train" is closer to "unlocked" than to "powered off" for disk-encryption purposes.

### 1.6 The nuance that makes this less of a jump than it looks

On Apple silicon the volume is encrypted **whether or not FileVault is on**: *"If FileVault isn't turned on in a Mac with Apple silicon during the initial Setup Assistant process, the volume is still encrypted but the volume encryption key is protected only by the hardware UID in the Secure Enclave"* ([Apple Platform Security](https://support.apple.com/guide/security/volume-encryption-with-filevault-sec4c6dc1b6e/web) — *documented*). Apple's Data Protection overview puts it as: without FileVault, *"Data Protection defaults to Class C … but uses a volume key rather than a per-extent or per-file key—effectively re-creating the security model of FileVault for user data"*, and *"Users must still opt in to FileVault to receive the full protection of entangling the encryption key hierarchy with their password"* ([Apple, *Data Protection overview*](https://support.apple.com/guide/security/protecting-data-at-rest-secf6276da8a/web) — *documented*).

The practical consequence: even the FileVault-off case on this target is strictly better than `nvme0n1p3`, because the drive cannot be pulled and read elsewhere. FileVault adds the thing that matters against someone who has the whole machine: the key is useless without the password. **So confirming FileVault is on is worth doing (it is item 1 on the check list), but the at-rest inversion does not hinge on it.**

---

## 2. The new threat: loss and theft

The hypothesis is right that this appears, and it deserves to be weighed rather than mentioned.

**What actually changes.** The Fedora box's threat surface for physical access is "someone in the house, or someone who takes the machine from the house". A laptop's is "anywhere the laptop goes", which for a work machine is airports, cafés, cars, and conference rooms. The base rate is not comparable. Against that:

- **FileVault plus Apple silicon is a genuinely strong answer to theft-at-rest.** A stolen, powered-off, FileVault-enabled Mac is not a data breach; it is a hardware loss. This is a materially better position than a stolen Fedora desktop with no LUKS, which *is* a data breach.
- **macOS adds recovery/erase machinery the Fedora box has none of.** Find My supports remote erase, and Apple documents *"Instant remote wipe is available on a Mac with Apple silicon and a Mac with an Apple T2 Security Chip or if FileVault is turned on"*; Activation Lock *"requires your Apple Account password or device passcode before anyone can turn off Find My, erase your Mac, or reactivate and use your Mac"* ([Apple, *If your Mac is lost or stolen*](https://support.apple.com/en-us/102481); [*Activation Lock for Mac*](https://support.apple.com/en-us/102541) — *documented*). Note the caveat Apple states: remote erase requires the Mac to be *"powered on and connected to the internet"*.
- **The exposure that remains is the stolen-while-unlocked case**, and there FileVault contributes nothing. Screen-lock timeout, `Require password immediately after sleep`, and not leaving it open are the whole defence, and they are ordinary laptop hygiene rather than anything Tome can specify.

**The honest net.** Theft becomes much more *likely* and much less *consequential*. My reading is that hypothesis 2 does not offset hypothesis 1 — encrypted-and-stealable beats unencrypted-and-stationary — but it does change which residual risk deserves a row in §13.2, and it changes what the retraction promise is understood to cover. Specifically:

**Retraction interacts with theft in a way worth writing down.** Retraction's promise is about agent reachability, and it delivers that immediately. The thing a user actually fears when they retract something *sensitive* and then lose the laptop is that the content is still on the disk somewhere — in a dump, in a local snapshot, in a heap tuple not yet vacuumed. On the Fedora box the honest answer was "yes, and so is everything else, on an unencrypted disk". On the Mac the honest answer becomes **"yes, but only to someone who has your password"**, which is a much better answer and is one of the clearest end-user-visible improvements in the whole spike.

**One new exposure the desktop did not have: the backup disk.** If Time Machine is adopted (§3), there is now a second copy of everything, on a disk that lives at home. That is the point. But an *unencrypted* Time Machine disk would reintroduce exactly the risk §8.7 records, on new media. Apple documents the fix as a checkbox — *"To encrypt a backup disk, control-click your backup disk, click Encrypt"* ([Apple, *Choose a backup disk and set encryption options on Mac*](https://support.apple.com/guide/mac-help/choose-a-backup-disk-set-encryption-options-mh11421/mac) — *documented*) — and it must be a stated obligation, not an assumption, because Time Machine will happily use an unencrypted disk.

---

## 3. Off-machine backup: does it flip to trivial?

**Yes on the substance; "trivial" is a slight overstatement, and the overstatement is worth naming.**

### 3.1 Both ruling-out facts are Fedora-box facts

§8.2's exclusion rests on exactly two premises, quoted:

> **Destination: `nvme0n1p3` — the same btrfs filesystem as the live database.** Both alternatives were ruled out on facts: `nvme1n1` is earmarked for **Windows**, and the tailnet has **no always-on peer**, leaving only a push to an intermittently-present laptop or a plug-in-a-drive ritual. Both are backups that quietly stop working, and **a mechanism nobody can rely on is worse than a documented gap.**

Neither premise exists on the target. There is no second NVMe earmarked for anything; there is no tailnet; and the "intermittently-present laptop" *is the machine*. The decision does not need porting — it needs re-deciding, and the inputs have changed completely.

### 3.2 What Time Machine actually is, from Apple's documentation

- Frequency: *"hourly, daily, and weekly backups of your files"* ([Apple, *Back up your files with Time Machine on Mac*](https://support.apple.com/guide/mac-help/back-up-your-files-with-time-machine-mh35860/mac) — *documented*).
- Destination must not be the internal disk: Apple's guidance is to back up *"to a location other than your internal disk, such as an external hard disk, a disk on your network, or a Time Capsule"* (*documented*). **So an external disk or a network share is required; there is no zero-hardware option.**
- Local snapshots: hourly, on the startup disk, *"saved for up to 24 hours or until space is needed on the disk"*, APFS only, *"even if your backup disk is not attached"* ([Apple, *About Time Machine local snapshots*](https://support.apple.com/en-us/102154) — *documented*).
- Encryption of the destination is opt-in and documented ([*Choose a backup disk and set encryption options*](https://support.apple.com/guide/mac-help/choose-a-backup-disk-set-encryption-options-mh11421/mac) — *documented*).
- Failure is surfaced to the user; Apple documents the failure states and retry behaviour ([*If a Time Machine backup fails on Mac*](https://support.apple.com/guide/mac-help/if-a-time-machine-backup-fails-mchlb955003d/mac) — *documented*).
- Exclusions are a first-class, scriptable facility: `tmutil addexclusion` (sticky, via the `com.apple.metadata:com_apple_backup_excludeItem` xattr) and `tmutil addexclusion -p` (fixed-path), with `tmutil isexcluded` to verify ([`tmutil(8)`](https://keith.github.io/xcode-man-pages/tmutil.8.html) — *documented*).

### 3.3 Can Time Machine safely capture a live Postgres data directory?

This is the part the hypothesis flagged, and it has a clean answer that is *nearly* yes and should nonetheless be **no**.

**What PostgreSQL says.** The manual is categorical about naive copies and explicit about the snapshot exception ([*File System Level Backup*](https://www.postgresql.org/docs/current/backup-file.html) — *documented*):

> "The database server *must* be shut down in order to get a usable backup. Half-way measures such as disallowing all connections will *not* work (in part because `tar` and similar tools do not take an atomic snapshot of the state of the file system, but also because of internal buffering within the server)."

> "An alternative file-system backup approach is to make a 'consistent snapshot' of the data directory, if the file system supports that functionality (and you are willing to trust that it is implemented correctly)… This will work even while the database server is running. However, a backup created in this way saves the database files in a state as if the database server was not properly shut down; therefore, when you start the database server on the backed-up data, it will think the previous server instance crashed and will replay the WAL log."

Plus two conditions: *"be sure to include the WAL files in your backup"*, and if the database spans filesystems *"the snapshots **must** be simultaneous."*

**Does Time Machine meet the conditions?** On the technical merits, close to yes:

- APFS snapshots are volume-atomic, read-only, point-in-time. Time Machine takes one at the start of each backup and copies from it — Howard Oakley's reconstruction from `backupd`'s own log output is that TM mounts the new "Stable" snapshot and the previous "Reference" snapshot and diffs them ([eclecticlight.co, *How Time Machine makes backups*](https://eclecticlight.co/2018/10/17/how-time-machine-makes-backups/) — *documented as a third-party reconstruction from logs; Apple does not document the mechanism*).
- Under a default Homebrew install, `PGDATA` is a single directory tree on the Data volume with `pg_wal` inside it, so "spread across multiple filesystems" does not arise and the WAL is captured with the heap. (*Assumed* — true of a default `initdb` with no tablespaces, which is Tome's configuration.)

So a full-volume restore of the whole Mac from a Time Machine backup would, in principle, yield a crash-consistent `PGDATA` that recovers by WAL replay. **I would still not rely on it, for four reasons, and the fourth is decisive:**

1. **The consistency guarantee is undocumented by Apple.** Nothing in Apple's Time Machine documentation says a backup is derived from a single atomic snapshot, or that a long or interrupted backup does not span snapshots. PostgreSQL's own caveat is *"and you are willing to trust that it is implemented correctly"*. That is a lot of trust to place in an inference from log lines.
2. **The restore path invites the wrong thing.** Time Machine's user-facing affordance is per-file restore. A `PGDATA` restored file-by-file, or partially, or merged with a newer file, is silently corrupt in a way `pg_restore -f /dev/null` would never catch, because there is no artifact to verify.
3. **It reintroduces exactly the coupling #19 rejected.** *"The store should not marry a Fedora-default filesystem"* generalises without modification to *"the store should not marry an Apple-default filesystem."* A `PGDATA` snapshot is restorable only into the same Postgres major version on a compatible platform; a `pg_dump` *"restores into a newer Postgres than it came from"* and is *"a file on any Unix"*.
4. **It breaks retraction, in precisely the way #18 warned and #19 dissolved.** §3.10 and §8.2 are explicit: the ledger *"composes with a replay into the restored database, whereas a read-only snapshot cannot be replayed into at all and only deleting it removes the content."* A Time Machine copy of `PGDATA` *is* that read-only snapshot. Retract an entry and every Time Machine generation holding `PGDATA` retains it, unreachable by the ledger, for the whole of Time Machine's retention schedule — which is unbounded from Tome's point of view. **This single point is enough on its own.**

**Recommendation, unambiguous:**

- **Exclude the Postgres data directory from Time Machine** (`tmutil addexclusion -p /opt/homebrew/var/postgresql@18`).
- **Include the backup directory** holding the daily `-Fc` dumps, `pg_dumpall --globals-only` output, the retraction ledger, and the `tome.env` copy.
- Everything §8.2 already says about that set is unchanged. Time Machine's only job is to put a copy of an artifact Tome already produces, and already verifies, onto a second physical disk.

This also disposes of a subtle failure mode: the dumps are written once and never modified, so Time Machine's diffing sees a small number of whole new files per day rather than a churning multi-hundred-megabyte directory tree. The backup set is *ideally* shaped for Time Machine, and the data directory is close to worst-case for it.

### 3.4 Does this violate the portability boundary?

**No — and the case sharpens the boundary rather than testing it to destruction.**

The principle as inferred was: *the data and durability layer stays host-agnostic (which is why backups are `pg_dump`, not btrfs snapshots), while operational plumbing may use the host's native facilities freely.* The interesting thing this case reveals is that the principle was stated one notch too coarsely. There are three layers, not two:

| Layer | Example here | Must be host-agnostic? |
|---|---|---|
| **The recovery artifact** | the `-Fc` dump, the globals, the ledger, `tome.env` | **Yes.** This is what #19 protected and it is non-negotiable. |
| **The mechanism that produces it** | a `tome-backup` unit running `pg_dump` on a timer | Ideally, and it is: `pg_dump` on a timer is trivially re-expressible on any init system. |
| **The mechanism that moves it to other media** | `cp` to a second disk, `rsync` to a NAS, **Time Machine** | **No.** This is plumbing by the boundary's own definition — replaced wholesale if the host changes, and losing it costs nothing but the copy. |

Time Machine sits squarely in the third row. If Tome ever moved to a Linux box, you would delete the Time Machine exclusion list, point a `systemd` unit at an external disk, and lose *nothing* — the artifact, the verification, the ledger, and the restore procedure are all unchanged. That is the test the boundary predicts, and it passes.

**The violating version is easy to describe and should be named so it is not proposed later:** using Time Machine's `PGDATA` copy *as* the backup, deleting the `pg_dump` timer on the grounds that the OS already backs everything up. That trades a host-agnostic artifact for a host-specific one and breaks retraction. It is the btrfs-snapshot proposal with an Apple logo.

### 3.5 What Time Machine does *not* fix, stated so the good news is not the only news

- **It is not literally free.** It needs an external disk (Apple: not the internal disk), which is a purchase and a ritual. My claim is not that the ritual disappears but that **the reason #19 rejected the ritual does not transfer**: #19's objection was *"backups that quietly stop working"*, and Time Machine is precisely the counter-example — it runs whenever the disk is present, retains hourly/daily/weekly automatically, and reports its own failures. On a laptop that gets plugged into a desk, the disk is present most days. *This is the argument, and it should be stated as a judgement about reliability rather than as a cost claim.*
- **It does not cover the theft-with-the-disk case**, and it slightly worsens the theft case if the disk is unencrypted (§2).
- **It does not make the 10 GB free-space guard unnecessary** — if anything the guard matters more, because the internal SSD is likely much smaller than 929 GB (§4).
- **It adds a second retention surface Tome does not control**, which is the §8.3 clause noted above and the reason §8.1's "what each bound does not touch" needs a sentence.
- **A first Time Machine backup of a machine holding tens of gigabytes of model weights is slow and large**, which is the model-directory exclusion in §8.

---

## 4. §8.2's free-space guard on APFS

The guard reads:

> **Below 10 GB free: skip the dump and raise a warning instead of writing it.** The failure mode this exists for is not "backups stop working" but **"Postgres stops working"** — `/var/lib/tome` shares a filesystem with root and the live database […] btrfs sharpens this by returning ENOSPC on metadata while apparently having free space.

**The coupling survives identically.** On macOS the Data volume, the system volume, Preboot, Recovery and VM all share one APFS *container* and its free space pool. Postgres's data directory and Tome's backup directory are both on the Data volume. A runaway backup directory fills the container, and Postgres cannot write WAL. Nothing about that changes.

**The btrfs-specific sharpener is replaced by an APFS-specific one, not removed.** On APFS "free space" is genuinely ambiguous, in a documented and slightly perverse way:

- Apple's own APIs distinguish `volumeAvailableCapacity` from `volumeAvailableCapacityForImportantUsage`, the latter being *"the volume's available capacity for storing important resources"* — i.e. counting purgeable space as available ([Apple Developer, `volumeAvailableCapacityForImportantUsage`](https://developer.apple.com/documentation/foundation/urlresourcevalues/volumeavailablecapacityforimportantusage) — *documented*).
- Time Machine local snapshots are the dominant contributor to purgeable space on a Mac with Time Machine on, and macOS deletes them under space pressure (Apple: *"Time Machine automatically removes local snapshots when space is needed on the disk"* — *documented*).
- `statfs`/`statvfs` — what a Python guard using `shutil.disk_usage` or `os.statvfs` will see — reports the **conservative** figure, which is why `df -h /` routinely shows far less available than the Finder. (*Documented indirectly*: the Apple Developer Forums thread on purgeable space and the Finder's use of the "important usage" key; the direction is well-attested but I did not find an Apple sentence stating the `statfs` behaviour explicitly, so treat the direction as *documented* and the exact accounting as *assumed*.)

**Consequence for the guard: it survives unchanged and errs safe.** A `statvfs`-based 10 GB check on APFS will fire *earlier* than macOS's own notion of trouble, because it does not count snapshots as reclaimable. That is the right direction for a guard whose job is to protect Postgres, and it means the guard needs no macOS-specific code. What it does need is a note in the runbook that "10 GB free" on this host may be sitting behind several gigabytes of purgeable snapshots, so `tmutil thinlocalsnapshots` is a legitimate first remediation before deleting anything real.

**The number 10 GB is the thing to revisit, not the mechanism.** On the Fedora box the guard was theoretical: 876 GB free against a bound of ~1.6 GB at 10k entries. On a MacBook that is also holding tens of gigabytes of model weights, Xcode, and everything else, 10 GB may be a live threshold rather than a tripwire that never fires. **This is a check-the-machine item, and it is the one most likely to change a number in the PRD.**

---

## 5. `chattr +C` and APFS copy-on-write

### 5.1 What btrfs's mitigation was for

§3.11: *"Postgres on copy-on-write btrfs fragments badly and suffers write amplification. Applying it after the fact does not affect existing files."* On btrfs, data CoW is unconditional: every overwrite of a database page allocates a new extent, so a heap file becomes a scatter of small extents and every 8 KB page write costs more than 8 KB. `chattr +C` turns that off for the file.

### 5.2 APFS is copy-on-write in a narrower sense

Apple's own reference is precise about *what* is copy-on-write, and it is the object layer:

> "Regardless of their storage, objects on disk are never modified in place, and modified copies of an object are always written to a new location on disk." — [Apple File System Reference](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf), on ephemeral/physical/virtual **objects** (*documented*).

Those are filesystem metadata objects — superblocks, B-tree nodes, the object map. File *data* lives in extents described by `j_file_extent_val_t`, and nothing in the reference says data extents are redirected on ordinary overwrite. The secondary literature agrees and is consistent about the wording: *"One key feature in APFS that makes errors highly improbable is its use of copy-on-write for all file system **metadata**"* ([eclecticlight.co, *Why use APFS?*](https://eclecticlight.co/2025/01/09/why-use-apfs/) — *documented as third-party*).

**The strongest evidence that data-CoW on APFS is snapshot-triggered rather than unconditional comes from Apple's own flag list:**

> **`INODE_SNAPSHOT_COW_EXEMPTION`** — "This inode is exempt from copy-on-write behavior **if the data is part of a snapshot**." […] "Don't add or remove this flag, but preserve the flag if it already exists." […] "The number of files with this flag is tracked by the `APFS_COW_EXEMPT_COUNT_NAME` extended attribute." — Apple File System Reference (*documented*)

and the companion xattr definition:

> **`APFS_COW_EXEMPT_COUNT_NAME`** — "The number of files on the volume that don't use copy on write." […] "This number is used by Time Machine when making snapshots." (*documented*)

Two things follow. First, the exemption is scoped *to the snapshot case*, which only makes sense if the non-snapshot case is not doing data CoW. Second — and this is the direct answer to the hypothesis — **an exact analogue of `chattr +C` exists in APFS's on-disk format and Apple explicitly reserves it.** "Don't add or remove this flag" is as clear a statement as one gets that this is not a knob for third parties.

### 5.3 So is there a user-facing equivalent? No.

`chflags(1)` documents the complete set of file flags on macOS: `arch`/`archived`, `nodump`, `opaque`, `sappnd`, `schg`, `uappnd`, `uchg`, `hidden`, and their clears ([`chflags(1)`](https://keith.github.io/xcode-man-pages/chflags.1.html) — *documented*). **There is no copy-on-write flag, and no `fcntl` equivalent I could find.** *Confirmed absent by enumeration of the man page, which is as strong as a negative gets.*

### 5.4 Does it matter here? No — and the reasoning, not just the verdict

Three independent reasons, in increasing order of force:

1. **The trigger is intermittent, not constant.** Data extents are redirected when pinned by a snapshot or a clone. With Time Machine on, hourly local snapshots mean *some* snapshot almost always pins recent extents — so this is not a rare case. But the snapshots roll off in 24 hours, so the redirection is bounded churn rather than permanent structural fragmentation.
2. **APFS has native defragmentation, and btrfs's equivalent was not in play.** `NX_FEATURE_DEFRAG` and `APFS_FEATURE_DEFRAG` are documented container/volume feature flags (the latter *"ignored by versions before macOS 10.14"*), and `diskutil apfs defragment` exposes them (*documented, but Apple's `diskutil` man-page coverage is minimal and the feature is off by default and aimed at rotational media* — [eclecticlight.co](https://eclecticlight.co/2019/10/19/should-you-enable-defragmentation-on-apfs-hard-drives/)). **I do not recommend enabling it.** It is listed to show the mitigation space is not empty, not because it is needed.
3. **The scale and the medium make it moot.** §1.5 sizes everything at ~20 entries/day, ~7k entries/year, a sub-gigabyte database. Fragmentation's cost is seek latency and read amplification; on internal NVMe there is no seek, and the read amplification of a fragmented sub-GB working set that mostly lives in the buffer cache is not measurable at this scale. Write amplification is bounded by the churn rate, which is twenty rows a day plus whatever a full re-derivation rewrites a handful of times in the system's lifetime.

**Verdict: the `chattr +C` line dissolves. No substitute exists, none is needed, and the honest statement is "the problem the mitigation solved is not present at this scale on this medium" rather than "APFS is not copy-on-write".**

One caveat worth carrying: `chattr +C` on btrfs also *disables checksums* (§5 of the next section), which the PRD noticed and used. Losing the flag on APFS therefore does **not** buy back data checksums, because APFS never had them.

### 5.5 The model-weight directory is a different access pattern and wants a different answer

Per the coordinator's note: wherever weights land, they are large, immutable after download, and read repeatedly. That is the *opposite* of the Postgres pattern. Consequences:

- **CoW is irrelevant to them** — they are written once and never overwritten, so no redirection ever occurs.
- **Compression is irrelevant to them** — GGUF/safetensors weights are already quantised and effectively incompressible; the btrfs `compress=zstd:1` on the Fedora box was doing nothing for `~/.ollama/models` either.
- **Time Machine is very much *not* irrelevant to them**, and that is the actionable part (§8).

---

## 6. Compression, and whether §8's space arithmetic still holds

**It holds, and the reason is more interesting than "it holds".**

### 6.1 APFS does not compress user data

APFS inherits HFS+'s `decmpfs` transparent compression, but it is not applied to ordinary user writes; it is an install/backup facility. `ditto`'s own documentation frames `--hfsCompression` as *"only intended to be used in installation and backup scenarios that involve system files"* and warns against using it on user content (*documented*). There is no volume-level "compress everything" equivalent to `compress=zstd:1`. (*Documented*; the absence of a mount-time option is confirmed by `diskutil`/`mount_apfs` having no such flag.)

### 6.2 But btrfs zstd was already doing almost nothing for Tome

Two facts, both from the PRD's own decisions and from primary documentation:

1. **The Postgres data directory was never compressed on the Fedora box either.** btrfs's documentation is explicit: *"Nodatacow implies nodatasum, and disables compression"* and *"If nodatacow or nodatasum are enabled, compression is disabled"* ([btrfs Administration docs](https://btrfs.readthedocs.io/en/latest/Administration.html) — *documented*). §7.9 applies `chattr +C` to `/var/lib/pgsql/data` before `initdb`. **Therefore `compress=zstd:1` never touched a single Postgres heap page, index page, or WAL segment.** Losing filesystem compression on the target costs exactly zero there.
2. **The backup directory holds files that are already compressed at the application layer.** `pg_dump`'s custom format *"is also compressed by default"*, using *"gzip at a moderate level"* per table-data segment ([PostgreSQL, `pg_dump`](https://www.postgresql.org/docs/current/app-pgdump.html) — *documented*). zstd on top of gzip output recovers a low single-digit percentage at best.

**So §8.2's table — ~16 KB/entry, ~160 MB at 1k, ~1.6 GB at 10k, ~8 GB at 50k — transfers unchanged**, because it was arithmetic on *compressed dump size* to begin with, not on filesystem-compressed bytes. This is a case where the Fedora-specific detail turns out to have been decorative.

### 6.3 What actually changes in the space budget

Not compression — **capacity and competition**:

| Input | Fedora box | Target | Effect |
|---|---|---|---|
| Free space | **876 GB measured** | unknown, plausibly 100–1500 GB | The 10 GB guard may become live. Check the machine. |
| Competing consumers | Ollama blobs ~9 GB | model weights (size TBD by Agent 1), Xcode, everything a work laptop holds | Materially more competition for the same pool. |
| Snapshot overhead | none (no snapshotting configured) | up to 24 h of hourly local snapshots, purgeable | New consumer, self-limiting, invisible to `statvfs` as free. |
| Compression | zstd:1 on the backup dir only, ~nil benefit | none | ~nil change. |

**Verdict: §8.2's space arithmetic survives; §8.2's free-space *guard* survives with the caveats in §4; the 888/876 GB figure in §1.4 and §8.5 is a Fedora fact that must be re-measured and appears in the reasoning of two sections.**

---

## 7. Durability primitives that got *worse*: `fsync` on macOS

**This was not in the hypothesis list and it is the most concrete regression I found.**

### 7.1 The facts

- PostgreSQL's reliability chapter says it in one sentence: **"On macOS, write caching can be prevented by setting `wal_sync_method` to `fsync_writethrough`."** ([PostgreSQL, *Reliability*](https://www.postgresql.org/docs/current/wal-reliability.html) — *documented*.)
- The mechanism, from a PostgreSQL committer on `pgsql-hackers`: **"On macOS, our fsync and fdatasync levels *don't* flush drive caches, because those system calls don't on that OS, and they offer a weird special fcntl, so there we offer [`fsync_writethrough`] for a good reason."** (Thomas Munro, [pgsql-hackers, 2022-08-26](https://www.postgresql.org/message-id/CA%2BhUKGJ2CG2SouPv2mca2WCTOJxYumvBARRcKPraFMB6GSEMcA%40mail.gmail.com) — *documented*.) The fcntl is `F_FULLFSYNC`.
- The default is not `fsync_writethrough`. PostgreSQL's `xlogdefs.h` selects:
  ```c
  #if defined(PLATFORM_DEFAULT_WAL_SYNC_METHOD)
  #define DEFAULT_WAL_SYNC_METHOD		PLATFORM_DEFAULT_WAL_SYNC_METHOD
  #elif defined(O_DSYNC) && (!defined(O_SYNC) || O_DSYNC != O_SYNC)
  #define DEFAULT_WAL_SYNC_METHOD		WAL_SYNC_METHOD_OPEN_DSYNC
  #else
  #define DEFAULT_WAL_SYNC_METHOD		WAL_SYNC_METHOD_FDATASYNC
  #endif
  ```
  and `src/template/darwin` does **not** define `PLATFORM_DEFAULT_WAL_SYNC_METHOD` — the file contains only sysroot, `CFLAGS_SL`, semaphore selection and `DLSUFFIX` (both files read verbatim from [postgres/postgres master](https://raw.githubusercontent.com/postgres/postgres/master/src/include/access/xlogdefs.h) — *documented*). On Darwin `O_DSYNC` and `O_SYNC` differ, so **the default resolves to `open_datasync`, which does not flush the drive cache.**
  *Note the derivation:* the O_DSYNC ≠ O_SYNC step on Darwin is *assumed* from the Darwin headers, not verified by running `SHOW wal_sync_method` on the target. **Verifying it is a one-line check on the machine** and is on the list.

### 7.2 Why this matters here and why it partly doesn't

**Why it matters.** Tome's capture path is the one thing the PRD protects hardest — `capture_entry` is the only write path, raw is the sole source of truth, and a failed capture fails visibly so the user retypes it. A *silently lost* capture is a different animal, and an unflushed drive cache at power loss is exactly how you get one: the transaction commits, the client is told it succeeded, and the WAL record was in a volatile cache. This is precisely the failure `fsync` exists to prevent, and on macOS the default does not prevent it.

**Why it partly doesn't.** The event required is *power loss or hard shutdown*, not a crash. A kernel panic, an OOM, a `SIGKILL`, or a forced restart all leave the drive powered and the cache intact. On a laptop with an internal battery, unexpected total power loss is rare in a way it is not on a mains-powered desktop with no UPS — **so the Fedora box arguably had the higher base rate for the triggering event even though it had the safer default.** Weighing them honestly: the target has a worse default and a lower event rate, and the fix is a one-line configuration change.

### 7.3 What to do

**Set `wal_sync_method = fsync_writethrough` explicitly in `postgresql.conf`, and record it as a build obligation.** Costs: `F_FULLFSYNC` is markedly slower than `open_datasync` because it actually waits for the drive to flush. At 20 commits/day this is not a throughput concern; the one place to watch is the **capture-time embedding path's 5 s budget** (§4.5), and even there the commit is one small transaction.

**Two adjacent items, for completeness:** `full_page_writes` should stay on (default) — APFS's 4 KB block size does not match Postgres's 8 KB page, so torn pages are possible and `full_page_writes` is the defence, exactly as on btrfs. And `fsync` itself obviously stays on. Neither needs a decision; they need not to be quietly changed by an installer.

---

## 8. The backup set under a different inference runtime

Per the coordinator's scope note. Agent 1 owns the runtime question; this is confined to §8.2's exclusion list and to Time Machine.

### 8.1 State the exclusion conditionally

§8.2 currently reads: *"Deliberately excluded: the ~9 GB of Ollama blobs (re-pullable; their pinning is structural, §8.8)"*. The PRD is honest around §3.7 that "re-pullable" is weaker than it sounds: Ollama refuses digest-addressed models, `latest` is a mutable pointer, and Ollama prunes unreferenced blobs at server start, so *"once upstream republishes, the artifact that embedded the first 500 entries is gone from both the registry and the disk"* — the recorded digest buys detection, not prevention.

**Under a HuggingFace-sourced runtime the justification gets strictly stronger, and I can support that with primary documentation:**

- **Exact-revision pinning is a first-class, documented parameter.** `hf_hub_download(..., revision="877b84a8f93f2d619faa2a6e514a32beef88ab0a")` and `snapshot_download(..., revision=...)` accept a branch, tag, or commit hash, with the note *"When using the commit hash, it must be the full-length hash instead of a 7-character commit hash"* ([HuggingFace Hub, *Download files from the Hub*](https://huggingface.co/docs/huggingface_hub/en/guides/download) — *documented*). This is the thing Ollama structurally refuses.
- **The local cache is revision-addressed on disk**: `~/.cache/huggingface/hub/models--<org>--<name>/snapshots/<commit-sha>/`, with content-addressed blobs behind it (*documented*, from the same page's example paths).
- **The runtime does not garbage-collect it.** Cache deletion in `huggingface_hub` is an explicit user action (`hf cache delete` / the delete-cache helper), not something that happens at process start. (*Documented* that explicit deletion tooling exists; *assumed* that nothing prunes automatically — but no auto-prune is documented anywhere, and the absence of one is the opposite of Ollama's documented behaviour.)

**So the conditional statement for §8.2 would be:**

> Model weights are excluded from the backup set because they are re-obtainable. Under Ollama this is a weak justification — digests cannot be requested, tags are mutable, and unreferenced blobs are pruned at server start — so the epoch digest buys detection rather than prevention (§3.7). **Under a HuggingFace-sourced runtime the justification is strong**: a full commit SHA names an immutable revision, the cache is revision-addressed on disk, and nothing prunes it, so a restore can re-obtain the *same* artifact rather than a same-named one. If the runtime changes, this exclusion should be restated, not inherited.

**A second-order effect worth flagging to Agent 1 and the synthesis:** if weights become genuinely pinnable, the Derivation Epoch's model fields stop being *attribution-only* for the embedding axis. §3.7's claim that *"reproducibility is unreachable, not merely expensive"* rests substantially on the Ollama fact. That is not my section to re-decide, but the spike should notice that the strongest evidence for it evaporates under a runtime change.

### 8.2 Time Machine and the model directory

**Yes, exclude it, explicitly, and say so as a recommendation rather than a caveat.**

- Tens of gigabytes of immutable, re-downloadable, incompressible files would be copied in the initial backup and then sit in every generation. On a Time Machine disk sized for a laptop this is a large fraction of the budget spent on bytes that are, by §8.2's own logic, not worth backing up.
- The mechanism is standard and scriptable: `tmutil addexclusion -p ~/.cache/huggingface` (or `~/.ollama/models`, or wherever Agent 1 lands), verified with `tmutil isexcluded`. Both verbs are documented in `tmutil(8)` and both require root and Full Disk Access for some forms (*documented*).
- Use the **fixed-path** form (`-p`) rather than the sticky xattr form, because a model cache is a directory that gets rebuilt rather than moved, and a path exclusion survives the directory being deleted and recreated. (`tmutil(8)`: the default sticky exclusion *"follows a file or directory"* and lives in an xattr; the `-p` form is *"agnostic of the item at that path"* — *documented*.)
- **Also exclude the Postgres data directory** (§3.3) and, if adopted, any container VM disk image (§9.4), for the same reason plus the consistency reason.

The general shape: **Time Machine should back up exactly what §8.2 already says the backup set is, and nothing else Tome owns.** That is a pleasingly small configuration and it makes the exclusion list a legible artifact rather than an accident.

---

## 9. How Postgres gets installed — Agent 3's input

**Recommendation: Homebrew `postgresql@18`, with `brew install pgvector`, started by a launchd *agent* under the user's login, with an explicitly re-run `initdb` using the builtin `C.UTF-8` locale provider.**

### 9.1 Homebrew — the recommendation

*Documented, from the formula source and Homebrew's own tree:*
- `postgresql@18` is current at **18.4**, with `arm64_tahoe`, `arm64_sequoia` and `arm64_sonoma` bottles — prebuilt Apple-silicon binaries, no compilation ([formula source](https://github.com/Homebrew/homebrew-core/blob/master/Formula/p/postgresql%4018.rb); [formulae.brew.sh](https://formulae.brew.sh/formula/postgresql@18)).
- Data directory, from the formula's own caveats: *"This formula has created a default database cluster with: `initdb --locale=en_US.UTF-8 -E UTF-8 $HOMEBREW_PREFIX/var/postgresql@18`"* — on Apple silicon, **`/opt/homebrew/var/postgresql@18`**, with `postgresql.conf` inside it. The `initdb` step is idempotent (guarded on `PG_VERSION` existing), so an upgrade never re-inits over a live cluster.
- **`pg_trgm`: yes.** The formula runs `make install-world`, which PostgreSQL defines as *"everything that can be built, including the additional modules (contrib)"* ([PostgreSQL, *Installation from Source*](https://www.postgresql.org/docs/18/install-make.html)). `pg_trgm` is contrib and is a **trusted** extension, so it installs without superuser.
- **pgvector: better than expected.** The Homebrew `pgvector` formula is at **0.8.5** and builds *once per PostgreSQL major*, shipping both `lib/postgresql@17/vector.so` and `lib/postgresql@18/vector.so` in one bottle; the formula's own test runs `CREATE EXTENSION vector;` against each. pgvector's README: *"With Homebrew Postgres, you can use: `brew install pgvector`. Note: This only adds it to the `postgresql@18` and `postgresql@17` formulas"* ([pgvector README](https://github.com/pgvector/pgvector)). **So the "bottle built against the wrong major" hazard does not exist inside the {17, 18} window.** The forward risk — the formula's pair sliding to {19, 20} and dropping 18 — is real but multi-year, and is *unverified* (no Homebrew policy documents an N/N−1 rule; it is inferred from the formula's shape).

**Why this over the others:**

- It is the only route that gives a **plain Unix filesystem layout** — a real `PGDATA` directory, a real `postgresql.conf`, real client binaries — which is what every line of §8.2 and §8.9 assumes.
- It is the only route where **`tmutil addexclusion -p <PGDATA>`** names a stable, sensible path.
- It is the only route with a **documented LaunchDaemon path** (§9.5).
- It is the closest structural analogue to the Fedora RPM story, which means §8.9's restore procedure ports by substituting a small number of lines.

**Three real costs, stated plainly. Two are new obligations for §8.2 and §8.9.**

1. **The default locale is wrong for a store meant to be portable.** Homebrew's `initdb --locale=en_US.UTF-8` uses the **libc** provider, i.e. Darwin's C library collation. PostgreSQL warns that `LC_COLLATE`/`LC_CTYPE` *"affect the sort order of indexes, so they must be kept fixed, or indexes on text columns would become corrupt"*, and that with libc *"the same locale name may have different behavior on different platforms"* ([PostgreSQL, *Localization*](https://www.postgresql.org/docs/current/locale.html) — *documented*). **This directly weakens §8.2's proudest claim** — that a dump *"is a file on any Unix"* — because restoring a Darwin-libc-collated dump onto glibc rebuilds every text index under a different ordering.
   **Fix, and it is a genuine improvement over the Fedora setup rather than a patch:** discard Homebrew's auto-created cluster and re-run `initdb --locale-provider=builtin --locale=C.UTF-8 -E UTF-8`. PostgreSQL documents the builtin provider as supporting only `C`, `C.UTF-8` and `PG_UNICODE_FAST`, with `C.UTF-8` collating *"using the code point values only"* — no libc, no ICU, no version drift, identical on every platform. Tome does no natural-language sorting; its text comparisons are equality on `natural_key` and trigram similarity. **Nothing in the PRD wants `en_US.UTF-8`.**
   *This is a finding about the current Fedora spec too, not only about the port.*
2. **The formula is keg-only, so the client binaries are suffixed.** `postgresql@18` is `keg_only :versioned_formula`; its `post_install_steps` runs `link_children "bin", suffix: "-18"`, which puts **`/opt/homebrew/bin/pg_dump-18`, `pg_dumpall-18`, `pg_restore-18`, `psql-18`** on `PATH` and leaves the bare names unlinked. Every command line in §8.2 and §8.9 therefore changes — either to the suffixed names or by prepending `/opt/homebrew/opt/postgresql@18/bin` to the unit's `PATH`. **Prefer the explicit absolute path in the backup and restore scripts**, because it pins the major version the dump was taken with, and because PostgreSQL is categorical about the skew direction: *"pg_dump cannot dump from PostgreSQL servers newer than its own major version; it will refuse to even try"* ([`pg_dump`](https://www.postgresql.org/docs/18/app-pgdump.html) — *documented*). A stray older `libpq` on `PATH` is a real way to break the backup timer silently.
3. **Major-version upgrades are manual — but the footgun the PRD would have expected is gone.** There is no unversioned `postgresql` formula (`postgresql` is an alias to `postgresql@18`, which is keg-only and versioned), so **`brew upgrade` cannot move you across majors and cannot orphan the data directory** — it only ever goes 18.4 → 18.5. Moving to 19 is an explicit `brew install postgresql@19` plus a hand-run `pg_upgrade`, with `var/postgresql@18` left untouched beside the new cluster.
   The one thing to record now: **Homebrew's `brew postgresql-upgrade-database` wrapper was deleted in Homebrew 4.3.0 (2024-05-07) as unfixable** — the deprecation commit says *"this command is broken and we're not going to fix it"*. So the runbook must carry the raw `pg_upgrade` invocation, or fall back to §8.2's dump-and-restore, which for a sub-gigabyte database is the simpler and more honest path anyway. **My recommendation: make dump-and-restore the documented major-upgrade procedure and never run `pg_upgrade`.** It reuses machinery §8.9 already requires to be correct, and it exercises the restore path on a schedule rather than never.

### 9.2 Postgres.app — ruled out, on one decisive fact

It is genuinely good software and the closest runner-up: v2.9.5 ships **PostgreSQL 18.4** as a verified universal binary (`lipo -verify_arch arm64 x86_64` in its own makefile), builds with `make install-world` so full contrib including `pg_trgm` is present, and **bundles pgvector** — pgvector's README lists it as a preinstalled source. Data directory: `~/Library/Application Support/Postgres/var-18`.

**But it is a login-session GUI app, not a service, and its trajectory is away from being one.** PostgreSQL's own download page describes it as: *"Open the app, and you have a PostgreSQL server ready and awaiting new connections. **Close the app, and the server shuts down.**"* Autostart is an `SMAppService` login item, never a LaunchDaemon. Its 3.x line makes this stricter — *"Servers now stop automatically when you quit Postgres.app or log out"*. And the maintainer's own answer to the daemon question is: *"I recommend to create a launch daemon that uses `pg_ctl`… **However, that is an advanced topic, and I don't know much about the details, so I can't really help there.**"*

Two secondary marks against it for this specific system: it bundles **pgvector 0.8.2** while Homebrew and the containers are on **0.8.5**, which is a live restore-skew hazard for §8.9 (*unverified* whether a 0.8.5→0.8.2 restore actually fails, but it is the wrong direction to be guessing about); and it requires `ALTER EXTENSION vector UPDATE;` after app updates, which is an unattended-upgrade path §8.8 would have to think about.

**Ruled out** — for a system built around a background enrichment timer and a background backup timer, a database that stops when you log out is a structural problem, not an inconvenience.

### 9.3 EDB installer — ruled out on a fact, not on fit

EDB does ship an arm64 macOS installer for PG 18. **But pgvector is not packaged for it on macOS** — EDB's pgvector distribution is Linux-repo-only, and pgvector's README mentions EDB solely as a `pg_config` path for *compiling from source* (`/Library/PostgreSQL/18/bin/pg_config`). That means hand-compiling pgvector with Xcode command-line tools and re-compiling on every PostgreSQL minor. All of Homebrew's downside, none of its packaging. **Ruled out.**

### 9.4 Container — ruled out, and the reason is my section's

`pgvector/pgvector:pg18-trixie` and friends exist as native multi-arch images (linux/arm64 published, no qemu), so the extension story is the easiest of any route and the version is pinnable in the tag. It is nonetheless the **worst** route here, for reasons that are specifically about storage and durability:

- **On Apple silicon the container's storage lands inside a VM disk image on the host.** Docker's own macOS FAQ: *"Docker Desktop stores Linux containers and images in a single, large 'disk image' file in the Mac filesystem"*, with the worked example at `~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw` (*documented*). Every property §8.2 relies on degrades: `PGDATA` is no longer a path you can exclude from Time Machine independently of every other container; the 10 GB free-space guard would measure the VM's view rather than the host's; and Docker documents that **space is not reclaimed automatically** — *"Space is only freed when images are deleted. Space is not freed automatically when files are deleted inside running containers"*, requiring a manual `docker/desktop-reclaim-space` run.
- **Docker Desktop already excludes its VM from Time Machine by default** (Settings → General → "Include VM in Time Machine backups", default **Disabled**). So on the container route, the naive "Time Machine backs up my Mac" answer silently backs up *none of Tome's data*. That is a trap, and it is the sort of trap the PRD's free-space guard and verification step exist to avoid.
- **It marries the store to a runtime**, which is the same failure mode as marrying it to a filesystem. "The store is a directory on a Unix filesystem" is worth keeping.
- **No documented headless-at-boot story on macOS.** Docker Desktop's autostart is *"when you sign in"*; there is no documented LaunchDaemon path, and *"Docker Desktop can only be run by one user-account per machine"*. OrbStack does document a real headless mode and has a better sparse-file story (auto-shrinking `data.img`), and would be the pick if a container were forced — but it is closed-source and commercially licensed, and it does not fix the disk-image indirection.
- One more trap worth recording because it is easy to get wrong: **PostgreSQL 18's official image changed `PGDATA`** to `/var/lib/postgresql/18/docker` with the volume at `/var/lib/postgresql` (*documented on Docker Hub*), so a mount written from 17-era memory silently produces a non-persistent database.

**The one thing the container route is genuinely good for, and should be kept for: restore rehearsal.** §8.9's *"walked by hand once at deploy time"* obligation is far cheaper to satisfy against a throwaway `pgvector/pgvector:0.8.5-pg18-trixie` container than against the live install, and it needs no `CREATE DATABASE` on the real cluster — which is precisely the objection #19 raised to a restore-into-scratch. That is a testing convenience, not a deployment choice, and it is worth naming because it makes the *procedure* rehearsable, which is the risk §8.9 actually manages.

### 9.5 The launchd consequences Agent 3 needs, and the FileVault interaction

Four things follow from choosing Homebrew. The third is a hard trap and the fourth is easy to miss.

1. **`brew services` can produce either a LaunchAgent or a LaunchDaemon, and this is documented.** From `brew services`' own usage text: *"If `sudo` is passed, operate on `/Library/LaunchDaemons` … (started at boot). Otherwise, operate on `~/Library/LaunchAgents` … (started at login)."* The plist is named `homebrew.mxcl.postgresql@18.plist`. The formula's service block runs `postgres -D /opt/homebrew/var/postgresql@18` with `keep_alive true`, `run_type: immediate` (so `RunAtLoad=true`, `KeepAlive=true`), logging to `/opt/homebrew/var/log/postgresql@18.log`. **So the "system unit vs user unit" choice that §7.3 agonised over is available on this target, in both directions, from one flag.**
2. **§7.3's hard constraint has a different shape here.** #15 chose *system* units because a user unit cannot order against `postgresql.service`. Here, both Tome and Postgres can be placed in the same launchd domain by choice — agent-and-agent, or daemon-and-daemon. That removes the cross-domain mismatch that forced the Fedora decision. Whether launchd can express ordering *at all* is Agent 3's question; my contribution is that the Homebrew route does not force the split.
3. **The LaunchDaemon route has a footgun that will look like a mystery: PostgreSQL refuses to run as root.** `check_root()` in `src/backend/main/main.c`: *"'root' execution of the PostgreSQL server is not permitted. The server must be started under an unprivileged user ID…"*, echoed in the docs. A plain `sudo brew services start postgresql@18` writes a plist with **no `UserName` key**, so `postgres` exits immediately at boot and keeps exiting under `KeepAlive`. The documented fix is Homebrew's `--sudo-service-user=` flag, which injects `UserName` into the plist:
   ```
   sudo brew services start --sudo-service-user=<user> postgresql@18
   ```
   **Agent 3 should treat this as a required detail, not a footnote** — it is exactly the kind of thing that produces "the database isn't there after a reboot" with a clean-looking `launchctl list`.
4. **FileVault makes the boot-time daemon much less valuable than it looks, and this is a storage fact.** With FileVault on, *"their credentials are required during the boot process"* — the Data volume, and therefore `/opt/homebrew/var/postgresql@18`, is not available until a user authenticates. **A LaunchDaemon pointed at a Data-volume path cannot usefully run "before login" on a FileVault machine.** So on this target the daemon-vs-agent choice collapses: they fire at nearly the same moment, and the agent is simpler, needs no `--sudo-service-user`, and matches the fact that the only consumer of the service is the logged-in user. **Recommendation to Agent 3: LaunchAgents throughout, and treat the daemon option as available-but-pointless rather than unavailable.** (*Documented* that credentials are required at boot; *assumed* that a Data-volume-path daemon therefore fails or blocks — the exact failure mode is a check-the-machine item, #10.)

---

## 10. §7.9 storage placement, translated

### 10.1 The paths

macOS's system volume is read-only and cryptographically sealed — *"a dedicated, isolated volume for system content"* whose seal *"encompasses every byte of data in the SSV"* ([Apple, *Signed system volume security*](https://support.apple.com/guide/security/signed-system-volume-security-secd698747c9/web) — *documented*). Writable content lives on the Data volume, reached through firmlinks. **`/opt` and `/usr/local` are among the firmlinked paths**, which is why Homebrew installs to `/opt/homebrew` on Apple silicon and `/usr/local` on Intel. (*Assumed* from the firmlink list at `/usr/share/firmlinks`; Apple's SSV document does not enumerate it. One-line check on the machine: `cat /usr/share/firmlinks`.)

Proposed translation:

| PRD path | Target | Note |
|---|---|---|
| `/var/lib/pgsql/data` | `/opt/homebrew/var/postgresql@18` | Homebrew's own default; do not fight it. **Exclude from Time Machine.** |
| `/var/lib/tome/` | `/opt/homebrew/var/tome/` or `/usr/local/var/tome/` | Either is firmlinked and writable. Prefer *not* `~/Library`, so a daemon-or-agent choice does not change the path. |
| `/var/lib/tome/dumps/` | `…/var/tome/dumps/` | unchanged in role |
| `/var/lib/tome/backups/` | `…/var/tome/backups/` | **`0700`, owned by the running user. Include in Time Machine.** |
| `/opt/tome/` | `/opt/tome/` | `/opt` is firmlinked; the path ports literally. |
| `/etc/tome/tome.env` | `/opt/homebrew/etc/tome/tome.env` or `/etc/tome/` | `/etc` → `/private/etc` is writable, but Homebrew convention favours its own `etc`. |

**The `chattr +C` line is deleted, not substituted** (§5).

**Do not put the data or the backups under `~/Documents`, `~/Desktop`, `~/Downloads`, or anywhere iCloud Drive syncs.** The first three are TCC-protected and would make a background job prompt or fail; the last would be an egress violation. Homebrew's `var` tree avoids all four. (TCC specifics are Agent 3's; the placement consequence is mine, and it is the reason for preferring a Homebrew-prefix path over a home-directory path.)

### 10.2 The clock

§7.9's clock discussion is in two halves and they separate cleanly.

**The Windows/RTC half dissolves entirely.** There is no dual boot, no `RTC in local TZ: yes`, no `RealTimeIsUniversal` registry key. macOS keeps the RTC in UTC and syncs against Apple's time service. The named NTP egress exception (§1.3) is Agent 2's, but the *reason* §7.9 gave for wanting the RTC right independently of the network — *"the clock is then right before the network comes up"* — is satisfied structurally rather than by configuration.

**The server obligation half survives, and half of it becomes unfireable.** §7.9 requires the server to compare incoming `captured_at` against its own clock and flag wild disagreement, because *"capture from the MacBook and it is the MacBook's clock"*. On an on-device install with a single machine, **client and server are the same clock**, so the comparison can never disagree. Two readings:

- *Delete it* — it is dead code guarding an impossible case.
- *Keep it* — it costs a subtraction and a comparison, it is the kind of check that pays for itself the day the assumption changes, and §3.2's immutability makes a wrong date permanent. **I prefer keeping it**, on the grounds that the cost is nil and the failure it prevents is unrecoverable.

The second obligation — *"tolerate a future-dated `last_successful_run_at`"* — survives unambiguously, and if anything matters more: a laptop that sleeps and resyncs its clock on wake produces exactly the backwards correction that obligation exists for. (Sleep semantics are Agent 3's; the tolerance requirement is mine and it does not weaken.)

---

## 11. §8 section by section, with the exact edit each would need

Consolidating, because "survives with a substitute" is only useful if the substitute is named.

**§8.1 — What each bound does not touch.** All four statements remain true *of Tome's bounds*. One sentence would need adding, and it is not a Tome bound at all:

> A fifth thing now retains content Tome's bounds do not reach: the host's own backup machinery. APFS local snapshots pin deleted blocks on the startup volume for up to 24 hours, and any Time Machine generation holding the backup set retains those dumps on the backup disk for as long as Time Machine keeps that generation. Neither is under Tome's control, and neither holds a Raw Entry that Tome's own retention would have removed — but the retraction guarantee (§8.3) has to name them.

**§8.2 — Backups.** Mechanism unchanged; two paragraphs need replacing.
- *Destination*: replaces "same filesystem, media failure accepted" with "same filesystem for the working set, Time Machine to an external encrypted disk for the second copy". The accepted risk downgrades from *accepted* to *conditional on the disk being connected*.
- *Verification*: the sentence *"btrfs checksums all data by default and returns EIO rather than bad bytes […] so the backup directory keeps them, and a dump that reads at all is reading its original bytes"* must be **deleted**, not translated. APFS checksums metadata objects with Fletcher-64 (`obj_phys_t.o_cksum`) and has no checksum field on file-data extents (`j_file_extent_val_t` is `len_and_flags`, `phys_block_num`, `crypto_id`) — both read directly from the [Apple File System Reference](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf) (*documented*), and corroborated by the standard analysis that APFS *"checksums metadata objects (Fletcher-64) but does not checksum user data blocks"* ([Adam Leventhal, *APFS in Detail: Data Integrity*](https://ahl.dtrace.org/2016/06/19/apfs-part5/) — *documented as third-party*). Apple's stated rationale is that device-level ECC suffices.
  **What this costs:** the withdrawal of the weekly restore-into-scratch had two legs — (a) `pg_restore -f /dev/null` already catches every kind of corruption a re-read would, and (b) the filesystem guarantees you are re-reading original bytes anyway. Leg (a) is untouched and is the stronger one: `-f /dev/null` decompresses and processes every data block on the day the dump is written. Leg (b) is gone, which means **silent bit rot in an old dump is no longer excluded by the filesystem**. The proportionate response is not to reinstate a weekly restore; it is to note that the daily verification covers freshly-written dumps and that the 7-day rotation means no dump is old. If a longer-retention tier is ever added, this reasoning has to be revisited. **Optionally**: `pg_restore -f /dev/null` over the *oldest* retained dump as well as the newest costs seconds and closes the gap entirely — cheap enough to be worth naming.

**§8.3 — Retraction.** Mechanics survive untouched; two sentences change.
- *"The exposure is tolerable because on an unencrypted filesystem, retraction's threat model cannot be disk forensics"* → the premise is void, the conclusion stands on its own merits, and the restatement is *stronger*: agent reachability is the right threat model for an LLM-only interface, and forensics is now separately defended by FileVault rather than conceded.
- The guarantee gains a clause: *"…and from backups within 7 days"* → *"…and from Tome's backups within 7 days; freed blocks may persist in APFS local snapshots for up to 24 hours, and if the data directory is not excluded from Time Machine, indefinitely."* **The excluded-`PGDATA` recommendation in §3.3 is what makes the second half of that clause not apply**, which is a good argument for writing the exclusion into the deploy step rather than the runbook.
- The scoped-purge paragraph (`journalctl --namespace=tome --rotate --vacuum-time=1s`) is Agent 4's; it is the one part of §8.3 I expect to break rather than substitute.

**§8.4 — Neighbours' event payloads.** Entirely inside Postgres. **Survives unchanged**, verbatim.

**§8.5 — `query_log` 90 days.** Survives; the privacy-dial paragraph dissolves (§1.1). The exclusion mechanism (`--exclude-table-data=query_log`, DDL retained) is a `pg_dump` flag and is host-independent. Note that the paragraph's justification for the exclusion — that an arbitrarily-old pre-migrate dump would otherwise hold expired query text — **still holds and is now the only reason**, since the disk it would sit on is encrypted. That is fine: the reason was always about the *bound being a fiction*, not about the disk.

**§8.6 — `enrichment_events` no pruning.** Capacity argument against a number (~300 MB ever). **Survives unchanged**, subject to the free-space re-measurement.

**§8.7 — Encryption as a calibrating fact.** **Dissolves and inverts.** The replacement is not a translation; it is a new short section saying: the volume is encrypted at rest by hardware default and by password entanglement under FileVault; the threats that remain are a running or unlocked machine and an unencrypted backup destination; the bounds that were calibrated against forensic exposure (§8.5's window) are freed; the bounds that were calibrated against agent reachability (§8.3, §7.12) are unaffected because that threat is orthogonal.

**§8.8 — Version pinning.** The *conclusion* survives (recording beats pinning); the *premise* is a fact about a hand-installed Ollama on Fedora and does not transfer. Under Homebrew, `postgresql@18` and `pgvector` both have an unattended upgrade path (`brew upgrade`), which is a **new** exposure §8.8 did not have to consider — the Fedora argument was literally *"there is no unattended upgrade path to defend against"*. Under a HuggingFace runtime the model half gets stronger (§8.1). **So §8.8 splits: stronger on models, weaker on the database.** Worth a `brew pin` on both formulae, which is Homebrew's `dnf versionlock`.

**§8.9 — Restore procedure.** Survives with four edits, and the restore *prerequisite* it exists to enforce is confirmed by PostgreSQL's own extension documentation: *"pg_dump knows that it should not dump the individual member objects of the extension — it will just include a `CREATE EXTENSION` command in dumps, instead"* ([PostgreSQL, *Packaging Related Objects into an Extension*](https://www.postgresql.org/docs/18/extend-extensions.html) — *documented*). The failure §8.9 step 1 prevents is structural on every install route.
1. Step 1 *"Install the pgvector RPM"* → *"`brew install postgresql@18 pgvector`, and confirm `CREATE EXTENSION vector` works before proceeding."*
2. A new step 0: *"Create the cluster with `initdb --locale-provider=builtin --locale=C.UTF-8 -E UTF-8`"* — because restoring into a cluster with a different collation is the one way a `-Fc` restore can succeed and still be subtly wrong (§9.1).
3. Every command line gains a version suffix or an absolute path: `pg_restore-18`, `psql-18`, `pg_dumpall-18`, or `/opt/homebrew/opt/postgresql@18/bin/…`. This is not cosmetic — `pg_dump` *"cannot dump from PostgreSQL servers newer than its own major version; it will refuse to even try"*, so an unpinned `pg_dump` on `PATH` is a way for the backup timer to fail rather than a way for it to be slightly wrong. The same substitution is needed in §8.2's `tome-backup` unit and in §11.9's build obligations.
4. Step 6's *"Start the units"* becomes launchd's equivalent (Agent 3), and the scoped journald purge note becomes whatever Agent 4 lands on.
   Everything else — restore globals before the database, replay the ledger, restore `tome.env` — is pure Postgres and ports verbatim. **The runbook-was-never-walked risk that §8.9 exists for is unchanged and is, if anything, sharper, because none of these steps have been performed on macOS by anyone.** The cheap mitigation is §9.4's: rehearse it against a `pgvector/pgvector:0.8.5-pg18-trixie` container, which costs nothing and needs no privilege on the real cluster.

**One new obligation §8 does not currently have: a documented major-version upgrade procedure.** On Fedora this was implicit in the distro. On Homebrew, `brew upgrade` cannot cross a major (§9.1), and Homebrew's own `pg_upgrade` wrapper was deleted as unfixable — so the procedure has to be written down. **Recommend dump-and-restore rather than `pg_upgrade`**: at sub-gigabyte scale it is faster to reason about, it reuses §8.9's machinery, and it turns a rare scary operation into a rehearsal of a procedure that has to be correct anyway.

---

## 12. Changes to §13.2's durability rows

| Current row | Fate |
|---|---|
| **A dead `nvme0n1` loses the store and its backups together** | **Downgraded to a configuration item.** Becomes: *"if the Time Machine disk is disconnected for an extended period, a media failure loses the store and its recent backups together"* — with the mitigation that macOS reports the staleness. This is the single biggest improvement in my area. |
| **The live database and every dump are unencrypted at rest** | **Deleted.** Replaced by a much smaller row: *"an unencrypted Time Machine destination would reintroduce this on new media"*, which is a checkbox rather than a fact of the hardware. |
| **Retracted content persists in backups for up to 7 days** | **Survives, with one added clause** for the 24-hour APFS local-snapshot window. Its *"on an unencrypted disk the threat model was never forensics"* justification is replaced by the stronger *"the residue is encrypted at rest"*. |
| **Retracted content persists indefinitely in neighbours' event payloads** | **Survives verbatim.** |
| **Retraction makes "never captured" and "retracted" indistinguishable** | **Survives verbatim.** |
| **The cascade is one hop** | **Survives verbatim.** |
| **Up to 15 minutes where `search_entities` returns nothing** | **Survives** (the timer is Agent 3's, the risk statement is unchanged in kind). |
| **`query_log` comes back empty from any restore** | **Survives verbatim.** |

**New rows this section would add:**

| New risk | Because |
|---|---|
| **PostgreSQL's default WAL sync on macOS does not flush the drive write cache** | Documented in PostgreSQL's reliability chapter. Mitigated by setting `wal_sync_method = fsync_writethrough`, at a performance cost. Becomes an accepted risk only if that setting is declined. |
| **APFS does not checksum file data, so silent bit rot in a dump is no longer excluded by the filesystem** | Confirmed from Apple's APFS reference. Bounded by the 7-day rotation and the per-dump `pg_restore -f /dev/null`; a second verification pass over the oldest dump would close it. |
| **Retracted content can persist for up to 24 hours in APFS local snapshots** | Time Machine's hourly local snapshots, documented by Apple. Encrypted at rest; not reachable by any agent; not reachable by the retraction ledger either. |
| **The machine leaves the house** | The theft base rate rises sharply; the consequence falls sharply (FileVault, remote erase, Activation Lock). Residual: stolen-while-unlocked. |
| **The free-space guard may become live rather than theoretical** | Unknown but likely much smaller free-space pool than 876 GB, competing with model weights and everything a work laptop holds. |
| **Homebrew's default cluster locale is Darwin libc `en_US.UTF-8`** | Weakens the "restores onto any Unix" property. Avoidable at `initdb` time with the builtin `C.UTF-8` provider — and doing so improves on the current Fedora spec. |
| **An unpinned `pg_dump` on `PATH` can silently break the backup timer** | Homebrew's formula is keg-only, so the binaries are `pg_dump-18` etc.; a stray older client refuses to dump a newer server outright. Mitigated by absolute paths in the backup unit, which is a one-line obligation. |
| **The major-version upgrade procedure is now Tome's to document** | Homebrew's `pg_upgrade` wrapper was deleted as unfixable. Dump-and-restore is the recommended procedure and it reuses §8.9's machinery — but until it is written down, the upgrade path is undefined rather than distro-provided. |

---

## 13. Check on the actual MacBook

Every one of these is faster to run than to reason about, and several change numbers in the PRD. Ordered by how much rests on them.

| # | What | Command | Why it matters |
|---|---|---|---|
| 1 | **FileVault status** | `fdesetup status` | The entire §8.7 inversion. Note: even "off" is better than no-LUKS on Apple silicon (§1.6), so this calibrates rather than decides. |
| 2 | **Free space, and the container layout** | `df -h /System/Volumes/Data`, `diskutil apfs list` | Replaces the 876/888 GB figure that appears in §1.4, §8.2 and §8.5. Likely to move the 10 GB guard from theoretical to live. |
| 3 | **Existing Time Machine configuration** | `tmutil destinationinfo`, `tmutil listlocalsnapshots /`, `tmutil currentphase` | Decides whether §8.2's destination flip is "buy a disk" or "add two exclusions". |
| 4 | **Purgeable vs. reported free space** | compare `df -h /` against Finder's figure | Confirms the direction of the guard's conservatism (§4). |
| 5 | **`wal_sync_method` default** | after install: `SHOW wal_sync_method;` | Confirms or kills the `open_datasync` derivation in §7.1, which is currently *assumed* from the Darwin headers. |
| 6 | **Firmlink list** | `cat /usr/share/firmlinks` | Confirms `/opt` and `/usr/local` are on the Data volume (§10.1). |
| 7 | **Whether Homebrew is already installed and at which prefix** | `brew --prefix` | Determines every path in §10.1. |
| 8 | **pgvector + pg_trgm actually load** | `brew install postgresql@18 pgvector`, then `CREATE EXTENSION vector; CREATE EXTENSION pg_trgm;` | The one thing that would break §8.9 outright. Both are documented as present; this confirms it on the machine. |
| 9 | **What `brew services` writes** | `brew services start postgresql@18`, then `cat ~/Library/LaunchAgents/homebrew.mxcl.postgresql@18.plist` | Agent 3's input; settles the plist contents from the artifact rather than from the formula's rendered JSON. |
| 10 | **Whether a LaunchDaemon can start before login under FileVault** | write a trivial daemon touching a Data-volume path, reboot, read the log | Confirms §9.5's fourth point, which is currently a prediction. |
| 11 | **Model-weight directory size** | `du -sh ~/.cache/huggingface ~/.ollama` | Sizes the Time Machine exclusion recommendation (§8.2). |
| 12 | **A dump-and-restore round trip** | `pg_dump -Fc` → `pg_restore -f /dev/null` → restore into a scratch container | Walks §8.9 once on the target, which is the obligation §8.9 exists to create. |

---

## 14. Hypotheses: confirmed, killed, and corrected

**H1 — FileVault dissolves the largest accepted risk. → Confirmed on the risk, substantially corrected on the consequences.**
The §13.2 row *"the live database and every dump are unencrypted at rest"* is deleted outright, and on Apple silicon it is deleted whether or not FileVault is enabled. But the hypothesis's follow-on — *"several retention bounds were calibrated against a threat that no longer applies"* — is **one bound**, not several. §8.5's privacy-dial framing is the only argument in §8 that was genuinely load-bearing on the unencrypted fact and genuinely loosens. §8.3's threat-model paragraph does not loosen (it was an inadmissibility argument, not a bound), and §7.12's keys-file refusal was over-attributed to the fact in the first place. **The correction the brief asked for is the right one: the threat FileVault addresses and the threat Tome's bounds address are largely orthogonal.**

**H2 — A new threat appears: loss and theft. → Confirmed, and it does not offset H1.**
Much higher likelihood, much lower consequence, with macOS-native mitigations (remote erase, Activation Lock) the Fedora box has no equivalent of. It changes one §13.2 row and adds one obligation (encrypt the Time Machine destination). It does not change any bound in §8.

**H3 — Off-machine backup flips from ruled-out to trivial. → Confirmed on the substance; "trivial" corrected to "cheap and reliable, with two required exclusions".**
Both ruling-out facts are Fedora-box facts and neither exists on the target. Time Machine is the right mechanism *for moving the dumps*, and the wrong mechanism for capturing `PGDATA` — decisively so, because a snapshot of the data directory cannot be replayed into by the retraction ledger, which is exactly the incompatibility #19 dissolved by choosing `pg_dump`. **This is the strongest single argument in my area for the move, and it comes with a precise configuration rather than a hope.**

**H4 — `chattr +C` has no APFS equivalent. → Confirmed, and the "so what" is: it does not matter.**
No user-facing equivalent exists (`chflags` enumerated; no `fcntl`). Apple's on-disk format *does* have one — `INODE_SNAPSHOT_COW_EXEMPTION`, used by Time Machine — and Apple explicitly says not to set it. But APFS is copy-on-write for *metadata*, with data redirection triggered by snapshots and clones rather than unconditionally; the scale is sub-gigabyte on NVMe; and a native defragmentation facility exists if it ever mattered. **The mitigation is not needed, which is a better outcome than a substitute.** A secondary consequence: losing `chattr +C` does not buy back data checksums, because APFS never had them (see the H-not-listed below).

**H5 — How Postgres gets installed matters more than it looks. → Confirmed, and settled: Homebrew.**
Homebrew is the only route that preserves a plain Unix filesystem layout, which is what every line of §8.2, §8.9 and §7.9 assumes. Postgres.app is a login-session app that PostgreSQL's own download page describes as shutting the server down when closed. A container hides the store inside a VM disk image that Docker Desktop excludes from Time Machine by default — a worse coupling than btrfs ever was, and a silent one. EDB has no macOS pgvector packaging at all. pgvector 0.8.5 is available natively on Homebrew and in the containers (Postgres.app ships 0.8.2), so the extension question narrows the field but does not decide it — the *filesystem shape* does.

Two sub-findings that the hypothesis did not anticipate and that change text outside §9: the keg-only formula means the client binaries are **`pg_dump-18`/`pg_restore-18`/`pg_dumpall-18`**, so every command line in §8.2, §8.9 and §11.9 changes; and a Homebrew LaunchDaemon needs `--sudo-service-user=` because Postgres refuses to run as root. Conversely, the *expected* Homebrew problem — `brew upgrade` jumping a major and orphaning the data directory — **no longer exists**, because there is no unversioned formula. What replaced it is smaller and needs writing down: Homebrew's `pg_upgrade` wrapper was deleted as unfixable, so the major-upgrade procedure has to be documented, and dump-and-restore is the right one at this scale.

**H6 — APFS vs btrfs, and the compression arithmetic. → Killed.**
Losing `compress=zstd:1` costs essentially nothing, for two reasons the PRD already contains without having connected them: btrfs's own documentation says *"Nodatacow implies nodatasum, and disables compression"*, so `chattr +C` meant the Postgres data directory was never compressed on Fedora either; and `pg_dump -Fc` output is already gzip-compressed at the application layer. **§8.2's space table transfers unchanged.** What actually changes is capacity and competition, not compressibility.

**Not in the hypothesis list, and the two findings I would most want the synthesis to carry:**

- **PostgreSQL's default WAL sync on macOS does not flush the drive write cache.** A documented, one-line-fixable, performance-costing regression in the exact property the capture path depends on.
- **APFS does not checksum file data.** This breaks a specific argument §8.2 makes — *"a dump that reads at all is reading its original bytes"* — which was one of the two legs holding up the withdrawal of the weekly restore-into-scratch. The withdrawal survives on the other leg; the sentence does not.

And one finding that is about the current spec rather than the port: **the store's collation should be the builtin `C.UTF-8` provider, on both hosts.** The portability claim in §8.2 — *"a file on any Unix"* — is weaker than it reads for any cluster created with a libc locale, and the fix costs one `initdb` flag.

---

## Sources

**Apple — primary**
- [Apple File System Reference (PDF)](https://developer.apple.com/support/downloads/Apple-File-System-Reference.pdf) — object copy-on-write; `obj_phys_t.o_cksum` (Fletcher 64); `j_file_extent_val_t` (no checksum field); `INODE_SNAPSHOT_COW_EXEMPTION`; `APFS_COW_EXEMPT_COUNT_NAME`; `NX_FEATURE_DEFRAG` / `APFS_FEATURE_DEFRAG`
- [Volume encryption with FileVault in macOS](https://support.apple.com/guide/security/volume-encryption-with-filevault-sec4c6dc1b6e/web) — AES-XTS, Secure Enclave key handling, credentials required at boot, hardware-UID-only protection when FileVault is off
- [Protecting data at rest / Data Protection overview](https://support.apple.com/guide/security/protecting-data-at-rest-secf6276da8a/web) — Class C with a volume key; opt-in required for password entanglement
- [Signed system volume security](https://support.apple.com/guide/security/signed-system-volume-security-secd698747c9/web) — read-only sealed system volume; separate Data volume
- [Back up your files with Time Machine on Mac](https://support.apple.com/guide/mac-help/back-up-your-files-with-time-machine-mh35860/mac) — hourly/daily/weekly; destination must not be the internal disk
- [About Time Machine local snapshots](https://support.apple.com/en-us/102154) — hourly, 24 h, APFS-only, auto-removed under space pressure
- [Choose a backup disk and set encryption options on Mac](https://support.apple.com/guide/mac-help/choose-a-backup-disk-set-encryption-options-mh11421/mac) — destination encryption
- [If a Time Machine backup fails on Mac](https://support.apple.com/guide/mac-help/if-a-time-machine-backup-fails-mchlb955003d/mac) — failure surfacing and retry
- [If your Mac is lost or stolen](https://support.apple.com/en-us/102481) and [Activation Lock for Mac](https://support.apple.com/en-us/102541) — remote erase, instant wipe with FileVault/Apple silicon, Activation Lock
- [`tmutil(8)`](https://keith.github.io/xcode-man-pages/tmutil.8.html) — `addexclusion` / `-p` / `isexcluded`, `localsnapshot`, `thinlocalsnapshots`
- [`chflags(1)`](https://keith.github.io/xcode-man-pages/chflags.1.html) — complete flag list; no copy-on-write flag
- [`volumeAvailableCapacityForImportantUsage`](https://developer.apple.com/documentation/foundation/urlresourcevalues/volumeavailablecapacityforimportantusage) — purgeable-aware capacity API

**PostgreSQL — primary**
- [26.2 File System Level Backup](https://www.postgresql.org/docs/current/backup-file.html) — server must be shut down; the consistent-snapshot exception and its conditions
- [28.1 Reliability](https://www.postgresql.org/docs/current/wal-reliability.html) — *"On macOS, write caching can be prevented by setting `wal_sync_method` to `fsync_writethrough`"*
- [19.5 Write Ahead Log](https://www.postgresql.org/docs/current/runtime-config-wal.html) — `wal_sync_method` values and default-selection rule; `fsync`; `full_page_writes`
- [`src/include/access/xlogdefs.h`](https://raw.githubusercontent.com/postgres/postgres/master/src/include/access/xlogdefs.h) and [`src/template/darwin`](https://raw.githubusercontent.com/postgres/postgres/master/src/template/darwin) — the default resolves to `open_datasync` on Darwin
- [Thomas Munro, pgsql-hackers, 2022-08-26](https://www.postgresql.org/message-id/CA%2BhUKGJ2CG2SouPv2mca2WCTOJxYumvBARRcKPraFMB6GSEMcA%40mail.gmail.com) — why `fsync_writethrough` exists on macOS
- [`pg_dump`](https://www.postgresql.org/docs/current/app-pgdump.html) — `-Fc` compressed by default; consistent export; `--exclude-table-data`; refuses to dump from a newer major
- [24.1 Locale Support](https://www.postgresql.org/docs/current/locale.html) — builtin/icu/libc providers; `C.UTF-8`; index-corruption warning on collation change
- [38.17 Packaging Related Objects into an Extension](https://www.postgresql.org/docs/18/extend-extensions.html) — dumps carry `CREATE EXTENSION`, not the extension's objects
- [17.4 Installation Procedure (`install-world`)](https://www.postgresql.org/docs/18/install-make.html) — `install-world` includes contrib
- [19.3 Starting the Database Server](https://www.postgresql.org/docs/18/server-start.html) and `src/backend/main/main.c` `check_root()` — the server must not run as root

**Other primary**
- [btrfs Administration documentation](https://btrfs.readthedocs.io/en/latest/Administration.html) — *"Nodatacow implies nodatasum, and disables compression"*
- [pgvector README](https://github.com/pgvector/pgvector) — 0.8.5, Postgres 13+, `brew install pgvector` (@17 and @18 only), Postgres.app, `pgvector/pgvector:pg18-*` images, EDB only as a from-source `pg_config` path
- [formulae.brew.sh — `postgresql@18`](https://formulae.brew.sh/formula/postgresql@18) and [formula source](https://github.com/Homebrew/homebrew-core/blob/master/Formula/p/postgresql%4018.rb) — 18.4, arm64 bottles, `initdb --locale=en_US.UTF-8 -E UTF-8 $HOMEBREW_PREFIX/var/postgresql@18`, `make install-world`, `link_children "bin", suffix: "-18"`, keg-only
- [Homebrew — `brew services`](https://docs.brew.sh/Manpage) — *"If `sudo` is passed, operate on `/Library/LaunchDaemons` … Otherwise … `~/Library/LaunchAgents`"*; `--sudo-service-user=`
- [Homebrew formula — `pgvector`](https://github.com/Homebrew/homebrew-core/blob/master/Formula/p/pgvector.rb) — 0.8.5, built per-major against postgresql@17 and @18
- [Postgres.app documentation](https://postgresapp.com/documentation/install.html) and [extensions list](https://postgresapp.com/extensions/) — PG 18.4 universal, pgvector 0.8.2 bundled, data directory `~/Library/Application Support/Postgres/var-XX`
- [postgresql.org — macOS packages](https://www.postgresql.org/download/macosx/) — *"Close the app, and the server shuts down"*; EDB arm64 availability
- [Docker Hub — `postgres`](https://hub.docker.com/_/postgres) — PG 18 `PGDATA` change to `/var/lib/postgresql/18/docker`
- [Docker Desktop macOS FAQs](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/macfaqs/) — the single large `Docker.raw` disk image; space not reclaimed automatically
- [Docker Desktop file sharing settings](https://docs.docker.com/desktop/settings-and-maintenance/settings/#file-sharing) — named volumes preferred over bind mounts for databases
- [HuggingFace Hub — Download files from the Hub](https://huggingface.co/docs/huggingface_hub/en/guides/download) — `revision=` full commit SHA; revision-addressed cache layout

**Third-party, used only where no primary source exists and labelled as such**
- [Adam Leventhal, *APFS in Detail: Data Integrity*](https://ahl.dtrace.org/2016/06/19/apfs-part5/) — APFS checksums metadata, not user data
- [The Eclectic Light Company, *Why use APFS?*](https://eclecticlight.co/2025/01/09/why-use-apfs/) — copy-on-write applies to filesystem metadata
- [The Eclectic Light Company, *How Time Machine makes backups*](https://eclecticlight.co/2018/10/17/how-time-machine-makes-backups/) — Stable/Reference snapshot diffing, reconstructed from `backupd` logs
- [The Eclectic Light Company, *Should you enable defragmentation on APFS hard drives?*](https://eclecticlight.co/2019/10/19/should-you-enable-defragmentation-on-apfs-hard-drives/) — `diskutil apfs defragment`, off by default, aimed at rotational media
- [The Eclectic Light Company, *Knowing what not to back up, and how*](https://eclecticlight.co/2021/08/03/knowing-what-not-to-back-up-and-how/) — the `com.apple.metadata:com_apple_backup_excludeItem` xattr
