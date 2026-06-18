# Countrydle — Handoff

## What this is
A Discord bot running a daily "guess the country" game for a friend group (Wordle/Connections
style). Each day it posts a striking, geotagged photo from Wikimedia Commons; players get **one**
guess, scored by how close their country is to the real one.

- **Repo:** https://github.com/dotdandotunderscore/countrydle (public, `main`)
- **Local path:** `/Users/daniel.woods/Documents/extras/countrydle`
- **Design summary + setup:** see `README.md` in the repo (don't duplicate it).
- **Stack:** Python 3.9, discord.py 2.x, SQLite. Target host: **Railway** (long-running worker).

## Status: Phases 1–5 complete, Phase 6 not started
- Phase 1 ✅ scaffold, config, SQLite schema, scoring math
- Phase 2 ✅ Wikimedia Commons sourcing pipeline (98 puzzles were queued during dev)
- Phase 3 ✅ `/guess` + gated results board
- Phase 4 ✅ daily scheduler (auto-post + reveal-previous w/ attribution)
- Phase 5 ✅ leaderboards, streaks, share text, 🚩 report + `/skip`
- **Phase 6 ⬜ Railway deploy** (`Procfile` / worker service, env vars) + any final EXIF/resize polish
- **30 tests passing** (`python -m pytest`). Test files in `tests/`.

The **next concrete task** is Phase 6: deploy to Railway. Before then, the user planned to
**test the bot locally** against a real Discord server — they may report bugs from that first.

## Architecture (where things live)
All game logic is in pure, unit-tested modules; Discord cogs are thin wrappers (the Discord
interaction layer itself is NOT unit-tested — no token in CI).

- `countrydle/config.py` — env-driven `Config` dataclass
- `countrydle/db.py` + `schema.sql` — SQLite (`users`, `puzzles`, `guesses`); `puzzles.message_id`
  added via an idempotent `_migrate()` in `init_db`
- `countrydle/game/scoring.py` — haversine + `score_for_distance` (decay 2000 km, exact=100)
- `countrydle/game/countries.py` — 244-country centroid registry, fuzzy `resolve()`,
  `distance_between()`, `flag_emoji()`
- `countrydle/game/repository.py` — **all stateful game logic**: guess recording (one-per-day via
  UNIQUE), board, `rotate_daily`, `void_live`, leaderboard, `current_streak`, `user_stats`
- `countrydle/game/share.py` — Wordle-style spoiler-free share line
- `countrydle/sourcing/commons.py` — MediaWiki API fetch, prefers object-location coords,
  attribution from extmetadata
- `countrydle/sourcing/geocode.py` — offline reverse-geocode (coords → ISO2)
- `countrydle/sourcing/candidates.py` — quality filters + queue; `DEFAULT_CATEGORIES` tuned to
  landscape/nature/cityscape categories
- `countrydle/sourcing/images.py` — download + downscale + strip EXIF + re-encode (kills GPS AND
  the Commons filename, which leaks the country in the URL)
- `countrydle/cogs/guess.py` — `/guess` (autocomplete + one-shot confirm), `/results` (gated)
- `countrydle/cogs/daily.py` — `tasks.loop` daily post, reveal embed, `/postnow`, `/skip`,
  🚩 report listener (auto-void at `REPORT_THRESHOLD = 3`)
- `countrydle/cogs/stats.py` — `/leaderboard`, `/stats`, `/share`
- `main.py` — builds bot, sets `bot.config`/`bot.db_path`, loads 3 cogs, syncs slash commands to guild
- `scripts/` — `build_countries.py`, `fetch_candidates.py`, `init_db.py`, `set_live.py` (dev helper)

## Key design decisions (already settled with the user)
- **Photos:** Wikimedia Commons Featured/Quality-image categories only (community curation = zero
  manual approval). Narrowed from the firehose after a dev run showed too much indoor/object junk.
- **One guess/day, distance-scored.** Exact country = 100.
- **Spoiler-safe + social:** you see nothing about others until your own guess is locked; then the
  full board (country + distance + score) opens via `/guess` reply and gated `/results`.
- **Cadence:** rolling 24h — next day's post reveals yesterday's answer + attribution + leaderboard.
- **Discussion happens in the main channel** (no auto spoiler-thread).
- Attribution is **legally required** (CC images) and is built into the reveal embed.

## Environment / running
- Env vars (see `.env.example`): `DISCORD_TOKEN`, `GUILD_ID`, `CHANNEL_ID`, `ADMIN_IDS`,
  `TIMEZONE`, `POST_HOUR`, `DATABASE_PATH`. **No secrets are committed** (`.env`, `data/game.db`,
  `.venv` are gitignored).
- Dev venv at `.venv/` (local only). `pip install -r requirements-dev.txt` for tests;
  `requirements.txt` for runtime.
- No privileged Discord intents needed (slash commands + reactions only). Invite scopes:
  `bot` + `applications.commands`; perms: Send Messages, Embed Links, Attach Files, Add Reactions,
  Read Message History.

## Open items / watch-outs
- **Phase 6 not done:** needs a `Procfile` (e.g. `worker: python main.py`), Railway env-var setup,
  and a persistent SQLite volume (Railway ephemeral disk will wipe `data/game.db` on redeploy —
  mount a volume or move DB to the volume path). Candidate-fetch is a manual script today; decide
  whether to run it on a schedule or pre-seed the queue before deploy.
- Reverse-geocoder pulls scipy/numpy (heavy); fine on Railway but affects image/build size.
- Local env runs Python 3.9 with LibreSSL → a harmless urllib3 `NotOpenSSLWarning` in test output.
- Slash commands sync per-guild on startup (fast). If they go multi-server later, switch to global sync.

## Suggested skills for the next session
- **`security-review`** — run before/around the public deploy: token handling, the report-void
  abuse path (3 reactions voids a puzzle — is that exploitable?), and Commons URL/EXIF leak checks.
- **`code-review`** — review the Phase 5 diff and Phase 6 deploy changes before shipping.
- **`verify`** — confirm the bot actually runs and posts once a token + test server exist.
- **Note:** the user has **caveman mode active** (terse responses). Keep responses terse;
  drop caveman only for multi-step setup sequences or warnings.
