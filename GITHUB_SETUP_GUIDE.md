# Set up your Sleeper Wall of Shame on GitHub

This file is specific to **Sleeper league `1391788553402347520`**. You do not need to edit the code or provide a Sleeper API key.

## 1. Download and extract

Download the configured ZIP on your Windows PC, right-click it, and select **Extract All**. Keep the resulting folder open. You will upload the **contents** of this folder. In File Explorer, select **View > Show > Hidden items** so you can see `.github`.

## 2. Create a free GitHub repository

1. Sign in at https://github.com/ (or create a free account).
2. Go to https://github.com/new.
3. Repository name: `sleeper-wall-of-shame` (or another name).
4. Visibility: **Public**, because free GitHub Pages hosting works with public repositories. Manager/team display names and resulting leaderboard will be publicly viewable.
5. **Do not initialize with a README** (leave README, .gitignore, and license unchecked); the ZIP already contains those files.
6. Click **Create repository**.

## 3. Upload files

1. In your empty repository, choose **uploading an existing file** (or use **Add file > Upload files**).
2. Drag the *contents of the extracted folder*, including the `.github`, `data`, `docs`, and `tests` folders, onto the upload area. Do not upload the ZIP itself.
3. Commit to **main**.
4. Verify the repository shows `.github/workflows/update.yml`, `tracker.py`, `dashboard_template.html`, `docs/demo.html`, and `README.md`.

If `.github/workflows/update.yml` is missing, it is essential: use **Add file > Create new file**, name it `.github/workflows/update.yml`, copy its contents from the downloaded folder, and commit to `main`.

## 4. Enable Pages for GitHub Actions

1. In your repository click **Settings > Pages**.
2. Under **Build and deployment > Source**, choose **GitHub Actions**.
3. Do **not** choose **Deploy from a branch**. The included workflow deploys the site directly.

## 5. Run it for the first time

1. Open the repository's **Actions** tab. If prompted to enable workflows, enable them.
2. In the left sidebar choose **Update Sleeper Wall of Shame**.
3. Click **Run workflow**, choose `main`, then click **Run workflow** again.
4. Open the new workflow run and confirm that **refresh** and **publish** complete successfully.
5. Go to **Settings > Pages > Visit site** for the public URL, usually `https://YOUR-GITHUB-USERNAME.github.io/sleeper-wall-of-shame/`.

The first run should add generated files: `docs/index.html`, `docs/busts.csv`, `docs/leaderboard.json`, `data/events.json`, and `data/state.json`.

## 6. Let it run automatically

The workflow attempts updates every 30 minutes, and also supports **Run workflow** at any time. GitHub may delay scheduled runs. You can share the Pages URL with the league. The page displays all recorded qualifying zero and negative starts after the corresponding NFL games have been marked final.

## Optional: Discord alerts

Create a Discord channel webhook. In the repository go to **Settings > Secrets and variables > Actions > New repository secret**, give it the exact name `DISCORD_WEBHOOK_URL`, and enter the webhook URL. This adds new current-week bust announcements to your channel; do not expose the webhook publicly.

## Troubleshooting

- If **Actions** doesn't show the update workflow, verify `.github/workflows/update.yml` exists on `main`.
- If **refresh** reports **Resource not accessible by integration** when pushing, check **Settings > Actions > General > Workflow permissions > Read and write permissions**, and rerun. The workflow requests `contents: write`, but repository policy may restrict it.
- If **publish** fails, confirm **Settings > Pages > Source = GitHub Actions** (not branch publishing).
- The published dashboard uses `docs/index.html`; `docs/demo.html` is fictional sample data.
- The league cannot be verified until the first successful run against Sleeper. If the API reports it is not found, verify your league link or whether the league ID is correct.

Official guidance: https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
