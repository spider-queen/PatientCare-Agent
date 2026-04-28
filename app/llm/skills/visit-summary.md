---
name: "visit-summary"
description: "Handle recent or latest visit questions consistently."
---

When the user asks about the most recent or latest visit:
- Prefer `get_patient_visit_records`.
- If the user only needs the latest visit, make sure `limit=1` is included.
- Base the answer on tool results, and highlight department, physician, visit time, and summary when available.
