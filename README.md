# Synthesis Workbench

*v1.0 · public foundation — see the [Roadmap](#roadmap) for what's private.*

A small, local desktop app that captures a person's work history at a structured level, then runs reusable lenses ("formulas") over the data to produce synthesized, resume-grade points.

The app does **not** write resume bullets — it stops at synthesized points, leaving final voice and formatting to a downstream pass (a human, or an LLM, or both). The point is that your data exists once, in one shape, and any number of formulas can read it.

---

## Where to start reading

The docs are numbered for reading order:

1. **README.md** — you're here.
2. **[JOURNEY.md](./JOURNEY.md)** — short build story (5-minute read).
3. **[CLAUDE.md](./CLAUDE.md)** — brief for AI agents working on the codebase. Also a useful technical orientation for humans.
4. **[MD/01_System_Principles.md](<./MD/01_System_Principles.md>)** — the nine load-bearing rules.
5. **[MD/02_Feature Design - Repeating Entities.md](<./MD/02_Feature Design - Repeating Entities.md>)** — the multi-entry mechanism.
6. **[MD/03_Feature Design - Derived Variables.md](<./MD/03_Feature Design - Derived Variables.md>)** — server-as-authority for computed fields.
7. **[MD/04_Feature Design - Story Track + Visual Vocabulary.md](<./MD/04_Feature Design - Story Track + Visual Vocabulary.md>)** — the Story track + per-section colors.
8. **[MD/05_Feature Design - Intake Code.md](<./MD/05_Feature Design - Intake Code.md>)** — the text-card grammar.
9. **[MD/06_Intake Card Authoring Kit.md](<./MD/06_Intake Card Authoring Kit.md>)** — user-facing reference for the intake card format.

---

## Roadmap

**v1.X — polish on this foundation.** Refinements to the existing architecture, UI, documentation, performance. Anything that improves what's already here without changing the structural shape lands as v1.1, v1.2, etc.

**v2.0+ — private development.** The next layers — formulas that declare tier and engagement requirements, the synthesis output engine, the bolstering loop, multi-job orchestration — are being built in a private workspace. This public repo represents the foundation; the application logic that compounds on top of it stays private until it's worth sharing.

---

## Project layout

```
.
├── CLAUDE.md       ← brief for AI agents working on the codebase
├── JOURNEY.md      ← short build story
├── LICENSE         ← MIT
├── README.md       ← you're here
├── requirements.txt
│
├── DB/
│   └── build_synthesis_db.py     ← SSOT for schema + variable metadata
│
├── Frontend/
│   ├── server.py                 ← Flask web layer
│   ├── data.py                   ← data layer (ONLY code with SQL)
│   ├── test_api.py               ← 118-assertion suite
│   ├── *.html                    ← start / profile / job / workbench
│   ├── desktop.py + .bat         ← pywebview launcher (Windows)
│   └── synthesis.{ico,png}       ← app icons
│
└── MD/
    ├── 01_System_Principles.md
    ├── 02_Feature Design - Repeating Entities.md
    ├── 03_Feature Design - Derived Variables.md
    ├── 04_Feature Design - Story Track + Visual Vocabulary.md
    ├── 05_Feature Design - Intake Code.md
    ├── 06_Intake Card Authoring Kit.md
    └── generate_authoring_kit.py
```

---

## Architecture in one paragraph

Three tiers. The browser (`Frontend/*.html`) calls `Frontend/server.py` (Flask) which calls `Frontend/data.py` (the only code that speaks SQL) which reads/writes `DB/synthesis.db` (SQLite). The schema is built by `DB/build_synthesis_db.py` — that file is the SSOT for the 79 Index variables and every classification rail on them. Never write SQL outside `data.py`. Never bypass `server.py` from the HTML.

---

## What it does

For each company on a user's work history, the app captures **79 variables** across three logical sheets — Company Facts, Personal Info, Story — through a single unified view (the **By Tier** picker). That view exposes the same 79 variables four different ways:

- **Tier 1** (7 vars) — super-tight anchors (disclosure, legal name, primary industry, title, start, end, tenure)
- **Tier 2** (16 vars) — effort-worthy substrate (scale, ownership, mission, role-level fields)
- **Tier 3** (43 vars) — varying / niche (certifications, references, period events)
- **Stories** (13 vars) — the engagement track (people, story arcs, operating model)

A handful of variables are **derived** — the server computes them from other fields and refuses to be lied to. `how_many_roles` is the count of role entries; `tenure (overview)` is the duration between start and end dates; `tenure (per-role)` is per-role. Try to set them by hand and the server silently overwrites the lie with the truth.

Each repeating section has its own color, consistent across every view, so a user reading the form knows "this teal stack is Roles, this amber stack is References" without reading a single label. **Color is structural identity.**

---

## What's interesting about it as a portfolio piece

A few patterns worth pointing out, because they show up everywhere in the codebase:

**Schema-as-data.** Every variable carries four classification rails on its row — `input_type`, `tier`, `derived`, `track`. Each rail is a one-line entry in a SSOT seed list inside `DB/build_synthesis_db.py`, build-time validated, idempotently backfilled, exposed through `/api/variables`. Adding a fifth rail tomorrow follows the same template. Documented in `MD/01_System_Principles.md` §9.

**Server-as-authority for derived values.** A variable marked `derived` carries a recipe string (`count:<section>` or `duration:<vid>,<vid>`). The server's `compute_derived_value()` dispatches by verb. `save_job` silently drops any incoming user value for a derived variable. Manual edits cannot lie to the system because lying is not representable.

**Schema-version startup check.** `data.verify_schema()` runs at server boot. If the database is missing any column the app now expects, the server refuses to start and prints a one-line "run python build_synthesis_db.py" hint. The class of bug where code drifts past schema is gone.

**Visual vocabulary as a first-class identifier.** Each unique repeating section has its own color (driven by a `data-home-section` attribute in the DOM). The SAME section keeps the SAME color across every tier view filter. Color is identity, not decoration.

**118-assertion test suite.** Covers every API surface plus the derivation engine, the tier progress logic, and the engagement-active stories behavior. `python Frontend/test_api.py` to run.

For the longer story (principles, design decisions, the journey from prototype to here) see `MD/01_System_Principles.md` and the per-feature design docs in `MD/`.

---

## Quick start

Tested on Windows + Python 3 (miniconda). Flask is the only required dependency; `pywebview` is optional and powers the windowless Windows desktop launcher.

```powershell
# 0. Install Python dependencies
pip install -r requirements.txt

# 1. Build / migrate the database (non-destructive, safe to re-run)
cd DB
python build_synthesis_db.py

# 2. Run the test suite (should land at 118 passing assertions)
cd ..\Frontend
python test_api.py

# 3a. Start the server (browser mode)
python server.py
# → http://127.0.0.1:5000/profile

# 3b. Or launch as a desktop app (Windows, requires pywebview)
.\"Synthesis Workbench.bat"
```

---

## Status

Personal project. Not currently published as a product. If you'd like to discuss it — current or future — my contact information is in my application.

## License

MIT — see [LICENSE](./LICENSE). You're free to use, modify, and redistribute as long as the copyright + license notice are included.

---

## Why this README exists

The codebase shows the *what*. This file shows the *why*. The principles are load-bearing — they're what makes adding the next feature a one-line edit instead of a refactor. Anyone reading the code should know they exist, even if the implementation looks straightforward in the moment.

If you're another agent picking up this codebase later: read `MD/01_System_Principles.md` first, then the per-round design docs in `MD/`. Listen for the framings before proposing architecture — most decisions in this codebase came from naming a frustration out loud rather than designing top-down.

