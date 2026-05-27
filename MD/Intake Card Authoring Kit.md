# Intake Card Authoring Kit -- Synthesis Workbench

*Generated from `DB/build_synthesis_db.py` -- the schema source of truth -- on 2026-05-27. The 79-variable snapshot in section 5 mirrors the `p1_variables` table exactly. If the Index changes, regenerate this file (see section 8).*

---

## 0 - What this kit is

An **intake card** is a block of plain text. Pasted into the Synthesis Workbench job page, a deterministic parser turns it into field values written to a job's record -- no AI in that step, no network call, the same card always producing the same result.

This kit is the complete reference for **writing those cards**. It is meant to be handed to a Claude Code session that has access to source documents -- employment records, company filings, personnel files -- so that session can author cards from them. Everything that session needs is here: the grammar (section 3), the value rules (section 4), and a snapshot of all 79 Index variables (section 5).

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

Each token must be a number and a real Index id (1 to 79). The manifest is **cross-checked both ways** against the field lines: every id in `Inputs` must have at least one matching field line, and every field line's id must appear in `Inputs`. The same id can fire on multiple entries -- list it once. The manifest is the card's own checksum.

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

## 5 - The 79-variable Index

The Index is three sheets: **Company Facts** (#1-#46), **Personal Info** (#47-#66), **Story** (#67-#79). Every variable has a globally unique #id.

### Section names -- exact strings for the headers

**Company Facts**

- `Disclosure` -- #1
- `C1 Identity` -- #2-#8
- `C1 Ownership & Industry` -- #9-#14
- `C1 Scale` -- #15-#31
- `C1 Offering & Character` -- #32-#36
- `C3` -- #37-#41  *(repeats)*
- `C3 Industry Memberships` -- #42-#46  *(repeats)*

**Personal Info**

- `P1 Overview` -- #47-#53
- `P1 Roles` -- #54-#62  *(repeats)*
- `P2 References` -- #63-#66  *(repeats)*

**Story**

- `S1 People` -- #67-#71  *(repeats)*
- `S2 Arc` -- #72-#76  *(repeats)*
- `S3 Operating Model` -- #77-#79  *(repeats)*

*Sections marked "(repeats)" hold several entries per job -- multiple roles, certifications, or people. Use `entry: N` lines (section 3.5) to set them in a card.*

### Variable tiers

Each variable carries a **tier** — 1, 2, or 3 — that says how central it is to the system as a whole:

- **Tier 1 — super tight (7 vars).** The minimum to identify a job at all. Almost every formula reads these (disclosure, legal_name, primary_industry, title, start, end, tenure).
- **Tier 2 — large; effort-worthy (19 vars).** The working substrate. Filling these opens up the bulk of formulas — scale, sector, ownership, products, mission, role-level fields.
- **Tier 3 — varying / optional (53 vars).** Niche, situational, or narrative-deep. Filling them unlocks specialized formulas — market_cap, certifications, references.

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

### Company Facts -- #1 through #46

| # | Tier | Track | Section | Field key | Type | Derived | Accepts | What it means |
|--:|:-:|:-:|---|---|---|---|---|---|
| 1 | T1 | — | Disclosure | `disclosure` | select | — | one of: Publicly traded / Privately held | Whether the company is publicly traded or privately held — this decides whether a third-party-verifiable public record of the company exists. |
| 2 | T1 | — | C1 Identity | `legal_name` | text | — | free text | The company's full registered legal name, exactly as it appears on incorporation records. |
| 3 | T2 | — | C1 Identity | `headquarters` | text | — | free text | The city and country of the company's primary headquarters. |
| 4 | T3 | — | C1 Identity | `legal_entity_type` | select | — | one of: LLC / C-Corporation / S-Corporation / Sole Proprietorship / Partnership / Nonprofit / Cooperative / Other | The legal form the company is incorporated as — LLC, C-Corp, S-Corp, Inc, plc — which tells you what kind of official record exists. |
| 5 | T3 | — | C1 Identity | `date_of_incorporation` | date | — | a date, YYYY-MM-DD | The date the company was legally formed. |
| 6 | T3 | — | C1 Identity | `jurisdiction` | text | — | free text | The state or country whose laws the company is incorporated under. |
| 7 | T3 | — | C1 Identity | `website` | url | — | a URL | The company's primary public website address. |
| 8 | T3 | — | C1 Identity | `ticker` | text | — | free text | The stock-exchange symbol the company trades under, if it is publicly listed. |
| 9 | T3 | — | C1 Ownership & Industry | `founders` | text | — | free text | The person or people who originally started the company. |
| 10 | T1 | — | C1 Ownership & Industry | `primary_industry` | text | — | free text | The broad industry the company operates in, such as healthcare, finance, or manufacturing. |
| 11 | T2 | — | C1 Ownership & Industry | `primary_sector` | text | — | free text | The narrower sector within that industry that best describes the company's work. |
| 12 | T2 | — | C1 Ownership & Industry | `ownership` | select | — | one of: Founder-owned / Family-owned / Private-equity-backed / Venture-backed / Employee-owned / Publicly held / Other | How the company is owned — founder-owned, family-owned, private-equity-backed, employee-owned, or publicly held. |
| 13 | T3 | — | C1 Ownership & Industry | `parent_company` | text | — | free text | The larger company that owns this one, if it is a subsidiary. |
| 14 | T3 | — | C1 Ownership & Industry | `subsidiaries` | text | — | free text | Any companies this one owns or controls. |
| 15 | T3 | — | C1 Scale | `locations_count` | number | — | a number | The number of physical sites the company operates. |
| 16 | T3 | — | C1 Scale | `facility_types` | text | — | free text | The kinds of physical sites the company runs — offices, plants, warehouses, retail stores, clinics. |
| 17 | T2 | — | C1 Scale | `geographic_reach` | select | — | one of: Local / Regional / National / International | How far the company's operations extend — local, regional, national, or international. |
| 18 | T3 | — | C1 Scale | `main_markets` | text | — | free text | The geographic markets or customer regions the company primarily serves. |
| 19 | T2 | — | C1 Scale | `total_employee_headcount` | number | — | a number | The total number of people the company employs. |
| 20 | T2 | — | C1 Scale | `revenue` | text | — | free text | The company's annual revenue figure, or N/A when it is not known. |
| 21 | T3 | — | C1 Scale | `market_cap` | text | — | free text | The total market value of the company's shares, if it is publicly traded. |
| 22 | T3 | — | C1 Scale | `margin_or_valuation` | text | — | free text | The company's profit margin, or for a private company its estimated valuation. |
| 23 | T3 | — | C1 Scale | `major_customers` | text | — | free text | The most significant customers or clients the company is known for. |
| 24 | T3 | — | C1 Scale | `major_partners` | text | — | free text | The most significant business partners the company works with. |
| 25 | T3 | — | C1 Scale | `major_milestones` | text | — | free text | Notable events in the company's history — funding rounds, launches, awards, anniversaries. |
| 26 | T3 | — | C1 Scale | `acquisitions` | text | — | free text | Companies this one has bought. |
| 27 | T3 | — | C1 Scale | `leadership_changes` | text | — | free text | Significant changes in the company's senior leadership during the period that matters. |
| 28 | T3 | — | C1 Scale | `restructures` | text | — | free text | Reorganizations of the company — department mergers, layoffs, or structural overhauls. |
| 29 | T3 | — | C1 Scale | `expansions` | text | — | free text | New sites, markets, or product lines the company added. |
| 30 | T3 | — | C1 Scale | `closures` | text | — | free text | Sites, divisions, or product lines the company shut down. |
| 31 | T3 | — | C1 Scale | `major_product_or_service_changes` | text | — | free text | Significant changes to what the company sells, or to the tools and platforms it runs on — including ERP or system migrations. |
| 32 | T2 | — | C1 Offering & Character | `products_services` | text | — | free text | What the company actually sells — its products and services. |
| 33 | T3 | — | C1 Offering & Character | `market_share` | text | — | free text | The portion of its market the company holds, if it is known. |
| 34 | T3 | — | C1 Offering & Character | `core_values` | text | — | free text | The stated values the company says guide how it operates. |
| 35 | T2 | — | C1 Offering & Character | `mission` | text | — | free text | The company's stated mission — the purpose it says it exists to serve. |
| 36 | T3 | — | C1 Offering & Character | `vision` | text | — | free text | The company's stated vision — the future state it says it is working toward. |
| 37 | T3 | — | C3 | `category` | text | — | free text | The type of certification, accreditation, or audited standard the company holds, such as ISO 9001 or SOC 2. |
| 38 | T3 | — | C3 | `issued_by` | text | — | free text | The body that issued or audits that certification. |
| 39 | T3 | — | C3 | `about` | text | — | free text | What the certification covers — the system, process, or domain it applies to. |
| 40 | T3 | — | C3 | `year` | number | — | a number | The year the certification was awarded or last renewed. |
| 41 | T3 | — | C3 | `notes` | text | — | free text | Any extra detail about the certification worth recording. |
| 42 | T3 | — | C3 Industry Memberships | `category` | text | — | free text | The type of industry body or trade association the company belongs to. |
| 43 | T3 | — | C3 Industry Memberships | `issued_by` | text | — | free text | The organization that grants or governs the membership. |
| 44 | T3 | — | C3 Industry Memberships | `about` | text | — | free text | What the membership covers or signifies. |
| 45 | T3 | — | C3 Industry Memberships | `year` | number | — | a number | The year the membership began or was last active. |
| 46 | T3 | — | C3 Industry Memberships | `notes` | text | — | free text | Any extra detail about the membership worth recording. |

### Personal Info -- #47 through #66

| # | Tier | Track | Section | Field key | Type | Derived | Accepts | What it means |
|--:|:-:|:-:|---|---|---|---|---|---|
| 47 | T1 | — | P1 Overview | `title` | text | — | free text | the user's headline title at this company — the role they are best identified by, usually the most senior position held across the whole tenure. |
| 48 | T1 | — | P1 Overview | `start` | text | — | free text | The date the user first started working at this company, across all roles. |
| 49 | T1 | — | P1 Overview | `end` | text | — | free text | The date the user stopped working at this company, or 'present' if still employed there. |
| 50 | T2 | — | P1 Overview | `promotions` | text | — | free text | The number of promotions or upward title changes the user earned during their time at the company. |
| 51 | T2 | — | P1 Overview | `how_many_roles` | text | `count:P1 Roles` | free text | The total count of distinct roles or positions the user held at the company. |
| 52 | T1 | — | P1 Overview | `tenure` | text | `duration:48,49` | free text | The total length of time the user was employed at the company, spanning every role. |
| 53 | T2 | — | P1 Overview | `what_carries_forward` | text | — | free text | The skills, relationships, or reputation built at this company that stay relevant to the user's later work. |
| 54 | T2 | — | P1 Roles | `title` | text | — | free text | The job title of this role. |
| 55 | T2 | — | P1 Roles | `start` | text | — | free text | The date the user began this role. |
| 56 | T2 | — | P1 Roles | `end` | text | — | free text | The date the user left this role, or moved out of it into their next one, or 'present' if still held. |
| 57 | T2 | — | P1 Roles | `tenure` | text | `duration:55,56` | free text | The length of time the user held this role. |
| 58 | T3 | — | P1 Roles | `employment_type` | text | — | free text | The employment arrangement for this role — full-time, part-time, contract, temporary, or internship. |
| 59 | T3 | — | P1 Roles | `work_mode` | text | — | free text | Where the work was performed — on-site, remote, or hybrid. |
| 60 | T3 | — | P1 Roles | `reported_to` | text | — | free text | The title of the manager or person the user reported to in this role. |
| 61 | T3 | — | P1 Roles | `held_concurrently_with` | text | — | free text | Any other role the user held at the same time as this one, when the positions overlapped. |
| 62 | T2 | — | P1 Roles | `one_line_summary` | text | — | free text | A single sentence capturing what the user did in this role. |
| 63 | T3 | — | P2 References | `reference_name` | text | — | free text | The name of a person who can vouch for the user's work at this company. |
| 64 | T3 | — | P2 References | `reference_relationship` | text | — | free text | How the reference knew the user — as a manager, peer, direct report, client, or similar. |
| 65 | T3 | — | P2 References | `reference_reachability` | text | — | free text | How easily the reference can be contacted, and through what channel. |
| 66 | T3 | — | P2 References | `reference_notes` | text | — | free text | Any extra detail about the reference worth recording — what they can speak to, or cautions about using them. |

### Story -- #67 through #79

| # | Tier | Track | Section | Field key | Type | Derived | Accepts | What it means |
|--:|:-:|:-:|---|---|---|---|---|---|
| 67 | T2 | story | S1 People | `name` | text | — | free text | The name of a person who played a part in the user's story at this company. |
| 68 | T2 | story | S1 People | `role_at_company` | text | — | free text | The job or position that person held at the company. |
| 69 | T2 | story | S1 People | `relationship_to_joe` | text | — | free text | How this person related to the user — boss, mentor, teammate, rival, direct report, or similar. |
| 70 | T3 | story | S1 People | `bio` | text | — | free text | A short background on who this person is. |
| 71 | T3 | story | S1 People | `voice` | text | — | free text | How this person speaks and comes across — their tone, manner, and characteristic way of communicating. |
| 72 | T3 | story | S2 Arc | `name` | text | — | free text | A short label for this chapter or phase of the user's story at the company. |
| 73 | T3 | story | S2 Arc | `dates` | text | — | free text | The span of time this chapter of the story covers. |
| 74 | T3 | story | S2 Arc | `role_in_arc` | text | — | free text | What this chapter contributes to the overall story — setup, turning point, climax, or resolution. |
| 75 | T3 | story | S2 Arc | `external` | text | — | free text | What visibly happened in this chapter — the events, projects, and outcomes others could observe. |
| 76 | T3 | story | S2 Arc | `internal` | text | — | free text | What the user was thinking or feeling during this chapter — the inner experience behind the visible events. |
| 77 | T3 | story | S3 Operating Model | `name` | text | — | free text | The name of a way of working, principle, or habit the user relied on at this company. |
| 78 | T3 | story | S3 Operating Model | `one_line` | text | — | free text | A single sentence describing what this operating principle is. |
| 79 | T3 | story | S3 Operating Model | `emerged_in` | text | — | free text | When or where this way of working first took shape. |

## 6 - Worked examples

Each card below is valid -- checked against the live parser.

**A. An add card** -- nine Company Facts fields across four sections:

```
card: 1.1
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
total_employee_headcount: 240
```

**B. A subtract card** -- clears two fields; intent `2`, values omitted:

```
card: 1.2
Inputs: 8, 15

C1 Identity
ticker:

C1 Scale
locations_count:
```

**C. A batch** -- two cards in one paste, an add then a subtract:

```
card: 1.1
Inputs: 10, 11

C1 Ownership & Industry
primary_industry: Manufacturing
primary_sector: Industrial tooling

card: 1.2
Inputs: 33

C1 Offering & Character
market_share:
```

**D. A multi-entry add card** -- two role entries set in one paste, the kind a Claude Code session writes when a source document describes a multi-role tenure:

```
card: 1.1
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
employment_type: Full-time
```

## 7 - What the parser rejects

Each becomes a line-numbered error; the card carrying it is skipped on Apply.

- a `card:` code that is not `<number>.<number>`
- an intent digit other than `1` or `2`
- any line before the first `card:` line
- a card with no `Inputs:` line, or with two of them
- an `Inputs` token that is not a number, or not a real Index id (1 to 79)
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
