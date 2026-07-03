# BingeTime.tv

Binge-watch utility + content hub. Find how long it takes to binge any show,
watch the original viral breakdown, and plan your watch schedule.

All-Python stack: **FastAPI + Jinja2 SSR**, **Postgres** via **SQLAlchemy 2.0 +
Alembic**, **psycopg 3**. See `BingeTime-Spec.md` for the product spec.

## Project layout

```
app/
  main.py            FastAPI app, static/template mounts, caching middleware
  config.py          env-driven settings (.env)
  database.py        engine + session (pooled)
  models.py          shows, creator_videos, binge_stories, users, user_shows
  embeds.py          TikTok/YouTube/Instagram embed parsing
  templating.py      Jinja env + filters (humanize_count/runtime)
  services/          calculator.py, planner.py (pure logic), tmdb.py (client)
  routers/           catalog, calculator, planner, stories
  templates/         SSR pages
  static/            css + js (calculator.js, planner.js)
migrations/          Alembic (0001_initial_schema)
scripts/             import_videos.py, enrich_tmdb.py
tests/               calculator/planner/api tests (no DB needed)
```

## Setup

```bash
py -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
cp .env.example .env                                            # then edit
```

### 1. Provision Postgres (Railway)

1. railway.app → New Project → **Provision PostgreSQL**.
2. Postgres service → **Connect** → copy the **public** connection URL.
3. In `.env`, set `DATABASE_URL`, changing the prefix `postgresql://` →
   `postgresql+psycopg://` (rest unchanged).

### 2. Create the schema

```bash
./.venv/Scripts/python.exe -m alembic upgrade head
```

### 3. Import the creator videos + shows

```bash
./.venv/Scripts/python.exe -m scripts.import_videos
```

### 4. Seed video-less catalog entries + enrich with TMDB (needs `TMDB_API_KEY`)

```bash
./.venv/Scripts/python.exe -m scripts.seed_extra_shows
./.venv/Scripts/python.exe -m scripts.enrich_tmdb
# review auto-picked matches in tmdb_review.csv; fix a single show with:
./.venv/Scripts/python.exe -m scripts.enrich_tmdb --only the-flash
```

To access the story-moderation queue at `/account/moderation`, put your login
email in `ADMIN_EMAILS` in `.env`.

## Run

```bash
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload
# http://127.0.0.1:8000
```

## Test

```bash
./.venv/Scripts/python.exe -m pytest -q
```

## Data notes

- `shows.episodes` is the **total** episode count across seasons (TMDB's shape);
  `total_runtime_min = episodes × avg_runtime_min`. When TMDB omits the
  series-level runtime, enrichment averages a real season's episode runtimes.
- Ambiguous slugs are pinned in `app/titles.py` (`SEARCH_OVERRIDES`). **`fate`**
  anchors to *Fate/stay night* — TMDB has no single "franchise" record, so a
  franchise-total runtime (summing every Fate series) would be a separate
  feature if wanted. `gundam` anchors to the original 1979 *Mobile Suit Gundam*.
- Video-less catalog entries (e.g. *Fullmetal Alchemist: Brotherhood*, distinct
  from the 2003 *Fullmetal Alchemist*) live in `scripts/seed_extra_shows.py`.

## Status

Built: catalog (grid/search/filter/detail), watch-time calculator, binge
planner (+ .ics export), binge-story submission + public feed, TMDB enrichment,
and **accounts** — email/password signup/login (bcrypt + signed session
cookies), watchlist/history dashboard with total-time-watched stat, planner
persistence, and the admin story-moderation queue.

Auth note: the spec suggested passlib; it's unmaintained and breaks on Python
3.14, so we use the `bcrypt` library directly (same algorithm).

**Deferred:** password-reset email flow (needs an email provider), JustWatch
"watch now" links.

## Deploy (Railway)

The app deploys on Railway alongside the Postgres service (`railway.json` sets
the build/start/migrate steps). Connect the GitHub repo as a new service; every
push to `master` auto-deploys.

Set these service variables (Settings → Variables):

| Variable | Value |
|---|---|
| `DATABASE_URL` | the Postgres service's **internal** URL (`postgres.railway.internal`). The `postgresql://` prefix is auto-upgraded to `postgresql+psycopg://` in `config.py`. |
| `SECRET_KEY` | a long random hex string (`python -c "import secrets; print(secrets.token_hex(32))"`) |
| `DEBUG` | `false` — enables secure (HTTPS-only) session cookies and hides tracebacks |
| `TMDB_API_KEY` | your TMDB key |
| `ADMIN_EMAILS` | your email, for `/account/moderation` + `/account/feedback` |
| `BASE_URL` | `https://www.bingetime.tv` — builds absolute links in emails |
| `RESEND_API_KEY` | Resend API key (password-reset email). Unset = links logged, not sent |
| `EMAIL_FROM` | `BingeTime <noreply@bingetime.tv>` (verify the domain in Resend) |
| `CLARITY_PROJECT_ID` | Microsoft Clarity project id (analytics); unset = no snippet |

`preDeployCommand` runs `alembic upgrade head` before each release. Health check
is `/healthz`. Add the custom domain under Settings → Networking (auto-TLS,
HTTP→HTTPS redirect handled by Railway's edge).
