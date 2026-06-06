"""End-to-end smoke test for the LegalMind backend. Run with `python smoketest.py`."""
import io
import os
import sys

# Ensure a clean DB
for f in ("vakilai.db",):
    if os.path.exists(f):
        os.remove(f)

from app import create_app
app = create_app()
c = app.test_client()

PASS, FAIL = 0, 0


def check(label, cond, payload=""):
    global PASS, FAIL
    mark = "OK  " if cond else "FAIL"
    if cond:
        PASS += 1
    else:
        FAIL += 1
    print(f"[{mark}] {label}  {payload}")


# 1. Health
r = c.get("/health")
check("GET /health", r.status_code == 200 and r.get_json()["ok"], str(r.get_json()))

# 2. Seed
r = c.post("/seed")
d = r.get_json()
check(
    "POST /seed",
    r.status_code == 200 and d["seeded"]["lawyers"] == 0 and d["seeded"]["cases"] == 0
    and d["seeded"]["documents"] == 0 and d["seeded"]["notes"] == 0,
    str(d),
)

# 3. List cases (empty after seed)
r = c.get("/cases/")
d = r.get_json()
check("GET /cases/ count=0", r.status_code == 200 and d["count"] == 0, str(d))

# 4. Single case with relations (should fail)
r = c.get("/cases/1")
check("GET /cases/1 404", r.status_code == 404)

# 5. Create case
r = c.post(
    "/cases/",
    json={
        "title": "Khan Cheque Bounce",
        "client_name": "M/s Brightway Traders",
        "case_type": "Criminal",
        "court": "Tis Hazari",
        "sections": ["BNS 318", "NI Act 138"],
        "hearing_date": "2026-06-22",
        "status": "Active",
    },
)
d = r.get_json()
check("POST /cases/ creates new case", r.status_code == 201 and d["case"]["title"] == "Khan Cheque Bounce")

# 6. Missing field validation
r = c.post("/cases/", json={"title": "oops"})
check("POST /cases/ 400 on missing field", r.status_code == 400, str(r.get_json()))

# 7. Update status (use case created in step 5)
case_id = d["case"]["id"] if d.get("case") else None
r = c.put(f"/cases/{case_id}", json={"status": "Hearing"})
check("PUT /cases/{id} status=Hearing", r.status_code == 200 and r.get_json()["case"]["status"] == "Hearing")

# 8. Update with invalid status
r = c.put(f"/cases/{case_id}", json={"status": "Pending"})
check("PUT /cases/{id} 400 on bad status", r.status_code == 400, str(r.get_json()))

# 9. Chat post
r = c.post(f"/cases/{case_id}/chat", json={"content": "What are the leading bail precedents for BNS 103?"})
d = r.get_json()
check(
    "POST chat creates user + AI messages",
    r.status_code == 201 and d["user_message"]["role"] == "user"
    and d["ai_message"]["role"] == "ai" and "Indian Kanoon" in d["ai_message"]["content"],
)

# 10. Chat list (no seed messages, just posted 2)
r = c.get(f"/cases/{case_id}/chat")
d = r.get_json()
check("GET chat history count=2", r.status_code == 200 and d["count"] == 2)

# 11. Chat empty content
r = c.post(f"/cases/{case_id}/chat", json={"content": "  "})
check("POST chat 400 on empty content", r.status_code == 400)

# 12. Upload missing file
r = c.post(f"/cases/{case_id}/documents", data={}, content_type="multipart/form-data")
check("POST upload 400 on no file", r.status_code == 400)

# 13. Upload real file
data = {"file": (io.BytesIO(b"%PDF-1.4 fake content"), "bail.pdf")}
r = c.post(f"/cases/{case_id}/documents", data=data, content_type="multipart/form-data")
d = r.get_json()
doc_id = d["document"]["id"] if d.get("ok") else None
check(
    "POST upload saves file and returns metadata",
    r.status_code == 201 and d["ok"] and doc_id is not None,
    f"doc_id={doc_id}",
)

# 14. File exists on disk
import pathlib
upload_dir = pathlib.Path(app.config["UPLOAD_FOLDER"])
saved = list(upload_dir.iterdir())
check("Uploaded file present on disk", len(saved) >= 1, f"files={[f.name for f in saved]}")

# 15. Delete document
r = c.delete(f"/documents/{doc_id}")
check("DELETE /documents/<id>", r.status_code == 200)

# 16. Delete missing
r = c.delete("/documents/9999")
check("DELETE /documents/9999 404", r.status_code == 404)

# 17. Delete case (cascade)
r = c.delete(f"/cases/{case_id}")
check("DELETE /cases/{id}", r.status_code == 200)

# 18. Get missing case
r = c.get("/cases/9999")
check("GET /cases/9999 404", r.status_code == 404)

# 20. Re-seed
r = c.post("/seed")
d = r.get_json()
check("POST /seed idempotent", r.status_code == 200 and d["seeded"]["cases"] == 0)

print(f"\n=== {PASS} passed, {FAIL} failed ===")
sys.exit(0 if FAIL == 0 else 1)
