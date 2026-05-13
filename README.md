# Estádio — 2026 World Cup Sticker Album

A privacy-first React + Vite app for tracking your Panini-style 2026 World Cup
sticker album, finding trades with nearby collectors, and forecasting how close
you are to a complete set. Designed to deploy as a static bundle on **GitHub
Pages** with no live backend.

## Features

- **Privacy-first onboarding.** Alias, optional contact, coarse region pick or
  browser geolocation rounded to the nearest 0.5° (~55 km). Explicit GDPR
  Article 6(1)(a) consent checkbox. Local-only storage; export/clear from the
  Profile screen.
- **Realistic seeded catalog.** 980 stickers across 50 sections, aligned to the
  reported 2026 structure: 20 opening / museum stickers plus 48 national teams
  with 20 stickers each. Replace
  [`src/data/catalog.json`](src/data/catalog.json) with the official Panini
  checklist for production — the structure is stable.
- **Responsive album.** Search, status filters (all / owned / missing /
  doubles), confederation filter, per-section bulk "mark all owned" and
  "reset", and a sheet/modal that adjusts copies (0 = missing, 1 = owned,
  &gt;1 = duplicate).
- **Explainable trade matching.** By default, no people are shown in the static
  build because it is not connected to real collector accounts. A visible demo
  mode can be enabled to test matching against generated collectors; score
  formula and components are visible per match.
- **Monte Carlo completion forecast.** 600-trial uniform-draw simulation
  conditioned on packs you plan to buy and trades you've proposed; reports
  mean, P10–P90, probability of full set, expected duplicates, and a
  histogram of outcomes. Includes the analytic coupon-collector baseline.
- **Dark mode**, mobile-first responsive layout, custom SVG logo, full
  keyboard navigation, WCAG-AA contrast.

## Architecture

```
src/
  data/
    catalog.json         # seeded sticker catalog (regenerate via scripts/)
    users.json           # generated demo collectors for algorithm testing only
  lib/
    storage.ts           # localStorage persistence (replaceable by /api/state)
    geo.ts               # coarse distance buckets + region presets
    trade.ts             # match scoring (overlap + balance + distance + activity)
    forecast.ts          # Monte Carlo completion simulator
  components/            # Onboarding, AlbumView, TradesView, ForecastView, ProfileView
  state.tsx              # React Context store
  App.tsx                # Shell + tab navigation
scripts/
  generateCatalog.mjs    # regenerate src/data/catalog.json
  generateUsers.mjs      # regenerate src/data/users.json
```

Everything is client-side. The "API" layer is `loadState` / `saveState` in
`src/lib/storage.ts`. To attach a real backend later, swap those two functions
for `fetch('/api/state')` calls — see "Serverless extension" below.

## Local development

```bash
npm install
npm run dev          # http://localhost:5173
npm run build        # outputs to dist/
npm run preview      # serve the production build locally
```

Regenerate the data files (optional):

```bash
node scripts/generateCatalog.mjs
node scripts/generateUsers.mjs
```

## Deploying to GitHub Pages

**Option 1 — `gh-pages` branch (project page):**

1. Push this folder to a GitHub repo, e.g. `your-user/wc2026-album`.
2. Set `VITE_BASE` to the repo path so asset URLs resolve under
   `your-user.github.io/wc2026-album/`:

   ```bash
   VITE_BASE="/wc2026-album/" npm run build
   npx gh-pages -d dist
   ```

3. In the repo's **Settings → Pages**, choose **Deploy from branch:
   `gh-pages` / root**.

**Option 2 — GitHub Actions:** add the workflow below at
`.github/workflows/deploy.yml`:

```yaml
name: Deploy
on: { push: { branches: [main] } }
permissions: { contents: read, pages: write, id-token: write }
jobs:
  build-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: VITE_BASE="/${{ github.event.repository.name }}/" npm run build
      - uses: actions/upload-pages-artifact@v3
        with: { path: dist }
      - uses: actions/deploy-pages@v4
```

**Option 3 — user/organization page (`your-user.github.io`):** no base path
needed; just build with default `VITE_BASE` and push `dist/` to the `main`
branch of `your-user.github.io`.

The default `vite.config.ts` falls back to `./` so the build also works on any
static host (Netlify, Cloudflare Pages, S3) with no configuration.

## Simulated API / serverless extension

`src/lib/storage.ts` is the entire data-access layer. To replace it with a
real backend:

1. **GitHub-hosted serverless functions** (Cloudflare Pages Functions / Vercel
   / Netlify): create `/api/state` that reads and writes a per-user record
   keyed by a signed cookie or magic-link token. Replace `loadState` /
   `saveState` with `await fetch('/api/state')` and `fetch('/api/state', { method: 'PUT', body: JSON.stringify(...) })`.
2. **GitHub Gist as a persistence layer** for hobby use: store the state JSON
   in a private gist using a fine-scoped PAT — no infra needed beyond
   GitHub.
3. **Real nearby users:** `src/data/users.json` is generated demo data for
   algorithm testing only. Replace it with an API call (`/api/users?near=...`)
   that returns the same shape: `{ users: SimUser[] }`. Only opted-in collectors
   should be returned, and only the bucket of distance should ever be shown to
   other users — exact coordinates never need to leave the server.

The matching algorithm and forecast model are pure functions in `src/lib/` —
they can be reused unchanged on the server.

## Privacy notes

- The static build stores everything locally; **nothing is uploaded**.
- Browser geolocation is rounded with `roundCoarse()` to the nearest 0.5°
  before persistence. Even if a future API is added, only the coarse
  coordinates need to be sent.
- The Profile screen exposes **Export my data** (JSON download) and **Clear
  all data**, satisfying GDPR access + erasure rights for the
  device-local copy.
- The privacy copy in Onboarding states explicitly what is stored and where.

## Not affiliated with FIFA or Panini

The sticker catalog is a structurally accurate demo for development. Swap in
the official checklist before production use; the file format is documented
inside `scripts/generateCatalog.mjs`.
