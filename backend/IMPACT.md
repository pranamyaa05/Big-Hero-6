# Per-design statistics and impact

ReForm3D keeps one compact **View Impact** panel inside each completed History
entry. The main Statistics tab opens the same per-design analysis with a design
selector; aggregate counts are kept under collapsed History totals. It has exactly
three primary comparison charts: cost (₹), carbon (kg CO₂e),
and production material consumption (g). It does not create a new dashboard or
change measurement, AI interpretation, CAD generation, slicing, or validation.

## Architecture audit and reuse

The repository has a FastAPI API, SQLite jobs and history, a process-isolated CAD
worker, material profiles in `app/printability.py`, and an esbuild single-page UI.
Saved History result JSON already retains piece dimensions and CAD volume,
material, estimated filament mass, print minutes, design interpretation, and,
when sliced, support grams. Those are reused even after job files expire.

The original database had only `jobs` and `history`. It had no pricing, tariff,
energy, product benchmark, carbon-factor, source, or impact-report tables. The
new tables live in the **same** `reform3d.db`, under `backend/data` by default:

- `impact_evidence`: immutable, content-addressed publisher-source versions.
- `impact_refresh`: last refresh attempt and outcome; failures retain prior values.
- `impact_inputs`: client-scoped manufacturing assumptions for each history item.
- `impact_reports`: immutable computed reports and complete input/source snapshots.
- `impact_research`: per-client, per-design search cache, source observations and provider status.

The migration only adds tables and indexes. Existing History rows are untouched.
Clearing a client's history also removes that client's reports and inputs, while
leaving other clients and the shared reference catalog intact. Back up the entire
data folder with the server stopped, including the SQLite file and any WAL files.

## What is actually known

Saved sliced mass already includes support material. It is not added twice. Extra
print waste is a separate explicit input for purge/brim/raft **not already counted**.
Without slicing the existing rough estimate is labeled; if neither estimate is
available, saved CAD volume × the existing material density is a solid-volume
fallback, not a prediction of infill, supports or waste. Changing material in the
report does not reuse another material's mass and print time. This input editor
changes the report only; regenerate or reslice to change the actual design.

No printer energy meter, actual print completion, labor, component inventory,
failure-rate measurement, tariff bill, or product-specific LCA was present. They
are unknown until explicitly supplied. A zero is accepted only as an explicit
scenario assumption with saved notes. Measurements can be labeled measured, but
calculated comparisons remain **estimated**, never experimentally verified.

## Reviewed source catalog and its limits

`app/data/impact_sources.json` is the reviewed seed catalog. Each record stores
exact URL, publisher, publication date (null if not given), retrieval timestamp,
region, units, reliability, refresh method, and the values actually supported.
These are cached observations, not live offers. Do not infer stock or universal
material properties from them.

- [Robu PLA category](https://robu.in/product-category/pro-range-pla/) and
  [PETG category](https://robu.in/product-category/pro-range-petg-pro/): black
  1 kg listing prices. Individual product redirects were inconsistent, so those
  pages are not automatically used to renew verification.
- [WOL3D flexible white](https://wol3d.com/product/flexible-1kg-white-filaments/):
  a TPU price reference, out of stock at review; not a purchasing quote.
- [IKEA GUBBARP](https://www.ikea.com/in/en/p/gubbarp-knob-white-30336435/):
  ₹60 for two knobs normalizes to ₹30/item. Minimum purchase is ₹60; delivery
  is excluded and it was not sold online at review. The listed 30 g is **packaged
  weight**, not net knob mass, production material input, or waste avoided.
- [Medilab Pencil Grip](https://medilabindia.com/products/pencil-grip): an
  ergonomic retail grip. A specialized grip must not be chosen merely to inflate
  savings over a simpler functionally adequate alternative.
- [Kidospark three-pack](https://www.kidospark.com/products/pencil-grip-set-of-3):
  publisher listing found via search index, direct page unavailable at review.
  Marked limited reliability and backordered; comparisons stay blocked until a
  structured publisher refresh verifies it. Early-learner suitability differs
  from adult assistive use. The cheapest category candidate still needs functional
  confirmation; source currency and identity must pass a refresh to renew it.
- [Zapvi range](https://zapvi.in/glossy-metal-tpu-mobile-cover/): starting price
  only, not an exact phone-model offer. It cannot establish a comparable phone case.
- [Prusa's published LCA](https://blog.prusa3d.com/introducing-prusament-petg-recycled-with-calculated-life-cycle-assessment_65806/):
  brand-specific PLA/PETG factors for the 2021 production study, including spool
  production. They are selectable scenarios, never automatic universal factors
  for arbitrary spools. Filament delivery, print use and disposal are outside that
  filament study boundary.
- [BMC climate budget](https://mcap.mcgm.gov.in/wp-content/uploads/2025/06/English_CB-Report-2025-26_digital.pdf):
  contextual grid CO₂ data. Operational CO₂ is not silently used as a full life-cycle
  CO₂e electricity factor. A matching full factor has not been seeded.
- [CEA tariff publications](https://www.cea.nic.in/reports/dashboardView?headingId=107&lang=en&source=archive&subHeadingId=1001&subSubHeadingId=10008&title=Tariff+%26+Duty+of+electricity+supply+in+India):
  determine the applicable distributor, period, slab and charges from the actual bill.
  No nationwide tariff or standard printer wattage is assumed.
- [California DSS utensil guidance](https://cdss.ca.gov/agedblinddisabled/res/VPTC2/9%20Food%20Nutrition%20and%20Preparation/Assistive_Devices_for_Mealtimes.pdf)
  distinguishes grip build-ups and cuffs. No Indian retail mass/price or LCA for an
  equivalent utensil grip was established; it remains unavailable.
- [Samsung India refrigerator support](https://www.samsung.com/in/support/category/home-appliances/refrigerator/):
  exact appliance/OEM model compatibility and a spare-part quote are required.
  An entire refrigerator's price or mass is never substituted for a handle.
- [ALIMCO schemes](https://alimco.in/content/36_1_SchemesandForms): scheme context
  only. Procurement cost, subsidy and beneficiary payment are distinct. No zero
  manufacturing cost, eligibility, or entitlement is inferred from a scheme.

Where publication dates are absent, they remain absent. Retrieval dates do not
change an older study's reference year. Freshness policy defaults to 30 days for
prices and 365 days for reference studies; the UI shows last verification and a
review-due flag. Old studies retain their stated limitations even when re-read.

## Deterministic calculations and comparison gates

Classification uses request/title/template-ID rules and, secondarily, saved AI
understanding. Conflicting or missing categories remain unclassified. Candidate
selection chooses the lowest normalized retail price in the same functional
category and region. A selected benchmark may be changed only among that category.
Government procurement, subsidies and beneficiary prices are excluded from retail
selection. The user must document fit, dimensions, function and intended-user
suitability. Phone cases and appliance handles additionally require an exact model
match in the benchmark. A category starting price cannot pass this gate.

All values use normalized INR, kg/g, minutes/h, W/kW and kg CO₂e units. Unsupported
currency conversions are rejected. Source publication, region, material grade and
lifecycle boundary must remain visible when importing data.

For one successful functional item:

```
raw filament cost = saved/entered filament_g / 1000 × INR/kg
consumed print grams = filament_g + explicit extra print waste_g
print electricity kWh = measured/entered kWh OR average W / 1000 × minutes / 60
printing subtotal = consumed print grams / 1000 × INR/kg + kWh × tariff
labor = labor minutes / 60 × hourly rate
machine overhead = print minutes / 60 × hourly overhead
retry multiplier = 1 / (1 - failure probability)
repeat base = print filament + electricity + consumables + labor + machine overhead
failed-print allowance = repeat base × p / (1-p)
complete production = repeat base + failed-print allowance + setup + components + post-processing
delivered consumer cost = complete production + consumer delivery
```

The conservative retry model assumes a full print and per-attempt labor are
consumed on failure. Setup, components and post-processing occur once per successful
item. The report spells this out; do not interpret it as measured failure behavior.
Missing values keep the complete total unavailable; a **known subtotal** is never
shown as complete production. Optional component lines each retain their cost,
mass, CO₂e and provenance; explicitly no components is different from unknown.

Cost graph: complete ReForm3D manufacturing cost vs retail acquisition price for
one equivalent item, both excluding consumer delivery. This answers making versus
buying; it is not a comparison of both factories' production costs. Delivered cost
is shown separately and not mixed into the graph. Multipack normalization and
minimum purchase cost remain visible in source notes.

Carbon graph: cradle-to-delivered on both sides, excluding use/end-of-life. It
requires an appropriate cradle-to-filament factor, a life-cycle electricity factor,
printing electricity, failure allowance, component impacts, other process impacts,
and relevant delivery, plus an equivalent commercial product's published impact
with the same boundary. Available carbon components are shown in the downloadable
report but are never presented as the complete footprint. No full product LCA was
established for the seed alternatives, so initial carbon comparisons are unavailable.

Material graph: **production material consumed**, including expected printing
waste and components. It needs a comparable production-input mass for the alternative.
Net product or packaged mass is not substituted. Neither lower mass nor a repair
claim proves avoided disposal. No whole-appliance or end-of-life credit is applied.

Absolute difference = industry − ReForm3D; percentage uses the industry denominator
only when positive. Missing values or unequal boundaries suppress comparisons.
Worse outcomes are clearly marked higher; uncertain lower estimates remain neutral,
with no green experimentally verified savings badge.

## Refresh and adding verified evidence

From `backend`, using the existing data directory:

```
.venv/bin/python -m app.impact_sources --list
.venv/bin/python -m app.impact_sources --refresh
.venv/bin/python -m app.impact_sources --refresh --id medilab-pencil-grip
.venv/bin/python -m app.impact_sources --import /path/to/reviewed-sources.json
```

Set `REFORM3D_DATA_DIR` for another store. The refresh command is suitable for an
operator's periodic scheduler. The separate per-design research feature below can
automatically search when a research snapshot is absent or stale. Attempts
are cached for one hour (`--force` bypasses the attempt cache). Supported refreshes
read bounded publisher Product JSON-LD or Shopify public Ajax product data. Shopify
prices are normalized from minor currency units only after checking the active
storefront currency via the public cart API; exact product title, configured
product ID and a single variant price are required. JSON-LD needs an unambiguous
positive INR Offer and the configured pack quantity. Generic price
regexes, redirects, AggregateOffer ranges and unrelated/recommended products are
not accepted. Only bundled reviewed URLs can be refreshed automatically; imports
remain manual until a retrieval adapter is reviewed. There are no external services,
API keys, accounts, or paid data dependencies.

Refresh failures preserve both the last verified values and date, record the failed
attempt, and appear in Sources. Mere HTTP success does not renew verification.
Never set `verified` on a manually imported source unless the evidence was checked.

The import file is a JSON list with the same structure as `app/data/impact_sources.json`.
Every numeric source requires exact URL, publisher, retrieval timestamp with timezone,
region, units and reliability. Set unknown publication dates/quantities to null.
Use these supported data structures:

- `material_price`: subject `pla|petg|tpu|abs|nylon`, unit `INR/kg`, `data.inr_kg`.
- `benchmark`: functional category subject, unit `INR/item`, `price_inr`, `price_basis`,
  optional pack fields; exact `compatibility` for phone/OEM parts. Product mass and
  package mass are separate. Material comparison needs `material_consumed_g` with
  `mass_basis: production_consumed`. Full carbon comparison needs
  `production_delivery_co2e_kg` with `carbon_boundary: cradle_to_delivered`.
- `filament_factor`: material subject, unit `kg CO2e/kg filament`, `kg_co2e_kg`,
  `boundary: cradle_to_filament`, and documented brand/grade and study assumptions.
- `grid_factor`: region subject matching report region, unit `kg CO2e/kWh`,
  `kg_co2e_kwh`, `boundary: life_cycle_electricity`. Do not relabel CO₂ as CO₂e.
- `reference` or `manufacturing`: structured contextual evidence; no automatic
  universal manufacturing assumptions are inferred from it.

A source's content hash identifies its immutable version. Loading an unchanged
panel reuses the cached report. Input/material/weight/tariff/evidence changes create
a new report. Older report IDs retrieve original snapshots even after job cleanup
or restart. Clearing history deletes the client's reports. Report JSON can be
exported from the UI for independent inspection.

## API and tests

`GET /api/v1/history/{job_id}/impact` returns the current saved report, freshness,
versions and factor choices. `POST` replaces this entry's report inputs and
recalculates. `GET .../impact?report_id=...` retrieves a historical snapshot.
All calls use the existing API-key guard, IP rate limiter and `X-Client-Id` scope.
Failed or declined designs do not receive impact calculations.

`tests/test_impact.py` covers classification, all requested categories, arithmetic,
source selection, units, missing data, support double-counting, model compatibility,
boundaries, worse outcomes, input validation, freshness, refresh failures, source
version changes, isolation, deletion and restart retrieval. Its numerical fixtures
are explicitly synthetic and are never seeded as real product data.

`tests/browser_history.py` checks three impact charts, incomplete and complete BOMs,
saving inputs, mobile overflow, existing History/Statistics, result reopening,
Esc/Back, clear history and persistence after restart. Run it with Playwright and
Chromium installed as described in the frontend README.


## Model-backed current market research

The Statistics/Impact view automatically requests research when its saved research
is absent, older than 24 hours, or for a different selected material. Failed attempts
are cached for 15 minutes. **Refresh web research** requests a fresh lookup, with a
60-second minimum retry interval. The source fetch is independent of generation.

The backend reuses configured Gemini pool members through Google's native REST
`generateContent` API with the `google_search` tool. It requires actual
`groundingMetadata` and citation supports. Two distinct configured Gemini model
names are attempted at most, preferring the model used for the design; it does not
fan out across every key. If Gemini is unavailable or quota-limited, one configured
OpenRouter model can use `openrouter:web_search` with bounded calls/results. Plain
uncited LLM answers are not accepted as research. Other compatibility endpoints
are not falsely advertised as search-capable.

References for these integrations:
[Gemini search grounding](https://ai.google.dev/gemini-api/docs/generate-content/google-search),
[OpenRouter web-search server tool](https://openrouter.ai/docs/guides/features/server-tools/web-search).
Provider web-search charges/quotas can apply independently of free model inference;
ReForm3D does not purchase credits, configure billing or add API keys.

Only title, intended function, selected material, saved dimensions and print mass
are sent to research. Photos, CAD code, who-for metadata, client IDs, credentials
and the full request are not included. Credentials remain backend-only. Each
research record and imported source is scoped to the client and history job.

Numerical observations need INR units, a positive pack/spool quantity and an actual
provider citation segment supporting that value and source. The backend checks
source identity, polymer and functional category. Explicit advertised physical pack
counts override a model's mistaken single-pack count (e.g. 20 pulls in one pack).
Pack minimums remain visible. Unrelated broader products, such as a button-hook
combo for a simple zipper pull, are filtered out.

Public publisher pages are fetched with bounded sizes/timeouts and per-redirect
public-address checks. Local/private addresses are rejected. Exact INR structured
offers or matching publisher excerpts can upgrade a value to page-checked. A
search-grounded price that cannot be checked on the publisher page remains marked
**limited**; it can inform a labeled filament-cost reference or the market context,
but cannot establish full comparable savings. A product's net mass is not assumed
from shipping weight, nor is an LCA invented from a price listing.

Each design now includes market listing bars, current filament observations and a
cost-composition donut alongside the three primary comparisons. The donut shows
only known cost components and clearly excludes unknown costs. Price timelines
appear only when multiple real observations of the same listing have been stored;
a single snapshot never becomes an invented historical trend. Market source
versions used in a report are snapshotted with that immutable report.

`POST /api/v1/history/{job_id}/research?force=false` returns the updated report and
research state under the existing API-key/IP-rate/client-scope guard. Quota errors
(e.g. HTTP 429), unavailable models and missing citations are shown without leaking
provider bodies or credentials. Cached observations survive those failures and
server restarts. Clearing history removes the client's research cache.

The initial live Gemini check returned RESOURCE_EXHAUSTED. The configured
OpenRouter search fallback returned cited price observations successfully. This is
an observed integration result, not a guarantee of future provider quota or data
availability. Actual labor, failure probability, electricity tariff applicability,
printer-meter readings and matched product LCAs cannot be determined merely by
asking an LLM; they remain explicit inputs or documented missing evidence.

## Default home-printing scenario (engine 1.2.0)

Until now every manufacturing input was blank, so no design could show a complete cost. The report now
fills only the inputs a person has **not** saved with the scenario in `app/data/impact_scenario.json`, and says so
at the top of the impact view. Saved inputs always win, field by field. The scenario's text is prepended to the
input notes, and each value lists its basis and source (or states that it is an assumption with no source).

| Input | Default | Basis |
|---|---|---|
| Average printer power | 150 W | Top of a 50–150 W range one article estimates; the Ender-3 V3 SE is rated 350 W peak (₹17,999 listing) |
| Electricity tariff | ₹8.16/kWh | Highest BESCOM domestic slab in a third-party summary of the FY 2026–27 order |
| Labor | 10 min at ₹112.39/h | Minutes are an assumption; the rate is ₹899.09/8 h from a reported draft Karnataka wage notification |
| Machine overhead | ₹9/h | ₹17,999 printer over an assumed 2,000 h life (the life is an assumption) |
| Failed prints | 20% | Assumption, set high on purpose |
| Setup, consumables, post-processing, extra waste, delivery, components | none | Assumption for small single-material parts |

The four new source records (`scenario-*` in `impact_sources.json`) are secondary or third-party pages and are marked
`limited`. They are not live data. Replace any default with your own bill, meter reading or wage in Manufacturing inputs.

Functional equivalence is also defaulted, for two categories only, and the note says so:
`pen_grip` (an ordinary ergonomic pencil grip) and `drawer_knob` (a plain retail knob). Uncheck it in the panel to undo it.

Comparison selection changed: the report now compares against the cheapest candidate whose publisher page was
**verified**. A cheaper `limited` listing is no longer silently chosen (which blocked the whole comparison); it is shown as
a caveat under the cost chart with its price. A person can still pick any candidate manually.

Still unavailable, and why: carbon (no published life-cycle figure for any retail alternative; no life-cycle electricity
factor), material consumed by the alternative (only packaged weights exist), and any category with no verified Indian retail
benchmark (utensil grips, jar grips, cane tips, zip pulls, appliance handles, phone cases). Add a benchmark with
`python -m app.impact_sources --import FILE` once its price has been read from the publisher's page.

## Simple statistics view (engine 1.3.1)

The Statistics page now shows only: cost (store vs 3D print), carbon footprint, time to get it, and the part's size.
`report.simple` carries those numbers; the older `metrics`, `bom` and `sources` are still saved in every report.

- **Cost**: store price is the person's own price (`POST /history/{id}/store-price`, or `null` to reset), else the verified retail
  listing for the category, else none. With no store price there is no savings figure.
- **Carbon**: part weight x a per-gram factor, from `app/data/impact_carbon.json`. PLA: 0.08 kg (material) + 0.06 kg (printing) per 35 g,
  from the team's baseline paper (Faludi et al., 2023; TotalEnergies Corbion LCA). That figure is used for PETG, TPU, ABS and Nylon too
  until a material-specific one is added. The same failed-print allowance as the cost is added. A bought item is assumed to weigh the
  same and to emit about 8.5 g CO2e per gram (the paper's 12-35 kg for 1,500-4,000 g products).
- Delivery time (3-14 days) is from the same paper. Edit the numbers in `impact_carbon.json`; reports regenerate automatically.
