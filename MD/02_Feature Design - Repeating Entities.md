# Feature Design — Repeating Entities

*Drafted 2026-05-25. Status: **SHIPPED 2026-05-25.** All four stages (R1–R4) are
built and verified, end to end on real data. Sits beside
`05_Feature Design - Intake Code.md`; this document covers the Personal Info
restructure and the multi-entry build.*

> **Verification log.** Across R1 → R4 the sandbox harnesses logged **119 passing
> checks** before anything reached the live database: 14 schema checks +
> 17 example-card checks (R1), 30 data + Flask checks (R2), 11 + 21 = 32 checks
> for the entries-map and the multi-entry UI logic (R3), 26 parseIntake checks
> with the new `entry:` grammar (R4). The user then pasted a real multi-entry
> card on the live app — the user's ExampleCo role progression — and the database
> received it cleanly: variable #54 stored at both entry 1 and entry 2,
> `P1 Roles` carrying two entries with values.

---

## 0 · The problem

Personal Info models a person's roles as **two fixed slots** — `P1 Role 1 · Earliest`
(variables #53–61) and `P1 Role 2 · Latest` (#62–70). That hard-caps a job at exactly
two roles. Someone who held six roles at one company across twenty years cannot be
represented — the structure has nowhere to put roles three through six.

References carry the identical flaw: #71–74 are `reference_1_name`,
`reference_1_relationship`, `reference_1_reachability`, `reference_1_notes` — one
hardcoded reference slot.

This document is the design for the fix, and the staged plan to ship it.

---

## 1 · The principle — model the shape, not the count

A variable in the Index should describe the **shape** of a fact — what a role is,
what a certification is — never **how many** of them a given job has. How many roles
a person held, how many certifications a company carries: that is data, and it varies
job to job. It must live in the data, never in the variable list.

The schema was already built for this. `p1_variables` carries a `repeats` flag.
`p1_variable_values` carries an `entry_no` column, and its primary key is
`(job_id, variable_id, entry_no)` — so one variable already holds many values for one
job, distinguished by `entry_no`. The C3 certification sections (#37–46) and the
entire Story sheet (#76–88) are already marked `repeats: 1`. Roles and references
simply were not — they were modeled as fixed slots instead of repeating entities.

**The smell test, worth keeping as procedure:** if a variable's name contains a
number — `Role 1`, `Role 2`, `reference_1_name` — that number is a count that has
leaked out of the data and frozen into the schema. Whenever it appears, the fix is
the same: collapse the numbered slots into one variable-set, mark it `repeats`, and
let `entry_no` carry the count.

Note the direction this fix moves the Index: **88 variables down to 79.** Fewer
variables, unbounded capacity. Shrinking the schema while growing what it can hold is
the signature of getting the model right.

---

## 2 · The new Index — 79 variables

**Company Facts — #1–46 — unchanged.** No renumbering, no retyping. Every typed
variable (the ten selects / dates / numbers / urls) lives here, so `VARIABLE_TYPES`
in `build_synthesis_db.py` is untouched.

**Personal Info — #47–66 — restructured into three sections:**

- **`P1 Overview` · #47–53 · singular** — `title`, `start`, `end`, `promotions`,
  `how_many_roles`, `tenure`, `what_carries_forward`. The company-level summary: one
  per job. (`what_carries_forward`, old #75, moves here from the reference block.)
- **`P1 Roles` · #54–62 · repeating** — `title`, `start`, `end`, `tenure`,
  `employment_type`, `work_mode`, `reported_to`, `held_concurrently_with`,
  `one_line_summary`. One nine-variable block; a job stores one entry per role, in
  order. The old two blocks (#53–70, eighteen variables) collapse into this one.
- **`P2 References` · #63–66 · repeating** — `reference_name`,
  `reference_relationship`, `reference_reachability`, `reference_notes`. The
  `reference_1_` prefix is dropped; a job stores one entry per reference.

**Story — #67–79 — content unchanged, renumbered** from #76–88 (`S1 People`,
`S2 Arc`, `S3 Operating Model` — all already repeating).

After the restructure, seven sections repeat: `C3`, `C3 Industry Memberships`,
`P1 Roles`, `P2 References`, `S1 People`, `S2 Arc`, `S3 Operating Model`. The
multi-entry work in Stage R3 serves all seven at once.

---

## 3 · Why we delete the data and rebuild

In production you never wipe data — you migrate it, because migration protects data
that is expensive or impossible to recreate. The Synthesis prototype's data is
neither: it is hours old, the source documents still exist, and most of it was
entered as **intake cards** — deterministic text that reproduces the data exactly
when re-pasted. The cards are the backup.

A migration here would mean writing the most error-prone part of this whole change —
remapping live values and formula wiring across a renumbered 88→79 Index — purely to
preserve data that costs minutes to re-enter. We skip it. Deleting the data also
makes the renumber **free**: with no jobs and no formulas referencing variable ids,
there is nothing to remap.

The rebuild is one operation, not two. `build_synthesis_db.py` is the schema's source
of truth and is deliberately non-destructive — it will not wipe an existing database.
So: edit the Index in that script, delete `synthesis.db`, re-run the script. It
rebuilds every table fresh and reseeds the variables, the nine output kinds, the
`_guide`, and the BASE control job; jobs, formulas, and clusters all start empty. The
**table architecture** — the eleven tables, their columns, `data.py`, `server.py`,
the app — does not change. Only the Index (the variable catalog) and the code that
reads entries.

---

## 4 · The plan — four stages

Each stage ends with the app in a **working state** and a **passing verification
harness** — the same discipline the river build held to (31 + 21 + 39 + 21 checks).

### Stage R1 — New Index + barebones rebuild

1. **Safety export.** Dump the three current jobs (ExampleCo, Cheshire Pizza, GlobalCorp) to a
   plain-text file, with the Company Facts portions also written as ready-to-paste
   intake cards. Costs nothing; turns re-entry into paste-not-retype.
2. Rewrite the `VARIABLES` list in `build_synthesis_db.py` to the 79-variable
   structure in §2 — collapse the role blocks, collapse references, move
   `what_carries_forward`, set the `repeats` flags, renumber Personal Info and Story
   contiguously.
3. Delete `synthesis.db`.
4. Re-run `build_synthesis_db.py` → fresh 79-variable database, BASE seeded,
   everything else empty.
5. Regenerate the authoring kit — `generate_authoring_kit.py` reads the new schema,
   so the snapshot updates itself.

**Verify:** a script confirms the rebuilt DB has 79 variables, the correct sections
and `repeats` flags, BASE present with 79 blank value rows, and the `p2_*` tables and
non-BASE `jobs` empty.

**State after:** the app runs. Personal Info shows one `P1 Roles` section and one
`P2 References` section; until R3 the form renders one entry each — fully usable,
just single-role for now. Nothing is broken.

### Stage R2 — Multi-entry data layer

1. Lock the job-dict shape — leaning: singular variables keep `{id: value}`;
   repeating variables return an ordered list of entries.
2. `data.py` — `get_job` / `_job_dict` stop hardcoding `entry_no = 1` and read every
   entry; `save_job` writes multiple entries; validation extended.
3. `server.py` — `/api/jobs/<id>` GET and PUT carry the entry dimension;
   `_job_from_request` extended.
4. `test_api.py` and `data.py`'s self-test gain multi-entry cases.

**Verify:** sandbox harnesses, the pattern used across the river phases.

**State after:** the backend stores and serves N entries; the form still shows one.
Still not broken.

### Stage R3 — Multi-entry UI

1. `job.html` — a repeating section renders its entries as a stack of cards, each
   with the section's fields, plus **+ Add** and **Remove** controls; the `VALUES`
   model and `captureValue` track `(variable, entry)`.
2. This serves every repeating section at once — Roles, References, both C3 sections,
   all three Story sections.

**Verify:** Node harness.

**State after:** multi-role data entry works end to end — fill six roles, save,
reload, edit.

### Stage R4 — Intake grammar for entries

1. The card grammar gains a way to target an entry — create a new role entry, or
   address an existing one. (Exact syntax is R4's first design task; leaning: a card
   creates entries in order, and a section header may carry an entry index.)
2. `parseIntake` in `job.html` updated; the authoring kit's grammar section and
   example cards updated.

**Verify:** the card-parser harness, extended.

**State after:** a Claude Code session can author multi-role cards from source
documents — the original goal, now reaching the repeating sections.

---

## 5 · Formulas — no schema change

A formula's inputs are stored in `p2_formula_inputs` as plain `variable_id`
references. When a formula input points at a repeating variable, it yields that
variable's entries as an **ordered list** — the `repeats` flag already tells the
engine the input is list-valued. A "role progression" formula reading the role
`title` variable receives `[Intern, Analyst, Manager]` in order, which is exactly
what a narrative formula wants. Nothing in the formula tables changes; the engine
reads repeating inputs as lists when it is built.

---

## 6 · Scope, risks, and what is deliberately not changing

- **The current data is deleted** — ExampleCo, Cheshire Pizza, GlobalCorp, the six formulas,
  the one cluster. Confirmed acceptable; the safety export in R1 makes re-entry fast.
- **The table architecture does not change** — eleven tables, their columns,
  `entry_no`, `data.py`, `server.py`, the app's structure. Only the Index and the
  entry-reading code change.
- **The trickiest stage is R4** (intake grammar for entries); R1–R3 are
  well-understood.
- **`how_many_roles` (#51) is kept** in Overview as a stated headline figure, though
  the role entry count is now the structural truth. Flagged here in case you would
  rather drop it.
- **Out of scope:** the Formulas engine itself; the Story-sheet content design; any
  change to Company Facts.

---

## 7 · Decision points for approval

1. Approve the 79-variable Index in §2 — including references becoming a repeating
   block, and `what_carries_forward` moving into Overview.
2. Approve the wipe-and-rebuild approach in §3.
3. Approve the four-stage plan, or scope it down (e.g. ship R1 alone first).
4. `how_many_roles` — keep or drop (§6).
