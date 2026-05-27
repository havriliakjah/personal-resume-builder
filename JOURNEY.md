# Synthesis Workbench — The Journey

How a "make me a resume" tool became a small structured app worth its own dev folder. Not a feature log (those live in the per-round design docs in `MD/`). This is the arc.

---

## Origin

The starting problem was familiar: a person mid-career-pivot, sitting on years of work history spread across multiple companies, with the data structured *for memory*, not *for production*. Pulling a tailored resume bullet out of it was an archaeology session every single time.

The first instinct was small: a script that takes Job + Target → Resume Bullet. That instinct's mistake was assuming the script knew what variables to read. It didn't. Nothing did. The data was structured per-document, not per-question.

So the project pivoted before it really started. The first real build wasn't a bullet generator, it was an **Index**. A fixed list of *questions every company can be asked*, with the answers stored uniformly per company.

The thinking: if every company answers the same questions, then a "formula" can read them generically. Person + CompanyA + Formula 1 produces a structurally comparable point to Person + CompanyB + Formula 1. The formula is the reusable thing. The Index is the language formulas speak.

---

## Principle accumulation

Each round of pain produced a principle.

**Cardinality is data, not schema.** Early rounds had variable names with numbers in them: `role_1_title`, `reference_1_name`, etc. Adding a sixth role meant a schema migration. The fix was to define each repeating thing *once* and track count per job in `entry_no`. Smell test: if a variable name contains a digit, that digit is data that leaked into the schema.

**Applicability is data, not absence.** A blank field meant "not yet answered." A field marked N/A meant "answered: does not apply." These needed to be different states. The fix was a sentinel ("N/A") that passes type validation, counts toward readiness, and is rendered as a distinct visual pill.

**Readiness is data, not a flag.** A job's status (ready / in_progress) is computed from values plus entries at read time, never stored. Drift between flag and reality becomes impossible when the flag doesn't exist.

**Priority is data, not folklore.** Every variable carries a `tier` (1, 2, or 3) on its row. Nothing client-side hardcodes which variables matter. Retiering is a one-line edit.

**A variable knows where its value comes from.** Some values are computed from others (count of role entries, duration between dates). These are flagged via a `derived` column with a recipe string. The server computes them on save and refuses to be lied to.

**Server is the authority on derived values.** Intake cards, manual saves, automation — every write path funnels through one function that drops user-supplied values for derived variables. Inconsistency isn't validated against; it's *not representable*.

**Engagement is its own dimension.** Some content (the "Story" track — people, story arcs, operating model) is qualitatively different from facts about a company. It's engagement, not depth. It got its own classification rail (`track`) parallel to tier, and its own picker option in the UI. A job can be "tier 3 ready" without any stories filled.

**Color is structural identity.** Each unique repeating section has its own color. The SAME section keeps the SAME color across every tier view filter. Color answers "what *is* this thing" by sight, before any text is read.

---

## The visual vocabulary

Late in the build, color became a first-class identifier. Roles is teal everywhere it appears. References is amber. Certifications is blue, Industry Memberships indigo. People is violet, Story Arc indigo-violet, Operating Model magenta.

The principle: two stacks of the same color are the same section, full stop. Cross-tier filter views inherit the section's home color rather than the filter's color. Color encodes *what* before *where*.

This extends naturally to anything downstream: a formula UI showing its inputs as colored chips; a profile page showing which sections of each job have content; an intake card preview highlighting which sections it writes into. The vocabulary stays consistent because color is identity, not decoration.

---

## What this project is now

A small but real software project. Three-tier architecture (HTML → Flask → data.py → SQLite). SSOT discipline — the schema in `build_synthesis_db.py` is the canonical source for everything else. Four classification rails per variable. Server-as-authority for derivations. A visual vocabulary that turns color into a queryable property. 118-test suite. Boot-time schema verification.

Designed first to handle one specific person's work history. Generalizes to anyone whose work history can be captured in 79 structured variables.

What comes next:

- **Tier-aware readiness** (shipped). Status now graduates from "none" through "T1 ready" → "T2 ready" → "T3 ready" with a progress bar in the UI.
- **Real formulas.** Lenses that declare `requires_tier` and `requires_stories` and consume the actual variables. The Index has been ready for this since the multi-entry restructure; the missing piece is the formula DSL.
- **Synthetic output.** A "Page 3" where filled-in variables meet defined formulas and produce candidate resume points. Currently a sandbox.
- **Profile rollup.** Per-job tiles showing colored dots for which sections have content. Visual vocabulary is already in place.
