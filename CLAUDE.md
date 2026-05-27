# Synthesis Workbench — Agent Brief

You are working on **Synthesis Workbench**, a small local desktop app that turns one company's facts plus the user's role-level data plus narrative content into reusable lenses (formulas) that downstream produce synthesized resume-style points. The app is not a resume writer; it stops at *synthesized points*, leaving the bullet-writing to a human or downstream LLM.

The system is designed to be generalizable to any user's career.

---

## Read these in this order before touching anything

1. **`MD/01_System_Principles.md`** — the nine rules the system runs by. If you propose a change that violates one, name which and why.
2. **`JOURNEY.md`** — short build story, the arc.
3. **`MD/02_Feature Design - Repeating Entities.md`** — the multi-entry mechanism (SHIPPED).
4. **`MD/03_Feature Design - Derived Variables.md`** — server-as-authority for computed fields (SHIPPED).
5. **`MD/04_Feature Design - Story Track + Visual Vocabulary.md`** — the Story track and per-section colors (SHIPPED).
6. **`MD/06_Intake Card Authoring Kit.md`** — the user-facing intake-card grammar, regenerable.

---

## Architecture in one paragraph

Three tiers. The browser (`Frontend/*.html`) calls `Frontend/server.py` (Flask) which calls `Frontend/data.py` (the only code that speaks SQL) which reads/writes `DB/synthesis.db` (SQLite). The schema is built by `DB/build_synthesis_db.py` — that file is the SSOT for the 79 Index variables and every classification rail on them. Never write SQL outside `data.py`. Never bypass `server.py` from the HTML.

Four classification rails on each variable, each a one-line entry in a seed list inside `build_synthesis_db.py`:

- `input_type` (text / select / date / number / url) → `VARIABLE_TYPES`
- `tier` (1 / 2 / 3) → `VARIABLE_TIERS`
- `derived` (NULL or `verb:args` recipe) → `VARIABLE_DERIVATIONS`
- `track` (NULL or `story`) → `VARIABLE_TRACKS`

A fifth rail probably gets added someday. The pattern is documented in `01_System_Principles.md` §9.

---

## How to run

**Migrate the database** (run after pulling, or after changing the schema):

```powershell
cd DB
python build_synthesis_db.py
```

Non-destructive — only adds missing columns and reseeds metadata. User data in `synthesis.db` survives.

**Run the test suite** (118 assertions at time of writing — keep it green):

```powershell
cd Frontend
python test_api.py
```

**Start the server** (Flask dev mode, port 5000):

```powershell
cd Frontend
python server.py
```

Then `http://127.0.0.1:5000/profile` in the browser. Server boot runs `data.verify_schema()` — refuses to start if the DB is missing an expected column, with a "run python build_synthesis_db.py" hint.

**Launch as desktop app** (Windows):

```
Frontend\Synthesis Workbench.bat
```

Uses pywebview + pythonw for a windowless Chromium-embedded window. Debug variant (`Synthesis Workbench (debug).bat`) keeps a console plus writes `launcher_log.txt`.

**Regenerate the Authoring Kit**:

```powershell
cd MD
python generate_authoring_kit.py
```

Reads SSOT from `DB/build_synthesis_db.py`, writes `MD/06_Intake Card Authoring Kit.md`.

---

## House rules

1. **Schema is data.** A new property on a variable is a new column plus a new SSOT seed list plus a one-line entry per affected variable. Not a hardcoded set in some helper file.
2. **Server is the authority** for derived values. Don't validate-and-reject; drop-and-recompute. (Principle §6.)
3. **Color is structural identity.** If you add a new repeating section, give it a distinct color in the existing palette family (PI green/amber, CF blue/indigo, Story violet/magenta). Don't reuse an existing section's color. (Principle §8.)
4. **Don't bypass the data layer.** All SQL lives in `data.py`. `server.py` calls `data.py` functions; HTML calls `/api/*`. If a feature needs a new query, add it to `data.py` first.
5. **Tests stay green.** Every shipped round added test_api.py assertions for its behavior. Don't ship without extending the suite.
6. **Screenshots rotate, the README does not.** `Docs/Visual Examples/` follows the canonical + audit-trail pattern: flat level holds the current canonical files (`Main Page.png`, `In Progress Jobs.png`); `Previous_Versions/` holds the superseded ones, date-stamped (e.g. `Main Page - 2026-05-27.png`). When you take a fresh screenshot, move the current one into `Previous_Versions/` with a date in its name, then save the new one over the canonical filename. The README references the canonical filenames only, so it never needs re-editing on refresh.

---

## Anti-patterns we've already paid for

- **Counting in variable names** (`role_1_title`, `role_2_title`) — collapsed in an early round. Use `repeats: 1` plus `entry_no`.
- **Status as a flag stored on `jobs`** — never built; computed on every read instead. (Principle §3.)
- **Hardcoding important-variable lists** in client code — replaced by the `tier` column. (Principle §4.)
- **Allowing manual writes to derived fields** — silently dropped in `save_job`. (Principle §6.)
- **Server columns that the schema doesn't enforce** — caught by `data.verify_schema()` at boot. Add to `SCHEMA_EXPECTATIONS` when adding a column.
