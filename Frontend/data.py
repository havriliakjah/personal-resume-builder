"""
data.py  --  THE DATA LAYER  (your "back end")
==============================================================
This file is the ONLY part of the program that knows the data
lives in a SQLite database. Everything else -- the whole user
interface -- talks to THESE FUNCTIONS, never to SQL directly.

That rule is the entire point of the file. It has a name in
systems engineering: SEPARATION OF CONCERNS. The benefit:
if you ever move from SQLite to Postgres, or to plain files,
you rewrite THIS ONE FILE and nothing else. The interface
never finds out, because it only ever saw the functions.

Think of this file as a CONTRACT. The functions below are the
promises the data layer makes to the rest of the app:
    list_tables()        -> list of table names
    get_columns(table)   -> list of column names
    get_rows(table)      -> list of rows
    count_rows(table)    -> an integer
As long as the promises hold, the insides can change freely.
"""

import sqlite3
from pathlib import Path

# --------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------
# This points at synthesis.db -- your one real database, the
# whole 11-table Synthesis system. It lives in the DB folder,
# which sits right next to this Frontend folder:
#       Synthesis Routing\DB\synthesis.db
# synthesis.db is built by DB\build_synthesis_db.py, which is the
# single source of truth for the SCHEMA. The app both reads this
# file and writes it -- the create / update / delete functions
# further down are how it writes.
#
# .resolve() turns this file's own path into a full absolute
# path first, so .parent.parent reliably means "the Synthesis
# Routing folder" no matter which folder the app is launched
# from. From there we step down into DB\synthesis.db.
DB_PATH = Path(__file__).resolve().parent.parent / "DB" / "synthesis.db"


# --------------------------------------------------------------
# SCHEMA VERSION CHECK
# --------------------------------------------------------------
# Tables get columns added over time (slot, ready_at, input_type,
# options, tier, ...). Each addition lives in build_synthesis_db.py
# as an _add_column_if_missing call; running that script migrates
# an old synthesis.db forward. The check below is the safety net:
# the server reads it once at startup and refuses to come up if
# the DB is missing any column the app now depends on, with a
# clear pointer to the migration script. This is the trap we hit
# in R7 (server SELECTed ready_at before the column existed) made
# impossible going forward.
SCHEMA_EXPECTATIONS = {
    "jobs":         {"id", "name", "slot", "ready_at"},
    "p1_variables": {"id", "field", "file", "section", "repeats",
                     "definition", "input_type", "options", "tier",
                     "derived", "track"},
}


class SchemaOutOfDate(RuntimeError):
    """Raised when synthesis.db is missing a column the app now needs.

    The message tells the user exactly what to run.  Server boot catches
    this and prints it; the app then refuses to start, which is the
    behavior we want — a half-migrated DB is worse than a missing one.
    """
    pass


def verify_schema():
    """Compare the live DB's columns to SCHEMA_EXPECTATIONS.

    Returns silently when everything is present.  Raises SchemaOutOfDate
    with a fix-it hint when one or more expected columns is missing.
    """
    missing = []
    with sqlite3.connect(DB_PATH) as conn:
        for table, expected in SCHEMA_EXPECTATIONS.items():
            have = {r[1] for r in conn.execute(
                'PRAGMA table_info("%s")' % table)}
            for col in sorted(expected - have):
                missing.append("%s.%s" % (table, col))
    if missing:
        raise SchemaOutOfDate(
            "synthesis.db is missing columns the app now needs: " +
            ", ".join(missing) +
            "\n  Fix:  cd DB  &&  python build_synthesis_db.py"
            "\n  The migration is non-destructive — it only ADDs columns.")


def _connect():
    """Open a fresh connection to the database.

    This is an INTERNAL helper. The leading underscore is a Python
    convention meaning "private -- not part of the public contract".
    The user interface never calls this. It only calls the named,
    underscore-free functions further down.

    `row_factory = sqlite3.Row` makes each returned row behave like
    a dictionary, so we can read a value by column name.

    `PRAGMA foreign_keys = ON` turns on foreign-key enforcement.
    SQLite keeps it OFF by default, and it has to be set on every
    new connection. The schema's wiring tables declare
    `REFERENCES ... ON DELETE CASCADE`, and that promise is only
    real with this pragma on -- with it, the database itself
    refuses a lens that points at a variable id that does not exist.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def list_tables():
    """Return the name of every table in the database.

    Returns: a list of strings. For synthesis.db that is the 11
    tables -- _guide, jobs, p1_variables, p1_variable_values,
    p2_formulas, p2_formula_inputs, p2_formula_output_kinds,
    p2_output_kinds, p2_clusters, p2_cluster_variables,
    p3_synthetic_outputs.

    `sqlite_master` is a built-in table that SQLite keeps about
    itself -- it lists every table. We skip SQLite's own internal
    tables (their names start with "sqlite_").
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    return [r["name"] for r in rows]


def get_columns(table):
    """Return the column names of one table, as a list of strings."""
    _guard_table_name(table)
    with _connect() as conn:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return [r["name"] for r in rows]


def get_rows(table, limit=200):
    """Return up to `limit` rows from `table`.

    Each row comes back as a plain tuple of values, in column order,
    e.g. (1, "disclosure", "Company Facts", "Disclosure", 0, "...").

    The `LIMIT ?` with a `?` placeholder is the SAFE way to put a
    value into a query: SQLite inserts it for us and can never
    mistake it for SQL commands.
    """
    _guard_table_name(table)
    with _connect() as conn:
        cursor = conn.execute(f'SELECT * FROM "{table}" LIMIT ?', (limit,))
        return [tuple(row) for row in cursor.fetchall()]


def count_rows(table):
    """Return the total number of rows in `table`, as an integer."""
    _guard_table_name(table)
    with _connect() as conn:
        (total,) = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    return total


def _guard_table_name(table):
    """Reject any value that is not a real table name.

    WHY THIS EXISTS -- a security lesson worth learning early:
    A table name CANNOT be passed through a `?` placeholder; it has
    to be written straight into the query text. If we let arbitrary
    text through, a hostile value could smuggle in extra SQL. That
    attack is called SQL INJECTION.

    The defence here is an ALLOW-LIST: we only accept a name that
    already appears in the real table list. Anything else raises an
    error before it ever reaches the database.
    """
    if table not in list_tables():
        raise ValueError(f"Unknown table: {table!r}")


# --------------------------------------------------------------
# SENTINELS  (the meta-state vocabulary)
# --------------------------------------------------------------
# A SENTINEL is a reserved string value with a meta-meaning rather than a
# real one. "N/A" -- the first sentinel -- stands for "this variable has
# been considered and marked not applicable to this job," a distinct state
# from a blank value, which means "not yet filled in." Sentinels bypass
# type validation everywhere in the workbench: a select / date / number /
# url field can carry one even though it would normally reject anything
# off-list or malformed.
#
# **Adding a new sentinel** (TBD, UNKNOWN, REDACTED, ...) is a one-line
# change here -- append the canonical string to SENTINELS. The list is
# exposed by server.py via /api/sentinels so the workbench fetches it on
# boot rather than hardcoding it; this file stays the single source of
# truth. The helpers below let any layer ask "is this value a sentinel?"
# and normalise an incoming "n/a" / "N/a" to canonical "N/A" before
# storage, so future consumers (formulas, completion counts, exports) can
# pattern-match on a literal canonical form.

SENTINELS = ["N/A"]


def get_sentinels():
    """Return the canonical sentinel list, ordered for display."""
    return list(SENTINELS)


def is_sentinel(value):
    """True when `value` (case-insensitive, trimmed) matches a recognised
    sentinel. False for None, the empty string, and any real value.
    """
    if value is None:
        return False
    s = str(value).strip()
    return any(s.lower() == sentinel.lower() for sentinel in SENTINELS)


def normalize_value(value):
    """If `value` matches a sentinel, return its canonical form (any case
    of 'n/a' becomes 'N/A'). Otherwise return the value unchanged.

    The data layer's job: whichever shape the caller sent, one canonical
    form lands in the database. Future consumers -- formulas, completion
    counts, exports -- can rely on the literal canonical sentinel as the
    marker. A non-sentinel string, None, or an empty string passes through
    untouched.
    """
    if value is None:
        return None
    s = str(value).strip()
    for sentinel in SENTINELS:
        if s.lower() == sentinel.lower():
            return sentinel
    return value


# --------------------------------------------------------------
# API READ FUNCTIONS
# --------------------------------------------------------------
# The functions above (list_tables, get_rows, ...) are generic --
# they work on any table. The three below are SPECIFIC to this
# app: each returns one of the exact shapes the web layer
# (server.py) hands to the workbench as JSON. This is still the
# data layer -- still the only code here that speaks SQL.


def get_variables():
    """Return all 79 Index variables, ordered by id.

    Each variable is a dict: {id, field, file, section, repeats,
    definition, input_type, options, tier}.

    `input_type` says which control the workbench renders for the field:
    'text' (free text, the default), 'select' (a fixed dropdown), 'date'
    (a calendar -- the value is stored ISO YYYY-MM-DD), 'number', or 'url'.

    `options` is the choice list for a 'select'. The database stores it as
    one '|'-joined string; this function splits it into a real list before
    handing it up, and returns [] when the field is not a select. Keeping
    that split here means the '|' encoding stays the database's business --
    the web layer above only ever sees a clean list.

    `tier` is 1, 2, or 3. Tier 1 is super-tight (the minimum to identify a
    job — disclosure, legal_name, primary_industry, title, start, end,
    tenure). Tier 2 is the large effort-worthy substrate (scale facts,
    role-level fields, key people). Tier 3 is varying / optional (niche
    company facts, certs/memberships, references, deep story content). The
    workbench reads it for the per-field T1/T2/T3 pill and (later) for
    tier-aware readiness gating.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, field, file, section, repeats, definition, "
            "input_type, options, tier, derived, track "
            "FROM p1_variables ORDER BY id"
        ).fetchall()
    variables = []
    for r in rows:
        variable = dict(r)
        raw = variable["options"]
        variable["options"] = raw.split("|") if raw else []
        variables.append(variable)
    return variables


def get_output_kinds():
    """Return the 9 output kinds, ordered by id.

    Each is a dict: {id, name, description}.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, description FROM p2_output_kinds ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def get_lenses():
    """Return every lens, each as a dict with its wiring filled in.

    A lens lives across three tables: p2_formulas holds the lens
    itself, and two wiring tables hold its links. So for each lens
    we run two small follow-up queries to gather:
        inputs        -> the variable ids the lens reads
        output_kinds  -> the output-kind ids the lens yields
    The result is one tidy dict per lens:
        {id, name, status, section, lens, inputs, output_kinds}

    One follow-up query per lens is perfectly fine here: this is a
    local app with a handful of lenses, not a high-traffic service.
    """
    with _connect() as conn:
        lenses = [dict(r) for r in conn.execute(
            "SELECT id, name, status, section, lens, intake_code "
            "FROM p2_formulas ORDER BY id"
        ).fetchall()]
        for lens in lenses:
            lens["inputs"] = [row["variable_id"] for row in conn.execute(
                "SELECT variable_id FROM p2_formula_inputs "
                "WHERE formula_id = ? ORDER BY variable_id", (lens["id"],)
            ).fetchall()]
            lens["output_kinds"] = [row["output_kind_id"] for row in conn.execute(
                "SELECT output_kind_id FROM p2_formula_output_kinds "
                "WHERE formula_id = ? ORDER BY output_kind_id", (lens["id"],)
            ).fetchall()]
    return lenses


# --------------------------------------------------------------
# API WRITE FUNCTIONS  (Phase 3)
# --------------------------------------------------------------
# Phase 1 gave this file its read functions. These are the other
# half: create, update, and delete a lens. A lens is not one row
# -- it spans THREE tables (p2_formulas plus the two wiring
# tables) -- so every write below happens inside ONE transaction.
# `with _connect() as conn:` IS that transaction: if anything in
# the block raises, SQLite rolls the WHOLE thing back and the
# database is left exactly as it was. A half-written lens can
# never happen.


def _check_lens_fields(name, status, lens, section):
    """Reject bad scalar fields before touching the database.

    A raw SQLite constraint error ("CHECK constraint failed") is
    cryptic. Catching the problem here, with a plain-English
    message, is the kindness the layer above (server.py) passes on.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("lens name must be a non-empty string")
    if status not in ("Active", "Inactive"):
        raise ValueError(
            "status must be 'Active' or 'Inactive', got %r" % (status,))
    if not isinstance(lens, str):
        raise ValueError("lens text must be a string (it may be empty)")
    if not isinstance(section, str):
        raise ValueError("section must be a string (it may be empty)")


def _check_refs(conn, inputs, output_kinds):
    """Reject any variable id or output-kind id that does not exist.

    The foreign keys would catch these too, but a named error here
    -- "variable id 999 is not one of the 88" -- is far clearer
    than a raw foreign-key failure.
    """
    valid_vars = {r["id"] for r in conn.execute("SELECT id FROM p1_variables")}
    for variable_id in inputs:
        if variable_id not in valid_vars:
            raise ValueError(
                "variable id %r is not one of the 88 Index variables"
                % (variable_id,))
    valid_kinds = {r["id"] for r in
                   conn.execute("SELECT id FROM p2_output_kinds")}
    for kind_id in output_kinds:
        if kind_id not in valid_kinds:
            raise ValueError(
                "output-kind id %r is not one of the 9 output kinds"
                % (kind_id,))


def _write_wiring(conn, formula_id, inputs, output_kinds):
    """Replace a formula's wiring rows.

    Used by create and update alike: clear whatever links the
    formula has, then write the given ones. `dict.fromkeys(...)`
    de-duplicates while keeping order -- it has to, because each
    wiring table's primary key is the (formula_id, id) PAIR, so the
    same variable listed twice would collide.
    """
    conn.execute("DELETE FROM p2_formula_inputs WHERE formula_id = ?",
                 (formula_id,))
    conn.execute("DELETE FROM p2_formula_output_kinds WHERE formula_id = ?",
                 (formula_id,))
    for variable_id in dict.fromkeys(inputs):
        conn.execute(
            "INSERT INTO p2_formula_inputs (formula_id, variable_id) "
            "VALUES (?, ?)", (formula_id, variable_id))
    for output_kind_id in dict.fromkeys(output_kinds):
        conn.execute(
            "INSERT INTO p2_formula_output_kinds "
            "(formula_id, output_kind_id) VALUES (?, ?)",
            (formula_id, output_kind_id))


def _lens_dict(conn, formula_id):
    """Build the full lens dict for one id, or None if it does not exist.

    Same shape get_lenses() returns for each lens:
    {id, name, status, section, lens, inputs, output_kinds}. The
    write functions call this at the end so they hand back exactly
    what the caller just stored.
    """
    row = conn.execute(
        "SELECT id, name, status, section, lens, intake_code FROM p2_formulas "
        "WHERE id = ?", (formula_id,)).fetchone()
    if row is None:
        return None
    lens = dict(row)
    lens["inputs"] = [r["variable_id"] for r in conn.execute(
        "SELECT variable_id FROM p2_formula_inputs "
        "WHERE formula_id = ? ORDER BY variable_id", (formula_id,))]
    lens["output_kinds"] = [r["output_kind_id"] for r in conn.execute(
        "SELECT output_kind_id FROM p2_formula_output_kinds "
        "WHERE formula_id = ? ORDER BY output_kind_id", (formula_id,))]
    return lens


def get_lens(formula_id):
    """Return one lens as a dict, or None if no lens has that id.

    The single-lens companion to get_lenses(). server.py will use
    it to answer "give me lens #N" and to echo back the result of
    a create or an update.
    """
    with _connect() as conn:
        return _lens_dict(conn, formula_id)


def create_lens(name, status, section, lens, inputs, output_kinds,
                intake_code=None):
    """Create one lens. Return the new lens dict, including the id
    the database assigned.

    `inputs` is a list of Index variable ids; `output_kinds` is a list
    of output-kind ids. `intake_code` is the Intake Code provenance
    string (e.g. "1.0.3") when the lens was built by an intake card,
    or None when it was built by hand. The whole write -- the
    p2_formulas row and every wiring row -- is one transaction.
    """
    _check_lens_fields(name, status, lens, section)
    with _connect() as conn:
        _check_refs(conn, inputs, output_kinds)
        cursor = conn.execute(
            "INSERT INTO p2_formulas (name, status, lens, section, intake_code) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, status, lens, section, intake_code))
        formula_id = cursor.lastrowid          # the id SQLite just assigned
        _write_wiring(conn, formula_id, inputs, output_kinds)
        return _lens_dict(conn, formula_id)


def update_lens(formula_id, name, status, section, lens, inputs,
                output_kinds):
    """Update one lens in place. Return the updated lens dict, or
    None if no lens has that id.

    The scalar fields are overwritten and the wiring is fully
    replaced -- simpler and safer than working out which links
    changed. One transaction, so a failure changes nothing.
    """
    _check_lens_fields(name, status, lens, section)
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM p2_formulas WHERE id = ?",
            (formula_id,)).fetchone()
        if exists is None:
            return None
        _check_refs(conn, inputs, output_kinds)
        conn.execute(
            "UPDATE p2_formulas SET name = ?, status = ?, lens = ?, "
            "section = ? WHERE id = ?",
            (name, status, lens, section, formula_id))
        _write_wiring(conn, formula_id, inputs, output_kinds)
        return _lens_dict(conn, formula_id)


def delete_lens(formula_id):
    """Delete one lens and all of its wiring.

    Return True if a lens was removed, False if no lens had that
    id. The wiring rows are deleted explicitly rather than left to
    ON DELETE CASCADE, so this function stays correct even if
    foreign-key enforcement is ever off.
    """
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM p2_formulas WHERE id = ?",
            (formula_id,)).fetchone()
        if exists is None:
            return False
        conn.execute("DELETE FROM p2_formula_inputs WHERE formula_id = ?",
                     (formula_id,))
        conn.execute(
            "DELETE FROM p2_formula_output_kinds WHERE formula_id = ?",
            (formula_id,))
        conn.execute("DELETE FROM p2_formulas WHERE id = ?", (formula_id,))
        return True


# --------------------------------------------------------------
# CLUSTER FUNCTIONS  (hardening — clusters move into the database)
# --------------------------------------------------------------
# A cluster is a saved bundle of Index variables -- a lens-builder
# preset. It used to live ONLY in the browser's localStorage, which
# meant it vanished the moment the app was opened on another machine.
# Now it is a database citizen, stored exactly like a lens: one
# p2_clusters row, plus one p2_cluster_variables wiring row per
# variable. Same two-table shape, same one-transaction-per-write rule.


def _check_cluster_name(name):
    """Reject a bad cluster name before touching the database."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("cluster name must be a non-empty string")


def _cluster_dict(conn, cluster_id):
    """Build the full cluster dict for one id, or None if it does not exist.

    Shape: {id, name, variables:[Index ids]} -- the exact shape the
    workbench keeps a cluster in. The companion of _lens_dict().
    """
    row = conn.execute(
        "SELECT id, name, intake_code FROM p2_clusters WHERE id = ?",
        (cluster_id,)).fetchone()
    if row is None:
        return None
    cluster = dict(row)
    cluster["variables"] = [r["variable_id"] for r in conn.execute(
        "SELECT variable_id FROM p2_cluster_variables "
        "WHERE cluster_id = ? ORDER BY variable_id", (cluster_id,))]
    return cluster


def get_clusters():
    """Return every cluster, each as {id, name, variables:[ids]}.

    The cluster companion to get_lenses(). One follow-up query per
    cluster -- perfectly fine for a local app with a handful of them.
    """
    with _connect() as conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM p2_clusters ORDER BY id")]
        return [_cluster_dict(conn, cid) for cid in ids]


def get_cluster(cluster_id):
    """Return one cluster as a dict, or None if no cluster has that id."""
    with _connect() as conn:
        return _cluster_dict(conn, cluster_id)


def create_cluster(name, variables, intake_code=None):
    """Create one cluster. Return the new cluster dict, id included.

    `variables` is a list of Index variable ids. `intake_code` is the
    Intake Code provenance string when the cluster came from an intake
    card, or None when built by hand. The whole write -- the
    p2_clusters row and every wiring row -- is one transaction, so a
    half-written cluster can never happen. `_check_refs` is reused
    with an empty output-kinds list: it then only validates the
    variable ids, which is all a cluster has.
    """
    _check_cluster_name(name)
    with _connect() as conn:
        _check_refs(conn, variables, [])      # reuse the lens id-checker
        cursor = conn.execute(
            "INSERT INTO p2_clusters (name, intake_code) VALUES (?, ?)",
            (name, intake_code))
        cluster_id = cursor.lastrowid          # the id SQLite just assigned
        for variable_id in dict.fromkeys(variables):   # de-dup, keep order
            conn.execute(
                "INSERT INTO p2_cluster_variables (cluster_id, variable_id) "
                "VALUES (?, ?)", (cluster_id, variable_id))
        return _cluster_dict(conn, cluster_id)


def delete_cluster(cluster_id):
    """Delete one cluster and all of its wiring.

    Return True if a cluster was removed, False if no cluster had that
    id. The wiring rows are deleted explicitly rather than left to
    ON DELETE CASCADE, so this stays correct even if foreign-key
    enforcement is ever off.
    """
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM p2_clusters WHERE id = ?",
            (cluster_id,)).fetchone()
        if exists is None:
            return False
        conn.execute("DELETE FROM p2_cluster_variables WHERE cluster_id = ?",
                     (cluster_id,))
        conn.execute("DELETE FROM p2_clusters WHERE id = ?", (cluster_id,))
        return True


# --------------------------------------------------------------
# JOB FUNCTIONS  (the river -- a job's answers become database rows)
# --------------------------------------------------------------
# A job is the spine of the whole machine, and it is the LARGEST
# thing this file writes. A lens is one row plus a little wiring; a
# job is one `jobs` row -- its name and its Work Experience slot --
# PLUS one p1_variable_values row for every Index variable it
# answers. Three functions cover its life:
#     create_job  lays down the blank skeleton (every variable, no
#                 answers) -- exactly how build_synthesis_db.py
#                 seeds the BASE control job.
#     save_job    fills the skeleton in, and can be called again and
#                 again as the user edits.
#     get_job     reads the whole thing back.
# Same rule as everywhere in this file: one transaction per write,
# so a half-written job can never reach the database.
#
# A value is addressed by (variable_id, entry_no). Most variables are
# singular and hold one entry; a variable marked `repeats` (a role, a
# certification, a story person) holds several. The job dict carries
# `values` as a flat map keyed "<variable_id>.<entry_no>" -- "1.1" for a
# singular fact, "54.1"/"54.2"/"54.3" for the entries of a repeating one.
# The count of entries lives here, in the data, never in the Index.


def _check_job_name(name):
    """Reject a bad job name before touching the database.

    `jobs.name` is the job's short identity in the spine -- "ExampleCo",
    "BASE" -- and the schema marks it NOT NULL UNIQUE.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError("job name must be a non-empty string")


def _check_job_slot(slot):
    """Reject a bad Work Experience slot.

    `slot` is the job's position in the Work Experience list on Page 2.
    None is allowed and ordinary: the BASE control job has no slot, and
    a job may exist before it is placed. A real slot is a positive whole
    number. `isinstance(slot, bool)` is screened out first because in
    Python True and False ARE ints -- 1 and 0 -- and a boolean slot is a
    caller mistake, not a position.
    """
    if slot is None:
        return
    if isinstance(slot, bool) or not isinstance(slot, int) or slot < 1:
        raise ValueError("job slot must be a positive whole number, or None")


def _parse_value_keys(values):
    """Turn a {"<variable_id>.<entry_no>": value} dict into a list of
    (variable_id, entry_no, value) triples.

    The web layer hands `values` down with composite string keys --
    "1.1", "54.2" -- because that is what the form and the JSON carry.
    Splitting them into real integers is this layer's job. A key that is
    not "<digits>.<digits>", or an entry number below 1, is a caller
    mistake and raises ValueError -- which server.py turns into a 400.
    """
    parsed = []
    for key, value in values.items():
        parts = str(key).split(".")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(
                "value key %r must be '<variable_id>.<entry_no>'" % (key,))
        variable_id, entry_no = int(parts[0]), int(parts[1])
        if entry_no < 1:
            raise ValueError("entry number in %r must be 1 or greater" % (key,))
        parsed.append((variable_id, entry_no, value))
    return parsed


def _check_value_refs(conn, parsed):
    """Reject any entry that does not fit the Index.

    `parsed` is the list of (variable_id, entry_no, value) triples from
    _parse_value_keys(). Two things are checked: the variable id must be a
    real Index variable, and an entry number above 1 is allowed only on a
    `repeats` variable -- a singular fact cannot have a second entry. A
    named error here is far clearer than a raw foreign-key failure.
    """
    meta = {r["id"]: r["repeats"] for r in
            conn.execute("SELECT id, repeats FROM p1_variables")}
    for variable_id, entry_no, value in parsed:
        if variable_id not in meta:
            raise ValueError(
                "variable id %r is not one of the %d Index variables"
                % (variable_id, len(meta)))
        if entry_no > 1 and not meta[variable_id]:
            raise ValueError(
                "variable id %r is not a repeating variable -- it cannot "
                "have an entry %d" % (variable_id, entry_no))


def _parse_entries(entries):
    """Turn a {"<variable_id>": N} dict into a list of (variable_id, N) pairs.

    `entries` is the cardinality declaration: for each repeating variable
    listed, the job has exactly N entries; any p1_variable_values row with
    a higher entry_no will be deleted on save. None or {} means "no
    cardinality declared -- only upsert what is in `values`." The web
    layer passes the body's `entries` field straight through; this is
    where it becomes Python ints. Raises ValueError on a malformed key or
    a non-integer / negative count.
    """
    if entries is None:
        return []
    if not isinstance(entries, dict):
        raise ValueError("'entries' must be a JSON object of '<id>' -> count")
    parsed = []
    for key, count in entries.items():
        if not str(key).isdigit():
            raise ValueError("entries key %r must be a variable id number"
                             % (key,))
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("entries count %r must be a non-negative integer"
                             % (count,))
        parsed.append((int(key), count))
    return parsed


def _check_entries_refs(conn, parsed_entries):
    """Reject any entry-count that does not fit the Index.

    The variable id must be real, and a cardinality declaration is only
    valid on a `repeats` variable -- a singular fact's cardinality is
    always exactly one, fixed by the schema, never by a save call.
    """
    meta = {r["id"]: r["repeats"] for r in
            conn.execute("SELECT id, repeats FROM p1_variables")}
    for vid, count in parsed_entries:
        if vid not in meta:
            raise ValueError(
                "variable id %r is not one of the %d Index variables"
                % (vid, len(meta)))
        if not meta[vid]:
            raise ValueError(
                "variable id %r is not a repeating variable -- its entry "
                "count is fixed at 1 by the schema" % (vid,))


# --------------------------------------------------------------
# DERIVATION ENGINE
# --------------------------------------------------------------
# A variable is either user-entered or DERIVED. A derived variable carries
# a recipe string on its p1_variables row ("count:<section>",
# "duration:<vid>,<vid>") and the dispatch below turns that recipe into a
# computed value. The server is the authority: save_job silently drops any
# incoming value for a derived var, and the read path overwrites whatever
# the DB column holds with the freshly-computed result. The DB still
# stores the latest computed value so that lenses can JOIN on it cheaply
# downstream, but the SCREEN never trusts the DB for these — it asks the
# engine.  The frontend mirrors the same two verbs locally so that the
# pill on the form updates the instant a +Add fires.


def _parse_loose_date(s):
    """Parse a free-text date as best we can.

    Returns a (year, month) tuple, the string 'ongoing' for present-style
    sentinels ('present', 'current', 'now'), or None if the value cannot
    be interpreted. Day precision is dropped because the things that key
    off this — tenure expressed in years and months — never need it.
    """
    if s is None: return None
    s = str(s).strip()
    if not s: return None
    if s.lower() in ("present", "current", "now", "ongoing"):
        return "ongoing"
    # ISO-ish forms — YYYY-MM-DD, YYYY-MM, YYYY (with - or /)
    parts = s.replace("/", "-").split("-")
    try:
        if len(parts) >= 2:
            y, m = int(parts[0]), int(parts[1])
            if 1900 <= y <= 2100 and 1 <= m <= 12:
                return (y, m)
        if len(parts) == 1:
            y = int(parts[0])
            if 1900 <= y <= 2100:
                return (y, 1)
    except ValueError:
        pass
    return None


def _format_duration_months(total_months, ongoing):
    """Render N months as 'Xy Ym', dropping zero parts. Adds ' · ongoing'
    when the end side was a present-style sentinel."""
    if total_months < 0:
        return None
    years = total_months // 12
    months = total_months % 12
    if years and months:
        out = "%dy %dm" % (years, months)
    elif years:
        out = "%dy" % years
    elif months:
        out = "%dm" % months
    else:
        out = "<1m"
    return out + " · ongoing" if ongoing else out


def _compute_duration(start_str, end_str):
    """`start_str` and `end_str` from VALUES. Returns the rendered duration
    string, or None if either side is missing/unparseable."""
    start = _parse_loose_date(start_str)
    end   = _parse_loose_date(end_str)
    if start is None or end is None: return None
    if start == "ongoing": return None     # nonsense: a role can't start "present"
    ongoing = (end == "ongoing")
    if ongoing:
        import datetime
        t = datetime.date.today()
        end = (t.year, t.month)
    months = (end[0] - start[0]) * 12 + (end[1] - start[1])
    return _format_duration_months(months, ongoing)


def compute_derived_value(recipe, entry, stored, section_N):
    """Run one recipe at one entry. Returns the computed value (str/int),
    or None when the recipe lacks the inputs it needs.

      recipe    a string like 'count:P1 Roles' or 'duration:48,49'
      entry     which entry index we're computing FOR (1 for singular vars)
      stored    dict[(vid, entry_no)] -> value, the job's stored answers
      section_N dict[section_name] -> how many entries that section holds

    Verbs:
      count:<section>             -> int, the section's entry count
      duration:<start_vid>,<end_vid> -> 'Xy Ym' / 'Xy Ym · ongoing'
    """
    if not recipe: return None
    if recipe.startswith("count:"):
        section = recipe[len("count:"):]
        n = section_N.get(section)
        return n if n is not None else None
    if recipe.startswith("duration:"):
        try:
            a, b = recipe[len("duration:"):].split(",")
            vid_a, vid_b = int(a), int(b)
        except (ValueError, IndexError):
            return None
        return _compute_duration(stored.get((vid_a, entry)),
                                 stored.get((vid_b, entry)))
    return None


def _derived_recipes(conn):
    """{vid: recipe} for every derived variable. Cached at the call site
    when callers want to avoid the round-trip; in practice the table is
    79 rows so the query is essentially free."""
    return {r["id"]: r["derived"] for r in conn.execute(
        "SELECT id, derived FROM p1_variables WHERE derived IS NOT NULL")}


def _variable_homes(conn):
    """{vid: (section, repeats)} for every variable. Used so the read
    path knows which home section a derived variable belongs to, and
    therefore how many entries to compute it for."""
    return {r["id"]: (r["section"], r["repeats"]) for r in conn.execute(
        "SELECT id, section, repeats FROM p1_variables")}


def _recompute_derived(conn, job_id):
    """Recompute every derived variable for one job and upsert the
    results into p1_variable_values. Called from save_job after
    user-written values have been upserted, so the DB stays in sync
    with the engine's view of the world."""
    recipes = _derived_recipes(conn)
    if not recipes: return
    homes = _variable_homes(conn)
    stored = {(r["variable_id"], r["entry_no"]): r["value"] for r in
        conn.execute(
            "SELECT variable_id, entry_no, value FROM p1_variable_values "
            "WHERE job_id = ?", (job_id,))}
    # entry counts per section
    section_vids = {}
    section_is_rep = {}
    for vid, (section, repeats) in homes.items():
        section_vids.setdefault(section, set()).add(vid)
        section_is_rep[section] = bool(repeats)
    section_N = {}
    for section, vids in section_vids.items():
        if section_is_rep.get(section):
            es = [e for (vid, e) in stored if vid in vids]
            section_N[section] = max(es) if es else 1
        else:
            section_N[section] = 1
    for vid, recipe in recipes.items():
        section, repeats = homes[vid]
        N = section_N.get(section, 1) if repeats else 1
        for e in range(1, N + 1):
            v = compute_derived_value(recipe, e, stored, section_N)
            if v is None:
                conn.execute(
                    "DELETE FROM p1_variable_values "
                    "WHERE job_id = ? AND variable_id = ? AND entry_no = ?",
                    (job_id, vid, e))
            else:
                conn.execute(
                    "INSERT INTO p1_variable_values "
                    "(job_id, variable_id, entry_no, value) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT (job_id, variable_id, entry_no) "
                    "DO UPDATE SET value = excluded.value",
                    (job_id, vid, e, str(v)))


def compute_job_status(conn, job_id):
    """Compute a job's readiness, tier-graduated and engagement-aware.

    Returns None when no job has the given id (callers depend on the
    short-circuit). Otherwise returns a dict with this shape:

        {
          "status":           "ready" | "in_progress",   # overall
          "tier_level":       "none" | "t1" | "t2" | "t3",
          "stories_active":   bool,
          "assessed": N, "total": N, "pending": [...],   # overall, engagement-aware

          "tier_progress": {
            "t1": {"assessed":N, "total":N, "ready":bool, "pending":[...]},
            "t2": {"assessed":N, "total":N, "ready":bool, "pending":[...]},
            "t3": {"assessed":N, "total":N, "ready":bool, "pending":[...]},
          },
          "stories_progress": {
            "assessed":N, "total":N,
            "ready":bool, "active":bool, "pending":[...]
          },
        }

    -------------------------------------------------------------------
    SEMANTICS — what each level means.

    A (variable, entry) cell is "assessed" when it carries a non-empty
    user value, an N/A sentinel, or (for derived vars) yields a value
    from its recipe given the current stored state.

    Tier-level readiness is graduated: T1 is ready when every T1 cell
    (across CF + PI, excluding story-track vars) is assessed; T2 ready
    requires T1 ready AND every T2 cell assessed; T3 ready requires T2
    ready AND every T3 cell assessed. `tier_level` is the highest of
    these reached.

    The Story track is a parallel rail. `stories_active` is true when
    any story cell is assessed. ENGAGEMENT-ACTIVE rule: story cells
    count toward the overall total/assessed/pending ONLY when the user
    has actually engaged with at least one of them. A job that fills
    every CF/PI cell and zero story cells is "ready" — stories are
    opt-in. A job with one story field filled and the rest blank is
    "in_progress" — engagement started, finish what you began.

    Overall status: "ready" when tier_level == "t3" AND (NOT
    stories_active OR stories_ready). Otherwise "in_progress".

    The shape preserves the old fields (status / assessed / total /
    pending) so legacy callers still work; the new fields are additive.
    """
    if conn.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone() is None:
        return None
    # ---- pull the schema once: (vid, field, section, repeats, tier, track) ----
    var_rows = list(conn.execute(
        "SELECT id, field, section, repeats, tier, track "
        "FROM p1_variables ORDER BY id"))
    # the job's stored (vid, entry) -> value
    stored = {(r["variable_id"], r["entry_no"]): r["value"] for r in
        conn.execute(
            "SELECT variable_id, entry_no, value FROM p1_variable_values "
            "WHERE job_id = ?", (job_id,))}
    # ---- section_N: how many entries each section expects -------------------
    # Group ids by section to detect "all repeating" vs "all singular".
    section_vars = {}
    for r in var_rows:
        section_vars.setdefault(r["section"], []).append(r)
    section_N = {}
    for section, rows in section_vars.items():
        if rows and rows[0]["repeats"] == 1:
            vids = {r["id"] for r in rows}
            entries = [e for (vid, e) in stored if vid in vids]
            section_N[section] = max(entries) if entries else 1
        else:
            section_N[section] = 1
    recipes = _derived_recipes(conn)

    # ---- walk every expected cell, bucketing into tier / story --------------
    def _assess_cell(vid, e, value):
        """Returns (assessed_bool, pending_entry_or_None)."""
        if vid in recipes:
            dval = compute_derived_value(recipes[vid], e, stored, section_N)
            ok = dval is not None and str(dval).strip() != ""
        else:
            ok = value is not None and str(value).strip() != ""
        return ok

    buckets = {
        "t1": {"assessed": 0, "total": 0, "pending": []},
        "t2": {"assessed": 0, "total": 0, "pending": []},
        "t3": {"assessed": 0, "total": 0, "pending": []},
        "story": {"assessed": 0, "total": 0, "pending": []},
    }
    for r in var_rows:
        vid, field, section, repeats, tier, track = (
            r["id"], r["field"], r["section"], r["repeats"], r["tier"], r["track"])
        N = section_N[section] if repeats == 1 else 1
        for e in range(1, N + 1):
            value = stored.get((vid, e))
            ok = _assess_cell(vid, e, value)
            entry_info = {"vid": vid, "entry": e,
                          "section": section, "field": field}
            bkey = "story" if track == "story" else ("t%d" % tier)
            buckets[bkey]["total"] += 1
            if ok:
                buckets[bkey]["assessed"] += 1
            else:
                buckets[bkey]["pending"].append(entry_info)

    # ---- per-tier readiness flags ------------------------------------------
    def _ready(bk):
        return bk["total"] > 0 and bk["assessed"] == bk["total"]

    t1, t2, t3, s = buckets["t1"], buckets["t2"], buckets["t3"], buckets["story"]
    # graduated: each tier requires the previous to be ready first.
    t1_ready = _ready(t1)
    t2_ready = t1_ready and _ready(t2)
    t3_ready = t2_ready and _ready(t3)
    stories_active = s["assessed"] > 0
    stories_ready  = _ready(s)

    if   t3_ready: tier_level = "t3"
    elif t2_ready: tier_level = "t2"
    elif t1_ready: tier_level = "t1"
    else:          tier_level = "none"

    # ---- overall (engagement-active) ---------------------------------------
    # Stories don't count toward the overall denominator unless the user has
    # actually engaged. This is the engagement-active rule.
    if stories_active:
        overall_assessed = t1["assessed"] + t2["assessed"] + t3["assessed"] + s["assessed"]
        overall_total    = t1["total"]    + t2["total"]    + t3["total"]    + s["total"]
        overall_pending  = t1["pending"] + t2["pending"] + t3["pending"] + s["pending"]
    else:
        overall_assessed = t1["assessed"] + t2["assessed"] + t3["assessed"]
        overall_total    = t1["total"]    + t2["total"]    + t3["total"]
        overall_pending  = t1["pending"] + t2["pending"] + t3["pending"]
    overall_ready = t3_ready and (not stories_active or stories_ready)

    return {
        "status":         "ready" if overall_ready else "in_progress",
        "tier_level":     tier_level,
        "stories_active": stories_active,
        "assessed":       overall_assessed,
        "total":          overall_total,
        "pending":        overall_pending,
        "tier_progress": {
            "t1": {**t1, "ready": _ready(t1)},
            "t2": {**t2, "ready": _ready(t2)},
            "t3": {**t3, "ready": _ready(t3)},
        },
        "stories_progress": {
            **s,
            "ready":  stories_ready,
            "active": stories_active,
        },
    }


def _job_dict(conn, job_id):
    """Build the full job dict for one id, or None if it does not exist.

    Shape: {id, name, slot, ready_at, values, status}. `values` is a flat
    map keyed "<variable_id>.<entry_no>". `status` is the readiness object
    from compute_job_status -- 'ready' / 'in_progress' plus the pending
    list. `ready_at` is the timestamp the job most recently entered ready
    (NULL while in_progress). Companion of _lens_dict() and _cluster_dict().

    Derived variables (those carrying a recipe in p1_variables.derived)
    are computed FROM the stored map after it is read, and the computed
    value REPLACES whatever was in the DB. The DB column stays writable
    so downstream JOINs can read it cheaply, but the SCREEN always sees
    the freshly-computed result.
    """
    row = conn.execute(
        "SELECT id, name, slot, ready_at FROM jobs WHERE id = ?",
        (job_id,)).fetchone()
    if row is None:
        return None
    job = dict(row)
    stored_pairs = [(r["variable_id"], r["entry_no"], r["value"]) for r in
        conn.execute(
            "SELECT variable_id, entry_no, value FROM p1_variable_values "
            "WHERE job_id = ? ORDER BY variable_id, entry_no", (job_id,))]
    stored_map = {(vid, e): val for (vid, e, val) in stored_pairs}
    # entry counts per section — same derivation as compute_job_status
    recipes = _derived_recipes(conn)
    homes   = _variable_homes(conn)
    section_vids = {}
    section_is_rep = {}
    for vid, (section, repeats) in homes.items():
        section_vids.setdefault(section, set()).add(vid)
        section_is_rep[section] = bool(repeats)
    section_N = {}
    for section, vids in section_vids.items():
        if section_is_rep.get(section):
            es = [e for (vid, e) in stored_map if vid in vids]
            section_N[section] = max(es) if es else 1
        else:
            section_N[section] = 1
    # apply derivations — overwrite stored values for every derived (vid, e).
    # Use None (rather than popping) when the recipe can't yet compute, so
    # the values dict has the same shape regardless of whether a variable
    # is user-entered or derived: 79 keys, some still None.  Callers that
    # check `.get("52.1")` see None either way; callers that iterate the
    # dict don't have to special-case missing keys.
    values = {"%d.%d" % (vid, e): val for (vid, e, val) in stored_pairs}
    for vid, recipe in recipes.items():
        section, repeats = homes[vid]
        N = section_N.get(section, 1) if repeats else 1
        for e in range(1, N + 1):
            computed = compute_derived_value(recipe, e, stored_map, section_N)
            key = "%d.%d" % (vid, e)
            values[key] = str(computed) if computed is not None else None
    job["values"] = values
    job["status"] = compute_job_status(conn, job_id)
    return job


def list_jobs(status_filter=None):
    """Return every job as {id, name, slot, ready_at, status, tier_level,
    stories_active}, ordered by id.

    The lightweight list -- no variable values -- for a screen that only
    needs to know which jobs exist and where each one stands. `status` is
    the overall readiness string ('ready' / 'in_progress'); `tier_level`
    is the graduated state ('none' / 't1' / 't2' / 't3'); `stories_active`
    flags whether any story field has content.  `ready_at` is the
    timestamp the job most recently entered overall-ready (NULL while
    in_progress).  Full pending detail lives on the single-job GET.

    `status_filter`, when given, drops rows whose status does not match.
    The eventual Phase 5 formula engine calls this with status_filter='ready'
    to get its input set; the rest of the app calls it with no filter.
    An invalid filter is ignored (returns all rows).

    The BASE control job is included; a screen that wants to hide it
    filters it out itself.
    """
    if status_filter is not None and status_filter not in ("ready", "in_progress"):
        status_filter = None
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, slot, ready_at FROM jobs ORDER BY id").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            stat = compute_job_status(conn, r["id"])
            if stat:
                d["status"]         = stat["status"]
                d["tier_level"]     = stat["tier_level"]
                d["stories_active"] = stat["stories_active"]
            else:
                d["status"]         = "in_progress"
                d["tier_level"]     = "none"
                d["stories_active"] = False
            if status_filter is None or d["status"] == status_filter:
                out.append(d)
        return out


def get_job(job_id):
    """Return one job in full -- {id, name, slot, values} -- or None
    if no job has that id. The single-job companion of list_jobs()."""
    with _connect() as conn:
        return _job_dict(conn, job_id)


def create_job(name, slot=None):
    """Create one job and return its dict, the new id included.

    The write is two parts in one transaction: the `jobs` row, then a
    blank p1_variable_values row for every Index variable. Seeding the
    blank skeleton up front -- every variable present, every value
    NULL -- means save_job never has to wonder whether a row exists. A
    duplicate name is reported as a plain ValueError rather than a raw
    UNIQUE-constraint failure.
    """
    _check_job_name(name)
    _check_job_slot(slot)
    with _connect() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO jobs (name, slot) VALUES (?, ?)", (name, slot))
        except sqlite3.IntegrityError:
            raise ValueError("a job named %r already exists" % (name,))
        job_id = cursor.lastrowid              # the id SQLite just assigned
        variable_ids = [r["id"] for r in
                        conn.execute("SELECT id FROM p1_variables")]
        conn.executemany(
            "INSERT INTO p1_variable_values "
            "(job_id, variable_id, entry_no, value) VALUES (?, ?, 1, NULL)",
            [(job_id, vid) for vid in variable_ids])
        return _job_dict(conn, job_id)


def save_job(job_id, name, slot, values, entries=None):
    """Save one job: update its name and slot, write the answers in
    `values`, and (optionally) trim repeating variables to the cardinality
    declared in `entries`. Return the updated job dict, or None if no job
    has that id.

    `values` is a dict keyed "<variable_id>.<entry_no>" -- see
    _parse_value_keys(). The entries it carries are upserted in place; a
    brand-new entry, like the third role on a job that had two, is created
    on the spot.

    `entries` is the cardinality declaration -- {"<vid>": N} -- saying
    "this repeating variable has exactly N entries; drop anything beyond."
    The frontend builds it from the form's current shape, so the database
    matches what the user sees. Without it, save_job is a pure upsert: the
    intake's partial apply, the data.py self-tests, and any caller that
    only wants to add values omits `entries` and nothing is removed.

    Order matters: the entry caps fire FIRST (DELETE), then the upserts
    write. A value at entry > its declared count is a caller mistake and
    raises before the database is touched. One transaction.
    """
    _check_job_name(name)
    _check_job_slot(slot)
    parsed = _parse_value_keys(values)
    parsed_entries = _parse_entries(entries)
    caps = {vid: count for vid, count in parsed_entries}
    for variable_id, entry_no, value in parsed:
        if variable_id in caps and entry_no > caps[variable_id]:
            raise ValueError(
                "value at entry %d exceeds the declared entry count %d "
                "for variable #%d" % (entry_no, caps[variable_id], variable_id))
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if exists is None:
            return None
        _check_value_refs(conn, parsed)
        _check_entries_refs(conn, parsed_entries)
        # The server owns derived variables — any incoming value for one
        # is silently dropped. Intake cards, manual saves, automation:
        # all funnel through here, so there is exactly one place to
        # enforce the rule.  After the user-written values land, the
        # final pass below RECOMPUTES every derived (vid, entry) and
        # writes the freshly-computed result back to the DB so the
        # column stays queryable for downstream lens JOINs.
        derived_ids = set(_derived_recipes(conn).keys())
        parsed = [(vid, e, v) for (vid, e, v) in parsed
                  if vid not in derived_ids]
        try:
            conn.execute("UPDATE jobs SET name = ?, slot = ? WHERE id = ?",
                         (name, slot, job_id))
        except sqlite3.IntegrityError:
            raise ValueError("a job named %r already exists" % (name,))
        # apply the cardinality caps first -- entries above N are removed
        for vid, count in parsed_entries:
            conn.execute(
                "DELETE FROM p1_variable_values "
                "WHERE job_id = ? AND variable_id = ? AND entry_no > ?",
                (job_id, vid, count))
        # then upsert every value the caller sent
        for variable_id, entry_no, value in parsed:
            conn.execute(
                "INSERT INTO p1_variable_values "
                "(job_id, variable_id, entry_no, value) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (job_id, variable_id, entry_no) "
                "DO UPDATE SET value = excluded.value",
                (job_id, variable_id, entry_no, normalize_value(value)))
        # Recompute every derived variable now that user-written values
        # have landed.  We READ the just-saved state, compute each recipe,
        # and write the result back to the DB. This keeps the DB column
        # queryable for downstream lens JOINs while leaving the engine
        # as the only authority on the value.
        _recompute_derived(conn, job_id)
        # stamp ready_at on the transition into ready, clear on the way out.
        # COALESCE preserves an existing timestamp across re-saves while still
        # ready -- so the value reads as "ready since when," not "last saved
        # at." When a value drops out and status slides back to in_progress,
        # ready_at clears, and the next ready transition gets a fresh stamp.
        status = compute_job_status(conn, job_id)
        if status and status["status"] == "ready":
            conn.execute(
                "UPDATE jobs SET ready_at = COALESCE(ready_at, datetime('now')) "
                "WHERE id = ?", (job_id,))
        else:
            conn.execute("UPDATE jobs SET ready_at = NULL WHERE id = ?",
                         (job_id,))
        return _job_dict(conn, job_id)


def delete_job(job_id):
    """Delete one job and all of its variable values.

    Return True if a job was removed, False if no job had that id. The
    value rows are deleted explicitly rather than left to ON DELETE
    CASCADE, so this stays correct even if foreign-key enforcement is
    ever off -- the belt-and-braces rule delete_lens follows too.
    """
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if exists is None:
            return False
        conn.execute("DELETE FROM p1_variable_values WHERE job_id = ?",
                     (job_id,))
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return True


# --------------------------------------------------------------
# A tiny self-test. Runs only if you do:  python data.py
# It does NOT run when app.py imports this file. That is what the
# `if __name__ == "__main__"` check below means -- a standard
# Python idiom for "only when this file is the one being run".
# --------------------------------------------------------------
if __name__ == "__main__":
    print(f"Database: {DB_PATH}")
    for name in list_tables():
        print(f"  {name}: {count_rows(name)} rows, "
              f"columns = {get_columns(name)}")
    print(f"  API shapes: {len(get_variables())} variables, "
          f"{len(get_output_kinds())} output kinds, "
          f"{len(get_lenses())} lenses")

    # ---- Phase 3 self-test: create -> read -> update -> delete one lens.
    # It runs against the real synthesis.db and cleans up after itself --
    # the lens it makes is deleted again, so p2_formulas ends exactly where
    # it started. (One harmless trace remains: the AUTOINCREMENT counter
    # advances by one, so the next real lens will not be id 1. That is
    # normal SQLite behaviour and costs nothing.)
    print("\nPhase 3 write self-test:")
    start_count = count_rows("p2_formulas")
    made = None
    try:
        made = create_lens(
            name="SELF-TEST lens", status="Active", section="Personal Info",
            lens="a throwaway lens written by data.py's self-test",
            inputs=[1, 3, 47], output_kinds=[1, 4])
        print(f"  create  -> #{made['id']}  inputs={made['inputs']}  "
              f"output_kinds={made['output_kinds']}")

        echo = get_lens(made["id"])
        assert echo == made, "get_lens did not return what create_lens stored"
        print(f"  read    -> #{echo['id']}  matches what was created")

        edited = update_lens(
            made["id"], name="SELF-TEST lens (edited)", status="Inactive",
            section="Story", lens="edited lens text",
            inputs=[2, 2, 5], output_kinds=[9])
        assert edited["status"] == "Inactive"
        assert edited["inputs"] == [2, 5], "duplicate input should de-dup"
        print(f"  update  -> #{edited['id']}  status={edited['status']}  "
              f"inputs={edited['inputs']}  output_kinds={edited['output_kinds']}")

        assert delete_lens(made["id"]) is True, "delete should report success"
        assert get_lens(made["id"]) is None, "lens should be gone after delete"
        assert delete_lens(made["id"]) is False, "deleting a gone lens is False"
        made = None
        end_count = count_rows("p2_formulas")
        assert end_count == start_count, (
            f"row count drifted: {start_count} -> {end_count}")
        print(f"  delete  -> p2_formulas back to {end_count} rows")
        print("  CRUD round trip OK -- the data layer can write a lens.")
    finally:
        # belt and braces: if an assert above failed, the lens still exists.
        # Remove it so a failed run never leaves test data in the database.
        if made is not None:
            delete_lens(made["id"])
            print("  (cleaned up the test lens after a failed run)")

    # ---- cluster self-test: create -> read -> delete one cluster.
    # Same shape as the lens test above, and just as tidy -- the cluster
    # it makes is deleted again, so p2_clusters ends where it started.
    print("\nCluster write self-test:")
    cluster_start = count_rows("p2_clusters")
    cluster_made = None
    try:
        cluster_made = create_cluster(
            name="SELF-TEST cluster", variables=[3, 3, 8, 47])
        print(f"  create  -> #{cluster_made['id']}  "
              f"variables={cluster_made['variables']}")
        assert cluster_made["variables"] == [3, 8, 47], (
            "duplicate variable should de-dup")

        echo = get_cluster(cluster_made["id"])
        assert echo == cluster_made, (
            "get_cluster did not return what create_cluster stored")
        print(f"  read    -> #{echo['id']}  matches what was created")

        assert delete_cluster(cluster_made["id"]) is True, (
            "delete should report success")
        assert get_cluster(cluster_made["id"]) is None, (
            "cluster should be gone after delete")
        assert delete_cluster(cluster_made["id"]) is False, (
            "deleting a gone cluster is False")
        cluster_made = None
        cluster_end = count_rows("p2_clusters")
        assert cluster_end == cluster_start, (
            f"row count drifted: {cluster_start} -> {cluster_end}")
        print(f"  delete  -> p2_clusters back to {cluster_end} rows")
        print("  CRUD round trip OK -- the data layer can write a cluster.")
    finally:
        if cluster_made is not None:
            delete_cluster(cluster_made["id"])
            print("  (cleaned up the test cluster after a failed run)")

    # ---- job self-test: create -> read -> save -> delete one job.
    # The same shape as the lens and cluster tests above, and just as
    # tidy -- the job it makes is deleted again, so `jobs` ends exactly
    # where it started. jobs.name is UNIQUE, so any "SELF-TEST job" left
    # behind by a failed earlier run is cleared first; otherwise the
    # create below would collide with the leftover.
    print("\nJob write self-test:")
    for _stale in list_jobs():
        if _stale["name"] == "SELF-TEST job":
            delete_job(_stale["id"])
            print("  (cleared a SELF-TEST job left by an earlier run)")
    job_start = count_rows("jobs")
    job_made = None
    try:
        job_made = create_job(name="SELF-TEST job", slot=99)
        blanks = len(job_made["values"])
        print(f"  create  -> #{job_made['id']}  slot={job_made['slot']}  "
              f"{blanks} blank value rows")
        assert blanks == count_rows("p1_variables"), (
            "a fresh job should have one value row per Index variable")
        assert all(v is None for v in job_made["values"].values()), (
            "every value on a fresh job should be blank")

        echo = get_job(job_made["id"])
        assert echo == job_made, "get_job did not return what create_job stored"
        print(f"  read    -> #{echo['id']}  matches what was created")

        saved = save_job(
            job_made["id"], name="SELF-TEST job (saved)", slot=98,
            values={"1.1": "Privately held", "2.1": "Test Co LLC",
                    "54.1": "Floor Worker", "54.2": "Sales Manager"})
        assert saved["name"] == "SELF-TEST job (saved)", "name should update"
        assert saved["slot"] == 98, "slot should update"
        assert saved["values"]["1.1"] == "Privately held"
        assert saved["values"]["2.1"] == "Test Co LLC"
        assert saved["values"]["54.1"] == "Floor Worker", "role entry 1 stored"
        assert saved["values"]["54.2"] == "Sales Manager", "role entry 2 stored"
        assert saved["values"]["3.1"] is None, (
            "a variable not in the values dict should stay blank")
        print(f"  save    -> #{saved['id']}  name={saved['name']!r}  "
              f"slot={saved['slot']}  -- #54 carries 2 role entries")

        # a non-repeating variable cannot take a second entry
        try:
            save_job(job_made["id"], "SELF-TEST job (saved)", 98,
                     {"1.2": "a second disclosure?"})
            assert False, "entry 2 on a singular variable should raise"
        except ValueError:
            print("  guard   -> entry 2 on a singular variable is rejected")

        # the entries map shrinks cardinality -- entry 2 of #54 should drop
        trimmed = save_job(
            job_made["id"], name="SELF-TEST job (saved)", slot=98,
            values={}, entries={"54": 1})
        assert "54.1" in trimmed["values"], "entry 1 of #54 survives the trim"
        assert "54.2" not in trimmed["values"], "entry 2 of #54 was dropped"
        print("  remove  -> entries={54:1} dropped #54.2 from the DB")

        # sentinel normalisation: case-insensitive input -> canonical "N/A"
        sentinel_test = save_job(
            job_made["id"], name="SELF-TEST job (saved)", slot=98,
            values={"5.1": "N/A", "15.1": "n/a", "1.1": "N/a"})
        assert sentinel_test["values"]["5.1"] == "N/A", "N/A on #5 stays canonical"
        assert sentinel_test["values"]["15.1"] == "N/A", "'n/a' normalised to 'N/A'"
        assert sentinel_test["values"]["1.1"] == "N/A", "'N/a' normalised to 'N/A'"
        assert get_sentinels() == ["N/A"], "get_sentinels exposes the list"
        assert is_sentinel("n/a") and not is_sentinel("hello"), "is_sentinel works"
        print("  sentinel-> N/A normalised to canonical form across cases")

        # entries cannot declare a count on a singular variable
        try:
            save_job(job_made["id"], "SELF-TEST job (saved)", 98,
                     {}, entries={"1": 1})
            assert False, "entries on a singular variable should raise"
        except ValueError:
            print("  guard   -> entries on a singular variable is rejected")

        # readiness: a job is 'ready' only when every (variable, entry) is touched
        n_vars = count_rows("p1_variables")
        fresh = create_job(name="STATUS-TEST job", slot=97)
        try:
            assert fresh["status"]["status"] == "in_progress", \
                "a freshly created job is in_progress"
            assert fresh["status"]["assessed"] == 0
            assert fresh["status"]["total"] == n_vars
            assert len(fresh["status"]["pending"]) == n_vars
            # marking every variable N/A at entry 1 satisfies the rule
            filled = save_job(
                fresh["id"], name="STATUS-TEST job", slot=97,
                values={"%d.1" % vid: "N/A" for vid in range(1, n_vars + 1)})
            assert filled["status"]["status"] == "ready", \
                "every-variable-N/A job is ready"
            assert filled["status"]["assessed"] == n_vars
            assert filled["status"]["pending"] == []
            print("  status  -> fresh job is in_progress; all-N/A job is ready")
        finally:
            delete_job(fresh["id"])

        assert save_job(999999, "ghost", None, {}) is None, (
            "saving a non-existent job should return None")

        assert delete_job(job_made["id"]) is True, "delete should report success"
        assert get_job(job_made["id"]) is None, "job should be gone after delete"
        assert delete_job(job_made["id"]) is False, (
            "deleting a gone job should be False")
        job_made = None
        job_end = count_rows("jobs")
        assert job_end == job_start, (
            f"row count drifted: {job_start} -> {job_end}")
        print(f"  delete  -> jobs back to {job_end} rows")
        print("  CRUD round trip OK -- the data layer can write a job.")
    finally:
        # belt and braces: if an assert above failed, the job still exists.
        if job_made is not None:
            delete_job(job_made["id"])
            print("  (cleaned up the test job after a failed run)")
