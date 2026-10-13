# Doc Gap Finder

Reads a batch of support tickets, groups them by topic with Claude, and checks each ticket against a public docs site. It flags the topics with lots of tickets and weak coverage, drafts a help article for the biggest gap, and re-checks the open tickets against the draft to give a before-and-after number.

It works on any help center with a sitemap. This run used Claude's own public docs.

- **Live demo:** https://doc-gap-finder.caseyledbetter.com
- **Stack:** Python (no framework), Claude API with structured outputs, BM25 search, SQLite or Supabase for the inbox, static site on Vercel.

## Results from this run

- **21 of 100 tickets (21%) had no doc that answered them**, and 43% had weak or no coverage.
- **Biggest gap: moving to a lower plan** (Max 20x to 5x, Max to Pro, annual to monthly). 13 tickets, 0 fully answered.
- **The drafted article answers 9 of the 21 unanswered tickets (43%)**, taking no-doc tickets from 21% to 12%.
- Bonus finding: one help article tells users to "change your password" while another says Claude accounts can't have one.

## Files

| File | What it does |
|---|---|
| `crawl_docs.py` | Crawls the sitemaps in `config.json` into `data/docs_index.jsonl` |
| `search.py` | BM25 search over the snapshot, no extra dependencies |
| `inbox.py` | Simulated helpdesk: replays `data/tickets.json` into a SQLite queue in arrival order |
| `find_gaps.py` | The pipeline: group, check coverage, rank, draft, re-check. Writes `output/results.json` |
| `build_report.py` | Builds the demo page: `output/report.html` and `site/index.html` (what Vercel serves) |
| `supabase/migrations/` | The `tickets` table for running the inbox on Supabase, with RLS on |
| `data/make_tickets.py` | Generates the 100 fictional tickets |
| `data/offline_judgments.json` | Saved Claude judgments so the pipeline runs without an API key |

## Run it

```
pip install anthropic beautifulsoup4
cp .env.example .env.local  # optional: add an API key or Supabase settings
python crawl_docs.py        # builds data/docs_index.jsonl (not committed)
python inbox.py replay
python find_gaps.py          # live with ANTHROPIC_API_KEY, otherwise uses saved judgments
python build_report.py
```

To preview the site locally, run `python -m http.server 3000 -d site` and open http://localhost:3000.

## Environment variables

All optional. See `.env.example`.

- `ANTHROPIC_API_KEY`: makes `find_gaps.py` call Claude live. Without it, the saved judgments are used.
- `SUPABASE_URL` and `SUPABASE_SECRET_KEY`: puts the inbox in a Supabase `tickets` table instead of `data/helpdesk.db`. Run the migration in `supabase/migrations/` first (paste it into the SQL editor or use `supabase db push`). The secret key stays on your machine; the public site never talks to Supabase, so it keeps working even when a free project pauses.

## Deploy

Vercel serves the `site/` folder as a static site (see `vercel.json`), so there's no build step and no environment variables on Vercel. After a new run, `python build_report.py` and push.

## How this run was done

No API key was set in the build environment, so Claude did the grouping, coverage checks and article draft inside a Claude Code session, reading the same retrieved docs the script would send. Those outputs are saved in `data/offline_judgments.json` in the exact shape the API calls return. With a key set, `find_gaps.py` makes the calls itself using `claude-opus-5-5` with structured outputs. The live path hasn't been run end to end yet.

Tickets are fictional. The docs snapshot is real: 992 pages crawled October 13, 2026.
