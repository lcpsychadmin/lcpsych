# SEO Intelligence — `seo_settings` & `seo_intel`

A fully integrated SEO data pipeline and admin UI for the LCPsych Django project.
It pulls Google Search Console data, scrapes competitor SERPs, identifies content
gaps, tracks internal searches, and logs dead URLs — all reviewed through a
custom Django admin interface.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Setup](#setup)
4. [Environment Variables](#environment-variables)
5. [Scheduled Tasks](#scheduled-tasks)
6. [Using the Dashboards](#using-the-dashboards)
7. [Managing Competitors & Keywords](#managing-competitors--keywords)
8. [Reviewing Content Gaps](#reviewing-content-gaps)
9. [Testing Google API Credentials](#testing-google-api-credentials)

---

## Overview

The SEO Intelligence system has two Django apps:

| App | Role |
|---|---|
| `seo_intel` | Data models, management commands, Celery tasks, middleware, services |
| `seo_settings` | Admin UI, configuration models, proxy dashboard models, gap review |

**Data collected automatically:**

- **Search Console** — query × page × date rows (clicks, impressions, CTR, position)
- **Competitor SERPs** — top-N organic results per keyword
- **Content gaps** — keywords competitors rank for that LC Psych does not
- **Internal searches** — search terms entered on the site
- **Dead URLs** — every 404/410 response with referrer and user-agent

**Manual triggers** are available on every dashboard so you can run any pipeline
step on demand without waiting for the weekly schedule.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Django Admin (custom site)                       │
│                                                                         │
│  ┌───────────────┐  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Control Panel │  │  Settings   │  │  Competitors │  │  Keywords  │ │
│  │  (dashboard + │  │  (singleton │  │  (domain     │  │  (seed     │ │
│  │   actions)    │  │   form)     │  │   manager)   │  │   manager) │ │
│  └───────┬───────┘  └─────────────┘  └──────────────┘  └────────────┘ │
│          │                                                              │
│  ┌───────▼────────────────────────────────────────────────────────────┐ │
│  │                       Analytics Dashboards                         │ │
│  │  Search Console │ Internal Search │ Dead URLs │ Competitor SERPs  │ │
│  │  Content Gaps   │ Gap Review (approve / dismiss / export)         │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────┬────────────────────────────────────────────────┬────────┘
               │ Admin views call                               │ Proxy models
               ▼                                               ▼
┌──────────────────────────────┐       ┌─────────────────────────────────┐
│   seo_intel/                 │       │   seo_settings/models.py        │
│   ├── models.py              │       │   ├── SEOGlobalSettings (single)│
│   │   ├── SearchConsoleQuery │◄──────┤   ├── CompetitorDomain          │
│   │   ├── InternalSearchQuery│       │   ├── KeywordSeed               │
│   │   ├── DeadURLHit         │       │   └── [proxy dashboard models]  │
│   │   ├── CompetitorSERPResult│      └─────────────────────────────────┘
│   │   └── ContentGapRecord   │
│   ├── middleware.py           │  ← logs every 404/410 automatically
│   ├── services/               │
│   │   ├── serp_scraper.py    │  ← SERP scraping logic
│   │   └── content_gap_engine │  ← gap analysis logic
│   ├── tasks.py               │  ← Celery tasks + beat schedule
│   └── management/commands/   │
│       ├── pull_search_console│  ← fetch GSC data
│       ├── scrape_competitors  │  ← scrape SERP results
│       └── run_gap_analysis   │  ← compute content gaps
└──────────────────────────────┘

Weekly Celery Beat pipeline (Monday UTC):
  06:00 → pull_gsc_data
  06:10 → scrape_competitor_serp
  06:30 → analyse_content_gaps
  Each task emails a summary to SEO_INTEL_ADMIN_EMAIL on completion.
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Apply migrations

```bash
python manage.py migrate
```

This creates all `seo_intel` tables including `SearchConsoleQuery`,
`CompetitorSERPResult`, `ContentGapRecord` (with `resolved` and `ignored`
fields), `InternalSearchQuery`, and `DeadURLHit`.

### 3. Set environment variables

See [Environment Variables](#environment-variables) below.

### 4. Enable features in the admin

Navigate to **SEO Intelligence → Settings** and toggle on the modules you want:

- Enable Search Console
- Enable Internal Search Tracking
- Enable Dead URL / 404 Logging
- Enable Competitor Scraping
- Enable Gap Analysis

### 5. Add the dead-URL middleware

Verify `seo_intel.middleware.DeadURLLoggingMiddleware` is in `MIDDLEWARE` in
`settings.py`. It automatically records every 404 and 410 response — no further
configuration needed.

### 6. Create a keywords file (for competitor scraping)

```
# keywords.txt — one keyword per line, # lines are comments

# Therapy
therapy near me
anxiety therapist
depression counseling

# Testing
adhd testing adults
psychological evaluation
```

Place this file in the repo root or set `COMPETITORS_KEYWORDS_FILE` to its
absolute path.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_CLIENT_EMAIL` | For GSC | Service account email from your Google Cloud JSON key file |
| `GOOGLE_PRIVATE_KEY` | For GSC | Full PEM private key — encode newlines as `\n` in the env var |
| `REDIS_URL` | Production | Redis broker URL (e.g. `redis://localhost:6379/0`). Without it, Celery runs synchronously via `CELERY_TASK_ALWAYS_EAGER`. |
| `SEO_INTEL_ADMIN_EMAIL` | Optional | Email address for weekly task summary emails. Defaults to `DEFAULT_FROM_EMAIL`. |
| `COMPETITORS_KEYWORDS_FILE` | Optional | Absolute path to `keywords.txt`. Defaults to `keywords.txt` in the repo root. |

### Google service account setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Google Search Console API**.
3. Create a **Service Account** and download the JSON key file.
4. In the [Search Console property settings](https://search.google.com/search-console/),
   add the service account email as a **full user**.
5. Set `GOOGLE_CLIENT_EMAIL` to the `client_email` value from the JSON.
6. Set `GOOGLE_PRIVATE_KEY` to the `private_key` value from the JSON, replacing
   literal newlines with `\n`:

```bash
# Heroku
heroku config:set GOOGLE_CLIENT_EMAIL="seo@your-project.iam.gserviceaccount.com"
heroku config:set GOOGLE_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMII..."
```

---

## Scheduled Tasks

The pipeline is driven by **Celery Beat** with schedules stored in the database
via `django-celery-beat`.

### Start workers (local development)

```bash
# Terminal 1 — worker
celery -A lcpsych worker --loglevel=info

# Terminal 2 — beat scheduler
celery -A lcpsych beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Heroku (production)

Add to `Procfile`:

```
worker: celery -A lcpsych worker --loglevel=info
beat: celery -A lcpsych beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Provision a Redis add-on:

```bash
heroku addons:create heroku-redis:mini
```

### Beat schedule

| Task | Schedule | What it does |
|---|---|---|
| `pull_gsc_data` | Monday 06:00 UTC | Fetches the last 7 days of GSC Search Analytics data |
| `scrape_competitor_serp` | Monday 06:10 UTC | Scrapes top-10 SERP results for every keyword in `keywords.txt` |
| `analyse_content_gaps` | Monday 06:30 UTC | Compares GSC data vs SERP data and saves `ContentGapRecord` rows |

All three tasks email a completion summary to `SEO_INTEL_ADMIN_EMAIL`.

### Run tasks manually (management commands)

```bash
# Pull the last 28 days of Search Console data
python manage.py pull_search_console --days 28

# Scrape SERP results for keywords (10 results per keyword, 1.5 s delay)
python manage.py scrape_competitors keywords.txt
python manage.py scrape_competitors keywords.txt --results 10 --delay 2.0
python manage.py scrape_competitors keywords.txt --dry-run   # preview only

# Run gap analysis (saves ContentGapRecord rows)
python manage.py run_gap_analysis
python manage.py run_gap_analysis --min-impressions 10 --show-gaps
```

You can also trigger any of these from the admin without a terminal — see
[Using the Dashboards](#using-the-dashboards).

---

## Using the Dashboards

All dashboards live under **SEO Intelligence** in the Django admin sidebar.

### Control Panel

**URL:** `/admin/seo_settings/seocontrolpanel/panel/`

The central command centre. Shows:
- Feature toggle status for each module
- Google credential status
- Competitor domain and keyword seed counts

**Data Actions** section lets you trigger pipeline steps on demand:

| Button | Action |
|---|---|
| Pull Search Console Data | Runs `pull_search_console` in-process and returns JSON |
| Run Competitor Scrape | Runs `scrape_competitors` using `COMPETITORS_KEYWORDS_FILE` |
| Run Gap Analysis | Runs `run_gap_analysis` |
| Clear Dead URLs | Deletes all `DeadURLHit` records |
| Clear Internal Search | Deletes all `InternalSearchQuery` records |
| Clear Competitor Results | Deletes all `CompetitorSERPResult` records |

Destructive actions show a confirmation dialog before executing.

### Search Console Dashboard

**URL:** `/admin/seo_settings/searchconsoledashboard/dashboard/`

- 90-day trend chart (impressions vs clicks)
- Top 25 queries by click volume
- Top 25 pages by click volume
- "Pull Data Now" button to fetch fresh data without leaving the page

### Internal Search Dashboard

**URL:** `/admin/seo_settings/internalsearchdashboard/dashboard/`

- Top 20 search terms bar chart
- Recent 50 searches
- Terms searched only once (potential content gaps)
- "Clear All" button to purge records

### Dead URLs Dashboard

**URL:** `/admin/seo_settings/deadurlanalytics/dashboard/`

- Top 20 dead URLs by hit count
- Hits whose referrers include active competitor domains
- Top 25 referrers
- "Clear All" button

### Competitor SERPs Dashboard

**URL:** `/admin/seo_settings/competitorserpanalytics/dashboard/`

- Rank distribution chart
- Top 20 ranked competitor URLs
- Top keywords by competitor presence
- "Run Scrape" and "Clear Results" buttons

### Content Gap Dashboard

**URL:** `/admin/seo_settings/contentgapanalytics/dashboard/`

Read-only analytics view. Filters by status, competitor presence, and LC Psych
presence. Use the **Gap Review** UI (below) for triage and approval workflows.
Export the full filtered dataset to CSV with the Export button.

---

## Managing Competitors & Keywords

### Competitor Domains

**URL:** `/admin/seo_settings/competitordomain/manager/`

Add the domains you want the SERP scraper to track (e.g. `psychologytoday.com`,
`talkspace.com`). Only **active** domains are included in analytics and dead-URL
competitor-referrer matching.

### Keyword Seeds

**URL:** `/admin/seo_settings/keywordseed/manager/`

Keywords are grouped into four categories:

| Category | Examples |
|---|---|
| `service` | "anxiety therapy", "couples counseling" |
| `testing` | "adhd testing adults", "psychological evaluation" |
| `modality` | "cbt therapy", "EMDR therapy" |
| `location` | "therapist near me", "therapist [city]" |

Only **active** keyword seeds are used when filtering the Gap Review by category.

> **Note:** The competitor scraper uses a separate flat `keywords.txt` file
> (pointed to by `COMPETITORS_KEYWORDS_FILE`), not the database seeds. The seeds
> are used by the gap analysis engine and for dashboard filtering.

---

## Reviewing Content Gaps

**URL:** `/admin/seo_settings/contentgapanalytics/review/`

The Gap Review UI is the primary triage workflow after a gap analysis run.

### Status tabs

| Tab | Meaning |
|---|---|
| **Open** | New gaps not yet acted on (`resolved=False, ignored=False`) |
| **Approved** | Gaps marked as actioned (`resolved=True`) |
| **Dismissed** | Gaps flagged as not relevant (`ignored=True`) |
| **All** | Every record regardless of status |

### Filters

- **Category** — restricts to keywords in active `KeywordSeed` rows for that category
- **Competitor presence** — filter by whether a competitor ranks for this keyword
- **Recommended action** — free-text search within the recommendation text

### Per-row actions

- **✓ Approve** — marks the gap as resolved (AJAX, no page reload)
- **✗ Dismiss** — marks the gap as not relevant (AJAX, no page reload)
- **👁 Detail** — opens the full detail view for the keyword

### Bulk actions

Check one or more rows, then use **Approve selected** or **Dismiss selected**.
Both prompt a confirmation dialog with the count before executing.

### Detail view

**URL:** `/admin/seo_settings/contentgapanalytics/review/<pk>/`

Shows:
- Keyword, search volume, competitor/LC Psych presence flags, current status
- Full recommended action text
- **Competitor URLs** — ranked SERP results from `CompetitorSERPResult` for this keyword
- **LC Psych Pages** — Search Console pages for this query (clicks + avg position)
- Approve / Dismiss buttons

### Export to CSV

The **Export CSV** button on the review table exports the current filter selection.
Columns: Keyword, Search Volume, Competitor Presence, LC Psych Presence,
Recommended Action, Status (Approved/Dismissed/Open), Date.

---

## Testing Google API Credentials

**URL:** `/admin/seo_settings/seoglobalsettings/dashboard/`

On the Settings dashboard, two test buttons are available in the **Google
Credential Status** section:

### Test Google API

Verifies that the service account credentials (`GOOGLE_CLIENT_EMAIL` /
`GOOGLE_PRIVATE_KEY`) are valid by attempting an authenticated API call. Returns:

```json
{ "success": true, "message": "Credentials valid." }
```

or a descriptive error message if authentication fails.

### Test Search Console Connection

Verifies that the authenticated service account has access to the configured
Search Console property (`search_console_property_url`). Returns success with
the property URL, or an error if the account lacks access.

### Updating credentials

Credentials can be stored either as environment variables (recommended for
production) or directly in the Settings form. The Settings form values act as
an override — if the fields are populated in the database, they take precedence
over the environment variables at runtime.

---

## Data Flow Summary

```
Google Search Console API
         │
         ▼
 pull_search_console ──► SearchConsoleQuery
                                │
                                ▼
External SERP (scraper)         │
         │                      │
         ▼                      │
 scrape_competitors ──► CompetitorSERPResult
                                │
                                ▼
                       run_gap_analysis ──► ContentGapRecord
                                                   │
                                        ┌──────────┴──────────┐
                                        ▼                     ▼
                                  Gap Review UI         Content Gap
                                  (approve/dismiss)      Dashboard
                                        │
                                        ▼
                               Export CSV / resolved

Site traffic (automatic)
         │
         ├── 404/410 responses ──► DeadURLHit (via middleware)
         └── /search?q=… ────────► InternalSearchQuery (via middleware)
```
