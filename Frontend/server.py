"""
server.py  --  THE WEB LAYER
==============================================================
This file is the bridge between the Synthesis Workbench (which
runs in a browser) and synthesis.db (which a browser cannot open
on its own). It is a small Flask program. Its job:

  - serve the workbench page itself
  - turn the workbench's HTTP requests into data.py calls
  - hand the answers back as JSON

It contains NO SQL. When it needs data it asks data.py -- the
very same data layer the Tkinter app uses. Three layers, one
rule: each layer only talks to the layer directly below it.

   browser  ->  server.py  ->  data.py  ->  synthesis.db
   (HTTP)       (this file)   (the SQL)     (the database)

HOW TO RUN IT:
    1. Open a terminal in this folder (the Frontend folder).
    2. Type:   python server.py
    3. It prints a line like "Running on http://127.0.0.1:5000".
    4. Open that address in your browser -- the workbench loads.
    5. Stop the server later with Ctrl+C in the terminal.

ENDPOINTS:
    GET    /                  the start screen (the app's home)
    GET    /formulas          the workbench — Pages 1 & 2
    GET    /profile           the Personal Profile page
    GET    /job               the job editor — a company's three sheets
    GET    /api/variables     the Index variables
    GET    /api/output-kinds  the 9 output kinds
    GET    /api/sentinels     the reserved sentinel values (N/A, ...)
    GET    /api/lenses        every lens
    POST   /api/lenses        create a lens          (Phase 3)
    PUT    /api/lenses/<id>   update the lens <id>    (Phase 3)
    DELETE /api/lenses/<id>   delete the lens <id>    (Phase 3)
    GET    /api/clusters      every cluster          (hardening)
    POST   /api/clusters      create a cluster       (hardening)
    DELETE /api/clusters/<id> delete the cluster <id> (hardening)
    GET    /api/jobs          every job — the Work Experience list
    GET    /api/jobs/<id>     one job in full, with its 88 answers
    POST   /api/jobs          create a job           (the river)
    PUT    /api/jobs/<id>     save the job <id>      (the river)
    DELETE /api/jobs/<id>     delete the job <id>    (the river)

The GET endpoints are Phase 1. The POST/PUT/DELETE endpoints are
Phase 3 -- the server can now be TOLD to change the database, not
just read it. The workbench itself starts USING them in Phase 4.
The /api/jobs endpoints are "the river" -- the same read/write reach
for a job that the lens routes give a lens; the job page uses them.
"""

from pathlib import Path

from flask import Flask, jsonify, request, send_file

import data  # the data layer -- the only code that speaks SQL

app = Flask(__name__)

# The folder this file lives in (the Frontend folder), as an absolute
# path -- so the server finds workbench.html no matter which folder it
# happens to be launched from.
HERE = Path(__file__).resolve().parent


@app.route("/")
def home():
    """Serve the start screen -- the app's front door, shown first on launch."""
    return send_file(HERE / "start.html")


@app.route("/formulas")
def formulas():
    """Serve the workbench -- Pages 1 & 2, the 88-Index and the lens warehouse."""
    return send_file(HERE / "workbench.html")


@app.route("/profile")
def profile():
    """Serve the Personal Profile page -- work experience and a job's three
    sheets. A stub for now; the Personal Profile river is built next."""
    return send_file(HERE / "profile.html")


@app.route("/job")
def job():
    """Serve the job editor -- a company's three sheets (the 88-variable
    Index laid out to fill in). The Personal Profile river; the look and
    design are built, saving to the database is not wired yet."""
    return send_file(HERE / "job.html")


@app.route("/api/variables")
def api_variables():
    """The 88 Index variables, as JSON."""
    return jsonify(data.get_variables())


@app.route("/api/output-kinds")
def api_output_kinds():
    """The 9 output kinds, as JSON."""
    return jsonify(data.get_output_kinds())


@app.route("/api/sentinels")
def api_sentinels():
    """The reserved sentinel values -- e.g. "N/A" -- that bypass type
    validation everywhere in the workbench. The frontend fetches this on
    boot so the list is never hardcoded; data.py's SENTINELS constant is
    the one source of truth. Adding a sentinel there exposes it here
    automatically."""
    return jsonify(data.get_sentinels())


@app.route("/api/lenses")
def api_lenses():
    """Every lens, each with its input and output-kind id lists, as JSON."""
    return jsonify(data.get_lenses())


# --------------------------------------------------------------
# WRITE ENDPOINTS  (Phase 3)
# --------------------------------------------------------------
# These let the workbench CHANGE the database, not just read it.
# Each one does the same three steps: read the request, ask data.py
# to do the work, hand back JSON. server.py still contains NO SQL --
# it only translates between HTTP and data.py function calls.
#
# What the status codes mean:
#   200 OK         -- done; body is the lens (or a small confirmation)
#   201 Created    -- a POST succeeded; body is the new lens, with its id
#   400 Bad Request-- the request was malformed (bad field, unknown
#                     variable id, ...); body is {"error": "why"}
#   404 Not Found  -- no lens has that id; body is {"error": "why"}


def _lens_from_request():
    """Pull the six lens fields out of the JSON request body.

    Returns a dict ready to hand to data.create_lens / update_lens.
    Raises ValueError if the body is not a JSON object or has no
    `name`; the routes below turn that ValueError into an HTTP 400.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("request body must be a JSON object")
    if "name" not in body:
        raise ValueError("a lens needs a 'name'")
    return {
        "name": body["name"],
        "status": body.get("status", "Active"),
        "section": body.get("section", ""),
        "lens": body.get("lens", ""),
        "inputs": body.get("inputs", []),
        "output_kinds": body.get("output_kinds", []),
        "intake_code": body.get("intake_code"),   # None unless from an intake card
    }


@app.route("/api/lenses", methods=["POST"])
def api_create_lens():
    """Create a lens. Body: a lens with no id. Returns the new lens
    -- id included -- with 201, or {"error": ...} with 400."""
    try:
        f = _lens_from_request()
        lens = data.create_lens(f["name"], f["status"], f["section"],
                                f["lens"], f["inputs"], f["output_kinds"],
                                f["intake_code"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(lens), 201


@app.route("/api/lenses/<int:formula_id>", methods=["PUT"])
def api_update_lens(formula_id):
    """Update the lens with this id. Body: the lens's new fields.
    Returns the updated lens; 404 if the id is unknown; 400 if the
    request body is malformed."""
    try:
        f = _lens_from_request()
        lens = data.update_lens(formula_id, f["name"], f["status"],
                                f["section"], f["lens"], f["inputs"],
                                f["output_kinds"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if lens is None:
        return jsonify({"error": f"no lens has id {formula_id}"}), 404
    return jsonify(lens)


@app.route("/api/lenses/<int:formula_id>", methods=["DELETE"])
def api_delete_lens(formula_id):
    """Delete the lens with this id. Returns {"deleted": id}, or 404
    if no lens has that id."""
    if data.delete_lens(formula_id):
        return jsonify({"deleted": formula_id})
    return jsonify({"error": f"no lens has id {formula_id}"}), 404


# --------------------------------------------------------------
# CLUSTER ENDPOINTS  (hardening — clusters move into the database)
# --------------------------------------------------------------
# A cluster is a saved bundle of Index variables. These three
# endpoints give it the same database-backed life a lens has: list
# them, create one, delete one. Same rule as the lens routes -- no
# SQL here, only translation between HTTP and data.py calls. There is
# no PUT: the workbench never edits a cluster in place, it only adds
# a cluster and removes one.


@app.route("/api/clusters")
def api_clusters():
    """Every cluster, each with its variable id list, as JSON."""
    return jsonify(data.get_clusters())


@app.route("/api/clusters", methods=["POST"])
def api_create_cluster():
    """Create a cluster. Body: {name, variables:[ids]}. Returns the new
    cluster -- id included -- with 201, or {"error": ...} with 400."""
    try:
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or "name" not in body:
            raise ValueError("a cluster needs a 'name'")
        cluster = data.create_cluster(body["name"],
                                      body.get("variables", []),
                                      body.get("intake_code"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(cluster), 201


@app.route("/api/clusters/<int:cluster_id>", methods=["DELETE"])
def api_delete_cluster(cluster_id):
    """Delete the cluster with this id. Returns {"deleted": id}, or 404
    if no cluster has that id."""
    if data.delete_cluster(cluster_id):
        return jsonify({"deleted": cluster_id})
    return jsonify({"error": f"no cluster has id {cluster_id}"}), 404


# --------------------------------------------------------------
# JOB ENDPOINTS  ("the river" — the job page reaches the database)
# --------------------------------------------------------------
# A job is the spine of the machine: one company's three sheets of
# answers. These five endpoints give the job page the same reach the
# lens routes give the workbench -- list, read one, create, save,
# delete. Same rule: NO SQL here, only translation between HTTP and
# data.py calls.
#
# A brand-new job is born in TWO steps, by design. POST creates it
# blank -- its name and its slot, plus the 88 empty answer rows. PUT
# then saves the answers into it. Keeping create and save apart maps
# each endpoint to exactly one data.py function and one transaction,
# so a failed save can never leave a half-written job behind.


def _job_from_request():
    """Pull the job fields out of the JSON request body.

    Returns {name, slot, values, entries}. `values` and `entries` are
    passed straight through; their keys are validated in data.py
    (_parse_value_keys, _parse_entries), the single place a malformed key
    surfaces -- which the routes below turn into an HTTP 400. This
    function raises only when the body is not a JSON object, carries no
    `name`, or has a `values` / `entries` field of the wrong JSON type.

    `entries` is the optional cardinality declaration on the PUT body --
    {"<vid>": N} -- saying "this repeating variable has exactly N
    entries." The frontend builds it from the form's current shape so
    the database matches what the user sees, including Removes.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError("request body must be a JSON object")
    if "name" not in body:
        raise ValueError("a job needs a 'name'")
    values = body.get("values", {})
    if not isinstance(values, dict):
        raise ValueError("'values' must be a JSON object of "
                         "'<id>.<entry>' -> answer")
    entries = body.get("entries", {})
    if not isinstance(entries, dict):
        raise ValueError("'entries' must be a JSON object of "
                         "'<id>' -> count")
    return {
        "name": body["name"],
        "slot": body.get("slot"),                  # None unless placed
        "values": values,
        "entries": entries,
    }


@app.route("/api/jobs")
def api_jobs():
    """Every job as {id, name, slot, ready_at, status}, as JSON -- the Work
    Experience list. Optional ?status=ready or ?status=in_progress query
    parameter filters the result set; the eventual Phase 5 formula engine
    calls with status=ready to get its input set. Invalid filter values are
    ignored, so a bad query string cannot crash the endpoint."""
    return jsonify(data.list_jobs(request.args.get("status")))


@app.route("/api/jobs/<int:job_id>")
def api_job(job_id):
    """One job in full -- {id, name, slot, values} -- as JSON.
    404 if no job has that id."""
    job = data.get_job(job_id)
    if job is None:
        return jsonify({"error": f"no job has id {job_id}"}), 404
    return jsonify(job)


@app.route("/api/jobs", methods=["POST"])
def api_create_job():
    """Create a job. Body: {name, slot?}. Returns the new job -- a blank
    skeleton with all 88 answers empty, id included -- with 201, or
    {"error": ...} with 400. The answers are written afterwards via PUT."""
    try:
        f = _job_from_request()
        job = data.create_job(f["name"], f["slot"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(job), 201


@app.route("/api/jobs/<int:job_id>", methods=["PUT"])
def api_save_job(job_id):
    """Save the job with this id. Body: {name, slot, values, entries?}.
    The optional `entries` map declares the cardinality of repeating
    variables -- {"<vid>": N} -- and trims anything beyond N. Returns the
    updated job; 404 if the id is unknown; 400 if the body is malformed."""
    try:
        f = _job_from_request()
        job = data.save_job(job_id, f["name"], f["slot"], f["values"],
                            f["entries"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if job is None:
        return jsonify({"error": f"no job has id {job_id}"}), 404
    return jsonify(job)


@app.route("/api/jobs/<int:job_id>", methods=["DELETE"])
def api_delete_job(job_id):
    """Delete the job with this id. Returns {"deleted": id}, or 404
    if no job has that id."""
    if data.delete_job(job_id):
        return jsonify({"deleted": job_id})
    return jsonify({"error": f"no job has id {job_id}"}), 404


if __name__ == "__main__":
    # Before the HTTP server opens, verify the database has every column
    # the app expects. data.verify_schema() raises SchemaOutOfDate when a
    # column added by a later build_synthesis_db.py run is missing — the
    # message tells the user exactly what to run. Catching it here means
    # the user sees a one-line "do this" prompt instead of a Flask stack
    # trace on the first /api/... request.
    import sys
    try:
        data.verify_schema()
    except data.SchemaOutOfDate as e:
        print("\n  SCHEMA OUT OF DATE\n  " + str(e).replace("\n", "\n  ") + "\n")
        sys.exit(1)

    # debug=True gives helpful error pages in the browser and auto-reloads
    # the server whenever you save a change to this file -- handy while
    # building. Turn it off when you package the app for real use.
    app.run(port=5000, debug=True)
