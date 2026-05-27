# Feature Design — Intake Code

## 0. What this is

A design for the **Intake Code** feature of the Synthesis Workbench: a small,
deterministic text language for building lenses and clusters in bulk. It sits
beside `System Design - the Synthesis app.md` (the whole-app design) and the
`Frontend Plan` (the phase roadmap) — this document covers one feature only.

Built 2026-05-24. Decided by the user directly: the engine is **not AI** — it is a
plain text parser. An AI can *author* an intake card in a separate chat,
because the grammar is fixed and documented, but the app itself never connects
to a model. In the user's words: "I do not need the AI directly connecting to it."

> Rewritten 2026-05-24 to match the **card grammar** as shipped. An earlier
> draft of this document described a keyword grammar (`LENS <name>` /
> `CLUSTER <name>` block headers); that draft is superseded — the card system
> below is what the code actually does.

---

## 1. Requirements

**What it does.** A button on Page 2 opens a modal. The user pastes a *card* —
a text block — and presses Preview. A parser turns it into a list of lenses or
clusters, validates every field, and shows a checklist: clean entries
pre-ticked, problems flagged with their line numbers. The user approves the
entries to keep and presses Create; each is written to the database and
stamped with a traceability code. It is the manual builder's work — pick
variables, set the lens text and output kinds, name a cluster, save — driven
by text instead of clicks, and able to mass-produce many at once.

**How it behaves.** Deterministic: the same card always produces the same
result. No AI, no network, no API key, no cost. Nothing is written until the
user has seen the preview and approved it. A malformed card never crashes — a
bad line becomes a flagged error, not an exception.

**What it touches.** The feature is mostly frontend — the parser, the preview,
and the create flow all live in `workbench.html` — but it is *not* purely
frontend: it adds an `intake_code` column to `p2_formulas` and `p2_clusters`
and threads that field through `data.py` and the `POST` endpoints, so every
intake-built object carries its provenance. (An earlier draft claimed "no
schema change"; the traceability requirement made a small, additive schema
change the honest choice.)

---

## 2. The grammar — cards

An intake **card** is a text block where **every line is `key: value`** — one
rule, no exceptions. A card opens with a `card:` code, then a list of entries;
each entry opens with `name:`, and the lines under it set its fields.

```
card: 1.0

name: Operational scale
  inputs: 15, 16, 17, 19
  clusters: 2
  outputs: scale-context, capability
  section: Company Facts
  text: How large and operationally complex the company was.

name: Market position
  inputs: 11, 18, 33
  outputs: differentiator
  text: Where the company stood in its market.
```

**The card code — `card: F.0`.** Digit one is the *family*: `1` = a formula
card (mass-produces lenses), `2` = a cluster card (mass-produces clusters).
The second digit is reserved. One card has one code and it governs every
entry — a formula card holds only formulas. Families `3` and `4` (edit,
delete) are reserved for later.

**Formula fields** (family `1`) — `inputs` (Index numbers), `clusters`
(cluster #ids — see below), `outputs` (output-kind *names*), `section`,
`status` (Active / Inactive — optional, defaults to Active), `text`.
**Cluster field** (family `2`) — `vars` (Index numbers).

**Clusters as a shortcut.** A formula may list `clusters:` alongside
`inputs:`. Each referenced cluster's variables are folded into the formula's
input set at create time — a snapshot, no live link, matching the manual
"paste cluster" behaviour. It is purely an efficiency: `clusters: 2` saves
retyping the numbers cluster #2 already bundles. Whether a formula uses
clusters is a per-*entry* choice, not a property of the card.

**Robustness.** Indentation is cosmetic — the parser trims every line and
identifies it by its `key:`, so a paste with mangled indentation still parses.
Key and value split on the *first* colon, so a value may itself contain
colons. Keys, the card keyword, status, and output-kind names are all
case-insensitive. Blank lines and `#` comments are ignored. Any line with no
colon — the signature of a value that spilled across a line break — is caught
and flagged by line number, never silently mis-parsed.

---

## 3. How it runs — parse, preview, create

```
   the textarea (one card)
        |  Preview
   parseIntake()  — the deterministic engine; returns
        |           { cardCode, family, items[], cardErrors[] }
   the preview checklist  — each entry with its 1.0.N code; problems flagged
        |  Create approved
   apiCreateLens() / apiCreateCluster()  — POST each ticked entry,
        |                                  stamped with its intake_code
   synthesis.db
```

`parseIntake()` is the whole engine, no dependencies. It reads the card line
by line: the `card:` line sets the family, each `name:` opens a new entry, and
field lines attach to the current entry. Every field is validated as it is
read — a variable number not in the live Index, an unknown output-kind name, a
missing cluster, a bad status, an unknown field, a colon-less line — each
becomes a line-numbered entry in `errors[]`. The parser never throws.

Variables are validated against the **live Index** (whatever `p1_variables`
currently holds), not a hard-coded count — add variables to the database later
and intake accepts them with no code change.

The preview lists every entry with the traceability code it would receive
(`1.0.1`, `1.0.2`, …). A clean entry gets a ticked checkbox; an entry with
errors — or any entry, when the card itself is malformed — is flagged and
cannot be ticked. On Create, each ticked entry is POSTed — a lens to
`POST /api/lenses`, a cluster to `POST /api/clusters` — carrying its
`intake_code`. A created entry locks with a check so it cannot be made twice
in the same session.

**Traceability codes.** Each created object is stamped with
`<card code>.<entry number>` — `1.0.1`, `1.0.2` — assigned by the engine, not
the author (identity is the engine's job). The code is stored in the
`intake_code` column; a hand-built lens or cluster leaves it `NULL`. The entry
number restarts per card; the database `id` stays the hard unique key, while
`intake_code` is the readable provenance tag.

Everything lives in `Frontend/workbench.html` — section "5a · INTAKE CODE" of
the script, plus a modal and a header button — with the small `intake_code`
additions in `build_synthesis_db.py`, `data.py`, and `server.py`.

---

## 4. Trade-offs

**One uniform rule — every line is `key: value`.** Including `card:` and
`name:`; no exceptions. It makes indentation cosmetic and turns any spillage
into a caught, located error rather than a silent corruption — the robustness
is worth the slight verbosity.

**One code per card; the family is fixed.** A formula card cannot also create
clusters — that needs its own card. But cluster-use is *not* in the code:
within a formula card, entries mix cluster-sourced and direct-input formulas
freely. The code declares the family; each entry declares how it sources its
variables.

**Single-line `text` in v1.** A lens's `text` is one line (it may be long).
Multi-line paragraphs were left out to keep the parser simple; wording can be
refined in the builder after import.

**Each entry POSTs independently.** There is no all-or-nothing batch. If one
entry fails server-side (rare — the preview validates first), the others still
succeed and the failure is reported; created entries lock so a retry cannot
duplicate them.

**No dedup against the existing warehouse.** Running the same card twice
creates fresh copies. The preview/approve step is the guard — the user sees
exactly what is about to be created.

---

## 5. Future extensions

- **Edit and delete cards** — families `3` and `4`, giving the intake code the
  same full reach over existing lenses and clusters that the manual UI has.
- **Multi-line lens text.**
- **An all-or-nothing batch mode** — create everything in a card, or nothing.
- **Upload-batch provenance** — an `intake_batches` table so every card run is
  a group that can be recalled or bulk-undone; the traceability codes already
  carry the information such grouping would key on.
- **A "copy as intake code" action** — turning an existing lens back into card
  text, making the format round-trippable like the YAML export.

(An earlier draft listed "let a formula reference a cluster" as a future item;
that shipped as the `clusters:` field — see §2.)

---

## 6. Verification

The card parser was tested against 26 cases — valid cards, the card code and
families, mixed cluster/direct formulas, cluster expansion, output-kind name
mapping, and every error path: out-of-range variables, missing clusters,
unknown output kinds and fields, a missing `card:` line, a bad family digit, a
colon-less spilled line, a field before any `name:`, an empty entry name, and
case-insensitivity — all passing. The full intake section passed a syntax
check, and the `intake_code` round-trip through `data.py` was verified
separately. `test_api.py` covers the `POST` endpoints the feature depends on.
