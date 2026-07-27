# Measurement traps — the ladder probe and everything built on it

Not a handoff. This is the accumulated list of ways this project's measurements have gone wrong,
kept because **every entry here cost real time or produced a published number that was false.**
It outlived `NEXT-STEPS.md`, which was deleted once #34/#35/#36 closed; the handoff was ephemeral
and this is not.

Pre-registration and its amendments live in `ladder-probe/CRITERIA.md`. This file is the shorter,
blunter thing to read first.

## The traps

- **The probe is not reproducible.** An unchanged prompt moved `Event → Fact` by 3 with nothing changed but the wall clock. `temperature: 0` and a fixed `seed` fix sampling, not kernel scheduling, and `keep_alive: 0` reloads the model every call. **Never read a single run as a measurement.**
- **Determinism varies by the whole configuration — model × prompt × corpus × runtime — and is not predictable from any part of it.** `qwen3:4b` reproduces bit-exactly; `qwen3:14b` does not on the control prompts but *does* on the fenced ones, which is the opposite of what it did on `corpus.py`; and on **Ollama 0.32.4 `qwen3:14b` reproduces bit-exactly on both prompts**, where on 0.32.1 it reproduced on neither. Replicate *files* are not replicate *observations* — **hash the payloads** before treating replicate count as sample size. This silently turned three 4b runs into one, and it makes the 0.32.4 non-overlap test empty. (`CRITERIA.md`, fifth, sixth and seventh amendments.)
- **A pre-registered check can pass on a technicality.** The relocation criterion tests the *largest single* new confusion against the reduction, not the sum. On 0.32.4 it passes (+2.0 < −4.0) while summed relocation (+3.0) cancels three-quarters of the gain. Read the criterion's exact words before quoting it as passed. (Seventh amendment.)
- **This entry was itself mis-recorded, which is the trap.** It read: *"`considered_types` is gated on the 0.7 threshold in the prompt, so it could never have been observed populated. A field's absence may be an instruction rather than a behaviour."* **Withdrawn 2026-07-27.** The field fires on **13.9% of paired entities** (129 of 930; `qwen3:14b`, Ollama 0.32.4, Fedora), and the fires land at **0.9–0.95 confidence — *above* the 0.7 gate**, so the gate was never what suppressed it. It is *noisy, not silent*: **4.7% precision against a 2.3% base error rate, 28.6% recall**, and the 6 hits **deduplicate to 2 distinct subjects**. The original wording is kept verbatim above because the general lesson survives *inverted* — a field's absence may be an instruction, a behaviour, **or an artifact of the corpus you happened to read**. Corrected entry: the last bullet in this list, and `ladder-probe/CONFIDENCE-FINDINGS.md` §2.
- **`format: "json"` induces degeneration** — previously `qwen3:8b`, now also `4b` under a ~150-token-longer prompt (cap hit, 1 entity from 40). Per-model hazard, not a free safety net.
- **Scoring schemes conflate omission with misclassification.** Letting one emitted entity match several subjects lets a *missing* entity score as a *wrong* one. Cost: the entire Person finding in #36.
- **Worked examples in a prompt must not quote the corpus** — that is teaching to the test, the defect #24's prompt had. Check it mechanically.
- **`OLLAMA_KEEP_ALIVE=24h`** is set in the drop-in; pass `keep_alive: 0` per request rather than editing the unit (which would need sudo).
- **Three JSON envelope shapes** across one model family; `analyze.py`'s `entities_in()` handles all three.
- **Agents anchor to numbers without checking provenance.** Three instances now: two in #32, and #36's confusion table, which did not reproduce.
- **`sudo` can't prompt from inside the harness** — no TTY. **None of the remaining Fedora work needs it.**
- **Concurrent GPU jobs corrupt runs** — `raw-contended.jsonl.bak` is the retained evidence. Serialize everything on this box.

- **The coverage matcher is many-to-one, and it has cost three findings.** `analyze.py`'s `covered`
  takes each subject's best entity independently and never excludes an entity already used, so one
  emitted entity can be credited with covering several subjects (`matched_ents` feeds only the
  `fabricated` tally). Measured inflation **+1.2 to +1.9 pp**. Victims: #36's Person finding; #36's
  *"the fence costs 0.9 pp coverage"* (**really 0.10 pp — 1 subject in 960**, which destroyed the
  entire case for rewriting the `Fact` sentence); and the ladder probe's headline coverage (14b
  99.1% → **97.8%**, 4b 92.5% → **90.6%**, no-entity rate 7.5% → **9.4%**). Relative comparisons
  barely move, which is exactly why it survived. **Use `type_accuracy.pair()`, and check which
  matcher produced any coverage number before believing it.** `fabricated` carries the same defect,
  unaudited, and is cited by no published claim.
- **Replicates are not the replication unit — the corpus draws are.** `macos-spike-inference.md`
  §19.9.5 pre-registered 8 paired 40-subject draws reported as a **paired per-draw difference with a
  bootstrap 95% CI**, and that is the only analysis that survived contact with 0.32.4, where every
  condition is bit-identical across replicates. Run `paired_bootstrap.py`, not just
  `compare_ablation.py`. On the four-condition ablation, **of eight metrics across three comparisons
  exactly one resolved.** Report the CI *and* the minimum detectable effect; never the headline
  ratio alone. This also removes the need to borrow 0.32.1's noise floor (`CRITERIA.md`, seventh
  amendment): the paired draws give a within-runtime bound.
- **Counts against this corpus are inflated ~4× by re-draws.** Each subject appears in ~4 of the 8
  draws, so a raw error count is not a subject count. **Deduplicate by subject before believing an
  effect size.** Doing so shrank *"`Commitment → Decision` 3 → 9, the largest single increase
  anywhere"* into a re-routing — deduplicated, the fenced condition mistypes *fewer* distinct
  `Commitment` subjects than the control (2 vs 3).
- **The corpus, not the draw count, is the binding constraint.** The fence's whole effect lives in
  **2 of the corpus's 12 `Event` subjects**. More draws resample the same 12, so they buy a tighter
  interval around a 2-subject phenomenon and no external validity. When an effect will not resolve,
  ask whether more draws or more *subjects* is the answer — it is usually subjects.
- **A negative result is a statement about the design until you bound it.** Report the minimum
  detectable effect, or the rule-of-three upper bound when a rate is 0/N (0 of ~2,350 below the 0.7
  threshold means "under ~0.13%", not "never"). "We saw none" is not a finding on its own.
- **Scope silently omitted is the same as scope misstated.** `CONFIDENCE-FINDINGS.md` §2 concluded
  `considered_types` was *"empty on ~2,950 entities"* while the table directly beneath it reported 15
  fires, and it had only ever examined `corpus_ambiguous` — on `corpus.py` the field fires on
  **13.9%**. State which corpus, which prompt, which runtime, every time.
