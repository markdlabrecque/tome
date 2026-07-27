"""Synthetic subject corpus for the enrichment model-ladder probe (issue #32 follow-up).

80 blocks, each one memorable "subject" with a ground-truth entity type and a
distinctive synthetic proper noun used to check natural-key coverage.

ENTIRELY SYNTHETIC. No real person, project, or event appears here. This file is
committed deliberately: #24 built an equivalent corpus, never committed it, and the
probe became unrepeatable. See research/macos-spike-synthesis.md harvest item 7.

Types follow CONTEXT.md: Person, Project, Preference, Decision, Fact, Commitment, Event.
Decision-shaped subjects are over-represented (14/80) so a 40-subject draw carries ~7,
reproducing the regime in which #24 measured its Decision-count invariant.
"""

# (type, marker, text) — `marker` is the distinctive token a correct natural key echoes.
SUBJECTS = [
    # --- Person (14) ---
    ("Person", "vidrine", "Corbin Vidrine runs the data platform team and is the person to ask about anything touching the ingest pipeline."),
    ("Person", "okonjo", "Adaeze Okonjo joined in March from a hardware background and still thinks in terms of fixed memory budgets."),
    ("Person", "halloran", "Fenn Halloran is the only person who understands the old billing reconciliation job end to end."),
    ("Person", "brisebois", "Yannick Brisebois prefers async written updates and gets visibly impatient in status meetings."),
    ("Person", "castellan", "Ilse Castellan is on secondment from the Lisbon office until the end of the year."),
    ("Person", "tarrant", "Moss Tarrant does the security reviews and has a standing veto on anything that opens a port."),
    ("Person", "delacroix", "Ondine Delacroix wrote most of the original scheduler and left detailed comments nobody has needed to change."),
    ("Person", "pemberton", "Wyatt Pemberton handles vendor relationships and keeps a spreadsheet of every contract renewal date."),
    ("Person", "nakagawa", "Sora Nakagawa is the newest member of the platform team and is still ramping on the deployment tooling."),
    ("Person", "everard", "Blythe Everard chairs the architecture forum and insists every proposal names what it rules out."),
    ("Person", "quillon", "Rafe Quillon maintains the internal component library and is protective of its API surface."),
    ("Person", "asplund", "Greta Asplund runs user research and has the strongest sense of what people actually do with the product."),
    ("Person", "mbeki", "Thabo Mbeki-Lawson looks after the observability stack and built the current alerting rules."),
    ("Person", "ferreira", "Ximena Ferreira is the escalation contact for anything involving the payments provider."),

    # --- Project (10) ---
    ("Project", "harborview", "Harborview is the effort to replace the legacy reporting stack; it is roughly half migrated and stalled on schema drift."),
    ("Project", "lanternfish", "Lanternfish is the internal search rebuild, currently blocked waiting on a decision about the index refresh cadence."),
    ("Project", "stonecrop", "Stonecrop is the compliance evidence-gathering workstream and has a hard external deadline."),
    ("Project", "windlass", "Windlass is the effort to consolidate three separate authentication paths into one."),
    ("Project", "kestrel", "Kestrel is the mobile client rewrite; it is on hold until the API versioning question is settled."),
    ("Project", "brightwater", "Brightwater is the data quality initiative and has produced more dashboards than fixes so far."),
    ("Project", "thornfield", "Thornfield is the effort to reduce build times, which have crept past twenty minutes."),
    ("Project", "marlinspike", "Marlinspike is the disaster recovery rehearsal programme, run twice a year."),
    ("Project", "goldcrest", "Goldcrest is the pricing engine replacement and is the largest thing currently in flight."),
    ("Project", "saltmarsh", "Saltmarsh is the internal developer portal, which nobody owns clearly since the last reorganisation."),

    # --- Decision (14) ---
    ("Decision", "queue-choice", "Chose the managed queue over running our own broker, because nobody wanted to be on call for it."),
    ("Decision", "monorepo", "Decided to keep the monorepo rather than split it, on the grounds that cross-cutting changes were the common case."),
    ("Decision", "drop-ie", "Decided to drop support for the oldest browser tier after traffic fell below half a percent."),
    ("Decision", "buy-not-build", "Chose to buy the feature-flag system rather than build one, because the build estimate exceeded three years of licence cost."),
    ("Decision", "region-pin", "Decided to pin all storage to a single region, accepting the latency, to avoid the replication complexity."),
    ("Decision", "no-graphql", "Decided against adopting GraphQL for the public API; the caching story did not justify the migration."),
    ("Decision", "weekly-release", "Chose a weekly release train over continuous deployment, because the manual verification step could not be removed yet."),
    ("Decision", "typed-config", "Decided to make all configuration typed and validated at startup after a malformed value took production down."),
    ("Decision", "vendor-swap", "Chose to move off the incumbent email provider following the third deliverability incident in a quarter."),
    ("Decision", "sunset-v1", "Decided to sunset the v1 API at the end of the year rather than maintain both indefinitely."),
    ("Decision", "postgres-over", "Chose Postgres over the document store for the new service, because the access patterns turned out to be relational after all."),
    ("Decision", "no-microservice", "Decided to keep the new billing logic inside the existing service rather than extract it, since the team is three people."),
    ("Decision", "async-review", "Chose asynchronous design review over a synchronous forum, after attendance at the forum collapsed."),
    ("Decision", "freeze-schema", "Decided to freeze the reporting schema until the migration completes, blocking two unrelated feature requests."),

    # --- Preference (10) ---
    ("Preference", "small-prs", "Consistently prefers small pull requests over large ones, and will ask for a split rather than review a big diff."),
    ("Preference", "boring-tech", "Has a standing preference for boring, well-understood technology on anything that has to run unattended."),
    ("Preference", "written-first", "Prefers a written proposal before any meeting; treats a meeting without a document as a bad sign."),
    ("Preference", "no-mocks", "Generally avoids mocks in tests, preferring real dependencies wherever they can be made fast enough."),
    ("Preference", "flat-structure", "Prefers flat directory structures and resists nesting beyond about three levels."),
    ("Preference", "explicit-errors", "Prefers explicit error handling over exceptions propagating silently up the stack."),
    ("Preference", "morning-deep", "Reserves mornings for deep work as a standing rule and schedules meetings after two."),
    ("Preference", "prose-comments", "Prefers comments that explain why rather than what, and deletes the ones that restate the code."),
    ("Preference", "one-tool", "Has a standing preference for one tool that does a job adequately over three that each do part of it well."),
    ("Preference", "sql-direct", "Prefers writing SQL directly over using an ORM for anything analytical."),

    # --- Event (12) ---
    ("Event", "outage-march", "The March outage lasted four hours and was traced to a certificate that expired without warning."),
    ("Event", "offsite-june", "The June offsite happened in Trondheim and produced the current roadmap."),
    ("Event", "audit-visit", "The external auditors visited for three days in the second week of the quarter."),
    ("Event", "migration-cutover", "The cutover to the new cluster happened over a weekend and finished six hours ahead of the window."),
    ("Event", "postmortem-friday", "The postmortem for the payment double-charge is scheduled for Friday afternoon."),
    ("Event", "conference-talk", "Gave the internal brown-bag talk on the caching redesign last Thursday."),
    ("Event", "vendor-demo", "The vendor demo for the replacement observability tool is booked for the twelfth."),
    ("Event", "team-restructure", "The platform team was split into two sub-teams at the start of the quarter."),
    ("Event", "load-test", "The load test ran overnight and surfaced a connection pool limit nobody had documented."),
    ("Event", "hiring-panel", "The hiring panel for the senior backend role meets next Tuesday."),
    ("Event", "cert-renewal", "The annual certification renewal was completed two weeks before the deadline."),
    ("Event", "roadmap-review", "The quarterly roadmap review is scheduled for the last week of the month."),

    # --- Commitment (10) ---
    ("Commitment", "owed-writeup", "Promised to send the caching redesign write-up before the end of the week."),
    ("Commitment", "review-owed", "Owes a review on the authentication consolidation proposal and has been sitting on it for days."),
    ("Commitment", "intro-promise", "Agreed to make an introduction to the contact at the analytics vendor."),
    ("Commitment", "runbook-due", "Committed to writing the runbook for the new deployment path before the next on-call rotation."),
    ("Commitment", "budget-numbers", "Promised the finance team revised infrastructure numbers by the end of the month."),
    ("Commitment", "onboarding-doc", "Agreed to update the onboarding document after the last two people found it out of date."),
    ("Commitment", "followup-audit", "Owes the auditors a written response on the two open findings."),
    ("Commitment", "mentor-session", "Committed to a fortnightly mentoring session with the newest team member."),
    ("Commitment", "spike-writeup", "Promised to circulate the results of the storage spike before any decision is taken."),
    ("Commitment", "deprecation-notice", "Agreed to give downstream consumers ninety days notice before removing the old endpoint."),

    # --- Fact (10) ---
    ("Fact", "retention-90", "Log retention across the estate is ninety days, which is shorter than most people assume."),
    ("Fact", "build-minutes", "The CI account is capped at fifty thousand build minutes a month."),
    ("Fact", "db-version", "The production database is two major versions behind the current release."),
    ("Fact", "traffic-peak", "Traffic peaks on Monday mornings at roughly triple the weekend baseline."),
    ("Fact", "licence-expiry", "The static analysis licence expires at the end of the calendar year."),
    ("Fact", "region-list", "The service is deployed in three regions, though only two carry production traffic."),
    ("Fact", "oncall-size", "The on-call rotation has six people, which is one fewer than it needs to be sustainable."),
    ("Fact", "test-runtime", "The full test suite takes forty minutes, most of it in the integration tier."),
    ("Fact", "storage-growth", "Object storage is growing at about four percent a month with no pruning in place."),
    ("Fact", "api-clients", "There are eleven known internal consumers of the reporting API."),
]

DECISION_INDICES = [i for i, (t, _, _) in enumerate(SUBJECTS) if t == "Decision"]

assert len(SUBJECTS) == 80, len(SUBJECTS)
assert len(DECISION_INDICES) == 14, len(DECISION_INDICES)
assert len({m for _, m, _ in SUBJECTS}) == 80, "markers must be unique"
