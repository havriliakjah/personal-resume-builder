# Feature Design — Story Track + Visual Vocabulary

**Status: SHIPPED** — 2026-05-27 (R8.O–U)
**Owner:** Synthesis Workbench
**Companion docs:** `01_System_Principles.md` §7 §8

---

## 1. What it does

Two structural shifts that landed together because they reinforce each other:

**Story Track.** The 13 Story variables (`#67–79`, the S1 People / S2 Arc / S3 Operating Model sections) were lifted out of the depth-tier system (T1/T2/T3) and given their own picker option. Story is no longer a tier — it's a parallel **track**, the second classification rail on a variable row alongside `tier`.

**Visual Vocabulary.** Every unique repeating section now carries its own color. The same section keeps the same color across every tier filter. Color is structural identity — a Roles stack is teal whether you're viewing it from T2 or T3, and the eye can tell Roles from References without reading a single label.

The tab bar at the top of the job page is gone. The tier picker (inside the only remaining "sheet," By Tier) is the entire navigation.

---

## 2. Why it was needed

**Story Track.** Story variables sat awkwardly in T2/T3 mixed with niche company facts. Reading T3 you saw "industry memberships, references, story arc" jumbled together. The user wanted *"stories to really mean something… takes effort to add but so worth it with formulas"* — engagement, not depth. Promoting Story to T1 would have ballooned T1 from 7 → 20 fields and broken its "super-tight anchors" meaning. The right answer was a second rail.

**Visual Vocabulary.** When all repeating stacks looked the same color (the default amber from R8.N), the user lost the ability to tell Roles from References at a glance — they're both teal PI sections; their schema names ("P1 Roles" / "P2 References") were small and faint; the user asked "why 2 roles in tier 3 but 1 role in tier 2 — that cannot happen!!" — they were counting the *stacks* and conflating Roles with References. The fix: color each section distinctly, and bold the section title.

---

## 3. The data model — Track

### 3.1 Schema

A new column on `p1_variables`:

```sql
ALTER TABLE p1_variables ADD COLUMN track TEXT;
```

`NULL` means the variable lives in the depth-tier system. A non-NULL track value routes it to its own picker option.

Added via `_add_column_if_missing`.

### 3.2 Seed (SSOT)

`build_synthesis_db.VARIABLE_TRACKS`:

```python
VARIABLE_TRACKS = [
    # Story track — all 13 S1/S2/S3 vars
    (67, 'story'), (68, 'story'), (69, 'story'), (70, 'story'), (71, 'story'),
    (72, 'story'), (73, 'story'), (74, 'story'), (75, 'story'), (76, 'story'),
    (77, 'story'), (78, 'story'), (79, 'story'),
]
```

Same idempotent pattern as `VARIABLE_TIERS` / `VARIABLE_DERIVATIONS`. Validator (`_validate_tracks`) checks that the only verb is `story` (extensible: a new track is one line in `known_tracks`).

### 3.3 What tier survives for tracked variables

Tracked variables keep their schema `tier` value (mostly T3, with the 3 S1 People anchor vars at T2). That `tier` is no longer used for display — the workbench filters tracked vars out of T1/T2/T3 picker options — but it's preserved on the row in case a future formula or query wants to know "what's the underlying depth tier of this story var."

---

## 4. The contract — Track

### 4.1 Backend

`data.get_variables()` returns `track` on every row. `SCHEMA_EXPECTATIONS` includes the new column so `verify_schema` catches a forgotten migration.

The current implementation **counts Story variables toward total/assessed/pending** like any other variable — so a job is "ready" only when story content is also filled. This is the simplest behavior and matches the user's "stories should mean something."

**An engagement-active variant is teed up but not shipped:** a future change can make Story vars count toward readiness *only when* any story field has been filled, so a no-stories job can still be "ready" but a story-rich job is held to the higher bar. The data shape supports it; the math is straightforward; the user just hasn't asked for it yet.

### 4.2 Frontend

`buildSheets` excludes story-tracked vars from the T1/T2/T3 picker options:

```js
const matches = vars.filter(v => v.tier === t && v.track !== 'story').sort(...);
```

And adds a 4th picker option (`'Stories'`) containing the 13 story vars:

```js
const storyVars = vars.filter(v => v.track === 'story').sort((a, b) => a.id - b.id);
if(storyVars.length){
  out['By Tier'].push({tier: 'Stories', vars: storyVars});
}
```

`renderStoriesSection` (a new render branch alongside `renderTierSection`) groups the 13 vars by their home section (S1 People / S2 Arc / S3 Operating Model) and renders each as a `linked-stack story-stack` — entry-card stack with +Add another buttons.

### 4.3 No tabs

`VISIBLE_TABS = []`. The `.tabs:empty` CSS rule hides the tab strip. Default `active = 'By Tier'`. The page goes straight from intake panel → picker → body.

---

## 5. Visual vocabulary

### 5.1 The principle

Each unique repeating section has its own distinct color. The SAME section keeps the SAME color across every tier filter. CSS targets `[data-home-section="<name>"]` so the linked-stack wrapper picks up the right palette regardless of which picker option contains it.

Two stacks of the same color = the same section. Different colors = different sections. The visual vocabulary makes this readable without reading any text.

### 5.2 The palette

| Section | Color | Family |
|---|---|---|
| Roles | teal-green (`--pi`) | PI |
| References | warm amber-gold | PI |
| Certifications | bright blue (`--cf`) | CF |
| Industry Memberships | indigo / slate | CF |
| People | violet (`--st`) | Story |
| Story Arc | blue-violet (indigo) | Story |
| Operating Model | magenta | Story |

The "family" column matters: PI sections all sit in the green / amber-warm-PI neighborhood; CF sections all sit in the blue / indigo-cool neighborhood; Story sections all sit in the violet / magenta neighborhood. Within a family, the hues are pushed apart enough to distinguish sections at a glance.

### 5.3 The CSS shape

A linked-stack carries two layers of identity:

```html
<div class="linked-stack from-pi" data-home-section="P1 Roles">…</div>
```

`from-pi` is the family fallback (used if no per-section rule exists yet). `data-home-section` is the exact-section identity, which CSS targets to override the family default with the section's own palette. Adding a new repeating section needs zero CSS (it'll inherit the family color); it's worth adding section-specific CSS once you want it to read distinctly.

### 5.4 Schema-prefix removal

The schema uses `"P1 Roles"`, `"P2 References"`, `"C3 Certifications"`, etc. as canonical taxonomy keys (intake cards key on them, the DB stores them, build_synthesis_db.VARIABLES lists them). The workbench now displays them stripped:

| Canonical | Display |
|---|---|
| P1 Roles | **Roles** |
| P2 References | **References** |
| C3 Certifications | **Certifications** |
| C3 Industry Memberships | **Industry Memberships** |
| S1 People | **People** |
| S2 Arc | **Story Arc** |
| S3 Operating Model | **Operating Model** |

`SECTION_DISPLAY` in `job.html`. The `.section-title` span renders the clean name in bold, with the metadata (count, fields-per-entry) following in a smaller weight.

---

## 6. What follows for free

Once **color is structural identity**, downstream UI inherits it:

- **Formula UI** can show its inputs as colored chips — a "narrative cover letter" formula visibly pulls from violet (People), magenta (Operating Model), and teal (Roles) without reading a single field name.
- **Profile per-job tile** can show a row of small colored dots indicating which sections that job has content in. "This job is rich in People + Roles, light on Story Arc" at a glance.
- **Intake card previews** can highlight which sections a card writes into with the same color vocabulary.

These aren't built. They're teed up by this round.

---

## 7. Test coverage

`Frontend/test_api.py` adds 4 track-specific assertions:

- Every variable carries `track` field.
- Exactly 13 variables on the `story` track.
- Story track ids are exactly `67..79`.
- No unexpected tracks exist (only `story` and `None`).

The full suite is at 93 passing assertions at ship time.

---

## 8. Operating notes

- A new track (e.g., `"credentials"`, `"references"`) is one line in `VARIABLE_TRACKS` + one entry in `known_tracks` in `_validate_tracks` + a render branch in `renderSheet`. Same shape of work as adding a new tier picker option.
- A new repeating section needs (a) its variables in `VARIABLES`, (b) `repeats: 1` set, (c) an `ENTRY_NOUN` mapping, (d) a `SECTION_DISPLAY` mapping for the clean label, and optionally (e) a section-specific CSS color block. (a)–(d) are required; (e) is polish.
- Color is one CSS edit per section. To retune the palette, hit the `.linked-stack[data-home-section="…"]` blocks in `job.html` — each section has a small ~6-rule group with `background`, `border-color`, `border-left-color`, `section-count color`, `entry-card`, `entry-add`. Keep the family neighborhood when tuning so it still reads as PI / CF / Story.

---

## 9. Tee-ups for R9 and beyond

**Tier-aware readiness.** "Tier 1 ready" as an intermediate green status before full ready. Formulas declare `min_tier` and `requires_stories`. The schema (tier + track on every variable) supports this; the readiness object can grow into `{tier_level: 't1_ready', stories: 'active'|'inactive', formulas_unlocked: [...]}`.

**Engagement-active stories.** Switch readiness to engagement-aware so a no-stories job can still be "ready" but a story-rich job is held to the story-complete bar. ~30 lines, server + JS mirror.

**Per-job visual rollup on profile.** A row of small colored dots per job tile showing which sections have any content. The color vocabulary is already in place; the render is the one piece of new work.
