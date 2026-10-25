# ReForm3D (accessibility theme)

Team Big Hero 6, Hack4SDG.

- `dist/reform3d.html` is the finished single-file page. Open it in a browser (it loads three fonts from Google Fonts and falls back to system fonts offline).
- To rebuild after editing `src/`: `npm install` then `npm run build`. The output is written to `dist/reform3d.html` (and a `www/index.html` test copy).

## Connecting the design server

The page talks to the ReForm3D backend (the AI design server). Tell it where the server is, in any of these ways:

- open the page with `?api=https://your-server` in the address (remembered on that browser; `?api=off` forgets it), or
- add `<meta name="reform3d-api" content="https://your-server">` to the page, or set `window.REFORM3D_API` before the page script.

On the server, set `REFORM3D_CORS_ORIGINS` to the page's origin. A page served over HTTPS needs the server on HTTPS too (a Cloudflare or ngrok tunnel works for a demo).

With a server connected:
- the request form shows the server's status, asks the AI's clarifying questions, then designs the part (a progress timer shows each stage);
- the finished part appears on the 3D stage in the printed look, next to the card with its summary, sizes it assumed, warnings, print time and plastic from a real slicer run, and downloads (zip, STL, fit test, print notes);
- "Adjust the sizes" rebuilds without AI in seconds, "Change the design" asks the AI for a revision;
- each example part has "Make this part for me", which builds the real template on the server.

Without a server the page is unchanged: the form says it is a demo and the example button is hidden.

## Source map
- `src/body.html` page markup and copy
- `src/style.css` styles
- `src/main.js` scroll director, how-it-works steps, examples picker, pins
- `src/world.js` three.js scene: stage, bottle, printer, wing-grip cap, example parts
- `src/parts.js` wing-grip cap (plus two rejected candidates) and the eight accessibility parts, modelled in code
- `src/ex.js` copy and camera settings for the eight example parts
- `src/backend.js` the design-server connection: status, questions, result panel, sizes, revisions, example builds
- `src/reform3d-client.js` the backend's own JavaScript client (copied from the backend's `web/` folder)
- `src/fx.js` shader patches (scan, wireframe, layer-by-layer print)
- `assets/WaterBottle.glb` Khronos glTF Sample Assets, CC0, by Microsoft

## History and statistics

With a backend connected, the top-right History button opens saved requests and
statistics. Search or filter cards, reopen a result, download its zip, copy the
request, or clear your own history after confirmation. Esc, Close and browser Back
close the overlay; keyboard focus returns to History. The last tab is remembered.

History is saved in SQLite under `backend/data` (`REFORM3D_DATA_DIR` can override
this), and survives server restarts. Deleting that folder erases it. To back it up,
stop the server and copy the whole folder. Expired job files do not remove saved
requests or numbers; those cards show “Files no longer available”. Browser storage
holds only the client UUID and preferences. Clearing it gives this browser a new ID.

Statistics distinguish sliced numbers from rough estimates and report missing
values and coverage. They describe generated requests and projected print usage,
not physical prints. Per-entry commercial and environmental comparisons are described below.

Browser regression check (isolated temporary database): install `playwright` in the
backend virtualenv, install Chromium with `python -m playwright install chromium`,
run `npm run build` here, then from the repository root run
`backend/.venv/bin/python backend/tests/browser_history.py`. Set
`PLAYWRIGHT_BROWSERS_PATH` if Chromium was installed in a custom location.

### Per-design Statistics & Impact

Use **View Impact** on a completed history card for exactly three compact
comparison graphs: cost (₹), carbon (kg CO₂e) and material consumed (g). Expand the
BOM, manufacturing inputs or Sources & Methodology as needed. Enter actual printer,
tariff, labor, failed-print and component assumptions to complete an estimate;
blank inputs remain unknown. Save changes to create a new reproducible report,
select older report versions, or download the full report JSON.

Comparisons require a relevant verified alternative, functional/model compatibility
and matching environmental boundaries. Cached prices show their verification date.
Package weight is not net product mass, and less material does not prove waste
avoided. Full carbon/product-mass comparisons remain unavailable where source data
cannot support them. See [backend/IMPACT.md](../backend/IMPACT.md) for the evidence
catalog, formulas and source-refresh mechanism. The Statistics tab opens this per-design analysis directly with a completed-design
selector. Aggregate history counts remain available under collapsed History totals.
The same view is also accessible through View Impact on a history card.


### Current-price research

Statistics now uses the existing backend Gemini configuration for Google Search
research, with a configured OpenRouter search fallback. It searches on first use
and after cache expiry, saves citations/observations in SQLite, and offers a
**Refresh web research** button. Market-price bars, a known-cost donut and genuine
price-observation history use those saved values. Provider quota and verification
limits are visible; cached data is never described as live. No browser API keys
are required. See [the research methodology](../backend/IMPACT.md).
