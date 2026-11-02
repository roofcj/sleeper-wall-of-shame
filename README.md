# Sleeper Fantasy Wall of Shame

Automatically tracks **every starter with 0.00 or negative fantasy points**, but only **after that player's NFL game has finished**. Maintains a season-long leaderboard, a shareable static webpage, CSV export, and optional Discord announcements. No subscription, additional Python packages, Sleeper login, or API key required.

**Your Sleeper league ID is already configured: `1391788553402347520`.** No edits or league variables are needed. The tracker looks up your real league name, season, managers, starting lineups and scoring from the Sleeper API on its first connected run. The sample dashboard is fictional and labeled as such. The league API could not be queried from the environment that prepared this package, so live results have **not** yet been verified; the first run will check your ID.

## What counts as a bust?

- The player must be in Sleeper's **`starters`** array for that week; bench players are ignored.
- Sleeper's **`starters_points`** value must be **less than or equal to `0.00`**, using your league's real scoring settings.
- The player's NFL team must have an NFL game marked **final** by ESPN. A player on bye is skipped.
- An injured, inactive, or nonplaying starter may count as a zero **if their NFL team played a completed game**.
- Empty lineup slots (`"0"`, blank, or null) are ignored, as are missing/unavailable scores.
- Every qualifying start counts once per `(season, week, roster, player)`; stat corrections can alter the record on a later scan.

## Your league settings

- Sleeper league ID: **`1391788553402347520`**
- League URL: https://sleeper.com/leagues/1391788553402347520
- Configured as the default in `tracker.py` and in the scheduled GitHub workflow.
- You can override it later with the `SLEEPER_LEAGUE_ID` GitHub Actions variable or `--league-id` command-line option.

## Option A — Set up automatic tracking (recommended)

This uses **GitHub Actions** to run the tracker on GitHub's servers **and to deploy the refreshed dashboard directly to GitHub Pages**. It works while your computer is off.

1. Create a free GitHub account, if needed, then create a new **public repository** (for example `sleeper-wall-of-shame`). The published results will be public, including fantasy team and manager display names. Make a private repository instead if you don't want publicly accessible source/data, but confirm your GitHub plan's Pages options before choosing it.
2. Extract the ZIP, then upload **the files and folders inside the extracted directory** (not the ZIP itself or its containing folder) to the repository's **main** branch. Be sure `.github/workflows/update.yml` is included: GitHub Actions cannot run without that file. If your file explorer hides dot-prefixed directories, enable hidden items.
3. **No league ID setup required.** This download already uses `1391788553402347520` by default. (Optional: add a GitHub Actions variable called `SLEEPER_LEAGUE_ID` to switch to another league.)
4. Go to **Settings → Pages**. Under **Build and deployment → Source**, select **GitHub Actions**. Do **not** select "Deploy from a branch": commits made by the GitHub Actions bot do not automatically trigger branch-based Pages builds. The included workflow uploads and deploys the site itself.
5. Go to **Actions → Update Sleeper Wall of Shame → Run workflow** on **main**. Watch the **refresh** and **publish** jobs; both should turn green. The tracker scans past weeks, generates `docs/index.html`, `docs/busts.csv`, and `docs/leaderboard.json`, and publishes them.
6. Open **Settings → Pages → Visit site** to get the published URL, normally `https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY-NAME/`. GitHub Actions is scheduled every **30 minutes**; scheduled jobs and page updates can be delayed. It is not guaranteed instant.

### Optional: Discord notifications

Create a **Discord channel webhook** (Discord server/channel Settings → Integrations → Webhooks; appropriate permissions are required). In **GitHub → Settings → Secrets and variables → Actions → Secrets**, add `DISCORD_WEBHOOK_URL` with the webhook URL.

When a newly qualifying starter is seen in the **current NFL week**, the bot sends a summary to the channel. Past weeks are added to the dashboard without spamming the channel. If the webhook is not configured, the dashboard still works perfectly. A player is announced once per week/roster/player even if a later stat correction changes the score.

**Security:** Keep the webhook URL secret and never put it in the repo or on a public webpage. Be aware that public GitHub Pages exposes players' and fantasy managers' display names.

A condensed click-by-click guide is included as **`GITHUB_SETUP_GUIDE.md`**.

## Option B — Run on your computer

Install Python **3.10 or newer**. In Terminal or PowerShell, navigate to this extracted folder:

**Windows (easiest):** After installing Python, double-click **`RUN_TRACKER_WINDOWS.bat`** to fetch results and open your dashboard.

**Windows PowerShell:**

```powershell
py tracker.py
start docs\index.html
```

**macOS / Linux**

```bash
python3 tracker.py
open docs/index.html  # macOS; xdg-open on Linux
```

Run the script again whenever you want an update. To refresh *every previous week* rather than only the most recent two after a successful daily scan:

```bash
python tracker.py --refresh-all
```

Generate an offline, clearly labeled fictional preview:

```bash
python tracker.py --demo
```

Open `docs/demo.html`. **The demo cannot be mistaken for your actual league results.**

## How it works

- Reads Sleeper's public `/league/{league_id}`, `/league/{league_id}/users`, `/league/{league_id}/rosters`, `/league/{league_id}/matchups/{week}`, and `/state/nfl` endpoints.
- Retrieves Sleeper's player ID dictionary at most once per day during normal operation and caches only names, teams, and positions used by your league. Additional fetches may happen when new player IDs appear.
- Reads ESPN's public NFL scoreboard week by week to find which NFL games are officially complete. This is an **unofficial/public ESPN endpoint**, which could change or become unavailable.
- Uses the index-aligned Sleeper `starters_points` scores (with `players_points` fallback) to apply your league's exact PPR/half-PPR and custom rules. Doesn't calculate fantasy scores itself.
- Saves `data/events.json` and `data/state.json`, including snapshot mappings of players' NFL teams by fantasy week. Backfills prior weeks on the first run, then the latest two weeks every run, and all weeks once daily to catch stat corrections.
- Writes `docs/index.html`, `docs/busts.csv`, and `docs/leaderboard.json`, and optionally sends newly detected current-week busts to Discord.

## Known limits

- **Initial historical backfills:** If an NFL player changed NFL teams earlier in the season, Sleeper's current player-team listing may not reflect their team in old weeks. This can cause missed or incorrectly attributed old-week results on the *first* retrospective scan. Weekly team snapshots make ongoing tracking more reliable from the point you enable it. Review backfilled results if this matters for your league.
- Sleeper may temporarily report zero while fantasy scoring is still updating. The game-final requirement removes most false zeros from players whose games haven't begun, but there can still be short-lived scoring delays and subsequent stat corrections. The dashboard updates on later runs; a previously posted Discord message cannot automatically retract itself.
- The dashboard only tracks the league season returned by your configured Sleeper league ID, not all seasons of a dynasty league. Change the ID for each rollover season.
- If fantasy rosters change ownership during the season, historical entries are associated with the roster's current manager when first backfilled. Ongoing snapshots preserve the manager label in existing records until the affected week is refreshed.
- An NFL game postponed or canceled without being marked final is not counted. Players on teams with a bye week are skipped. A missing/null point value is unknown, not 0.
- If your league has unique non-NFL slots or players without a recognized NFL team, those are skipped for final-game checking.
- The dashboard is republished when the tracked results change; **GitHub's scheduled run cadence is best effort**. GitHub Pages can have a further publishing delay.

## Troubleshooting

| Problem | Fix |
|---|---|
| Tracker says `Sleeper league not found` | Check that `1391788553402347520` is the right league ID or update the configured ID. If the API is unavailable, try again later. |
| Actions says `Resource not accessible by integration` or git push fails | In GitHub repository **Settings → Actions → General → Workflow permissions**, allow **Read and write permissions** and rerun. |
| Dashboard shows demo data | Open your Pages home URL (which serves `docs/index.html`) after both `refresh` and `publish` succeed; `docs/demo.html` is only a fictional preview. |
| No players listed on Sunday morning | Correct: only players whose NFL games are **final** are eligible. |
| Missing inactive player | Ensure they were in the weekly `starters` list and their NFL team completed a game. |
| Webhook fails | Check that `DISCORD_WEBHOOK_URL` is an Actions **secret** and the webhook hasn't been revoked. |
| Data is stale | Inspect both the **refresh** and **publish** jobs in the latest Actions run. Under Pages, use **Source: GitHub Actions**, not branch deployment. |

## Run the tests

```bash
python -m unittest discover -s tests -v
```

## Sources

- [Sleeper official API documentation](https://docs.sleeper.com/)
- [NFL weekly ESPN scoreboard interface](https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard)

Not affiliated with Sleeper, ESPN, or the NFL. For personal / non-commercial fantasy league use.
