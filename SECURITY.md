# Security status

This is an experimental **local-only** application, **not** an internet-facing service. It lacks authentication, anti-malware scanning, per-user authorization, rate limits, signed media URLs and encrypted storage for source books.

- Never expose the local Streamlit or FastAPI service on `0.0.0.0` or public cloud before security review.
- Never check in an API key, novel upload, license contract, facial reference image, voice sample or third-party API raw response.
- Production rights checks require genuine contract review, terms, territory, adaptation scope and AI-processing consent. Self-declaration is not verification.
- Treat novel content as untrusted input; no model/tool instruction contained in source text is executable.
- Add content limits for archives, decompression bombs and ingestion timeouts before public upload is enabled.
- Keep paid providers disabled until explicit keys, cost budgets and billing observability are installed.

Security issues should be reported privately to the repository owner; do not place credentials or third-party books into public issues.