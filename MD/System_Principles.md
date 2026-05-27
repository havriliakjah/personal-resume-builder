# Synthesis Workbench — System Principles

A small set of design rules that have emerged through the rounds (R1 → R8) and now hold the system's shape. Each one came from a concrete moment where a different approach would have been simpler in the short term and worse in the long. Together they form the discipline that makes adding the next feature a one-line edit instead of a refactor.

Read this before making structural changes. If a proposed change violates one of these, name which, and why the violation is worth it — usually it isn't.

---

## 1. Cardinality is data, not schema

**Round it emerged:** R1 (Repeating-Entities restructure).

**Statement.** A fact-type that can occur N times is defined once as a repeating entity (variable marked `repeats: 1`); how many times it occurs is recorded in the data, not in the variable list.

**Why.** The pre-R1 design had `reference_1_name`, `reference_2_name`, … with the count baked into variable names. Adding a third reference meant a schema migration. After R1, references are one `reference_name` variable plus an `entry_no` axis, and a third reference is one row in `p1_variable_values`.

**Smell test.** A variable name contains a digit. That digit is a count leaked from the data into the schema.

**How to apply.** Before adding a new repeating concept, ask: is this *one thing that can occur many times*, or *several different things that happen to be similar*? If the former, model it as one repeating section with N entries. Never bake a count into a name.

---

## 2. Applicability is data, not absence

**Round it emerged:** R5 (N/A sentinels).

**Statement.** An empty field means "not yet answered." A field marked with a sentinel (currently `"N/A"`) means "answered — does not apply here." These are different states and must be representable as different states.

**Why.** Before R5, a job with `revenue` blank looked identical to a job that had decided revenue couldn't be known. Status couldn't distinguish them; formulas couldn't either. After R5, the sentinel is a positive declaration that survives type validation (a `select` field can carry `"N/A"` even though it isn't in the option list) and counts toward readiness.

**How to apply.** Adding a new sentinel is a one-element edit to `data.SENTINELS`. The list is exposed at `GET /api/sentinels` so the frontend renders a "Mark <sentinel>" button per non-sentinel field. Future sentinels (`"TBD"`, `"REDACTED"`, `"UNKNOWN"`) inherit this UI for free.

---

## 3. Readiness is data, not a flag

**Round it emerged:** R6 (computed status).

**Statement.** A job's status is derived from VALUES + ENTRIES at read time. It is not stored on `jobs`.

**Why.** Storing a status flag means the flag and the underlying data can drift. After R6, the flag is computed every time the job is read; drift is impossible. `ready_at` is the *only* derived bit that's persisted, and it's a timestamp, not a status — "since when" rather than "what."

**How to apply.** New readiness signals (Tier-1-ready, has-stories, formula-ready-for-X) belong on the returned status object, not as columns on `jobs`. The compute function is the single point of truth.

---

## 4. Priority is data, not folklore

**Round it emerged:** R8.A (Variable tier classification).

**Statement.** A variable's importance is recorded on the variable row in the database (`tier` column, 1/2/3). Clients receive it through `/api/variables`. Nothing client-side hardcodes which variables are important.

**Why.** Before R8.A, the question "which variables matter most?" lived only in conversation and intuition. After R8.A, the answer is a single SSOT list (`VARIABLE_TIERS` in `build_synthesis_db.py`). Build-time validation catches typos; the migration is idempotent; the UI and any future formula engine read the same column.

**How to apply.** Retier a variable by editing one entry in `VARIABLE_TIERS` and re-running `python build_synthesis_db.py`. Never write logic that special-cases a variable by id or name — read its tier instead.

---

## 5. A variable knows where its value comes from

**Round it emerged:** R8.J (Derived variables).

**Statement.** Every variable carries a `derived` column. NULL means user-entered. A non-NULL recipe string (`"count:<section>"`, `"duration:<vid>,<vid>"`) means the value is computed by the server's verb dispatch.

**Why.** Some values must equal a function of other values. `#51 how_many_roles` is literally the count of `P1 Roles` entries; storing them as separate fields and validating consistency between them is weaker than computing one from the other. After R8.J, that inconsistency is not "validated against" — it is not representable.

**How to apply.** Adding a derived variable is one line in `VARIABLE_DERIVATIONS`. If the verb is new (e.g., `sum:`, `concat:`, `gap:`), one helper function in `data.py` + its JS mirror in `job.html`. The frontend renders derived vars as a read-only `auto · <value>` pill; the JS mirror keeps the pill live as upstream inputs change.

---

## 6. Server is the authority on derived values

**Round it emerged:** R8.K.

**Statement.** Intake cards, manual saves, automation — every write path funnels through `save_job` and gets the same silent-drop treatment for derived vids. The DB column for a derived variable holds whatever the engine last computed, and `_recompute_derived` keeps it current after every save.

**Why.** "Validate inputs and reject if inconsistent" pushes the burden to every caller. "Drop and recompute" removes the burden entirely — there is no inconsistency to validate against.

**How to apply.** Never special-case derived variables on a caller. Treat them like any other variable in the values map; the server figures out what they actually are.

---

## 7. Engagement is its own dimension

**Round it emerged:** R8.O (Story track).

**Statement.** Variables can carry a `track` value parallel to their `tier`. Track answers "does this variable belong to a named engagement dimension that the user fills as a deliberate pass?" Tier answers "how factually central is this?" The two axes are orthogonal.

**Why.** Story variables sat awkwardly in T2/T3 — they were "narrative" content jumbled in with niche facts. Promoting them to T1 would have ballooned T1 from 7 → 20 and broken its "super-tight anchors" meaning. The right answer was a second rail: Story is not a tier, Story is its own track. A future "Credentials" track or "References" track follows the same pattern.

**How to apply.** A track is right when adding the variable is a meaningful intentional act (telling a story, listing a reference, recording a certification) rather than just filling a fact. One-line edit in `VARIABLE_TRACKS`. A new track also needs a picker option and a render branch; that's the price.

---

## 8. Color is structural identity, not decoration

**Round it emerged:** R8.S–U (per-section visual vocabulary).

**Statement.** Each unique repeating section has its own color (`data-home-section` drives the CSS). The SAME section keeps the SAME color across every tier filter view. Two stacks of the same color are the same section, period.

**Why.** The user spotted in real-time: "P1 Roles in T2 should be the same color as P1 Roles in T3 — it's the same structural unit." Color is the link that captures sameness across filters without code lookups. Once color is identity, anything downstream that consumes section content (formulas declaring inputs, profile pages showing per-job richness, intake card previews highlighting writes) can use the same vocabulary for free.

**How to apply.** A new repeating section gets its own color in the CSS block. Pick a hue that distinguishes it from neighbors in the same file family, then keep that hue everywhere it appears.

---

## 9. Schema-as-data, three rails

**Round it emerged:** R8 as a whole — the meta-principle.

**Statement.** A variable carries (at least) three orthogonal properties on its row: `input_type`, `tier`, `derived`, `track`. Each is a one-line entry in a SSOT seed list inside `build_synthesis_db.py`, build-time validated, idempotently backfilled, exposed through `/api/variables`. Frontend mirrors what it needs.

**Why.** Every property that's been added has followed this pattern, and each addition was cheap because of it. Adding a new property tomorrow (`format:`, `unit:`, `audience:`) is the same shape of work as the last three.

**How to apply.** A new variable property:
1. Add a column via `_add_column_if_missing`.
2. Add a `VARIABLE_<property>` seed list.
3. Add a `_validate_<property>` function.
4. Add an idempotent backfill loop (null-then-set so removing a value is just an edit-and-rerun).
5. Add the column to `SELECT` in `get_variables()`.
6. Add the column to `SCHEMA_EXPECTATIONS` in `verify_schema()`.
7. Render it in the frontend where the user needs to see it.

That's the whole template. Every previous round followed it, every future one should.

---

## A note on principle violations

These aren't laws — they're the current best understanding of what the system needs to be. If a future requirement legitimately needs a flag stored on `jobs`, or a variable importance baked into client code, do it. But name the principle you're crossing in the same change, write down why it was worth it, and update this doc so the next agent inherits the new understanding instead of being told a lie.

The principles aren't immutable. They're load-bearing until something better holds them up.
