#!/usr/bin/env python3
"""
build_synthesis_db.py  —  builds synthesis.db, the Synthesis prototype database.

Lives in: Synthesis Routing/DB/   (alongside synthesis.db)
Safe to re-run: it creates only missing tables and seeds only empty
ones, so it never destroys user data (the lenses saved from the app).

TABLE NAMING — page-prefix scheme (2026-05-22):
  Tables are prefixed by the part of the machine they belong to, so a
  viewer's flat A-Z list reorganizes itself into the 3-page machine.
    jobs        the spine — every page hangs off it (bare on purpose)
    p1_*        page 1 — variables
    p2_*        page 2 — formulas
    p3_*        page 3 — synthetic output
    _guide      in-database legend; the leading _ sorts it to the top

Seeds: the 79 Index variables, the 9 output kinds, one control job "BASE"
(carrying the full 79-variable skeleton, all blank), and the _guide rows.
All other tables are created empty and ready.
"""
import sqlite3, os

# synthesis.db sits beside this script. Deriving the path from the script's
# own location keeps the build reproducible no matter where it is run from.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthesis.db")

SCHEMA = """
-- ============================================================
--  SYNTHESIS PROTOTYPE — schema (10 tables + _guide)
--  jobs = spine . p1_* = variables . p2_* = formulas . p3_* = output
-- ============================================================

-- the spine -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT    NOT NULL UNIQUE,
    slot     INTEGER,                  -- Work Experience position on Page 2; NULL = unplaced (the BASE control job)
    ready_at TEXT                      -- timestamp the job most recently entered 'ready' status (set by data.save_job; NULL while in_progress)
);

-- page 1 : variables ----------------------------------------------------
CREATE TABLE IF NOT EXISTS p1_variables (
    id         INTEGER PRIMARY KEY,         -- 1-79 : the Index number
    field      TEXT    NOT NULL,
    file       TEXT    NOT NULL,
    section    TEXT    NOT NULL,
    repeats    INTEGER NOT NULL DEFAULT 0,  -- 1 = a "per entry" variable
    definition TEXT    NOT NULL DEFAULT '', -- plain-English meaning of the field
    input_type TEXT    NOT NULL DEFAULT 'text', -- which control fills it: text|select|date|number|url
    options    TEXT                         -- '|'-joined choice list; only for input_type='select'
);

CREATE TABLE IF NOT EXISTS p1_variable_values (
    job_id      INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    variable_id INTEGER NOT NULL REFERENCES p1_variables(id),
    entry_no    INTEGER NOT NULL DEFAULT 1,
    value       TEXT,
    PRIMARY KEY (job_id, variable_id, entry_no)
);

-- page 2 : formulas -----------------------------------------------------
CREATE TABLE IF NOT EXISTS p2_formulas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Inactive')),
    lens        TEXT NOT NULL,
    section     TEXT NOT NULL DEFAULT '',
    intake_code TEXT          -- Intake Code provenance (e.g. "1.0.3"); NULL if built by hand
);

CREATE TABLE IF NOT EXISTS p2_output_kinds (
    id          INTEGER PRIMARY KEY,         -- 1-9
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS p2_formula_inputs (            -- formula <-> variable
    formula_id  INTEGER NOT NULL REFERENCES p2_formulas(id) ON DELETE CASCADE,
    variable_id INTEGER NOT NULL REFERENCES p1_variables(id),
    PRIMARY KEY (formula_id, variable_id)
);

CREATE TABLE IF NOT EXISTS p2_formula_output_kinds (      -- formula <-> output_kind
    formula_id     INTEGER NOT NULL REFERENCES p2_formulas(id) ON DELETE CASCADE,
    output_kind_id INTEGER NOT NULL REFERENCES p2_output_kinds(id),
    PRIMARY KEY (formula_id, output_kind_id)
);

-- page 2 : clusters -- saved bundles of Index variables ----------------
-- A cluster is a named preset bundle of page-1 variables. It mirrors a
-- formula's shape exactly: one row in p2_clusters, plus one wiring row
-- per variable in p2_cluster_variables. Clusters used to live only in
-- the browser's localStorage; moving them here means they survive a
-- reinstall and a move to another machine, the same way lenses do.
CREATE TABLE IF NOT EXISTS p2_clusters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    intake_code TEXT          -- Intake Code provenance (e.g. "2.0.1"); NULL if built by hand
);

CREATE TABLE IF NOT EXISTS p2_cluster_variables (         -- cluster <-> variable
    cluster_id  INTEGER NOT NULL REFERENCES p2_clusters(id) ON DELETE CASCADE,
    variable_id INTEGER NOT NULL REFERENCES p1_variables(id),
    PRIMARY KEY (cluster_id, variable_id)
);

-- page 3 : synthetic output --------------------------------------------
CREATE TABLE IF NOT EXISTS p3_synthetic_outputs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    formula_id INTEGER NOT NULL REFERENCES p2_formulas(id),
    point_text TEXT,
    strength   TEXT CHECK (strength IN ('full','partial','none')),
    bolstered  INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- _guide : in-database legend (leading _ sorts it to the top) ----------
CREATE TABLE IF NOT EXISTS _guide (
    table_name TEXT PRIMARY KEY,
    page       TEXT NOT NULL,
    purpose    TEXT NOT NULL
);
"""

# the 79 Index variables : (id, field, file, section, repeats, definition)
#   definition = plain-English meaning of the field, shown to the user.
#   repeats = 1 marks a variable that holds several entries per job (a role,
#   a certification, a story person); the count lives in p1_variable_values
#   .entry_no, never in this list. Company Facts 1-46, Personal Info 47-66,
#   Story 67-79.
VARIABLES = [
 (1,'disclosure','Company Facts','Disclosure',0,
   'Whether the company is publicly traded or privately held — this decides whether a third-party-verifiable public record of the company exists.'),
 (2,'legal_name','Company Facts','C1 Identity',0,
   "The company's full registered legal name, exactly as it appears on incorporation records."),
 (3,'headquarters','Company Facts','C1 Identity',0,
   "The city and country of the company's primary headquarters."),
 (4,'legal_entity_type','Company Facts','C1 Identity',0,
   'The legal form the company is incorporated as — LLC, C-Corp, S-Corp, Inc, plc — which tells you what kind of official record exists.'),
 (5,'date_of_incorporation','Company Facts','C1 Identity',0,
   'The date the company was legally formed.'),
 (6,'jurisdiction','Company Facts','C1 Identity',0,
   'The state or country whose laws the company is incorporated under.'),
 (7,'website','Company Facts','C1 Identity',0,
   "The company's primary public website address."),
 (8,'ticker','Company Facts','C1 Identity',0,
   'The stock-exchange symbol the company trades under, if it is publicly listed.'),
 (9,'founders','Company Facts','C1 Ownership & Industry',0,
   'The person or people who originally started the company.'),
 (10,'primary_industry','Company Facts','C1 Ownership & Industry',0,
   'The broad industry the company operates in, such as healthcare, finance, or manufacturing.'),
 (11,'primary_sector','Company Facts','C1 Ownership & Industry',0,
   "The narrower sector within that industry that best describes the company's work."),
 (12,'ownership','Company Facts','C1 Ownership & Industry',0,
   'How the company is owned — founder-owned, family-owned, private-equity-backed, employee-owned, or publicly held.'),
 (13,'parent_company','Company Facts','C1 Ownership & Industry',0,
   'The larger company that owns this one, if it is a subsidiary.'),
 (14,'subsidiaries','Company Facts','C1 Ownership & Industry',0,
   'Any companies this one owns or controls.'),
 (15,'locations_count','Company Facts','C1 Scale',0,
   'The number of physical sites the company operates.'),
 (16,'facility_types','Company Facts','C1 Scale',0,
   'The kinds of physical sites the company runs — offices, plants, warehouses, retail stores, clinics.'),
 (17,'geographic_reach','Company Facts','C1 Scale',0,
   "How far the company's operations extend — local, regional, national, or international."),
 (18,'main_markets','Company Facts','C1 Scale',0,
   'The geographic markets or customer regions the company primarily serves.'),
 (19,'total_employee_headcount','Company Facts','C1 Scale',0,
   'The total number of people the company employs.'),
 (20,'revenue','Company Facts','C1 Scale',0,
   "The company's annual revenue figure, or N/A when it is not known."),
 (21,'market_cap','Company Facts','C1 Scale',0,
   "The total market value of the company's shares, if it is publicly traded."),
 (22,'margin_or_valuation','Company Facts','C1 Scale',0,
   "The company's profit margin, or for a private company its estimated valuation."),
 (23,'major_customers','Company Facts','C1 Scale',0,
   'The most significant customers or clients the company is known for.'),
 (24,'major_partners','Company Facts','C1 Scale',0,
   'The most significant business partners the company works with.'),
 (25,'major_milestones','Company Facts','C1 Scale',0,
   "Notable events in the company's history — funding rounds, launches, awards, anniversaries."),
 (26,'acquisitions','Company Facts','C1 Scale',0,
   'Companies this one has bought.'),
 (27,'leadership_changes','Company Facts','C1 Scale',0,
   "Significant changes in the company's senior leadership during the period that matters."),
 (28,'restructures','Company Facts','C1 Scale',0,
   'Reorganizations of the company — department mergers, layoffs, or structural overhauls.'),
 (29,'expansions','Company Facts','C1 Scale',0,
   'New sites, markets, or product lines the company added.'),
 (30,'closures','Company Facts','C1 Scale',0,
   'Sites, divisions, or product lines the company shut down.'),
 (31,'major_product_or_service_changes','Company Facts','C1 Scale',0,
   'Significant changes to what the company sells, or to the tools and platforms it runs on — including ERP or system migrations.'),
 (32,'products_services','Company Facts','C1 Offering & Character',0,
   'What the company actually sells — its products and services.'),
 (33,'market_share','Company Facts','C1 Offering & Character',0,
   'The portion of its market the company holds, if it is known.'),
 (34,'core_values','Company Facts','C1 Offering & Character',0,
   'The stated values the company says guide how it operates.'),
 (35,'mission','Company Facts','C1 Offering & Character',0,
   "The company's stated mission — the purpose it says it exists to serve."),
 (36,'vision','Company Facts','C1 Offering & Character',0,
   "The company's stated vision — the future state it says it is working toward."),
 (37,'category','Company Facts','C3',1,
   'The type of certification, accreditation, or audited standard the company holds, such as ISO 9001 or SOC 2.'),
 (38,'issued_by','Company Facts','C3',1,
   'The body that issued or audits that certification.'),
 (39,'about','Company Facts','C3',1,
   'What the certification covers — the system, process, or domain it applies to.'),
 (40,'year','Company Facts','C3',1,
   'The year the certification was awarded or last renewed.'),
 (41,'notes','Company Facts','C3',1,
   'Any extra detail about the certification worth recording.'),
 (42,'category','Company Facts','C3 Industry Memberships',1,
   'The type of industry body or trade association the company belongs to.'),
 (43,'issued_by','Company Facts','C3 Industry Memberships',1,
   'The organization that grants or governs the membership.'),
 (44,'about','Company Facts','C3 Industry Memberships',1,
   'What the membership covers or signifies.'),
 (45,'year','Company Facts','C3 Industry Memberships',1,
   'The year the membership began or was last active.'),
 (46,'notes','Company Facts','C3 Industry Memberships',1,
   'Any extra detail about the membership worth recording.'),
 (47,'title','Personal Info','P1 Overview',0,
   "the user's headline title at this company — the role they are best identified by, usually the most senior position held across the whole tenure."),
 (48,'start','Personal Info','P1 Overview',0,
   'The date the user first started working at this company, across all roles.'),
 (49,'end','Personal Info','P1 Overview',0,
   "The date the user stopped working at this company, or 'present' if still employed there."),
 (50,'promotions','Personal Info','P1 Overview',0,
   'The number of promotions or upward title changes the user earned during their time at the company.'),
 (51,'how_many_roles','Personal Info','P1 Overview',0,
   'The total count of distinct roles or positions the user held at the company.'),
 (52,'tenure','Personal Info','P1 Overview',0,
   'The total length of time the user was employed at the company, spanning every role.'),
 (53,'what_carries_forward','Personal Info','P1 Overview',0,
   "The skills, relationships, or reputation built at this company that stay relevant to the user's later work."),
 (54,'title','Personal Info','P1 Roles',1,
   'The job title of this role.'),
 (55,'start','Personal Info','P1 Roles',1,
   'The date the user began this role.'),
 (56,'end','Personal Info','P1 Roles',1,
   "The date the user left this role, or moved out of it into their next one, or 'present' if still held."),
 (57,'tenure','Personal Info','P1 Roles',1,
   'The length of time the user held this role.'),
 (58,'employment_type','Personal Info','P1 Roles',1,
   'The employment arrangement for this role — full-time, part-time, contract, temporary, or internship.'),
 (59,'work_mode','Personal Info','P1 Roles',1,
   'Where the work was performed — on-site, remote, or hybrid.'),
 (60,'reported_to','Personal Info','P1 Roles',1,
   'The title of the manager or person the user reported to in this role.'),
 (61,'held_concurrently_with','Personal Info','P1 Roles',1,
   'Any other role the user held at the same time as this one, when the positions overlapped.'),
 (62,'one_line_summary','Personal Info','P1 Roles',1,
   'A single sentence capturing what the user did in this role.'),
 (63,'reference_name','Personal Info','P2 References',1,
   "The name of a person who can vouch for the user's work at this company."),
 (64,'reference_relationship','Personal Info','P2 References',1,
   'How the reference knew the user — as a manager, peer, direct report, client, or similar.'),
 (65,'reference_reachability','Personal Info','P2 References',1,
   'How easily the reference can be contacted, and through what channel.'),
 (66,'reference_notes','Personal Info','P2 References',1,
   'Any extra detail about the reference worth recording — what they can speak to, or cautions about using them.'),
 (67,'name','Story','S1 People',1,
   "The name of a person who played a part in the user's story at this company."),
 (68,'role_at_company','Story','S1 People',1,
   'The job or position that person held at the company.'),
 (69,'relationship_to_joe','Story','S1 People',1,
   'How this person related to the user — boss, mentor, teammate, rival, direct report, or similar.'),
 (70,'bio','Story','S1 People',1,
   'A short background on who this person is.'),
 (71,'voice','Story','S1 People',1,
   'How this person speaks and comes across — their tone, manner, and characteristic way of communicating.'),
 (72,'name','Story','S2 Arc',1,
   "A short label for this chapter or phase of the user's story at the company."),
 (73,'dates','Story','S2 Arc',1,
   'The span of time this chapter of the story covers.'),
 (74,'role_in_arc','Story','S2 Arc',1,
   'What this chapter contributes to the overall story — setup, turning point, climax, or resolution.'),
 (75,'external','Story','S2 Arc',1,
   'What visibly happened in this chapter — the events, projects, and outcomes others could observe.'),
 (76,'internal','Story','S2 Arc',1,
   'What the user was thinking or feeling during this chapter — the inner experience behind the visible events.'),
 (77,'name','Story','S3 Operating Model',1,
   'The name of a way of working, principle, or habit the user relied on at this company.'),
 (78,'one_line','Story','S3 Operating Model',1,
   'A single sentence describing what this operating principle is.'),
 (79,'emerged_in','Story','S3 Operating Model',1,
   'When or where this way of working first took shape.'),
]

# derivation metadata — variables whose value is COMPUTED FROM OTHER FIELDS
#   rather than entered by the user. The recipe is a short verb:args string;
#   the server dispatches it to a Python helper in data.py and the frontend
#   mirrors the same math locally so the pill on the form updates the
#   instant another field changes.
#
# Verbs shipped today (data.py owns the contracts):
#   count:<section>             how many entries the repeating section holds
#   duration:<start_vid>,<end_vid>   "Xy Ym" from one date var to another
#                                    ('present', 'current', 'now' on the end
#                                    side means "ongoing as of today")
#
# Adding a new derived variable is one line here + (if the verb is new) one
# helper function in data.py. The pattern mirrors VARIABLE_TYPES and
# VARIABLE_TIERS — schema-as-data, no logic-in-the-rendering-code.
#
# IMPORTANT: a variable in this list is OWNED BY THE SERVER. save_job
# silently drops any incoming value for it; _job_dict (read path) replaces
# whatever sat in the DB with the freshly computed result. The DB column
# still holds whatever was last computed-and-saved, which makes derived
# values queryable for free — but they are never the source of truth.
VARIABLE_DERIVATIONS = [
    (51, 'count:P1 Roles'),       # how_many_roles
    (52, 'duration:48,49'),       # tenure (overview)  = end - start
    (57, 'duration:55,56'),       # tenure (per-role)  = role end - role start
]

# track metadata — a SECOND classification rail, parallel to tier. While
# `tier` (1/2/3) classifies a variable's factual depth, `track` answers a
# different question: does this variable belong to a NAMED ENGAGEMENT
# DIMENSION that should be filled as its own deliberate pass rather than
# mixed into the depth tiers?
#
# Shipped today:
#   "story"   — the 13 S1 People / S2 Arc / S3 Operating Model vars.
#               Story content is high-effort to author and high-value to
#               formulas, so we lift it OUT of the depth tiers and into
#               its own picker option in the workbench. Story vars don't
#               appear in the T1/T2/T3 views any more — they live only
#               under "Stories" in the tier picker.
#
# Variables not listed are NULL (no track) — the default. A track is the
# right home when adding the variable is a meaningful intentional act
# (telling a story, listing a reference, adding a certification) rather
# than just filling a fact about the company. Future tracks might be
# "references", "credentials", etc. — same pattern, one-line additions.
VARIABLE_TRACKS = [
    # Story track — 13 variables, all S1 / S2 / S3 sections.
    (67, 'story'), (68, 'story'), (69, 'story'), (70, 'story'), (71, 'story'),
    (72, 'story'), (73, 'story'), (74, 'story'), (75, 'story'), (76, 'story'),
    (77, 'story'), (78, 'story'), (79, 'story'),
]

# tier metadata — variable priority class, used to gate readiness and to mark
#   which variables matter for which family of formulas.
#     Tier 1 — "super tight": the minimum to identify a job at all. Almost
#              every formula reads these (disclosure, legal_name, industry,
#              title, start, end, tenure).
#     Tier 2 — "large; should put effort into": the working substrate.
#              Filling these opens up the bulk of formulas (scale, sector,
#              ownership, products, mission, role-level fields, key people).
#     Tier 3 — "varying degrees; almost optional": niche, situational, or
#              narrative-deep. Filling them unlocks specialized formulas
#              (market_cap, certifications, references, story arc, etc.).
#
# This list is the single source of truth for variable tier. Variables not
# named here keep the column default (Tier 2). The list is idempotently
# backfilled on every build (see below), so retiering a variable is just an
# edit here plus a re-run.
#
# Distribution: 7 T1 / 19 T2 / 53 T3 across the 79 Index variables.
VARIABLE_TIERS = [
 # ---- Tier 1 — super tight (7) ----
 ( 1, 1),  # disclosure
 ( 2, 1),  # legal_name
 (10, 1),  # primary_industry
 (47, 1),  # title (P1 Overview)
 (48, 1),  # start
 (49, 1),  # end
 (52, 1),  # tenure (overview)

 # ---- Tier 2 — large, effort-worthy (19) ----
 # Company Facts (8)
 ( 3, 2),  # headquarters
 (11, 2),  # primary_sector
 (12, 2),  # ownership
 (17, 2),  # geographic_reach
 (19, 2),  # total_employee_headcount
 (20, 2),  # revenue
 (32, 2),  # products_services
 (35, 2),  # mission
 # Personal Info (10)
 (50, 2),  # promotions
 (51, 2),  # how_many_roles
 (53, 2),  # what_carries_forward
 (54, 2),  # title (P1 Roles, per-role)
 (55, 2),  # start (P1 Roles, per-role)
 (56, 2),  # end (P1 Roles, per-role)
 (57, 2),  # tenure (P1 Roles, per-role)
 (62, 2),  # one_line_summary (per-role)
 # Story (3) — S1 People anchor trio
 (67, 2),  # name (S1 People)
 (68, 2),  # role_at_company (S1 People)
 (69, 2),  # relationship_to_joe (S1 People)

 # ---- Tier 3 — varying / optional (53) ----
 # Company Facts (28)
 ( 4, 3),  # legal_entity_type
 ( 5, 3),  # date_of_incorporation
 ( 6, 3),  # jurisdiction
 ( 7, 3),  # website
 ( 8, 3),  # ticker
 ( 9, 3),  # founders
 (13, 3),  # parent_company
 (14, 3),  # subsidiaries
 (15, 3),  # locations_count
 (16, 3),  # facility_types
 (18, 3),  # main_markets
 (21, 3),  # market_cap
 (22, 3),  # margin_or_valuation
 (23, 3),  # major_customers
 (24, 3),  # major_partners
 (25, 3),  # major_milestones
 (26, 3),  # acquisitions
 (27, 3),  # leadership_changes
 (28, 3),  # restructures
 (29, 3),  # expansions
 (30, 3),  # closures
 (31, 3),  # major_product_or_service_changes
 (33, 3),  # market_share
 (34, 3),  # core_values
 (36, 3),  # vision
 (37, 3),  # category (C3 Certifications)
 (38, 3),  # issued_by (C3 Certifications)
 (39, 3),  # about (C3 Certifications)
 (40, 3),  # year (C3 Certifications)
 (41, 3),  # notes (C3 Certifications)
 (42, 3),  # category (C3 Industry Memberships)
 (43, 3),  # issued_by (C3 Industry Memberships)
 (44, 3),  # about (C3 Industry Memberships)
 (45, 3),  # year (C3 Industry Memberships)
 (46, 3),  # notes (C3 Industry Memberships)
 # Personal Info (8)
 (58, 3),  # employment_type
 (59, 3),  # work_mode
 (60, 3),  # reported_to
 (61, 3),  # held_concurrently_with
 (63, 3),  # reference_name
 (64, 3),  # reference_relationship
 (65, 3),  # reference_reachability
 (66, 3),  # reference_notes
 # Story (12) — S1 deep + S2 + S3
 (70, 3),  # bio (S1 People)
 (71, 3),  # voice (S1 People)
 (72, 3),  # name (S2 Arc)
 (73, 3),  # dates (S2 Arc)
 (74, 3),  # role_in_arc (S2 Arc)
 (75, 3),  # external (S2 Arc)
 (76, 3),  # internal (S2 Arc)
 (77, 3),  # name (S3 Operating Model)
 (78, 3),  # one_line (S3 Operating Model)
 (79, 3),  # emerged_in (S3 Operating Model)
]

# Sanity check the tier list at build time — catches a typo before it lands
# in the database. Every variable must appear exactly once; tiers must be in
# {1,2,3}; counts must match the documented 7/19/53 distribution.
def _validate_tiers():
    seen = {}
    for vid, t in VARIABLE_TIERS:
        if t not in (1, 2, 3):
            raise ValueError("variable %d has invalid tier %r" % (vid, t))
        if vid in seen:
            raise ValueError("variable %d appears twice in VARIABLE_TIERS" % vid)
        seen[vid] = t
    expected = set(v[0] for v in VARIABLES)
    if set(seen) != expected:
        missing = sorted(expected - set(seen))
        extra   = sorted(set(seen) - expected)
        raise ValueError("VARIABLE_TIERS mismatch — missing=%r extra=%r" % (missing, extra))
    counts = {1: 0, 2: 0, 3: 0}
    for t in seen.values():
        counts[t] += 1
    if counts != {1: 7, 2: 19, 3: 53}:
        raise ValueError("VARIABLE_TIERS counts %r != expected {1:7,2:19,3:53}" % counts)
_validate_tiers()


# Mirror the same sanity check for VARIABLE_DERIVATIONS: every entry must
# point at a real variable id and carry a recipe with a known verb prefix.
# Catches a typo before it makes it into the database.
def _validate_derivations():
    valid_ids = {v[0] for v in VARIABLES}
    known_verbs = ('count:', 'duration:')
    seen = set()
    for vid, recipe in VARIABLE_DERIVATIONS:
        if vid not in valid_ids:
            raise ValueError("derivation references missing id %r" % vid)
        if vid in seen:
            raise ValueError("variable %d derived twice" % vid)
        if not any(recipe.startswith(v) for v in known_verbs):
            raise ValueError("derivation %d has unknown verb in %r" % (vid, recipe))
        seen.add(vid)
_validate_derivations()


# Same defensive sanity check for VARIABLE_TRACKS.
def _validate_tracks():
    valid_ids = {v[0] for v in VARIABLES}
    known_tracks = ('story',)
    seen = set()
    for vid, track in VARIABLE_TRACKS:
        if vid not in valid_ids:
            raise ValueError("track references missing id %r" % vid)
        if vid in seen:
            raise ValueError("variable %d tracked twice" % vid)
        if track not in known_tracks:
            raise ValueError("variable %d has unknown track %r" % (vid, track))
        seen.add(vid)
_validate_tracks()


# typed-input metadata — the variables that are NOT plain free text.
#   (id, input_type, options)
#   input_type : 'select' a fixed dropdown . 'date' a calendar (the value is
#                stored ISO YYYY-MM-DD) . 'number' digits only . 'url' a web
#                address . 'text' (the default, not listed here) free text.
#   options    : a '|'-joined choice list — only for 'select'; None otherwise.
#
# This list is the single source of truth for variable typing. The control
# the workbench renders IS the validation: a dropdown cannot emit an off-list
# value, a date picker cannot emit a malformed date — so the saved value
# lands formula-clean. It is backfilled with idempotent UPDATEs every build
# (see below), so retyping a variable is just an edit here plus a re-run.
# Variables not listed stay 'text'. Location fields (3 headquarters,
# 6 jurisdiction) are deliberately left 'text' for now — a location control
# is a later pass.
VARIABLE_TYPES = [
 (1,  'select', 'Publicly traded|Privately held'),
 (4,  'select', 'LLC|C-Corporation|S-Corporation|Sole Proprietorship|'
                'Partnership|Nonprofit|Cooperative|Other'),
 (5,  'date',   None),
 (7,  'url',    None),
 (12, 'select', 'Founder-owned|Family-owned|Private-equity-backed|'
                'Venture-backed|Employee-owned|Publicly held|Other'),
 (15, 'number', None),
 (17, 'select', 'Local|Regional|National|International'),
 (19, 'number', None),
 (40, 'number', None),
 (45, 'number', None),
]

# the 9 output kinds : (id, name, description)
OUTPUT_KINDS = [
 (1,'scale-context',"sets the size of the world the user worked in"),
 (2,'accomplishment',"a thing the user did and finished"),
 (3,'capability',"a skill or way of working the user can carry to a new job"),
 (4,'credibility',"standing borrowed from an audited system or verifiable record"),
 (5,'trajectory',"direction of movement over time"),
 (6,'proof',"evidence of a trait (trust, capacity) rather than a task"),
 (7,'narrative',"a story scaffold a writer can voice"),
 (8,'differentiator',"something distinctively the user's"),
 (9,'application-meta',"informs the application itself, not a resume bullet"),
]

# the _guide legend : (table_name, page, purpose)
GUIDE = [
 ('_guide','meta',"this legend — one row per table, a map of the database"),
 ('jobs','spine',"the list of jobs — the subject every page hangs off"),
 ('p1_variables','page 1',"the 79 Index variables — the questions, universal"),
 ('p1_variable_values','page 1',"a job's answers to the 79 variables"),
 ('p2_formulas','page 2',"the lenses — one row per formula"),
 ('p2_formula_inputs','page 2',"wiring — which variables each formula reads"),
 ('p2_formula_output_kinds','page 2',"wiring — which output kinds each formula yields"),
 ('p2_clusters','page 2',"saved bundles of Index variables — lens-builder presets"),
 ('p2_cluster_variables','page 2',"wiring — which variables each cluster holds"),
 ('p2_output_kinds','page 2',"the 9 output kinds — the tagging vocabulary"),
 ('p3_synthetic_outputs','page 3',"the generated synthetic points, per job"),
]

# NOTE: this script no longer wipes synthesis.db. It used to start from an
# empty file and rebuild; now it creates only what is missing and seeds
# only empty tables -- which makes it safe to re-run after the app has
# saved real data (lenses). That data lives only here, in no script.

con = sqlite3.connect(DB_PATH)
con.executescript(SCHEMA)          # IF NOT EXISTS throughout, so this is safe every run


def _add_column_if_missing(table, column, decl):
    """Add a column to an existing table -- only if it is not there yet.

    CREATE TABLE IF NOT EXISTS cannot alter a table that already exists,
    so a column added after the table was first built needs an explicit
    ALTER TABLE. Guarding on PRAGMA table_info keeps this safe to re-run.
    """
    have = [r[1] for r in con.execute('PRAGMA table_info("%s")' % table)]
    if column not in have:
        con.execute('ALTER TABLE "%s" ADD COLUMN %s %s' % (table, column, decl))
        print("  + added column %s.%s" % (table, column))


# intake_code was added to these tables after they first existed, so an
# existing synthesis.db gets the column here via ALTER TABLE.
_add_column_if_missing("p2_formulas", "intake_code", "TEXT")
_add_column_if_missing("p2_clusters", "intake_code", "TEXT")

# input_type / options were added to p1_variables after it first existed --
# they carry, per variable, which control the workbench should render (a
# dropdown, a date picker, ...). An existing synthesis.db gets the columns
# here via ALTER TABLE; their values are written by the backfill below.
_add_column_if_missing("p1_variables", "input_type", "TEXT NOT NULL DEFAULT 'text'")
_add_column_if_missing("p1_variables", "options", "TEXT")

# slot was added to jobs after it first existed -- it records which
# Work Experience position a job occupies on Page 2 of the workbench.
# An existing synthesis.db gets the column here via ALTER TABLE. slot is
# nullable (the BASE control job is unplaced) and carries no UNIQUE
# constraint -- ALTER TABLE ADD COLUMN cannot add one -- so when slot
# uniqueness has to be enforced it is data.py's job, not the schema's.
_add_column_if_missing("jobs", "slot", "INTEGER")

# ready_at records when a job most recently entered 'ready' status -- set by
# data.save_job after a status-flipping save; cleared when the job slides
# back to in_progress. Added later than the table itself, so existing
# synthesis.db files pick it up here via ALTER.
_add_column_if_missing("jobs", "ready_at", "TEXT")

# tier classifies each variable as 1 (super tight), 2 (large, effort-worthy)
# or 3 (varying/optional). Read by the workbench to show a tier pill on each
# field card, and by future tier-aware readiness logic (Tier-1 ready vs
# Tier-2 ready). Added after p1_variables first existed, so existing
# synthesis.db files pick it up here via ALTER. Default 2 — the "large"
# bucket — so any variable not explicitly named in VARIABLE_TIERS lands
# there rather than at the extremes.
_add_column_if_missing("p1_variables", "tier", "INTEGER NOT NULL DEFAULT 2")

# derived: a recipe string ("count:<section>", "duration:<vid>,<vid>") that
# marks a variable as server-computed.  NULL means user-entered (default).
# See VARIABLE_DERIVATIONS above and the dispatch in data.compute_derived_value.
_add_column_if_missing("p1_variables", "derived", "TEXT")

# track: a parallel classification rail to `tier`. NULL means the variable
# lives in the depth-tier system (T1/T2/T3). A non-NULL track ("story")
# routes the variable to its own picker option in the workbench, where the
# user fills it as a deliberate engagement pass instead of mixed into the
# depth tiers. See VARIABLE_TRACKS above for the seed.
_add_column_if_missing("p1_variables", "track", "TEXT")


def _empty(table):
    """True when a table holds no rows -- so we seed it once, then never again."""
    return con.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0] == 0


# Seed the reference data, but ONLY into tables that are still empty. On a
# re-run those tables already hold their rows, so we skip them -- and so we
# never collide with their PRIMARY KEY / UNIQUE constraints.
if _empty("p1_variables"):
    con.executemany("INSERT INTO p1_variables (id,field,file,section,repeats,definition) VALUES (?,?,?,?,?,?)", VARIABLES)

# Backfill the typed-input metadata onto the variable rows. Unlike the seed
# above, this runs EVERY build: on a re-run the 79 rows already exist, so
# there is nothing to INSERT -- only to UPDATE. Writing the same value twice
# is harmless, which makes the block safely idempotent. VARIABLE_TYPES is the
# source; any variable not in it keeps the column default, 'text'.
for _vid, _input_type, _options in VARIABLE_TYPES:
    con.execute("UPDATE p1_variables SET input_type = ?, options = ? WHERE id = ?",
                (_input_type, _options, _vid))

# Backfill the tier classification onto the variable rows. Same idempotent
# pattern as VARIABLE_TYPES: every build re-writes the 79 rows to whatever
# VARIABLE_TIERS currently says, so retiering is a single edit-and-rerun.
for _vid, _tier in VARIABLE_TIERS:
    con.execute("UPDATE p1_variables SET tier = ? WHERE id = ?", (_tier, _vid))

# Backfill the derivation recipe. Variables not in VARIABLE_DERIVATIONS are
# explicitly reset to NULL on every build, so REMOVING a recipe is just a
# delete-and-rerun — never a stale row in the DB. Same idempotency principle.
con.execute("UPDATE p1_variables SET derived = NULL")
for _vid, _recipe in VARIABLE_DERIVATIONS:
    con.execute("UPDATE p1_variables SET derived = ? WHERE id = ?",
                (_recipe, _vid))

# Backfill the track classification. Same null-then-set pattern so the
# track always reflects the current VARIABLE_TRACKS list, never a stale
# leftover from a prior build.
con.execute("UPDATE p1_variables SET track = NULL")
for _vid, _track in VARIABLE_TRACKS:
    con.execute("UPDATE p1_variables SET track = ? WHERE id = ?",
                (_track, _vid))

if _empty("p2_output_kinds"):
    con.executemany("INSERT INTO p2_output_kinds (id,name,description) VALUES (?,?,?)", OUTPUT_KINDS)
# _guide is topped up every run: INSERT OR IGNORE adds the legend row for
# any newly added table (its name is the primary key) without disturbing
# the rows already there.
con.executemany("INSERT OR IGNORE INTO _guide (table_name,page,purpose) VALUES (?,?,?)", GUIDE)

# control-group job BASE -- the full 79-variable skeleton, all blank. Seed it
# (and its 79 value rows) only when no BASE job exists yet.
if con.execute("SELECT id FROM jobs WHERE name = 'BASE'").fetchone() is None:
    base_id = con.execute("INSERT INTO jobs (name) VALUES ('BASE')").lastrowid
    con.executemany(
        "INSERT INTO p1_variable_values (job_id, variable_id, entry_no, value) VALUES (?,?,1,NULL)",
        [(base_id, v[0]) for v in VARIABLES])
con.commit()

print("=== synthesis.db checked (page-prefixed) ===\n")
print("tables, as a viewer now sorts them A-Z:")
for (nm,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='sqlite_sequence' ORDER BY name"):
    print("   " + nm)
print()
print("reference: p1_variables=%d, p2_output_kinds=%d" % (
    con.execute("SELECT COUNT(*) FROM p1_variables").fetchone()[0],
    con.execute("SELECT COUNT(*) FROM p2_output_kinds").fetchone()[0]))
print("defined  : %d of 79 variables carry a definition (full Index done)" %
    con.execute("SELECT COUNT(*) FROM p1_variables WHERE definition != ''").fetchone()[0])
print("typed    : %d of 79 variables use a non-text input control (select/date/number/url)" %
    con.execute("SELECT COUNT(*) FROM p1_variables WHERE input_type != 'text'").fetchone()[0])
print("tiered   : T1=%d, T2=%d, T3=%d (super-tight / large / varying)" % tuple(
    con.execute("SELECT COUNT(*) FROM p1_variables WHERE tier = ?", (t,)).fetchone()[0]
    for t in (1, 2, 3)))
print("derived  : %d of 79 variables are server-computed (count/duration recipes)" %
    con.execute("SELECT COUNT(*) FROM p1_variables WHERE derived IS NOT NULL").fetchone()[0])
print("tracked  : %d of 79 variables on a track (story=%d) — out of T1/T2/T3 picker" % (
    con.execute("SELECT COUNT(*) FROM p1_variables WHERE track IS NOT NULL").fetchone()[0],
    con.execute("SELECT COUNT(*) FROM p1_variables WHERE track = 'story'").fetchone()[0]))
print("jobs     : %s" % ", ".join(
    "%s%s" % (nm, "" if sl is None else " [slot %d]" % sl)
    for (nm, sl) in con.execute("SELECT name, slot FROM jobs ORDER BY id")))
print("BASE data: %d rows in p1_variable_values (the control skeleton)" %
    con.execute("SELECT COUNT(*) FROM p1_variable_values").fetchone()[0])
print("empty    : %s" % ", ".join("%s=%d" % (t, con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0])
    for t in ('p2_formulas','p2_formula_inputs','p2_formula_output_kinds',
              'p2_clusters','p2_cluster_variables','p3_synthetic_outputs')))
print()
print("_guide — the in-database legend:")
for r in con.execute("SELECT table_name,page,purpose FROM _guide ORDER BY table_name"):
    print("   %-26s %-7s %s" % r)
con.close()
