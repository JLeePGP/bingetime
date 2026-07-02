**BingeTime.tv — Product & Build Spec**

Domain: [bingetime.tv](http://bingetime.tv): [https://www.namecheap.com/domains/registration/results/?domain=bingetime.tv](https://www.namecheap.com/domains/registration/results/?domain=bingetime.tv) 

Owner: John Lee

Status: v1 spec, pre-build

Last updated: 2026-07-01

# 1\. Positioning

BingeTime is a binge-watch utility and content hub, not a generic calculator clone. The differentiator is a personal video archive (20-50 previously-viral creator videos, TikTok/YouTube/IG) embedded alongside the utility tools. The nearest competitor, Bingeclock.com, has run since 2014 with gamification, an app, and a community layer — BingeTime does not compete on those features. It competes on content credibility and a cleaner, modern product.

**One-line pitch: Find out how long it takes to binge any show, see the original viral breakdown video, and plan your watch schedule.**

# 2\. Target user

* Someone deciding whether to start a series ("is this a big commitment?")

* Someone mid-binge or just finished, wants a shareable stat

* Discovery: organic search ("how long to watch \[show\]") \+ shared calculator/planner results

# 3\. V1 Scope

| Feature | In scope | Notes |
| :---- | :---- | :---- |
| Show catalog | Yes | Grid/search, TMDB-sourced base data |
| Creator video embeds | Yes | Static — 20-50 shows with John's archived videos; no ongoing production required |
| Watch-time calculator | Yes | Total runtime → hours/days/weeks, adjustable watch pace |
| Rewatch multiplier | Yes | How many times watched? input on calculator, multiplies total\_runtime\_min; powers shareable "I've spent X weeks/months/years on this show" stat  |
| Binge planner/calendar | Yes | Input hours/week available → finish-by date, .ics export |
| Binge stories submission | Yes | Replaces old Google Form; public feed, moderated (John approves before publish) |
| Accounts | Yes | Sign up/login, save shows, track future/past binges, persist planner across sessions |
| Movie theater marathon events | Out of scope (parked) | Separate experiential/events business; revisit once site has traffic/audience |
| Gamification (points, leaderboards, app) | Out of scope (parked) | Bingeclock's established moat; not a v1 differentiator |

## Account features, v1 (scoped down from Bingeclock's full set)

| Bingeclock feature | BingeTime v1 equivalent | In scope? |
| :---- | :---- | :---- |
| Future Binges | Watchlist — planner-linked, shows a user intends to watch | Yes |
| Past Binges | History — shows a user marked complete, with total time watched | Yes |
| Your Shelf | Merged into Watchlist/History (no separate "shelf" concept needed) | Merged |
| Marathons / Latest Marathons | Group/social binge-tracking | Parked |
| Leaderboards / Technical Analysis / The Trough / Bingerdle | Gamification layer | Parked |
| Events Calendar | Separate from accounts — see experiential events (Section 10\) | Parked |

# 4\. Data model

## shows

| field | type | notes |
| :---- | :---- | :---- |
| id | string | slug, e.g. one-piece |
| title | string |  |
| tmdb\_id | string | for data sourcing/refresh |
| category | enum | movie / tv / anime |
| seasons | int |  |
| episodes | int |  |
| avg\_runtime\_min | int |  |
| total\_runtime\_min | int (computed) | seasons × episodes × avg\_runtime |
| poster\_url | string |  |
| streaming\_platforms | array | for affiliate "watch now" links (JustWatch API) |
| has\_creator\_video | boolean | gates video embed section on show page |

## creator\_videos

| field | type | notes |
| :---- | :---- | :---- |
| show\_id | string | FK to shows |
| video\_url | string | TikTok/YouTube/IG link |
| platform | enum | tiktok / youtube / instagram |
| view\_count | int | social proof, display on card |
| thumbnail\_url | string |  |
| posted\_date | date |  |

## binge\_stories

| field | type | notes |
| :---- | :---- | :---- |
| id | string |  |
| show\_id | string (optional) | may not map to catalog |
| story\_text | string |  |
| submitted\_at | timestamp |  |
| status | enum | pending / approved / rejected |
| display\_name | string (optional) | anonymous by default |

## users

| field | type | notes |
| :---- | :---- | :---- |
| id | string |  |
| email | string |  |
| password\_hash | string | or magic-link/passwordless — see Section 8 |
| display\_name | string |  |
| created\_at | timestamp |  |

## user\_shows

| field | type | notes |
| :---- | :---- | :---- |
| id | string |  |
| user\_id | string | FK to users |
| show\_id | string | FK to shows |
| status | enum | watchlist / in\_progress / completed |
| times\_watched | int (optional) | multiplies total\_runtime\_min for this user's stat; default 1  |
| added\_at | timestamp |  |
| completed\_at | timestamp (optional) | set when status → completed |
| planner\_hours\_per\_week | int (optional) | persists planner input for this show |
| planner\_finish\_date | date (optional) | computed from planner input, persisted |

# 5\. Core user flows

* Search/browse → show page: user finds a show → sees poster, total watch time, embedded creator video (if exists) with view count, "watch now" affiliate links, and a planner widget.

* Calculator (standalone): homepage widget, no show page required — quick total-time lookup.

* Planner: on show page or standalone — input available hours/week → output finish date, export to calendar.

* Submit a binge story: form (title, story, optional show link) → pending queue → John approves → appears on public stories feed.

* Sign up/login: email \+ password (or magic link — see Section 8). No signup required to use the calculator; account is needed to save/track shows.

* Add to watchlist: from show page, "Add to Watchlist" → creates user\_shows row with status watchlist; planner inputs on that show now persist to the account.

* Mark as watching/completed: user updates status on their watchlist/history page; completed shows roll into a personal "total time watched" stat.

* View history: dashboard shows two lists — upcoming (watchlist/in\_progress) and past (completed) — mirroring Bingeclock's Future/Past Binges, without the gamification layer.

# 6\. Data sourcing

* Show/episode data: TMDB API (free tier, no cost for this volume). Pull seasons/episodes/runtime programmatically; refresh periodically for ongoing/new seasons.

* Streaming availability: JustWatch API (free tier) for "where to watch" affiliate links.

* Creator video list: manual compilation required — recommend exporting via TikTok's account data export (Settings → Account → Download Your Data) to get full post history with links/stats faster than manual scrolling.

# 7\. Monetization

| Method | v1 | Notes |
| :---- | :---- | :---- |
| Display ads | Later | Needs real traffic first; don't over-build ad infra before there's volume |
| Affiliate "watch now" links | v1 | JustWatch API integration, live from launch |
| Email capture (planner export) | v1 (lightweight) | Sets up future newsletter/premium tier, no hard paywall in v1 |
| Premium tier | Parked | Revisit post-traction |

# 8\. Tech recommendations

* Hybrid site: static/SSR for catalog/show pages (SEO-critical, public), authenticated app layer for accounts/dashboard.

* Backend: Python (FastAPI recommended) for all API/data-sourcing/auth logic, consistent with standing project preference.

* Database: Postgres (needed once accounts exist — SQLite is no longer sufficient given concurrent user writes).

* Auth: keep simple for v1 — email/password with a standard library (e.g. passlib) or a magic-link flow to avoid password-reset overhead. Avoid building custom session/auth infra from scratch.

* Moderation queue (binge stories) and account dashboard can share the same authenticated backend — no need for a separate admin system.

# 9\. Open items before build

* Compile creator video list (title, video\_url, platform, view\_count) — minimum 5-10 to start, target full 20-50

* Register bingetime.tv

* Confirm TMDB API access (free, no blocking issues expected)

* Confirm JustWatch API access/terms for affiliate use

* Decide auth method: email/password vs. magic link vs. managed provider

* Confirm Postgres hosting (accounts require a real database from v1, not flat files)

# 10\. Explicitly out of scope for v1 (parked ideas, revisit later)

* Movie theater all-day marathon events (experiential/events business, separate from the website)

* Gamification layer (points, leaderboards, companion app)

* Premium/paid tier