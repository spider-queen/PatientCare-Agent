---
name: "medical-case-query"
description: "Handle diagnosis and medical case lookup requests."
---

Use `get_patient_medical_cases` for diagnosis, case, and treatment related questions.

Rules:
- Do not invent diagnoses or treatment plans that are not present in the tool results.
- If no case is found, state that the evidence is insufficient.
- Keep the answer grounded in structured patient data.
