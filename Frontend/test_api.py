"""
test_api.py  --  THE AUTOMATED TEST SUITE
==============================================================
Run this and it answers one question: does the API still work?

    python test_api.py

It exercises every endpoint -- the reads, and the lens, cluster, and
job writes -- and checks each answer. It prints a PASS or a FAIL line
per check, then a final tally. Exit code 0 means everything passed; a
non-zero exit code means something is broken.

WHY A TEST FILE EXISTS
This is the safety net. Before this file, the only way to know a
change had not broken something was to click through the whole app
by hand and hope. Now one command checks the entire API in about a
second. Run it after every change to data.py or server.py -- if it
still says all passed, the read/write path is intact.

IT NEVER TOUCHES THE REAL DATABASE
The suite copies synthesis.db to a throwaway temporary file and
points the data layer at the copy. Every lens and every cluster it
creates lives and dies inside that copy; the real synthesis.db is
never opened for writing. So this is safe to run any time, as often
as you like, with the app open or closed.
"""

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import data    # imported first, so we can read its real DB path...
import server  # ...and server.py imports this very same data module

# ---- build the throwaway test database -----------------------------
# Copy the real synthesis.db into a temp folder, then point the data
# layer at the copy. From here on every data.py / server.py call
# reads and writes the COPY -- the real database is left untouched.
REAL_DB = Path(data.DB_PATH)
TMP_DIR = Path(tempfile.mkdtemp(prefix="synthesis_test_"))
TEST_DB = TMP_DIR / "synthesis_test.db"
shutil.copy(REAL_DB, TEST_DB)

# Make sure the cluster tables exist in the copy. If the real database
# has not been rebuilt since the cluster tables were added to
# build_synthesis_db.py, the copy would lack them -- so we create them
# here. IF NOT EXISTS makes this harmless when they are already there.
_con = sqlite3.connect(TEST_DB)
_con.executescript("""
    CREATE TABLE IF NOT EXISTS p2_clusters (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        intake_code TEXT
    );
    CREATE TABLE IF NOT EXISTS p2_cluster_variables (
        cluster_id  INTEGER NOT NULL REFERENCES p2_clusters(id) ON DELETE CASCADE,
        variable_id INTEGER NOT NULL REFERENCES p1_variables(id),
        PRIMARY KEY (cluster_id, variable_id)
    );
""")
# Make sure the jobs table has the `slot` column (added with the job
# endpoints). If the real database has not been rebuilt since, the copy
# would lack it -- so we add it here. The guard makes this a no-op when
# the column is already present, the same way IF NOT EXISTS does above.
if "slot" not in [r[1] for r in _con.execute('PRAGMA table_info("jobs")')]:
    _con.execute("ALTER TABLE jobs ADD COLUMN slot INTEGER")
_con.commit()
_con.close()

data.DB_PATH = TEST_DB                # the data layer now uses the copy
client = server.app.test_client()     # a fake browser -- no real network

# ---- the check machinery -------------------------------------------
# Every test calls check(condition, label): it records a PASS or a
# FAIL and prints the line. The tally is reported at the very end.
_passed = 0
_failed = 0


def check(condition, label):
    """Record one test result and print it."""
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {label}")
    else:
        _failed += 1
        print(f"  FAIL  {label}")


def run_tests():
    """Every check, in order: reads first, then the three write cycles."""

    # ---- reads ------------------------------------------------------
    print("Reads:")
    r = client.get("/api/variables")
    check(r.status_code == 200, "GET /api/variables -> 200")
    all_vars_ = r.get_json()
    check(len(all_vars_) == 79, "  ...returns all 79 Index variables")
    # R8 — every variable carries a tier in {1,2,3}, and the 7/19/53 split
    # documented in build_synthesis_db.VARIABLE_TIERS is preserved end-to-end.
    check(all("tier" in v and v["tier"] in (1, 2, 3) for v in all_vars_),
          "  ...every variable carries a tier in {1,2,3}")
    _tier_counts = {1: 0, 2: 0, 3: 0}
    for _v in all_vars_:
        _tier_counts[_v["tier"]] += 1
    check(_tier_counts == {1: 7, 2: 19, 3: 53},
          "  ...tier counts are 7 T1 / 19 T2 / 53 T3 (got %r)" % _tier_counts)
    # Spot-check the anchors so a future retier doesn't silently slip:
    _by_id = {v["id"]: v for v in all_vars_}
    check(_by_id[1]["tier"]  == 1, "  ...disclosure (#1) is T1")
    check(_by_id[2]["tier"]  == 1, "  ...legal_name (#2) is T1")
    check(_by_id[10]["tier"] == 1, "  ...primary_industry (#10) is T1")
    check(_by_id[21]["tier"] == 3, "  ...market_cap (#21) is T3 (the niche example)")
    check(_by_id[20]["tier"] == 2, "  ...revenue (#20) is T2")
    # R8.J — every variable carries a `derived` field; three are server-
    # computed and the rest are NULL (user-entered).
    check(all("derived" in v for v in all_vars_),
          "  ...every variable carries a derived field")
    check(_by_id[51]["derived"] == "count:P1 Roles",
          "  ...#51 how_many_roles -> count:P1 Roles")
    check(_by_id[52]["derived"] == "duration:48,49",
          "  ...#52 tenure (overview) -> duration:48,49")
    check(_by_id[57]["derived"] == "duration:55,56",
          "  ...#57 tenure (per-role) -> duration:55,56")
    derived_count = sum(1 for v in all_vars_ if v["derived"] is not None)
    check(derived_count == 3,
          "  ...exactly 3 derived variables (got %d)" % derived_count)
    # R8.O — track classification. Story variables (#67-#79) are on the
    # 'story' track so they live in the Stories picker option, not in
    # the depth tiers. Every other variable is track=None.
    check(all("track" in v for v in all_vars_),
          "  ...every variable carries a track field")
    story_vars = [v for v in all_vars_ if v["track"] == "story"]
    check(len(story_vars) == 13,
          "  ...13 variables are on the story track (got %d)" % len(story_vars))
    story_ids = sorted(v["id"] for v in story_vars)
    check(story_ids == list(range(67, 80)),
          "  ...story track covers ids 67-79 (got %r)" % story_ids)
    # Spot-check: no CF/PI var is on the story track.
    non_story_tracked = [v for v in all_vars_
                         if v["track"] is not None and v["track"] != "story"]
    check(non_story_tracked == [],
          "  ...no unexpected tracks exist (got %r)" % non_story_tracked)

    r = client.get("/api/output-kinds")
    check(r.status_code == 200, "GET /api/output-kinds -> 200")
    check(len(r.get_json()) == 9, "  ...returns all 9 output kinds")

    r = client.get("/api/sentinels")
    check(r.status_code == 200, "GET /api/sentinels -> 200")
    sentinels = r.get_json()
    check(isinstance(sentinels, list) and "N/A" in sentinels,
          "  ...returns a list including 'N/A'")

    r = client.get("/api/lenses")
    check(r.status_code == 200, "GET /api/lenses -> 200")
    check(isinstance(r.get_json(), list), "  ...returns a list")

    r = client.get("/api/clusters")
    check(r.status_code == 200, "GET /api/clusters -> 200")
    check(isinstance(r.get_json(), list), "  ...returns a list")

    # ---- lens write cycle ------------------------------------------
    print("\nLens writes:")
    r = client.post("/api/lenses", json={
        "name": "TEST lens", "status": "Active", "section": "Personal Info",
        "lens": "a throwaway lens", "inputs": [1, 3, 47],
        "output_kinds": [1, 4]})
    check(r.status_code == 201, "POST /api/lenses -> 201")
    lens = r.get_json()
    check(isinstance(lens.get("id"), int), "  ...the new lens carries an id")
    lens_id = lens["id"]
    check(lens["inputs"] == [1, 3, 47], "  ...its inputs were stored")

    r = client.get("/api/lenses")
    check(any(l["id"] == lens_id for l in r.get_json()),
          "  ...it appears in GET /api/lenses")

    r = client.put(f"/api/lenses/{lens_id}", json={
        "name": "TEST lens (edited)", "status": "Inactive",
        "section": "Story", "lens": "edited", "inputs": [2, 5],
        "output_kinds": [9]})
    check(r.status_code == 200, f"PUT /api/lenses/{lens_id} -> 200")
    check(r.get_json()["status"] == "Inactive", "  ...the edit took effect")

    r = client.put("/api/lenses/999999", json={
        "name": "ghost", "status": "Active", "section": "", "lens": "",
        "inputs": [], "output_kinds": []})
    check(r.status_code == 404, "PUT a non-existent lens -> 404")

    r = client.post("/api/lenses", json={
        "name": "bad status", "status": "Maybe", "section": "",
        "lens": "", "inputs": [], "output_kinds": []})
    check(r.status_code == 400, "POST a lens with a bad status -> 400")

    r = client.post("/api/lenses", json={
        "name": "bad input", "status": "Active", "section": "",
        "lens": "", "inputs": [999], "output_kinds": []})
    check(r.status_code == 400,
          "POST a lens with an unknown variable id -> 400")

    r = client.delete(f"/api/lenses/{lens_id}")
    check(r.status_code == 200, f"DELETE /api/lenses/{lens_id} -> 200")
    r = client.delete(f"/api/lenses/{lens_id}")
    check(r.status_code == 404, "  ...deleting it again -> 404")

    # ---- cluster write cycle ---------------------------------------
    print("\nCluster writes:")
    r = client.post("/api/clusters", json={
        "name": "TEST cluster", "variables": [3, 3, 8, 47]})
    check(r.status_code == 201, "POST /api/clusters -> 201")
    cluster = r.get_json()
    check(isinstance(cluster.get("id"), int),
          "  ...the new cluster carries an id")
    cluster_id = cluster["id"]
    check(cluster["variables"] == [3, 8, 47],
          "  ...its variables were stored, de-duplicated, and sorted")

    r = client.get("/api/clusters")
    check(any(c["id"] == cluster_id for c in r.get_json()),
          "  ...it appears in GET /api/clusters")

    r = client.post("/api/clusters", json={"variables": [1]})
    check(r.status_code == 400, "POST a cluster with no name -> 400")

    r = client.post("/api/clusters", json={
        "name": "bad", "variables": [999]})
    check(r.status_code == 400,
          "POST a cluster with an unknown variable id -> 400")

    r = client.delete(f"/api/clusters/{cluster_id}")
    check(r.status_code == 200, f"DELETE /api/clusters/{cluster_id} -> 200")
    r = client.delete(f"/api/clusters/{cluster_id}")
    check(r.status_code == 404, "  ...deleting it again -> 404")

    # ---- job write cycle -------------------------------------------
    # A job is born blank with POST, then filled with PUT. Answers are
    # keyed "<variable_id>.<entry_no>", so a repeating variable can carry
    # several entries. The cycle below walks both writes, the reads, the
    # delete, and every error path the routes guard against.
    print("\nJob writes:")
    r = client.post("/api/jobs", json={"name": "TEST job", "slot": 7})
    check(r.status_code == 201, "POST /api/jobs -> 201")
    job = r.get_json()
    check(isinstance(job.get("id"), int), "  ...the new job carries an id")
    job_id = job["id"]
    check(job["slot"] == 7, "  ...its slot was stored")
    check(len(job["values"]) == 79,
          "  ...it is born with all 79 answer rows, blank")

    r = client.get("/api/jobs")
    check(any(j["id"] == job_id for j in r.get_json()),
          "  ...it appears in GET /api/jobs")

    r = client.get(f"/api/jobs/{job_id}")
    check(r.status_code == 200, f"GET /api/jobs/{job_id} -> 200")
    check(r.get_json()["name"] == "TEST job", "  ...GET returns the job")

    r = client.get("/api/jobs/999999")
    check(r.status_code == 404, "GET a non-existent job -> 404")

    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"1.1": "Privately held", "2.1": "Test Co LLC",
                   "54.1": "Floor Worker", "54.2": "Sales Manager"}})
    check(r.status_code == 200, f"PUT /api/jobs/{job_id} -> 200")
    saved = r.get_json()
    check(saved["name"] == "TEST job (saved)", "  ...the save took effect")
    check(saved["values"]["1.1"] == "Privately held",
          "  ...a singular answer comes back")
    check(saved["values"].get("54.1") == "Floor Worker"
          and saved["values"].get("54.2") == "Sales Manager",
          "  ...a repeating variable carries two entries")

    # bump #54 to a third entry, then trim back to one via the entries cap
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"54.3": "Director"}, "entries": {"54": 3}})
    check(r.status_code == 200, "PUT adding a 3rd entry -> 200")
    check(r.get_json()["values"].get("54.3") == "Director",
          "  ...the 3rd entry was stored")

    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {}, "entries": {"54": 1}})
    check(r.status_code == 200, "PUT with entries={54:1} -> 200")
    v = r.get_json()["values"]
    check("54.1" in v and "54.2" not in v and "54.3" not in v,
          "  ...the entries cap trimmed #54 to entry 1 only (Remove)")

    # entries on a singular variable is rejected
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {}, "entries": {"1": 1}})
    check(r.status_code == 400,
          "PUT with entries on a singular variable -> 400")

    # R8.J/K — derivation engine
    # ----------------------------------------------------------------
    # #51 (how_many_roles) is count:P1 Roles. Without any role values
    # written, ENTRIES defaults to 1, so the derived value should be 1.
    r = client.get(f"/api/jobs/{job_id}")
    derived_51 = r.get_json()["values"].get("51.1")
    check(derived_51 in (1, "1"),
          "Derived #51 reads as 1 when no roles have been added (got %r)"
          % derived_51)

    # Push two roles by giving #54 entry 2, then re-read #51
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"54.1": "Floor Worker", "54.2": "Sales Manager"},
        "entries": {"54": 2}})
    derived_51 = r.get_json()["values"].get("51.1")
    check(derived_51 in (2, "2"),
          "Derived #51 reflects 2 P1 Roles entries (got %r)" % derived_51)

    # Attempt to manually override #51 — the server should silently drop it
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"51.1": "99"}})
    derived_51 = r.get_json()["values"].get("51.1")
    check(derived_51 in (2, "2"),
          "Manual override of derived #51 is silently dropped "
          "(still 2, got %r)" % derived_51)

    # #52 (overview tenure) — duration:48,49. Set #48 start and #49 end.
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"48.1": "2020-01", "49.1": "2024-05"}})
    derived_52 = r.get_json()["values"].get("52.1")
    check(derived_52 == "4y 4m",
          "Derived #52 computes '4y 4m' for 2020-01..2024-05 (got %r)"
          % derived_52)

    # 'present' on the end side should append ' · ongoing'
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"48.1": "2023-01", "49.1": "present"}})
    derived_52 = r.get_json()["values"].get("52.1")
    check(derived_52 and "ongoing" in derived_52,
          "Derived #52 with end='present' appends ' · ongoing' (got %r)"
          % derived_52)

    # #57 (per-role tenure) — duration:55,56, computed PER ENTRY.
    # Two roles: 2020-01..2021-12 and 2022-01..present.
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {
            "55.1": "2020-01", "56.1": "2021-12",
            "55.2": "2022-01", "56.2": "present",
        },
        "entries": {"54": 2}})
    saved = r.get_json()["values"]
    check(saved.get("57.1") == "1y 11m",
          "Derived #57 entry 1 = 1y 11m (got %r)" % saved.get("57.1"))
    check(saved.get("57.2") and "ongoing" in saved.get("57.2"),
          "Derived #57 entry 2 marked ongoing (got %r)" % saved.get("57.2"))

    # Garbage dates should produce no derived value
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"48.1": "early Y2K", "49.1": "later on"}})
    check(r.get_json()["values"].get("52.1") is None,
          "Derived #52 yields nothing for unparseable dates")

    r = client.put("/api/jobs/999999", json={"name": "ghost"})
    check(r.status_code == 404, "PUT a non-existent job -> 404")

    r = client.post("/api/jobs", json={"slot": 1})
    check(r.status_code == 400, "POST a job with no name -> 400")

    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "bad ref", "values": {"999.1": "nope"}})
    check(r.status_code == 400,
          "PUT a job with an unknown variable id -> 400")

    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "bad key", "values": {"abc": "nope"}})
    check(r.status_code == 400,
          "PUT a job with a malformed value key -> 400")

    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "bad entry", "values": {"1.2": "nope"}})
    check(r.status_code == 400,
          "PUT a second entry on a singular variable -> 400")

    # sentinel values bypass type validation and normalise to canonical form
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": {"1.1": "n/a", "5.1": "N/A", "15.1": "N/a"}})
    check(r.status_code == 200,
          "PUT with N/A on a select, a date, and a number -> 200 (type bypass)")
    saved = r.get_json()
    sv = saved["values"]
    check(sv.get("1.1") == "N/A" and sv.get("5.1") == "N/A" and sv.get("15.1") == "N/A",
          "  ...all three case variants normalise to canonical 'N/A'")
    # readiness: most fields are still blank, so status is 'in_progress'
    check(saved["status"]["status"] == "in_progress",
          "  ...with most fields blank, status is 'in_progress'")
    check(saved["status"]["assessed"] >= 3,
          "  ...the three N/A markings count toward 'assessed'")

    # filling every variable with N/A flips the status to 'ready'
    # — except the four date inputs that feed the duration recipes, which
    # must carry real dates so #52 (overview tenure) and #57 (per-role
    # tenure) actually compute. A derived var that can't compute counts
    # as pending, so without this, status would stay in_progress.
    all_vars = client.get("/api/variables").get_json()
    full_values = {"%d.1" % v["id"]: "N/A" for v in all_vars
                   if v["id"] not in (48, 49, 55, 56)}
    full_values["48.1"] = "2020-01"   # overview start
    full_values["49.1"] = "2024-05"   # overview end
    full_values["55.1"] = "2020-01"   # role 1 start
    full_values["56.1"] = "2024-05"   # role 1 end
    # Trim every repeating section back to N=1 so total = 79 cells (the
    # earlier derivation tests left P1 Roles at N=2).  Every repeating
    # variable id sees the same cap, courtesy of a one-shot helper.
    repeating_ids = [v["id"] for v in all_vars if v["repeats"] == 1]
    trim_entries = {str(vid): 1 for vid in repeating_ids}
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": full_values, "entries": trim_entries})
    check(r.status_code == 200, "PUT marking every variable N/A -> 200")
    s = r.get_json()["status"]
    check(s["status"] == "ready", "  ...the job is now 'ready' for Phase 5")
    check(s["pending"] == [] and s["assessed"] == s["total"],
          "  ...pending is empty and assessed equals total")
    row = next(j for j in client.get("/api/jobs").get_json() if j["id"] == job_id)
    check(row["status"] == "ready",
          "GET /api/jobs carries the per-row status string")

    # ready_at: stamped on the transition to ready, preserved across re-saves
    check(row["ready_at"] is not None,
          "ready_at is stamped when the job becomes ready")
    first_ready_at = row["ready_at"]

    # ?status= filter: ready jobs in, in_progress jobs out (and vice-versa)
    ready_jobs = client.get("/api/jobs?status=ready").get_json()
    progress_jobs = client.get("/api/jobs?status=in_progress").get_json()
    check(any(j["id"] == job_id for j in ready_jobs),
          "GET /api/jobs?status=ready includes the ready job")
    check(not any(j["id"] == job_id for j in progress_jobs),
          "GET /api/jobs?status=in_progress excludes it")
    bad_filter = client.get("/api/jobs?status=blue").get_json()
    check(any(j["id"] == job_id for j in bad_filter),
          "  ...an invalid filter is ignored — full list returned")

    # re-saving the still-ready job preserves the original ready_at timestamp
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8, "values": full_values})
    check(r.get_json()["ready_at"] == first_ready_at,
          "re-saving a still-ready job preserves ready_at (since-when, not last-save)")

    # the single-job endpoint also carries ready_at
    single = client.get(f"/api/jobs/{job_id}").get_json()
    check("ready_at" in single and single["ready_at"] == first_ready_at,
          "GET /api/jobs/<id> carries ready_at")

    # drop one value -> status slides back to in_progress, ready_at clears
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8, "values": {"1.1": ""}})
    saved2 = r.get_json()
    check(saved2["status"]["status"] == "in_progress",
          "dropping one value flips status back to in_progress")
    check(saved2["ready_at"] is None,
          "  ...ready_at clears when the job is no longer ready")

    # =================================================================
    # R9 — tier-graduated readiness + engagement-active stories
    # =================================================================
    # The status object now carries tier_progress per tier (t1/t2/t3),
    # a graduated tier_level enum, stories_active, and stories_progress.
    # Stories are engagement-aware: a job can be 'ready' with zero
    # stories filled (engagement is opt-in); once a story field is
    # filled, all 13 count toward readiness.

    print("\nTier-graduated readiness (R9):")
    all_vars = client.get("/api/variables").get_json()

    # ---- reset to fully-blank, N=1 across all repeating sections -----
    blank_values = {"%d.1" % v["id"]: "" for v in all_vars}
    trim = {str(v["id"]): 1 for v in all_vars if v["repeats"] == 1}
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8,
        "values": blank_values, "entries": trim})
    s0 = r.get_json()["status"]
    check("tier_progress" in s0, "status carries tier_progress")
    check(s0["tier_level"] == "none", "blank job: tier_level='none'")
    check(s0["stories_active"] is False, "blank job: stories_active=False")
    tp0 = s0["tier_progress"]
    check(tp0["t1"]["total"] == 7,  f"t1.total=7 (got {tp0['t1']['total']})")
    check(tp0["t2"]["total"] == 16, f"t2.total=16 (got {tp0['t2']['total']})")
    check(tp0["t3"]["total"] == 43, f"t3.total=43 (got {tp0['t3']['total']})")
    check(s0["stories_progress"]["total"] == 13,
          f"stories.total=13 (got {s0['stories_progress']['total']})")
    check(s0["status"] == "in_progress", "blank job: status='in_progress'")

    # ---- fill all T1 (non-story) -> tier_level='t1' ------------------
    t1_vids = [v["id"] for v in all_vars if v["tier"] == 1 and not v["track"]]
    t1_values = {"%d.1" % vid: "N/A" for vid in t1_vids}
    t1_values["48.1"] = "2020-01"     # real dates so #52 (T1) derives
    t1_values["49.1"] = "2024-05"
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8, "values": t1_values})
    s1 = r.get_json()["status"]
    check(s1["tier_level"] == "t1",
          f"all T1 filled: tier_level='t1' (got {s1['tier_level']!r})")
    check(s1["tier_progress"]["t1"]["ready"] is True, "t1.ready=True")
    check(s1["tier_progress"]["t2"]["ready"] is False,
          "t2.ready still False (T2 vars not filled)")
    check(s1["status"] == "in_progress", "T1-only: status still in_progress")

    # ---- fill all T2 (non-story) -> tier_level='t2' ------------------
    t2_vids = [v["id"] for v in all_vars if v["tier"] == 2 and not v["track"]]
    # skip derived vids (52 already covered, 57 here); fill role dates
    t2_values = {"%d.1" % vid: "N/A" for vid in t2_vids if vid not in (52, 57)}
    t2_values["55.1"] = "2020-01"
    t2_values["56.1"] = "2024-05"
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8, "values": t2_values})
    s2 = r.get_json()["status"]
    check(s2["tier_level"] == "t2",
          f"all T2 filled: tier_level='t2' (got {s2['tier_level']!r})")
    check(s2["tier_progress"]["t2"]["ready"] is True, "t2.ready=True")
    check(s2["tier_progress"]["t3"]["ready"] is False, "t3.ready still False")

    # ---- fill all T3 (non-story) -> tier_level='t3', status='ready'
    #      (engagement-active: stories optional)
    t3_vids = [v["id"] for v in all_vars if v["tier"] == 3 and not v["track"]]
    t3_values = {"%d.1" % vid: "N/A" for vid in t3_vids}
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8, "values": t3_values})
    s3 = r.get_json()["status"]
    check(s3["tier_level"] == "t3",
          f"all T3 filled: tier_level='t3' (got {s3['tier_level']!r})")
    check(s3["stories_active"] is False,
          "stories still inactive (no story field filled)")
    check(s3["status"] == "ready",
          "engagement-active: status='ready' with all CF/PI but zero stories")

    # ---- engage one story -> stories_active=True, status -> in_progress
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8, "values": {"67.1": "Jane Doe"}})
    s4 = r.get_json()["status"]
    check(s4["stories_active"] is True,
          "one story field filled: stories_active=True")
    check(s4["status"] == "in_progress",
          "stories engaged but incomplete: status='in_progress'")
    check(s4["tier_level"] == "t3",
          "tier_level stays 't3' (stories don't gate tier)")

    # ---- fill all stories -> ready again -----------------------------
    story_vids = [v["id"] for v in all_vars if v["track"] == "story"]
    story_values = {"%d.1" % vid: "N/A" for vid in story_vids}
    r = client.put(f"/api/jobs/{job_id}", json={
        "name": "TEST job (saved)", "slot": 8, "values": story_values})
    s5 = r.get_json()["status"]
    check(s5["status"] == "ready",
          "all stories filled: status returns to 'ready'")
    check(s5["stories_progress"]["ready"] is True,
          "stories_progress.ready=True")

    # ---- /api/jobs row carries tier_level + stories_active ----------
    row = next(j for j in client.get("/api/jobs").get_json() if j["id"] == job_id)
    check(row.get("tier_level") == "t3",
          "GET /api/jobs row carries tier_level")
    check(row.get("stories_active") is True,
          "  ...and stories_active")

    r = client.delete(f"/api/jobs/{job_id}")
    check(r.status_code == 200, f"DELETE /api/jobs/{job_id} -> 200")
    r = client.delete(f"/api/jobs/{job_id}")
    check(r.status_code == 404, "  ...deleting it again -> 404")


# ====================================================================
# RUN — with a guaranteed clean-up of the throwaway database
# ====================================================================
print("Synthesis API test suite")
print(f"  test database: {TEST_DB}")
print()
try:
    run_tests()
except Exception as exc:                       # an unexpected crash
    _failed += 1
    print(f"  FAIL  the test suite crashed: {exc!r}")
finally:
    print()
    print(f"  {_passed} passed, {_failed} failed")
    shutil.rmtree(TMP_DIR, ignore_errors=True)  # delete the temp database
    print("  (temporary test database deleted)")

print("\n" + ("ALL CHECKS PASSED" if _failed == 0 else "SOME CHECKS FAILED"))
sys.exit(0 if _failed == 0 else 1)
