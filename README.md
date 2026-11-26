# Elon Worth

A live tracker for Elon Musk's net worth.
Built by Hess Cone. Unofficial fan tracker, not affiliated with Forbes, Elon Musk, Tesla, or SpaceX.

The site is meant to be served at `https://hesscone.github.io/elon-net-worth-tracker/`.

## How it works

- **Source:** [Forbes Real-Time Billionaires](https://www.forbes.com/real-time-billionaires/). `fetch.py` (Python standard library only, no API key) reads the public profile JSON Forbes's own page uses:
  `https://www.forbes.com/forbesapi/person/elon-musk.json`
- **Fallbacks:** if that file fails or is stale, the script tries the real-time list (`/forbesapi/person/rtb/0/position/true.json`) and then the list feed (`/ajax/list/data?type=person&year=0&uri=rtb`). The page shows which source was used. Bloomberg's billionaire index blocks this kind of unauthenticated request, so it is not a fallback.
- **Units:** Forbes reports worth in millions of US dollars. The script converts that to dollars. Nothing is hardcoded.
- **Holdings:** Tesla and SpaceX come from Forbes's financial-asset lines. Stock is shares × price. Options are shares × (price − strike), which is what makes the lines add up to Forbes's total. The breakdown is shown only when those lines plus Forbes's private-assets figure match the headline number. Forbes does not publish a separate xAI dollar amount (the profile says SpaceX acquired xAI).
- **History:** the first run copies Forbes's wealth history (about a month of daily points and a week of hourly points). Those points are rounded to the nearest million dollars and marked `"seeded": true`. Each later run appends the precise reading. `data/history.json` is the chart. `data/latest.json` is the current reading.
- The site (`index.html`, `style.css`, `app.js`, `calc.js`) is plain static files that read `data/*.json`. Chart.js loads from a CDN. No build step, no analytics, no ads.

## Run locally

```bash
python3 fetch.py                 # update data from Forbes
python3 -m unittest tests/test_fetch.py
node tests/calc.test.mjs
python3 -m http.server 8000      # then open http://localhost:8000
```

## Put it online (GitHub Pages)

Scheduled workflows only run from the default branch, so merge this to `main` first.

1. Repo **Settings → Pages → Build and deployment**: Source = "Deploy from a branch", Branch = `main`, folder `/ (root)`. Save.
2. If the hourly job fails while pushing, repo **Settings → Actions → General → Workflow permissions**: choose "Read and write permissions". Save. The workflow already asks for `contents: write`, and GitHub will not grant more than that setting allows.
3. **Actions** tab → "Update Elon net worth" → **Run workflow** once to test. After that it runs every hour at :05 UTC and commits new data. Pages republishes on each commit.
4. The site is at `https://hesscone.github.io/elon-net-worth-tracker/`.

## Notes

- GitHub may pause scheduled workflows in repos with no activity for 60 days. The hourly data commits normally keep it active.
- Net worth figures are Forbes estimates, not an audited statement. Times on the page are US Central.
