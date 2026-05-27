# Feature Design — Derived Variables

**Status: SHIPPED** — 2026-05-27 (R8.J–M)
**Owner:** Synthesis Workbench
**Companion docs:** `01_System_Principles.md` §5 §6 §9 · `02_Feature Design - Repeating Entities.md` (the design-doc format this one mirrors)

---

## 1. What it does

Some Index variables are not user-entered — they are *computed* from other variables. The first three shipped:

- `#51 how_many_roles` — always equals the count of P1 Roles entries.
- `#52 tenure (overview)` — auto-calculated from `#48 start` and `#49 end`.
- `#57 tenure (per-role)` — auto-calculated per role from `#55 start` and `#56 end`.

The workbench renders these as read-only `auto · <value>` pills. The server is the authority — manual writes to a derived variable are silently dropped on save, then the server recomputes the truth and writes it back. The DB column is kept current so downstream lens JOINs can read it cheaply.

---

## 2. Why it was needed

Before R8.J, `#51` was a plain integer text field. A user with one role entry could enter `5` and the system would dutifully store the lie. Status said the job was "ready" even though the data contradicted itself.

The user named the problem directly: *"can we lock this some way on the backend to make this tight."* The choice was between (a) validating consistency at save time and rejecting bad input, or (b) deriving the value so inconsistency is not representable. Option (b) is structurally stronger — there is no inconsistency to validate against.

---

## 3. The data model

### 3.1 Schema

A new column on `p1_variables`:

```sql
ALTER TABLE p1_variables ADD COLUMN derived TEXT;
```

`NULL` means user-entered (the default; 76 of 79 variables). A non-NULL string is a **recipe** with the shape `verb:args` — see §3.3 for verbs.

Added via `_add_column_if_missing` so existing databases migrate without data loss.

### 3.2 Seed (SSOT)

`build_synthesis_db.VARIABLE_DERIVATIONS`:

```python
VARIABLE_DERIVATIONS = [
    (51, 'count:P1 Roles'),       # how_many_roles
    (52, 'duration:48,49'),       # tenure (overview)
    (57, 'duration:55,56'),       # tenure (per-role)
]
```

Idempotent backfill: `UPDATE p1_variables SET derived = NULL` followed by the seeded values on every build. Adding or removing a recipe is one line + re-run.

Build-time validator `_validate_derivations()` refuses to build the DB if a recipe points at a missing id, repeats an id, or uses an unknown verb prefix.

### 3.3 The verbs

Each verb is a one-line dispatch in `data.compute_derived_value(recipe, entry, stored, section_N)`:

| Verb | Recipe shape | Returns | Example |
|---|---|---|---|
| `count` | `count:<section>` | int (entry count of the named section) | `count:P1 Roles` → 2 when the user has 2 roles |
| `duration` | `duration:<start_vid>,<end_vid>` | `"Xy Ym"` or `"Xy Ym · ongoing"` | `duration:48,49` → `"4y 4m"` |

Adding a new verb is one helper function on the server (Python) + one matching helper on the frontend (JS mirror, see §5).

---

## 4. The contract

### 4.1 Server is the authority

`save_job` filters out any incoming value whose vid is in the derived set:

```python
derived_ids = set(_derived_recipes(conn).keys())
parsed = [(vid, e, v) for (vid, e, v) in parsed if vid not in derived_ids]
```

After the user-written values land, `_recompute_derived(conn, job_id)` runs:

1. Reads the just-saved stored values.
2. For every derived (vid, entry), runs `compute_derived_value` against them.
3. Writes the result back to `p1_variable_values` (or deletes the row when the recipe yields `None`).

### 4.2 Read path

`_job_dict` re-derives on every read. Even if the DB column is stale for some reason, the wire always carries the freshly-computed value. The DB column is essentially a cache for lens-side JOINs.

### 4.3 Status

`compute_job_status` is derivation-aware: a derived variable counts as "assessed" when its recipe yields a non-empty result. For `#51`, this is always (entries default to 1). For `#52`/`#57`, only when both date inputs parse.

---

## 5. The JS mirror

The frontend mirrors the same two verbs locally so the read-only pill updates the instant a +Add fires or a date input changes — before any save. `job.html`:

- `_parseLooseDate(s)` — handles `YYYY-MM-DD`, `YYYY-MM`, `YYYY`, and `present`/`current`/`now`.
- `_computeDuration(startStr, endStr)` — months math + `"ongoing"` suffix when end is a present-sentinel.
- `computeDerivedValue(recipe, entry)` — verb dispatch. Reads from `VALUES` and `ENTRIES`.
- `renderInput(v, entry)` — when `v.derived` is set, renders the `<div class="derived-pill" data-vid=… data-entry=…>` instead of an input. Hides the Mark-N/A button.
- `refreshDerived()` — called from `captureValue`; walks every `.derived-pill` and recomputes in place.
- `computeStatus()` — also derivation-aware, so the live badge stays honest.

**The math here MUST match the Python in data.py.** If you add a verb in one place, add it in both. The signature and behavior should be identical.

---

## 6. UI

The derived pill:

```html
<div class="derived-pill" data-vid="51" data-entry="1" title="Auto — number of entries in P1 Roles">
  <span class="derived-tag">auto</span>
  <span class="derived-val">2</span>
</div>
```

Blue badge ("auto") + bold tabular value. Hover tooltip explains the recipe. No input, no Mark-N/A.

---

## 7. Test coverage

`Frontend/test_api.py` carries 11 derivation-specific assertions:

- `/api/variables` returns `derived` on every variable; exactly 3 are non-null.
- The three recipes (`#51`, `#52`, `#57`) carry the expected strings.
- Newly-created job: `#51` reads as `1` (default entry count).
- After saving two role values: `#51` reflects `2`.
- Manual override attempt `{"51.1": "99"}` is silently dropped — still `2`.
- `#52` computes `"4y 4m"` for `2020-01..2024-05`.
- `#52` with end `"present"` appends ` · ongoing`.
- `#57` computes per-entry (entry 1 normal, entry 2 ongoing).
- `#52` yields nothing for unparseable dates.

All green at the time of ship.

---

## 8. Extensions teed up

The pattern handles these for free with one line each (assuming the verb exists):

- `#50 promotions` — could derive from a hypothetical `is_promotion` flag per role. Skipped at ship time because the source signal isn't yet structurally captured.
- **Gap detection** — a `gap:<vid>,<vid>` verb that finds employment gaps between role end dates. Would compute as a list or a "gap or no gap" boolean.
- **Concatenation** — a `concat:<vid>,<vid>` verb for "City, State" type fields.
- **Sum** — a `sum:<vid>,<vid>,…` verb for numeric totals across multiple variables.

Each is one row in `VARIABLE_DERIVATIONS` + (if new) one verb function in two languages.

---

## 9. Operating note

If you ever need to interrogate "what does this job currently *think* `#52` is?" — do not read `p1_variable_values` directly. Hit `/api/jobs/<id>` and look at the `values` map. The wire always carries the freshly-computed value; the DB column is a cache that may briefly drift in edge cases (mid-migration, mid-debug, mid-restore).

If you ever need to test that the manual-override drop is working — `PUT /api/jobs/<id>` with `{"values": {"51.1": "<lie>"}}` and check the response: the returned `values["51.1"]` should be the recipe's computed value, not the lie.
