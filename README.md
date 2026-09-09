# Google Ads Automation

Automates: **secure login → pull & analyze data → report → suggest campaigns → deploy**.

Ships two ways to run it:
- **Vercel API + dashboard** — deploy once, trigger runs from a browser or `curl`/cron.
- **Local CLI** — `python main.py ...`, writes an HTML report with charts to `output/`.

Both share the same logic in `lib/`.

---

## Important limits to know before deploying to Vercel

- **OAuth login can't run on Vercel.** Google's consent flow needs an interactive
  browser + local redirect, which serverless functions can't do. You generate the
  refresh token **once, on your own machine** (`python auth.py`), then paste it into
  Vercel's environment variables. After that, Vercel calls Google Ads using that
  stored refresh token — no further interactive login needed.
- **No password is ever stored anywhere.** Google Ads doesn't support password login
  for the API; auth is OAuth2 token-based throughout.
- **`/api/deploy` can spend real money if misused.** It's gated behind a
  `DEPLOY_SECRET` header and defaults to a dry run (`validate_only`) unless you pass
  `"live": true`. Keep the secret private, and consider also turning on Vercel's
  Deployment Protection for this project.
- **Bundle size.** The Vercel API deliberately excludes `matplotlib`/`jinja2` (only
  needed for the local CLI's chart-based HTML report) to keep the serverless
  function small. The API returns JSON instead of a rendered HTML report.

---

## 1. One-time setup (before pushing to GitHub)

1. Get a **developer token**: Google Ads UI → Tools & Settings → API Center.
2. Create OAuth2 credentials: Google Cloud Console → APIs & Services → Credentials
   → OAuth client ID → "Desktop app".
3. Locally:
   ```bash
   pip install -r requirements.txt -r requirements-cli.txt --break-system-packages
   cp config.example.yaml google-ads.yaml   # fill in developer_token/client_id/client_secret
   python auth.py                           # opens browser, writes refresh_token into google-ads.yaml
   ```
4. Open `google-ads.yaml` and copy out `refresh_token` — you'll paste it into Vercel
   next. **Do not commit `google-ads.yaml`** (already in `.gitignore`).

## 2. Push to GitHub

```bash
git init
git add .
git commit -m "Google Ads automation pipeline"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## 3. Deploy to Vercel

1. Go to vercel.com → **Add New → Project** → import the GitHub repo you just pushed.
2. Framework preset: leave as "Other" (this is a Python serverless function + static
   HTML, not a JS framework — Vercel detects `api/index.py` automatically).
3. Under **Environment Variables**, add (see `.env.example`):
   - `GOOGLE_ADS_DEVELOPER_TOKEN`
   - `GOOGLE_ADS_CLIENT_ID`
   - `GOOGLE_ADS_CLIENT_SECRET`
   - `GOOGLE_ADS_REFRESH_TOKEN` (from step 1.4 above)
   - `GOOGLE_ADS_LOGIN_CUSTOMER_ID` (only if you use a manager/MCC account)
   - `DEPLOY_SECRET` — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`
4. Click **Deploy**.

Your dashboard is now live at `https://<your-project>.vercel.app/` and the API at
`https://<your-project>.vercel.app/api/...`.

## 4. Using it

**From the dashboard:** open the deployed URL, enter your Ads customer ID, click
Analyze → Suggest → Deploy (dry run) → review → Deploy LIVE.

**From the command line:**
```bash
curl -X POST https://<your-project>.vercel.app/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "123-456-7890", "days": 30}'

curl -X POST https://<your-project>.vercel.app/api/suggest \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "123-456-7890", "days": 30}' > suggestions.json

curl -X POST https://<your-project>.vercel.app/api/deploy \
  -H "Content-Type: application/json" \
  -H "X-Deploy-Secret: <your DEPLOY_SECRET>" \
  -d "{\"customer_id\": \"123-456-7890\", \"plan\": $(cat suggestions.json), \"live\": false}"
```

Add `"live": true` only once you've reviewed the plan and are ready to apply it.

## 5. Local CLI (alternative to the API)

```bash
python main.py analyze --customer-id 123-456-7890 --days 30   # -> output/report.html + CSVs
python main.py suggest --customer-id 123-456-7890              # -> output/suggestions.json
python main.py deploy  --customer-id 123-456-7890 --plan output/suggestions.json           # dry run
python main.py deploy  --customer-id 123-456-7890 --plan output/suggestions.json --live    # real changes
python main.py run-all --customer-id 123-456-7890 --days 30    # analyze + suggest in one pass
```

## File map

| Path | Purpose |
|---|---|
| `lib/gads_client.py` | Authenticated client — reads env vars (Vercel) or `google-ads.yaml` (CLI) |
| `lib/analyze.py` | Pulls campaign/keyword performance, computes KPIs |
| `lib/suggest.py` | Rule-based suggestion engine (budgets, bids, keywords, new campaign draft) |
| `lib/deploy.py` | Applies suggestions via mutate operations, dry-run by default |
| `lib/report.py` | Full HTML+chart report (local CLI only) |
| `api/index.py` | Flask app — the one Vercel serverless function, routes all `/api/*` |
| `public/index.html` | Browser dashboard for the deployed API |
| `auth.py` | One-time local OAuth2 login (run before deploying) |
| `main.py` | Local CLI orchestrator |
| `vercel.json` | Routes all `/api/*` traffic to `api/index.py` |
| `requirements.txt` | Installed by Vercel (lightweight) |
| `requirements-cli.txt` | Extra deps for the local CLI's chart report |

## Safety notes

- Test against a free **Google Ads test account** before pointing this at a live
  spending account.
- Every `/api/deploy` or `main.py deploy` call is logged with a timestamp — the API
  returns the log inline; the CLI appends to `output/deploy_log.jsonl`.
- Suggestions are heuristic (tune thresholds in `lib/suggest.py`) — review before any
  `live: true` deploy. This isn't a substitute for human sign-off on ad spend.
