"""Seed ~200 more catalog shows: Netflix hits, reality TV, and K-dramas.

Slug -> humanized title drives the TMDB search (see app/titles.py); category is
'tv' for all of these. Idempotent: existing slugs are skipped. Netflix-bucket
shows get streaming_platforms=['Netflix']. Run enrich_tmdb afterwards to fill
runtime/episodes/poster/rating from TMDB:

    python -m scripts.seed_more_shows
    python -m scripts.enrich_tmdb
"""
from __future__ import annotations

from app.database import SessionLocal
from app.models import Category, Show
from app.titles import humanize

# Netflix originals / exclusives (streaming_platforms -> Netflix).
NETFLIX: list[str] = [
    "wednesday", "the-witcher", "bridgerton", "money-heist", "dark", "ozark",
    "narcos", "the-umbrella-academy", "lucifer", "cobra-kai", "outer-banks",
    "ginny-and-georgia", "emily-in-paris", "the-sandman", "shadow-and-bone",
    "locke-and-key", "never-have-i-ever", "elite", "lupin", "the-queens-gambit",
    "maid", "beef", "the-night-agent", "3-body-problem", "sweet-tooth",
    "blood-of-zeus", "big-mouth", "virgin-river", "sweet-magnolias", "dead-to-me",
    "grace-and-frankie", "unbelievable", "when-they-see-us", "mindhunter",
    "the-haunting-of-hill-house", "midnight-mass", "vikings-valhalla",
    "the-last-kingdom", "russian-doll", "glow", "orange-is-the-new-black",
    "house-of-cards", "sense8", "altered-carbon", "love-death-and-robots",
    "ratched", "inventing-anna", "dahmer", "the-watcher", "the-diplomat",
    "fool-me-once", "the-lincoln-lawyer", "the-recruit", "1899",
    "the-fall-of-the-house-of-usher", "griselda", "the-gentlemen", "heartstopper",
    "the-brothers-sun", "eric", "supacell", "the-perfect-couple", "kaos",
    "bodkin", "bodies", "sex-education", "you", "the-crown", "stranger-things",
    "the-empress", "one-day", "baby-reindeer", "xo-kitty",
]

# K-dramas.
KDRAMA: list[str] = [
    "crash-landing-on-you", "goblin", "itaewon-class", "descendants-of-the-sun",
    "the-glory", "vincenzo", "hometown-cha-cha-cha", "business-proposal",
    "extraordinary-attorney-woo", "its-okay-to-not-be-okay", "start-up",
    "reply-1988", "signal", "kingdom", "sweet-home", "my-name", "hellbound",
    "all-of-us-are-dead", "d-p", "move-to-heaven", "mr-sunshine", "sky-castle",
    "strong-girl-bong-soon", "weightlifting-fairy-kim-bok-joo",
    "whats-wrong-with-secretary-kim", "boys-over-flowers", "the-heirs",
    "my-love-from-the-star", "w-two-worlds", "while-you-were-sleeping",
    "hotel-del-luna", "tale-of-the-nine-tailed", "the-king-eternal-monarch",
    "true-beauty", "nevertheless", "twenty-five-twenty-one",
    "our-beloved-summer", "hospital-playlist", "prison-playbook", "misaeng",
    "stranger", "my-mister", "when-the-camellia-blooms",
    "crash-course-in-romance", "the-uncanny-counter", "alchemy-of-souls",
    "little-women", "reborn-rich", "taxi-driver", "juvenile-justice",
    "yumis-cells", "queen-of-tears", "lovely-runner", "the-good-bad-mother",
    "my-demon", "gyeongseong-creature", "doctor-slump", "twinkling-watermelon",
    "a-time-called-you", "the-uncanny-counter-2", "moving", "mask-girl",
    "celebrity", "daily-dose-of-sunshine", "castaway-diva", "my-name-is-loh-kiwan",
    "flower-of-evil", "it-s-okay-to-not-be-okay", "18-again", "record-of-youth",
]

# Reality / competition / docuseries.
REALITY: list[str] = [
    "love-is-blind", "too-hot-to-handle", "the-circle", "selling-sunset",
    "queer-eye", "nailed-it", "the-great-british-baking-show", "is-it-cake",
    "love-on-the-spectrum", "indian-matchmaking", "bling-empire", "cheer",
    "tiger-king", "making-a-murderer", "survivor", "big-brother", "the-bachelor",
    "the-bachelorette", "keeping-up-with-the-kardashians",
    "the-real-housewives-of-beverly-hills", "rupauls-drag-race", "top-chef",
    "hells-kitchen", "masterchef", "the-amazing-race", "american-idol",
    "the-voice", "americas-got-talent", "dancing-with-the-stars",
    "project-runway", "shark-tank", "deadliest-catch", "below-deck",
    "vanderpump-rules", "jersey-shore", "90-day-fiance", "love-island",
    "married-at-first-sight", "naked-and-afraid", "the-ultimatum",
    "perfect-match", "physical-100", "singles-inferno", "the-mole",
    "squid-game-the-challenge", "dance-moms", "fixer-upper", "sugar-rush",
    "formula-1-drive-to-survive", "last-chance-u", "chefs-table",
    "queer-eye-were-in-japan", "the-great-pottery-throw-down", "old-enough",
    "the-floor-is-lava", "next-in-fashion", "blown-away", "instant-hotel",
    "the-final-table", "rhythm-plus-flow", "outlast", "beast-games",
    "americas-next-top-model", "project-greenlight", "the-apprentice",
    "hell-on-wheels", "the-mole-2022", "welcome-to-plathville",
]

CATEGORY = Category("tv")


def run() -> None:
    added = skipped = 0
    seen: set[str] = set()  # guard against repeated slugs within the lists
    with SessionLocal() as db:
        buckets = [(NETFLIX, ["Netflix"]), (KDRAMA, None), (REALITY, None)]
        for slugs, platforms in buckets:
            for slug in slugs:
                if slug in seen or db.get(Show, slug) is not None:
                    skipped += 1
                    continue
                seen.add(slug)
                db.add(
                    Show(
                        id=slug,
                        title=humanize(slug),
                        category=CATEGORY,
                        has_creator_video=False,
                        streaming_platforms=platforms,
                    )
                )
                added += 1
        db.commit()
    print(f"More shows: +{added} added (skipped {skipped} already-existing).")


if __name__ == "__main__":
    run()
