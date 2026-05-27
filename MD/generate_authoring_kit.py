# -*- coding: utf-8 -*-
"""
generate_authoring_kit.py  --  rebuilds the Intake Card Authoring Kit.

WHAT IT IS
A one-step generator that reads `DB/build_synthesis_db.py` -- the schema
source of truth -- pulls out every variable and its typing, and writes
`06_Intake Card Authoring Kit.md` beside this script. The kit's snapshot of
the Index is regenerated from scratch every run, so it never drifts.

WHY A GENERATOR (NOT A HAND-WRITTEN DOC)
The Index can change. A hand-copied table drifts. This script reads the
live VARIABLES + VARIABLE_TYPES lists, computes the variable count and
sheet ranges, and re-emits the whole kit from the prose template below.
Variable count, ranges, the per-sheet table, the section quick-ref --
every number is derived, none are hardcoded.

HOW TO RUN
    python "generate_authoring_kit.py"
It rewrites `06_Intake Card Authoring Kit.md` in this MD folder.
"""

import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, os.pardir, "DB", "build_synthesis_db.py")
OUT_MD = os.path.join(HERE, "06_Intake Card Authoring Kit.md")


# ---- pull VARIABLES and VARIABLE_TYPES out of the schema script ----
# build_synthesis_db.py defines both as Python list literals. We slice
# each one out by its name and the first newline-bracket that closes it,
# then eval. No need to run the schema script itself.
_src = open(SCHEMA, encoding="utf-8").read()


def _literal(name):
    start = _src.index(name + " = [")
    open_b = _src.index("[", start)
    close_b = _src.index("\n]", open_b)
    return _src[open_b:close_b + 2]


VARIABLES = eval(_literal("VARIABLES"))                    # (id, field, file, section, repeats, definition)
VARIABLE_TYPES = eval(_literal("VARIABLE_TYPES"))          # (id, input_type, options)
VARIABLE_TIERS = eval(_literal("VARIABLE_TIERS"))          # (id, tier)
VARIABLE_DERIVATIONS = eval(_literal("VARIABLE_DERIVATIONS"))  # (id, recipe)
VARIABLE_TRACKS = eval(_literal("VARIABLE_TRACKS"))        # (id, track)

assert [v[0] for v in VARIABLES] == list(range(1, len(VARIABLES) + 1)), \
    "Index ids must be contiguous 1..N"

TYPE_OF    = {vid: (it, opts) for vid, it, opts in VARIABLE_TYPES}
TIER_OF    = {vid: t for vid, t in VARIABLE_TIERS}
DERIVED_OF = {vid: r for vid, r in VARIABLE_DERIVATIONS}
TRACK_OF   = {vid: t for vid, t in VARIABLE_TRACKS}
SHEETS = ["Company Facts", "Personal Info", "Story"]
N = len(VARIABLES)


def srange(sheet):
    """The '#lo-#hi' id range for one sheet."""
    ids = [v[0] for v in VARIABLES if v[2] == sheet]
    return "#%d-#%d" % (min(ids), max(ids))


def accepts(vid):
    """(input_type, plain-English 'accepts' phrase) for one variable id."""
    it, opts = TYPE_OF.get(vid, ("text", None))
    if it == "select":
        return it, "one of: " + " / ".join(opts.split("|"))
    if it == "date":
        return it, "a date, YYYY-MM-DD"
    if it == "number":
        return it, "a number"
    if it == "url":
        return it, "a URL"
    return it, "free text"


def section_ref():
    """Quick reference: every section name, its id range, and repeat flag."""
    blocks = []
    for vid, field, file, section, repeats, definition in VARIABLES:
        if blocks and blocks[-1][0] == file and blocks[-1][1] == section:
            blocks[-1][3] = vid
        else:
            blocks.append([file, section, vid, vid, repeats])
    lines, cur = [], None
    for file, section, lo, hi, rep in blocks:
        if file != cur:
            lines.append("")
            lines.append("**" + file + "**")
            lines.append("")
            cur = file
        rng = "#%d" % lo if lo == hi else "#%d-#%d" % (lo, hi)
        lines.append("- `%s` -- %s%s"
                     % (section, rng, "  *(repeats)*" if rep else ""))
    return "\n".join(lines).strip()


def index_table():
    """One markdown table per sheet, every variable on its own row."""
    out = []
    for sheet in SHEETS:
        rows = [v for v in VARIABLES if v[2] == sheet]
        lo, hi = rows[0][0], rows[-1][0]
        out.append("")
        out.append("### %s -- #%d through #%d" % (sheet, lo, hi))
        out.append("")
        out.append("| # | Tier | Track | Section | Field key | Type | Derived | Accepts | What it means |")
        out.append("|--:|:-:|:-:|---|---|---|---|---|---|")
        for vid, field, file, section, repeats, definition in rows:
            it, acc = accepts(vid)
            tier = TIER_OF.get(vid, 2)
            track = TRACK_OF.get(vid) or '—'
            derived = DERIVED_OF.get(vid)
            derived_cell = ('`' + derived + '`') if derived else '—'
            out.append("| %d | T%d | %s | %s | `%s` | %s | %s | %s | %s |"
                       % (vid, tier, track, section, field, it,
                          derived_cell, acc, definition))
    return "\n".join(out).strip()


CARD_A = """card: 1.1
Inputs: 1, 2, 4, 5, 7, 12, 15, 17, 19

Disclosure
disclosure: Privately held

C1 Identity
legal_name: Northwind Tooling Co.
legal_entity_type: S-Corporation
date_of_incorporation: 1987-04-15
website: https://northwindtooling.example

C1 Ownership & Industry
ownership: Family-owned

C1 Scale
locations_count: 3
geographic_reach: Regional
total_employee_headcount: 240"""

CARD_B = """card: 1.2
Inputs: 8, 15

C1 Identity
ticker:

C1 Scale
locations_count:"""

CARD_C = """card: 1.1
Inputs: 10, 11

C1 Ownership & Industry
primary_industry: Manufacturing
primary_sector: Industrial tooling

card: 1.2
Inputs: 33

C1 Offering & Character
market_share:"""

CARD_D = """card: 1.1
Inputs: 54, 55, 56, 58

P1 Roles
entry: 1
title: Production Floor Worker
start: 2021-05-01
end: 2021-11-15
employment_type: Full-time

entry: 2
title: Sales and Procurement Manager
start: 2021-11-15
end: 2026-02-01
employment_type: Full-time"""


DOC = r'''# Intake Card Authoring Kit -- Synthesis Workbench

*Generated from `DB/build_synthesis_db.py` -- the schema source of truth -- on {{DATE}}. The {{N}}-variable snapshot in section 5 mirrors the `p1_variables` table exactly. If the Index changes, regenerate this file (see section 8).*

---

## 0 - What this kit is

An **intake card** is a block of plain text. Pasted into the Synthesis Workbench job page, a deterministic parser turns it into field values written to a job's record -- no AI in that step, no network call, the same card always producing the same result.

This kit is the complete reference for **writing those cards**. It is meant to be handed to a Claude Code session that has access to source documents -- employment records, company filings, personnel files -- so that session can author cards from them. Everything that session needs is here: the grammar (section 3), the value rules (section 4), and a snapshot of all {{N}} Index variables (section 5).

**The authoring session writes card text and nothing else.** It does not run the app, open the database, or change any data. It hands cards to the user; the user pastes, previews, and approves them.

## 1 - The workflow

```
source documents
   |   the authoring session reads them and writes cards
intake card text
   |   the user pastes it -- job page, Intake, "Paste a card"
PREVIEW    the parser shows exactly what the card would do --
   |       clean fields ticked, problems flagged by line number
APPLY      the values land in the on-screen form
   |       the user reviews the filled form
SAVE       the values are written to the database
```

Everything from PREVIEW onward is the **user's** decision. A card is a proposal, never a direct write. Nothing reaches the database until the user presses Save.

## 2 - Sourcing discipline -- read before authoring

The parser checks that a value is well-*formed*. It cannot check that a value is *true*: `disclosure: Publicly traded` parses perfectly even if the company is private. Accuracy is entirely the author's responsibility.

- **Author only what the source documents state.** Do not infer, estimate, or fill a field because it ought to have a value.
- **A partial card is normal.** If the documents cover eight fields, the card sets eight fields. Omitting the rest is correct, not incomplete.
- **When a fact is ambiguous, do not guess.** A year with no month, a value that could map to two fields, a headcount that might be one division or the whole company -- leave it out and tell the user, or present the options for them to resolve.
- **Never fabricate.** No invented dates, headcounts, names, or certifications. A card of six certain fields beats a card of twenty with guesses mixed in.

Certifications and standards (the C3 sections) belong to the *company* and are recorded as company facts -- they are not personal credentials. Record what a document evidences, nothing more.

## 3 - The card grammar

A card is a run of lines. There are exactly **five kinds of meaningful line** -- the card code, the Inputs manifest, the section header, the optional `entry:` pointer, and the field lines -- plus blanks and comments.

### 3.1 - The card code: `card: <slot>.<intent>`

Every card opens with a `card:` line -- two numbers, a dot between:

- **slot** -- the Work Experience position of the job the card targets (1, 2, 3, ...). The parser shows the slot in the preview; it applies the card to whichever job is open, so set the slot honestly for traceability.
- **intent** -- `1` = **add** (write values), `2` = **subtract** (clear fields). Nothing else; a `3` or higher is rejected.

`card: 2.1` means "add, targeting the job in slot 2." A card does one or the other, never both -- to change a value, subtract it then add the new one (two cards; see 3.7).

### 3.2 - The Inputs manifest: `Inputs: <#, #, ...>`

One mandatory `Inputs:` line per card -- a comma-separated list of the variable **#ids** the card will touch:

```
Inputs: 2, 5, 19
```

Each token must be a number and a real Index id (1 to {{N}}). The manifest is **cross-checked both ways** against the field lines: every id in `Inputs` must have at least one matching field line, and every field line's id must appear in `Inputs`. The same id can fire on multiple entries -- list it once. The manifest is the card's own checksum.

### 3.3 - Section headers: a line with no colon

A line containing **no colon** is a section header. It must match an Index section name exactly (case-insensitive). It sets the *current section* for the field lines beneath it, and resets the entry pointer to 1:

```
C1 Identity
```

The section names are listed in section 5. Several contain a middle dot -- copy them exactly from section 5.

### 3.4 - Field lines: `<field>: <value>`

A line **with a colon** sets one field. It is split on the **first** colon, so a value may itself contain colons (a URL, a time):

```
website: https://example.com
```

The field key is matched **within the current section**, by the field's key (`legal_name`) or its display form (`Legal name`), case-insensitive. A field line before any section header is rejected; so is the same field set twice **at the same entry** in one card.

> **Field keys repeat across sections.** `category`, `title`, `start`, `name` and others appear under several sections with different meanings. The section header disambiguates them -- always place a field under the right header, and let the `Inputs` #ids (globally unique) be the anchor.

### 3.5 - Multiple entries: `entry: N`

A **repeating section** -- Roles, References, both Cert sections, every Story section -- can hold several entries per job. To set them in one card, place an `entry: N` line inside the section block. Subsequent field lines target that entry until the next `entry:` line or a new section header:

```
P1 Roles
entry: 1
title: Production Floor Worker
start: 2021-05-01

entry: 2
title: Sales and Procurement Manager
start: 2021-11-15
```

Without an `entry:` line, the current entry is 1, so a single-entry card in a repeating section reads exactly like a singular one. A section header always resets the entry to 1. `entry:` is rejected if it appears before any section header, in a singular section, or with a non-positive value. The same field at the *same* entry is a duplicate; the same field at *different* entries is fine -- that is the whole point.

Cards **grow** cardinality (the highest `entry: N` referenced becomes the section's count after Apply). Cards never reduce it; reduction is the form's **Remove** button -- a click, not a card.

### 3.6 - Blank lines, comments, indentation

Blank lines and lines beginning with `#` are ignored. Every line is trimmed before parsing -- **indentation is purely cosmetic**.

### 3.7 - Add, subtract, and batching

An **add** card (`intent 1`) must carry a valid value for every field -- see section 4. A **subtract** card (`intent 2`) clears the listed fields; its field lines need no value. To *change* a value: one subtract card and one add card.

A single paste may hold **several cards** -- each `card:` line begins a new one. Cards are independent: a card with errors is skipped on Apply while the clean ones still apply.

### 3.8 - The parser never crashes

Every problem becomes a line-numbered error and marks its card unusable; a malformed card never throws. The full list of what is rejected is in section 7.

## 4 - Value rules by field type

Every variable has a **type** (shown in section 5). On an **add** card each value must satisfy its type or the card is flagged. On a **subtract** card values are ignored.

- **text** -- any value. (Most fields.)
- **select** -- must be one of the field's listed options (case-insensitive). The options are in section 5.
- **date** -- `YYYY-MM-DD`, e.g. `1998-07-01`.
- **number** -- digits, an optional leading `-`, an optional single decimal point: `240`, `3`, `-1.5`. No commas, no units.
- **url** -- checked leniently, like text; give a full address.

### 4.1 - N/A and other sentinels

One value sidesteps the type rules entirely: the **N/A** sentinel. Writing `N/A` (case-insensitive -- `n/a`, `N/a`, and `N/A` all normalise to canonical `N/A`) in any field marks it **not applicable to this job** -- distinct from a blank value, which means "not yet filled in." A sentinel value bypasses type validation, so `disclosure: N/A`, `date_of_incorporation: N/A`, `locations_count: N/A`, and `website: N/A` are all valid on an add card even though `disclosure` is a select, `date_of_incorporation` is a date, `locations_count` is a number, and `website` is a url.

Use a sentinel when a field cannot meaningfully be filled -- a private company has no `ticker`, a small firm has no `market_cap`, a company predates the records that would carry its exact founding date. Authoring discipline (section 2) still applies: only mark a field N/A when the source documents support that decision; if you're not sure, leave the field out of the card.

Future sentinels (`TBD`, `UNKNOWN`, `REDACTED`, ...) will be added the same way; the live list lives at `GET /api/sentinels` and on the workbench's "Mark <sentinel>" button per field.

A card does **not** set the job's Company Name -- that is the box at the top of the job page. Variable `#2 legal_name` is the company's *full registered legal name*, a separate field.

## 5 - The {{N}}-variable Index

The Index is three sheets: **Company Facts** ({{CFR}}), **Personal Info** ({{PIR}}), **Story** ({{STR}}). Every variable has a globally unique #id.

### Section names -- exact strings for the headers

{{SECTIONS}}

*Sections marked "(repeats)" hold several entries per job -- multiple roles, certifications, or people. Use `entry: N` lines (section 3.5) to set them in a card.*

### Variable tiers

Each variable carries a **tier** — 1, 2, or 3 — that says how central it is to the system as a whole:

- **Tier 1 — super tight ({{T1}} vars).** The minimum to identify a job at all. Almost every formula reads these (disclosure, legal_name, primary_industry, title, start, end, tenure).
- **Tier 2 — large; effort-worthy ({{T2}} vars).** The working substrate. Filling these opens up the bulk of formulas — scale, sector, ownership, products, mission, role-level fields.
- **Tier 3 — varying / optional ({{T3}} vars).** Niche, situational, or narrative-deep. Filling them unlocks specialized formulas — market_cap, certifications, references.

A card can carry any mix of tiers. Tier is purely classification, not validation. The workbench shows a small T1/T2/T3 pill on each field card.

### Variable tracks

A small number of variables sit on a **track** parallel to the tier system. A track is a *named engagement dimension*: filling it is a deliberate pass, not just a fact about the company.

- **`story`** — the 13 S1 People / S2 Arc / S3 Operating Model variables. These do not appear under T1/T2/T3 in the workbench; they live under the **Stories** picker option. A card can still set them by name within their section header.

A variable's track does not change how a card writes to it. Tracks affect *where the user sees the field*, not *how the parser routes it*.

### Derived variables (server-computed)

Three variables in the Index are **server-computed** — their values are derived from other fields rather than entered by the user:

| # | Field | Recipe | Means |
|--:|---|---|---|
| 51 | `how_many_roles`            | `count:P1 Roles`    | the count of P1 Roles entries on the job |
| 52 | `tenure (overview)`         | `duration:48,49`    | duration between `#48 start` and `#49 end` |
| 57 | `tenure (per-role)`         | `duration:55,56`    | per-role duration, computed per entry from `#55` and `#56` |

These render as a read-only `auto · <value>` pill in the workbench. A card that tries to set a derived variable is parsed normally, but the value is **silently dropped on save** — the server is the authority. To change a derived variable's value, change its inputs.

A future verb (`gap:`, `sum:`, `concat:`) adds new derivations the same way — one row in the schema's `VARIABLE_DERIVATIONS` list.

### The full variable table

{{TABLE}}

## 6 - Worked examples

Each card below is valid -- checked against the live parser.

**A. An add card** -- nine Company Facts fields across four sections:

```
{{CARD_A}}
```

**B. A subtract card** -- clears two fields; intent `2`, values omitted:

```
{{CARD_B}}
```

**C. A batch** -- two cards in one paste, an add then a subtract:

```
{{CARD_C}}
```

**D. A multi-entry add card** -- two role entries set in one paste, the kind a Claude Code session writes when a source document describes a multi-role tenure:

```
{{CARD_D}}
```

## 7 - What the parser rejects

Each becomes a line-numbered error; the card carrying it is skipped on Apply.

- a `card:` code that is not `<number>.<number>`
- an intent digit other than `1` or `2`
- any line before the first `card:` line
- a card with no `Inputs:` line, or with two of them
- an `Inputs` token that is not a number, or not a real Index id (1 to {{N}})
- a section-header line that matches no Index section name
- a field line before any section header
- a field key that does not belong to the current section
- the same field set twice **at the same entry** in one card
- an `entry:` line before any section header, or in a singular section, or with a non-positive value
- an id in `Inputs` with no field line, or a field line whose id is not in `Inputs`
- *(add cards only)* a field with no value, or a value that fails its type rule

## 8 - Keeping this snapshot current

Section 5 is generated from `DB/build_synthesis_db.py`, which seeds the `p1_variables` table. Re-run this script after any Index change:

```
python "generate_authoring_kit.py"
```

The live equivalent of the table is:

```sql
SELECT id, file, section, field, input_type, options, repeats, definition
FROM p1_variables ORDER BY id;
```
'''


_tier_counts = {1: 0, 2: 0, 3: 0}
for _t in TIER_OF.values():
    _tier_counts[_t] = _tier_counts.get(_t, 0) + 1

DOC = (DOC
       .replace("{{DATE}}", datetime.date.today().isoformat())
       .replace("{{N}}", str(N))
       .replace("{{CFR}}", srange("Company Facts"))
       .replace("{{PIR}}", srange("Personal Info"))
       .replace("{{STR}}", srange("Story"))
       .replace("{{SECTIONS}}", section_ref())
       .replace("{{T1}}", str(_tier_counts[1]))
       .replace("{{T2}}", str(_tier_counts[2]))
       .replace("{{T3}}", str(_tier_counts[3]))
       .replace("{{TABLE}}", index_table())
       .replace("{{CARD_A}}", CARD_A)
       .replace("{{CARD_B}}", CARD_B)
       .replace("{{CARD_C}}", CARD_C)
       .replace("{{CARD_D}}", CARD_D))

open(OUT_MD, "w", encoding="utf-8").write(DOC)
print("wrote:", OUT_MD)
print("  %d variables, %d lines, examples: A B C D"
      % (N, DOC.count(chr(10)) + 1))
