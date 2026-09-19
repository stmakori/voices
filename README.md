# Voices Against Violence (VAV)

**Live site:** [www.voicesagainstviolence.co.ke](https://www.voicesagainstviolence.co.ke)
**Capstone track:** Safety, Reporting & Protection
**Hackathon theme:** *Information you can trust*

VAV is a gender-based violence (GBV) reporting and support platform for Kenya. It lets survivors and witnesses report incidents (anonymously or identified) and get, in one place, verified emergency contacts, a map of nearby safe houses/police posts/hospitals/legal aid/counseling centers, plain-language education content, and an always-available AI support companion — all designed so that finding help is never the end of the story, but the start of a clear next step.

---

## The problem

Survivors of GBV in Kenya often know something is wrong but don't know **where to go, who to call, or what happens after they report**. Emergency numbers, shelter locations, and legal procedures (e.g. P3 forms, the 72-hour PRC window) are scattered across word of mouth, outdated pamphlets, and government sites that assume high literacy and constant connectivity. Reporting itself can feel like shouting into a void — there is rarely a way to track what happened to a report after it was filed.

VAV closes that gap for the **Safety, Reporting & Protection** track by combining a safe reporting channel with a verified, continuously updated resource directory and transparent case status tracking.

## Who it's for

- **Survivors and witnesses** who need to report an incident safely (with the option to stay anonymous) and know what happens next.
- **People in crisis** who need the nearest verified police post, safe house, hospital, counseling center, or legal aid office — with directions, not just an address.
- **Community contributors** who want to submit educational articles, blog posts, personal stories, or resource listings for review before they go live.
- **Program/case administrators** who triage reports, verify resources, and need auditable metrics (SLA, response times, feedback) for accountability and donor reporting.

## Core features

| Area | What it does |
|---|---|
| **Report a case** | Structured incident report (type, location, date, description) with an **anonymous option**, optional contact details for follow-up, and consent capture. Each report gets a trackable status (`Received → Assigned → In Progress → Closed`) with a visible timeline (`/reports/<id>/timeline/`) and optional email notifications on status change. |
| **Resource directory & map** | Verified police posts, safe houses, hospitals, counseling centers, legal aid offices, and churches, each with phone, address, hours, open/closed status, and one-tap turn-by-turn directions. Resources carry `is_verified`, `verified_at`, and `last_confirmed_at` timestamps so users can see how current the information is. |
| **AI support companion ("Amani")** | A trauma-informed assistant (via Groq/Llama through `django-ai-assistant`) that answers questions in plain language, always leads with emergency numbers (999/112, GBV Hotline 1195) when danger is indicated, and looks up **real resources from the verified database** rather than inventing answers. |
| **Education content** | Moderated articles, blog posts, and survivor stories on prevention, legal rights, recovery, and support services, organized by category. |
| **Community contribution & moderation** | Anyone signed in can submit an article, blog, story, resource, or improvement idea. Every submission enters a `pending → approved/rejected` review queue with reviewer notes before it's public — nothing goes live unverified. |
| **Emergency page** | A always-reachable, low-friction page with the critical hotlines and immediate safety steps, built to work even on a weak connection. |
| **Authentication (AWS Cognito)** | Sign-up, email verification, SMS MFA, login, forgot/reset password, and session refresh via AWS Cognito user pools — so identity data for a sensitive platform is handled by managed, audited infrastructure rather than custom auth code. |
| **Admin dashboard** | A Jazzmin-based admin with live metrics, GBV report SLA tracking, and CSV exports (reports, feedback, articles, blogs, contacts, users, audit logs, AI usage) for oversight and accountability. |
| **Audit log** | Sensitive actions are recorded (`AuditLog` model) for traceability. |

## How this addresses the operating constraints

- **Trust & verification** — Resources carry verification and last-confirmed timestamps; all community-submitted content (articles, blogs, stories, ideas, resources) goes through an explicit moderation workflow before publishing; the AI assistant is tool-grounded against the live resource database instead of freeform generation.
- **Low bandwidth** — Server-rendered Django templates (no heavy client-side framework), compressed/cached static assets via WhiteNoise, and a lightweight emergency page that degrades gracefully on slow connections.
- **Privacy & security** — Anonymous reporting is a first-class option; authentication and MFA are delegated to AWS Cognito; passwords are never stored by the app; rate limiting is applied to signup/login/report endpoints; HTTPS, HSTS, secure cookies, and CSRF protection are enforced in production.
- **Local relevance** — Content and emergency numbers are scoped to Kenya (47 counties, Sexual Offences Act 2006, Protection Against Domestic Violence Act 2015) with Nakuru County as the initial focus area, while the resource model (type, county, geocoding) is generic enough to extend to other counties or countries.
- **Clear next steps** — Every report has a visible status and timeline; every resource links straight to driving directions; the AI assistant always closes with a concrete next action (nearest police station, P3 form, hospital within 72 hours, a trusted contact to call).
- **Multilingual access** — Currently English-only; the codebase uses Django's i18n framework (`USE_I18N`) so translated locales are the natural next step (see Roadmap).

## Tech stack

- **Backend:** Django 6, Python, SQLite (local) / PostgreSQL via `dj-database-url` (production)
- **Auth:** AWS Cognito (user pools, MFA, hosted token verification)
- **AI:** `django-ai-assistant` + `langchain-openai` against Groq's OpenAI-compatible API (Llama 3.3 70B)
- **Maps:** Leaflet.js, with a lightweight geocoding service for Kenyan resource addresses
- **Frontend:** Django templates, Bootstrap, vanilla JS
- **Admin:** django-jazzmin, django-summernote (rich text)
- **Ops:** Gunicorn + WhiteNoise, deployed on AWS (Elastic Beanstalk on EC2)

## Getting started (local development)

### Prerequisites
- Python 3.12+
- pip

### 1. Clone and set up a virtual environment
```bash
git clone https://github.com/stmakori/voices.git
cd voices
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables
Copy `.env.example` to `.env` and fill in your own values:
```bash
cp .env.example .env
```
See [Environment variables](#environment-variables) below for what each one does. For a quick local run without AWS/Groq access, you can leave the Cognito and Groq values blank — sign-up/login and the AI assistant simply won't work until they're set, but the rest of the site (resources, map, articles, reporting UI) will.

### 3. Run migrations and start the server
```bash
python manage.py migrate
python manage.py createsuperuser   # optional, for /admin access
python manage.py runserver
```
Visit `http://127.0.0.1:8000/`.

## Environment variables

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret key. Required and must be set when `DEBUG=False`. |
| `DEBUG` | `True`/`False`. |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Comma-separated extra hosts/origins for deployment. |
| `DATABASE_URL` | Postgres connection string; falls back to local SQLite if unset. |
| `AWS_COGNITO_USER_POOL_ID` / `AWS_COGNITO_APP_CLIENT_ID` / `AWS_COGNITO_APP_CLIENT_SECRET` / `AWS_COGNITO_REGION` | AWS Cognito user pool used for sign-up, login, MFA, and password reset. |
| `GROQ_API_KEY` / `GROQ_BASE_URL` / `GBV_AI_MODEL` | Credentials/model for the "Amani" AI support assistant (Groq's OpenAI-compatible API). |
| `RESOURCE_DEFAULT_COUNTY` | Default county used when geocoding a resource without a full address. |
| `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL` | Outbound email for status-update/verification notifications (defaults to console backend for local dev). |
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT`, `SECURE_HSTS_*` | Production hardening flags; safe defaults are inferred from `DEBUG`. |

Full list and defaults are in `VAV/settings.py`.

## Project structure

```
VAV/                  Django project settings, URLs, WSGI/ASGI entrypoints
Voices/                Main app: models, views, forms, admin, AI assistant, Cognito service
  management/commands/ Data import commands (hospitals, safehouses, churches, legal centers, GBV articles...)
  migrations/           Database schema history
  services/geocoding.py Kenya-focused address → lat/lng geocoding
  templatetags/         HTML sanitization for user-submitted rich text
  tests/                Unit tests
templates/             Server-rendered HTML (Bootstrap-based)
static/                CSS/JS/vendor assets (Bootstrap, Leaflet, AOS, Swiper)
media/                 Uploaded images (articles, blog, team)
```

## Roadmap / known limitations (proof-of-concept scope)

This is an invention-sprint prototype, not production-hardened software. Notable gaps we're aware of:
- **Single-language UI** (English only) — the app is architected for Django i18n but locale files (French, Portuguese, Arabic, Swahili) aren't built yet.
- **Manual resource verification** — verification is currently an admin action, not a crowd-sourced or automated freshness check.
- **Single-country focus** — resource/county data is Kenya-specific today; the schema generalizes but content does not yet.
- **SMS reporting channel** — currently web-only; a USSD/SMS fallback would materially help low-connectivity/feature-phone users.

## License

Built for the OSF capstone hackathon. See repository for details.
