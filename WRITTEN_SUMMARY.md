# Written Summary — Voices Against Violence (VAV)

## Track
**Track 3: Safety, Reporting & Protection.** VAV lets survivors and witnesses of gender-based violence report incidents safely (with an anonymity option), tracks each report to resolution with a visible timeline, and connects users to verified emergency, medical, legal, and shelter resources with immediate next steps.

## The problem and who it's for
In Kenya, GBV survivors frequently know something is wrong but don't know where to go, who to call, or what happens after they report. Emergency contacts, shelter locations, and legal procedures are scattered across word of mouth, outdated pamphlets, and hard-to-navigate institutional sites. Reporting can feel like shouting into a void, with no visibility into what happens next. VAV serves survivors, witnesses, and community contributors who need a trustworthy, safe, single point of access to reporting, verified help, and plain-language education — and administrators who need auditable oversight of that pipeline.

## Information sources
- **Facility/geodata (hospitals):** imported from OpenStreetMap's Overpass API (public, community-maintained geodata), filtered to `amenity=hospital` entries with a name.
- **Safe houses, legal aid centers, counseling centers, churches:** compiled into curated JSON datasets from public directories and known GBV-response organizations operating in Kenya (e.g. FIDA Kenya, CREAW Kenya, LVCT Health, Nairobi Women's Hospital GBV Recovery Centre, Wangu Kanja Foundation, Grace Agenda), then imported via management commands and marked `is_verified` once cross-checked.
- **Educational articles:** original content referencing primary legal sources — the Sexual Offences Act (2006), the Protection Against Domestic Violence Act (2015), and the Children Act (2022) — and public health guidance on post-rape care (the 72-hour PRC window, PEP, P3 forms).
- **Emergency numbers:** national published hotlines (Police 999/112, national GBV Hotline 1195, ODPP GBV hotline, Befrienders Kenya).

## Approach to trust and accuracy
- **Verification metadata, not just data:** every `Resource` record carries `is_verified`, `verified_at`, and `last_confirmed_at` fields, so the map and the AI assistant can distinguish confirmed information from unverified entries and surface *when* something was last checked, not just what it says.
- **Moderation before publication:** all community-submitted content (articles, blog posts, survivor stories, resource suggestions, feature ideas) enters a `pending → approved/rejected` review queue with reviewer notes. Nothing a contributor submits goes live without an admin decision, which protects against both misinformation and unsafe content.
- **A grounded, not generative, AI assistant:** the in-app assistant ("Amani") is instructed to call live database tools to look up real, verified resources rather than inventing names, phone numbers, or addresses, and to always lead with official emergency numbers when danger is indicated.
- **Auditability:** an `AuditLog` model and CSV exports (reports, SLA, feedback, contributions, users) give administrators a traceable record of who changed what, supporting real accountability rather than a one-time content dump.

## How AI coding tools were used
The project was built end-to-end using **Claude Code** (Anthropic's agentic coding CLI) as the primary development tool — not to originate the product idea (which came from direct exposure to gaps in Kenya's GBV reporting/support ecosystem), but to implement and iterate on it. Claude Code was used to:
- Scaffold and extend the Django data model (`GBVReport` + status timeline, `Resource` verification/geocoding, the moderation workflow shared across `Article`, `Blog`, `Story`, and `Idea`).
- Build the AWS Cognito authentication flow (sign-up, email verification, SMS MFA, password reset) and the rate-limiting/security middleware.
- Wire up the Groq-backed AI support assistant and its resource-lookup tools via `django-ai-assistant`.
- Debug issues surfaced during development (login/session bugs, mapping/geocoding errors, admin UI theming) and refactor the admin dashboard, metrics, and CSV export tooling.
- Prepare this capstone submission: auditing the repository for a leaked `.env` file and CRLF-broken `.gitignore` rule before publishing a clean public repo, and writing this README and summary.

## Impact and scalability
The `Resource` model is deliberately generic (type, county/location, geocoding, verification metadata) so the same platform can be reseeded with a different country's emergency numbers, laws, and facility directory without a schema change — only new data and translated content are needed to adapt VAV to another region. The reporting, moderation, and AI-assistant patterns are similarly domain-agnostic and could extend to adjacent safety-reporting use cases beyond GBV.
