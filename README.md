# MM2 Collection Tracker

Live site: https://mm2inventory.netlify.app

- `site/` is what Netlify publishes (`index.html`, `values.json`, `history.json`).
- `.github/workflows/update-values.yml` runs every 6 hours, pulls the current values from
  [MM2Values](https://mm2values.com) (used with permission) via `scripts/update_values.py`
  and commits `site/values.json` + `site/history.json` when something changed.
  Netlify then redeploys automatically.
- Manual update: **Actions → Update values from MM2Values → Run workflow**.
