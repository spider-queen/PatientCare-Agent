---
name: "identity-verification"
description: "Require identity verification before private patient data access."
---

Use `verify_patient_identity` before accessing private patient data.

Rules:
- If the request asks for a patient's profile, medical cases, or visit records, do not call data tools until verification succeeds.
- When the server already provided patient context, reuse that context instead of claiming the user did not provide identity details.
- If verification fails, say that identity verification did not pass and avoid exposing private data.
