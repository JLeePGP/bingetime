# BingeTime Blog Content Agent — Spec v2

**Status:** approved for build pending final review. Updated 2026-07-05 after a strategy review — **supersedes v1.**
**Changed from v1:** personas removed (author is always **BingeTime**); content rebalanced **data-first for ranking**; added AEO (direct-answer + schema); demand-driven title ideation (Search Console + trending); a **data-study / link-bait** archetype; a distribution section.
**Prereq shipped:** the blog admin CMS at `/account/blog` (list, create/edit/schedule/publish/delete, draft/scheduled/live gating). This agent feeds drafts into it.

---

## 1. Purpose & guardrail

A steady stream of on-brand, **rank-and-cite-optimized** posts without John hand-writing each one, human firmly in the loop. The agent **proposes titles only**; it never writes a post until John selects a title or types his own. Every post lands as a **draft** for review before publish. Nothing publishes autonomously.

---

## 2. Strategic frame (read this first)

- **BingeTime's strongest SEO/AEO asset is the catalog, not the blog.** The show pages answer "how long to binge X" — high-intent, low-competition, uniquely answerable from proprietary data, and perfect for AI answer engines. The blog is a **complementary discovery layer**: it captures broader/editorial queries the catalog can't, earns backlinks, feeds internal links into the money pages, and adds freshness.
- **Priority order:** (1) rank + get cited via **data-grounded** content, (2) earn **backlinks** via data studies, (3) drive **engagement** via a *minority* of opinion.
- **New-domain reality:** organic traffic takes ~3–6+ months to build on a domain this young. Near-term value is AEO citations, shareable/linkable assets, and building the content base — not Google traffic next month. This is why we lean data-first and link-bait, not opinion.

---

## 3. Content archetypes & mix (data-first)

Weighted toward ranking and links; opinion is the minority spice.

1. **Data list / ranked roundup — PRIMARY workhorse.** "12 anime you can finish this weekend, ranked by exact runtime." Long-tail, low-competition, uniquely answerable from our data. This is what actually ranks for a young domain.
2. **Data study / link-bait.** Novel aggregate analyses designed to *earn backlinks and AI citations* — "We added up the total runtime of every show on Netflix; here's the longest binge on the platform." Backlinks are the one thing a new domain can't fake, and our data is a link-generating machine most sites don't have.
3. **Timely / trending.** Ride shows spiking in the viral-video feed, while there's active search + social demand for them.
4. **Opinion / hot take — MINORITY.** Stances for engagement and shareability ("the most overrated anime of 2026"). Kept deliberately small: it's the weakest ranking play and the highest AI-slop risk, but it's genuinely shareable.

Default ideation weights 1–3 heavily. Any *number* in any archetype is real catalog data (§4.2); opinion is allowed, not the default.

---

## 4. The three hard rules (enforced in code, not just prompt)

- **4.1 Zero em-dash.** No `—`, `--`, `–`, `&mdash;`, `&ndash;`, `&#8212;`, `&#8211;` anywhere in title, excerpt, kicker, TL;DR, or body — ever. Code-guaranteed by a normalizer at save (§10). Models reach for em-dashes constantly, so this is a guarantee, never a prompt hope.
- **4.2 Data moat (stats only).** Opinions unrestricted; any number/metric (runtime, episodes, seasons, year, rating) comes strictly from a pre-computed catalog payload. The agent writes prose *around* it and **never does its own arithmetic**. Aggregates are computed by our code, never by the model.
- **4.3 Show links.** Raw HTML; every catalog show a post leans on links to `/shows/{slug}`, **first mention only**, via an explicit marker validated against the catalog on save (§9). Never fuzzy prose-matching (titles like "You"/"It"/"Dark"/"1899" would produce disastrous false positives). Non-catalog shows may be mentioned but stay unlinked and stat-free; writing biases hard toward catalog shows.

---

## 5. Voice: two layers, brand-authored

Final voice = **base anti-slop** + **style preset**. Author is always **BingeTime** (no personas).

- **Base anti-slop (always on).** Casual, informal, authentic — an avid TV fan talking to a friend. Slang, jokes, varied sentence length, fragments for rhythm, conversational pacing. **No** robotic AI cadence, no "Let's dive in / Here's the thing / In conclusion", no uniform sentence rhythm. Imperfect *rhythm*, not broken text (no actual typos/grammar errors).
- **Style presets (pick one per post).** Light seasoning: **Funny / Educational / Roast / Hype / Chill.** Data pieces default toward a clear, informative tone; Roast is opinion-spice, punching at *shows* not real people. Style is subordinate to structure (below).
- **Author = BingeTime.** Byline and JSON-LD `author` = the brand/Organization (legit E-E-A-T, matches existing Organization schema). No fabricated human bylines.

**Hybrid structure (the key AEO move).** Every ranking post has a **clean, extractable skeleton** — a direct-answer TL;DR up top + a ranked list/table with real numbers — **wrapped in the conversational voice** (the connective prose). Structure serves the answer engines (liftable, citable); voice serves the human reader (engaging). The skeleton is clean; the paint is personality.

---

## 6. Length

Targets with **±75-word jitter, never exact:** Short ≈300, Medium ≈600, Long ≈900. **Surprise me** = a random target across ~300–1000. Hard rule: **never pad to hit the number** — the anti-slop rule wins ties.

---

## 7. Title ideation — demand-driven

On-demand **"Suggest titles"** button, **5 per click**, deduped against existing drafts/published posts. Ideation is fed by real demand, not just "what the catalog can support":

- **Google Search Console query data — primary, free, already connected.** Within a few weeks GSC shows the actual queries BingeTime gets impressions for; write posts to capture them. This is first-party and compounds over time.
- **Trending shows** from the viral-video feed (real-time demand signal).
- **Seed signals** — a manual seed-query list + Google autocomplete / People-Also-Ask (web-search-assisted).
- **Catalog-supportable angles** — what our data can uniquely answer.

Each suggested title carries its **grounding**: archetype (data list / study / trending / opinion), the catalog shows it anchors on (validated to exist), and for data/list angles the real count/number (locked before John picks — a "9 shows" title is backed by 9 real shows). John picks one, or types his own (which the agent then grounds, or writes as a no-stats opinion piece).

> **v1 pragmatics:** GSC data is thin for the first few weeks on a new domain anyway, so v1 ideation runs on **trending + seed list + catalog angles**, and **GSC API integration is a fast-follow** once there's query data worth mining.

---

## 8. Draft generation & output contract (AEO-aware)

Our code assembles: the committed **title** + **style** + **length target** + a compact **data payload** (anchor shows' citable fields + our pre-computed aggregates) + the cached system prompt (voice + rules + archetypes + contract). The agent returns structured JSON (`messages.parse()`), guaranteeing shape:

```
{
  "tldr":        "…",                    // 1–2 sentence direct answer — renders up top + feeds meta/AEO
  "body_html":   "<p>…</p> …",           // raw HTML; show links as <x-show slug="…">Title</x-show>
  "list_items":  [                       // structured (for ItemList schema + clean rendering); [] if not a list
    {"show_slug": "one-piece", "value": "1,050+ hrs", "note": "…"}, …
  ],
  "faq":         [{"q": "…", "a": "…"}], // optional — powers FAQPage schema; [] if none
  "excerpt":     "…",                    // ≤ ~200 chars — card + meta description
  "kicker":      "WEEKEND BINGE",        // 2–4 words, cover label (NOT the title)
  "cover_show":  "one-piece",            // slug to pull the cover poster from (or null)
  "shows_cited": ["one-piece", …]        // every slug the body links; validated on save
}
```

Title is fixed (John chose it), so it isn't returned. **Citable data surface = core `Show` fields + our computed aggregates ONLY.** Excluded from v1: creator-video view counts and user binge-stories.

---

## 9. Show-link mechanics

Agent wraps the **first mention** of each cited show as `<x-show slug="one-piece">One Piece</x-show>`. On save: validate each slug against the catalog → expand valid ones to `<a href="/shows/{slug}">Display</a>` → unwrap+flag invalid slugs to plain text → strip second+ occurrences (first-mention-only). Same validation applies to `list_items[].show_slug`. No fuzzy matching, ever.

---

## 10. Validation, lint & retry

Per draft: (1) structured-output parse guarantees shape → (2) **dash lint** on all text fields → (3) **slug validation** on every `<x-show>` and `list_items`/`shows_cited` entry → (4) **HTML sanitize** (allowlist `p, h2, h3, ul, ol, li, a, strong, em, blockquote, br, img, table, thead, tbody, tr, th, td`) → (5) length sanity (flag, not hard reject).

**Failure policy:** dash/slug failure → **one corrective retry** ("you used a banned dash / an invalid show — fix it, keep the rest"); if still failing → deterministic cleanup (normalize dashes, unwrap invalid links) + a **review flag** on the draft so John sees what was auto-fixed. Drafts always land; flagged when the net caught something.

---

## 11. LLM integration

- **Provider:** Anthropic API (Claude) via the official `anthropic` Python SDK. New dependency + a dedicated secret.
- **Key:** a dedicated **`ANTHROPIC_API_KEY`** so this agent's spend is isolated/trackable, env-gated like `RESEND_API_KEY` / `TMDB_API_KEY` / `CLARITY_PROJECT_ID` (Railway env + local `.env`). **Build step:** John creates the dedicated key and drops it where directed.
- **Model:** default **`claude-opus-4-8`** (best writing for published content). Cost option **`claude-sonnet-5`** (~half price, intro $2/$10 per 1M through 2026-08-31). Single config value — John's call at build.
- **Thinking / effort:** adaptive thinking; `effort: "high"` for drafting, `medium` for title ideation. Tunable.
- **⚠️ No temperature knob.** `temperature`/`top_p`/`top_k` are **rejected (400)** on Opus 4.8 / Sonnet 5. Voice variety and "human imperfection" come **entirely from prompting** (style preset + explicit vary-rhythm/fragment instructions) and the length jitter — not a sampling parameter. Hard API constraint.
- **Structured outputs:** `messages.parse()` against the §8 schema.
- **Prompt caching:** the stable system prompt (voice + rules + archetypes + contract, well over the 4096-token minimum) is marked `cache_control`; volatile bits (title, data payload, existing-titles list) go after the breakpoint. Repeat calls read the prefix at ~0.1× input cost.
- **Execution:** synchronous for v1 (click → ~10–30s → draft), streaming under the hood so large outputs don't hit HTTP timeouts.
- **Cost (ballpark):** ~$0.02–0.10 per 5-title click; ~$0.10–0.25 per post on Opus, <~$0.10 on Sonnet (caching lowers both).

---

## 12. Cover art

Every post gets a thumbnail (blog tab shows images, not a wall of text). **No AI image generation** in v1 (cost + copyright/licensing on show art + off-brand risk). **The on-site cover must not repeat the post title** (the title renders right below it — reads as a stutter).

- **On-site cover = imagery only.** Pillow-composed (same tool as `og-default.png`): poster-forward (single **hero poster** for single-show posts; a **2–3 poster collage** for roundups, which also signals post type), brand gradient + **category tint** (movie / tv / anime accent colors), and a short **kicker** — `CATEGORY` or the agent's 2–4 word label (e.g. "ANIME", "WEEKEND BINGE", "DATA") — as a design element, not the headline. Fallback: plain brand-gradient card when there's no obvious poster.
- **Social/OG share image = title-bearing card.** Generated separately (the one context where the image travels without the headline beside it, so title-on-image lifts CTR). Populates `share_image_url`, distinct from the on-site `cover_image_url`.
- Generated cards are written into `static/img/` and referenced by URL.

---

## 13. Admin UI additions (on `/account/blog`)

Add a **Generate panel** to the existing post-list screen:
- **"Suggest titles"** → 5 suggestions, each with its grounding (archetype + anchor shows + demand source); **"Regenerate suggestions"** re-rolls.
- **Generate form:** pick a suggested title **or** type your own + **style** dropdown (Funny / Educational / Roast / Hype / Chill) + **length** (Short / Medium / Long / Surprise me) → **"Draft it"** (spinner ~10–30s). *(No persona/author field — author is always BingeTime.)*
- Result lands as a draft. Each agent draft gets a **"Regenerate"** action (same or tweaked style/length) that replaces body/excerpt/cover.
- Review flags (§10) surface as a small note on flagged drafts.

Everything else (edit, schedule, publish, delete, gating) already exists.

---

## 14. Data-model changes (migration 0005)

Add to `BlogPost`:
- `share_image_url` (nullable) — title-bearing OG/social card, distinct from `cover_image_url`.
- `kicker` (nullable) — short cover label.
- `tldr` (nullable) — direct-answer line (top of post + meta + AEO).
- `list_items` (nullable JSON) — structured list for ItemList schema + rendering.
- `faq` (nullable JSON) — Q/A pairs for FAQPage schema.
- `source` (`'manual' | 'agent'`, default `'manual'`) — provenance.
- `review_flags` (nullable JSON/text) — what the lint auto-fixed.
- *(optional)* `gen_meta` (JSON) — style / length target / model / effort, for auditing.

Also: make the **slug editable while a post is a draft** (custom slug field), locking at first publish. `author` stays a string defaulting to **"BingeTime"** (no persona field, no author dropdown).

---

## 15. SEO / AEO integration

- Existing per-post **Article + Breadcrumb** JSON-LD, OG, canonical, sitemap (live-only), and draft/scheduled/live gating all carry over. `share_image_url` becomes `og:image` when present.
- **New:** emit **ItemList** JSON-LD from `list_items` on ranked-list posts, and **FAQPage** JSON-LD from `faq` where present. Lead the body with the **direct-answer TL;DR** (the answer-box pattern) so answer engines can lift and cite it.
- **Parallel high-ROI recommendation (not this agent, but flagged):** give the **catalog/show pages** the same direct-answer + FAQ/schema treatment. They're stronger AEO targets than the blog ("how long to binge X" is a single-answer factual query we own). Worth its own small workstream.

---

## 16. Distribution

Content production ≠ discovery. The agent produces posts; getting them seen is partly its job (via *what* it writes) and partly a manual workstream.

- **Agent-side content types that distribute themselves:**
  - **Data study / link-bait (§3.2)** — earns the backlinks a young domain needs.
  - **Trending (§3.3)** — rides existing search + social demand.
  - **AEO structure (§15)** — AI-answer citations are themselves a discovery channel.
- **Manual (John's workstream, not the agent):** seed genuinely-useful data posts into Reddit (r/anime, r/television, show subs) and short-form social using the share cards. Useful > promotional, or it gets flagged as spam.
- **Future (John, once cashflow):** run **paid ads against the viral videos** to drive initial traffic to the site and gauge real engagement/reactions. This is the near-term plan for getting the first real audience while organic builds.

---

## 17. Out of scope for v1 (future)
Comment section; AI-generated cover imagery; autonomous/scheduled title suggestion or publishing; citing creator-video view counts or user binge-stories; author personas (removed entirely).

---

## 18. Build sequence
1. Migration 0005 (new `BlogPost` fields) + draft-slug editability in the CMS.
2. Anthropic client wiring + `ANTHROPIC_API_KEY` env plumbing (John supplies the dedicated key).
3. Data-payload + aggregate builders (citable-facts surface from the catalog).
4. Prompt assembly: cached system prompt (voice + rules + archetypes + output contract) + per-request user content.
5. Title ideation endpoint (demand-fed: trending + seed list + catalog angles for v1; grounded, deduped, 5/click).
6. Draft generation endpoint (structured output → validate/lint/retry → persist draft).
7. SEO/AEO rendering: TL;DR block + ItemList/FAQPage JSON-LD.
8. Cover + share-image composition (Pillow, category tint).
9. Admin Generate panel + Regenerate.
10. End-to-end verify (rolled-back transaction, like the CMS verify) + live smoke test on the dedicated key.
11. *(Fast-follow)* GSC API integration to feed real query data into ideation.

---

## 19. Open items to confirm at build
- **Model lock:** Opus 4.8 (default) vs Sonnet 5 (cheaper) — John's call.
- Final **style-preset** tone calibration + sample outputs.
- `effort` levels after a quick quality/latency check.
- Kicker wording rules + category accent colors for covers.
- Whether GSC integration is v1 or fast-follow (default: fast-follow).
