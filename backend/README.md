# ReForm3D backend

Turns a description of a hard-to-use or broken everyday object, with optional measurements and photos, into **print-ready STL files**. An AI model **designs a new part from scratch** by writing CAD code. The server runs that code in a locked-down subprocess, proves the result is printable, shows the model a picture of its own result so it can correct itself, and returns STL files, a 3D preview, a PNG, a README and a zip.

The model can be Claude, any OpenAI-compatible provider, a model you host, or a **pool of several free models** that back each other up (see [Using several models at once](#using-several-models-at-once)).

Thirty-six hand-written, tested accessibility **templates** (grips, keyguards, tactile markers, one-handed aids, memory and hearing aids and more) also ship with it. They are building blocks the AI can reuse, and an offline fallback when no model is configured. They are not a catalog the AI has to pick from: anything outside the catalog goes to the AI.

```
 browser form / curl / CLI
        │  description, measurements, who it is for, up to 3 photos
        ▼
  FastAPI  ──►  job record (SQLite)  ──►  job thread
                                            │
              ┌─────────────────────────────┴───────────────────────────────┐
              │  DESIGN LOOP  (app/designer.py)                              │
              │  1. model reads request + photos, calls submit_design(code)  │
              │  2. AST allow-list check of the code                         │
              │  3. run it in a sandboxed subprocess (CPU, RAM, time limits) │
              │  4. closed-solid, volume, single-body, bed-size, thin-wall,  │
              │     overhang checks + a real slicer run (PrusaSlicer, if     │
              │     installed) ──► any problem goes back to the model        │
              │  5. render a picture ──► model accepts or corrects           │
              └─────────────────────────────┬───────────────────────────────┘
                                            ▼
                         build step in its own process (app/worker.py)
                         STL (binary) · model.glb · preview.png · README.txt · download.zip
```

## Contents
1. [Quick start](#quick-start)
2. [Choosing the model](#choosing-the-model)
3. [API](#api)
4. [How the STL files are made](#how-the-stl-files-are-made)
5. [The design loop in detail](#the-design-loop-in-detail)
6. [Templates](#templates)
7. [Using it from your website](#using-it-from-your-website)
8. [Command line](#command-line)
9. [Configuration](#configuration)
10. [Deploying and securing it](#deploying-and-securing-it)
11. [What has and has not been tested](#what-has-and-has-not-been-tested)
12. [Live results](#live-results)
13. [Honest limits](#honest-limits)
14. [Project layout](#project-layout)
15. [Extending it](#extending-it)
16. [Troubleshooting](#troubleshooting)

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate        # Python 3.11+ (tested on 3.13)
pip install -r requirements-dev.txt
cp .env.example .env                                     # then put your model key in it (next section)
set -a; source .env; set +a
uvicorn app.main:app --port 8000
```

Open <http://localhost:8000> for the demo page (describe a problem, get a 3D preview and downloads) or <http://localhost:8000/docs> for the interactive API docs.

With **no model configured** the server still starts. `GET /health` then reports `"design": false`, and requests are matched against the templates by an offline keyword matcher.

Docker:

```bash
docker build -t reform3d .
docker run --rm -p 8000:8000 --env-file .env -v reform3d-data:/data \
  --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges reform3d
# or: docker compose up --build
```

## Choosing the model

The designer needs a model that supports **tool calling** and, if you want photo understanding, **image input**. Everything model-specific lives in `app/llm.py`, so switching is configuration only.

| You want | Set | Notes |
|---|---|---|
| **Claude** (best designs) | `REFORM3D_LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...` | Default. Model defaults to `claude-sonnet-5-5`; override with `REFORM3D_LLM_MODEL`. Understands photos. |
| **Google Gemini** (free tier) | `REFORM3D_LLM_PROVIDER=gemini`, `GEMINI_API_KEY=...`, `REFORM3D_LLM_MODEL=<current model name>` | Google's OpenAI-compatible endpoint; its docs list tool calling and image input. Check Google AI Studio for current model names, limits and data-use terms. |
| **Qwen3-Coder** (Alibaba, strong open coding model), free | `REFORM3D_LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY=...`, `REFORM3D_LLM_MODEL=qwen/qwen3-coder:free`, `REFORM3D_LLM_VISION=false` | One 2026 article reports OpenRouter's free models at 20 requests a minute and about 50 a day (1,000 a day after a one-time $10 credit). A design uses 2 to 5 requests, so plan on roughly 10 to 25 designs a day on the free limit. Text only: photos are not used. Check OpenRouter's live terms. |
| **DeepSeek** (cheap, not free) | `REFORM3D_LLM_PROVIDER=deepseek`, `DEEPSEEK_API_KEY=...`, `REFORM3D_LLM_MODEL=<model from DeepSeek's docs>`, `REFORM3D_LLM_VISION=false` | OpenAI-compatible, billed per token. I found no confirmed free tier. |
| **Zhipu GLM via Z.ai** | `REFORM3D_LLM_PROVIDER=zai`, `ZAI_API_KEY=...`, `REFORM3D_LLM_MODEL=<model from Z.ai's docs>` | One aggregator lists a GLM Air model as free and a GLM Flash model as free but being retired. Free status changes, so confirm in Z.ai's console. A GLM vision model can read photos; set `REFORM3D_LLM_VISION=false` for a text-only one. |
| **Qwen on Alibaba Cloud** | `REFORM3D_LLM_PROVIDER=openai`, `REFORM3D_LLM_BASE_URL=<from your Model Studio console>`, `REFORM3D_LLM_API_KEY`, `REFORM3D_LLM_MODEL` | The base URL is specific to your workspace and region, so copy it from the console. Alibaba's free Qwen Code login tier was reported closed on 15 April 2026; check Model Studio for new-user credits. |
| **Cerebras** (free tier) | `REFORM3D_LLM_PROVIDER=cerebras`, `CEREBRAS_API_KEY=...`, `REFORM3D_LLM_MODEL=gpt-oss-120b`, `REFORM3D_LLM_VISION=false` | Listed by two community trackers with a free tier of about 1M tokens a day and 30k tokens a minute, enough for this loop. Text only. Check Cerebras' live limits and terms. |
| OpenRouter / Groq (other models) | `REFORM3D_LLM_PROVIDER=openrouter` (or `groq`), the matching `*_API_KEY`, `REFORM3D_LLM_MODEL` | Free models exist but are rate limited; pick one that supports tool calling. Groq's free tokens-per-minute limits for its larger models (reported as 8k) are probably too small for this loop: one call is about 3,000 tokens of instructions plus the conversation, and the request reserves up to 9,000 tokens of answer. |
| **A model you host** (no key) | `REFORM3D_LLM_PROVIDER=ollama` (or `openai` with `REFORM3D_LLM_BASE_URL`), `REFORM3D_LLM_MODEL` | Ollama, vLLM, llama.cpp server. A large Qwen3-Coder needs tens of GB of memory (one source quotes about 46 GB at 4-bit for the Next variant). Use a model with tool calling. |
| A model you **fine-tuned** | `REFORM3D_LLM_PROVIDER=openai`, `REFORM3D_LLM_BASE_URL=<your server>/v1` | See [Extending it](#extending-it). |

**Text-only models.** Most coding models cannot see images. Set `REFORM3D_LLM_VISION=false`: uploaded photos are then not sent (the model is told they exist and to use typical sizes), and the self-review step gives the model a measurement summary (size, volume, through-holes, wall thickness, bounding box) instead of a picture.

**Expect quality to follow the model.** Writing correct 3D CAD code for an unfamiliar object is hard. The loop (error feedback, printability checks, visual self-review) raises the success rate of every model, but a weaker model will fail more often, and when it fails the job reports it plainly instead of returning a broken file.

The loop makes roughly 2 to 5 model calls per design (one per attempt, plus one review call). It sends about 3,000 tokens of instructions each time, plus the conversation and, in the review call, one 640 px image. Turn the review off with `REFORM3D_REVIEW_ROUNDS=0` to save a call.

### Using several models at once

Free tiers are small (some allow 20 to 50 requests a day) and each one can fail, so the server can hold a **pool** of models instead of one:

```bash
REFORM3D_LLM_POOL="cerebras=gpt-oss-120b+text, gemini=<a Gemini Flash model>, openrouter=qwen/qwen3-coder:free+text"
CEREBRAS_API_KEY=...
GEMINI_API_KEY=...
OPENROUTER_API_KEY=...
```

**A second key for the same provider** (for example a teammate's own Gemini key): write `gemini:2=<model>` and set `GEMINI_API_KEY_2` (`:3` uses `GEMINI_API_KEY_3`, and so on). Each key is its own pool member with its own rest periods, so when one account's quota runs out the next is tried.

Entries are `provider=model`, best first, separated by commas, semicolons or new lines. Providers: `anthropic`, `gemini`, `openrouter`, `groq`, `cerebras`, `nvidia`, `mistral`, `sambanova`, `cloudflare` (also needs `CLOUDFLARE_ACCOUNT_ID`), `deepseek`, `zai`, `ollama`. Each uses its usual key variable. An entry whose key is missing is left out and the reason is logged; `python -m app.cli models` shows what will be called and what was left out. Use the model names from each provider's current docs: free model names change often. The single-model settings (`REFORM3D_LLM_PROVIDER` and the rest), when complete, count as the first member of the pool.

**Failover (always on once a pool is set).** Every model call goes to the first model in the list that is not resting.

- If it fails (quota used up, rate limit, bad key, server error, timeout), the same call moves to the next model, and the failed one rests: 60 seconds after a rate limit or quota error (or the provider's own `Retry-After` if longer), 10 minutes after a key or model-name error, 30 seconds after a rejected request, 20 seconds after a server error. Each failure in a row triples the rest, up to an hour; one success clears it. The record is shared by all jobs in the server process and starts empty after a restart.
- A short `Retry-After` (5 seconds or less) is waited out. A longer one means the quota is used up, so the call moves on at once instead of sleeping.
- The whole conversation is re-sent on every call, so a design can start on one model and finish on another. If every model is resting, the one that rests least is tried.
- Models are assumed to be text-only, except Gemini, Mistral and Anthropic. Add `+vision` or `+text` after a model to override. Photos and render images are sent when at least one model in the pool can see them; a text-only model gets a note in place of each picture. The review step always includes the measurement summary, so a text-only model can still check its work.

**Side by side (optional).** `REFORM3D_DESIGN_CANDIDATES=2` makes that many *different* ready models design the same part at the same time, each in its own conversation (the first N ready models in the list; with fewer models in the pool, all of them).

- `REFORM3D_DESIGN_RACE=first` (default): the first valid design wins and the others are stopped before their next call.
- `REFORM3D_DESIGN_RACE=best`: after the first valid design the others get `REFORM3D_DESIGN_RACE_GRACE` seconds (default 60). The winner is the one with the fewest printability warnings, then one the model confirmed after reviewing, then the fewest retries. This is a heuristic: it cannot tell which shape is closer to what the user wanted.
- A refusal from any model before the race is decided declines the whole request. A model that fails for another reason only drops out.
- This multiplies model calls by N. On free tiers of 20 to 50 requests a day, leave it at 1 and use failover. It suits a generous quota, such as Cerebras or a Gemma model. The result records which model won and how the others ended (`result.design.models`, `result.design.candidates`).

**Privacy.** Free tiers often come with data terms. Two community trackers say prompts on Google AI Studio's free tier (outside the EU, UK and Switzerland), on Mistral's free tier (training is an opt-in condition), on Kilo Gateway and on OpenCode Zen may be used to improve models. A design request carries the user's description and photos, so check each provider's current terms before you list it, and do not accept photos of people through a pool that includes such a provider.

## API

Base path `/api/v1`. Interactive docs at `/docs`. All responses are JSON except files.

| Method and path | What it does |
|---|---|
| `POST /generate` | JSON `{description, dims, who_for, material, mode}` → job. `mode`: `auto` (default: AI designs from scratch when a model is configured, otherwise a matching template), `design` (require AI design), `template` (templates only). |
| `POST /generate/form` | `multipart/form-data` with the website form's fields: `what`, `dims`, `mat`, `who`, `mode`, and up to 3 `photos` (JPEG, PNG, WEBP or GIF). |
| `POST /parts/{id}/build` | No AI. JSON `{params: {...}}` builds one template with explicit values. |
| `GET /parts`, `GET /parts/{id}` | The templates, with every parameter's label, unit, default and range. |
| `POST /plan` | Template matching only: which template and values would be used. |
| `GET /jobs/{id}` | Job status and result. |
| `GET /jobs/{id}/files/{name}` | Download a file (the URLs come from the job). |
| `DELETE /jobs/{id}` | Delete a job and its files. |
| `GET /health` | `{ok, version, llm, design, provider, pool, candidates, templates, jobs}`. With a pool, `provider` is `"pool"` and `pool` lists the model names and how many seconds each still rests. Never includes keys. |

`POST` calls accept `?wait=N` (0 to 60 seconds). The call then holds the connection until the job finishes or N seconds pass. It returns `200` when finished (`status` is `done` or `failed`) and `202` while still running, with a `Location` header. Without `wait` it returns at once. A new design usually takes one to three minutes, so poll `GET /jobs/{id}` about once a second after the first `202`.

Job statuses: `queued` → `planning` → `designing` (AI only) → `building` → `done` or `failed`. A `failed` job carries a plain-language `error`.

```bash
# the AI designs a new part
curl -s -X POST 'http://localhost:8000/api/v1/generate?wait=60' -H 'Content-Type: application/json' -d '{
  "description": "The zipper pull on my jacket is tiny and I cannot grip it. The slider hole is 4 mm.",
  "who_for": "Weak grip or arthritis"
}'

# the website form, with photos
curl -s -X POST 'http://localhost:8000/api/v1/generate/form?wait=60' \
  -F what='Cannot twist the cap on this bottle' -F dims='neck 50 mm' -F mat='Durable' -F who='Weak grip or arthritis' \
  -F photos=@bottle.jpg

# explicit template, no AI
curl -s -X POST 'http://localhost:8000/api/v1/parts/braille-tag/build?wait=30' -H 'Content-Type: application/json' -d '{"params": {"text": "SALT"}}'

# poll, then download
curl -s http://localhost:8000/api/v1/jobs/<id>
curl -O http://localhost:8000/api/v1/jobs/<id>/files/download.zip
```

A finished job looks like this (trimmed):

```jsonc
{
  "id": "4b16fe7205d549d894a175806ef77990",
  "status": "done",
  "plan":   { "source": "design", "rationale": "…how the AI understood the request…" },
  "result": {
    "part_id": "custom-big-zipper-pull",
    "design": { "understanding": "…", "assumptions": ["hole 4 mm (given)", "…"], "attempts": 2, "reviewed": true, "log": [ … ] },
    "pieces": [{ "name": "zipper-pull", "ok": true, "watertight": true, "bodies": 1, "size_mm": [62, 30, 7], "volume_cm3": 8.19, "min_wall_mm": 2.87, "warnings": [] }],
    "print_notes": ["…"], "fit_notes": ["…"], "notes": ["…"], "warnings": [], "disclaimer": "…"
  },
  "files": {
    "stl": [{ "piece": "zipper-pull", "name": "custom-big-zipper-pull.stl", "url": "/api/v1/jobs/…/files/custom-big-zipper-pull.stl" }],
    "glb": "…/model.glb", "preview": "…/preview.png", "zip": "…/download.zip", "readme": "…/README.txt", "code": "…/design.py"
  }
}
```

Errors: `401` wrong or missing `X-API-Key` (only when `REFORM3D_API_KEY` is set), `404` unknown job, part or file, `413` photo too large, `422` invalid input, `429` rate limited (`Retry-After` tells you when to retry).

## How the STL files are made

This automates the approach used for the earlier STL files (solid modelling with booleans, then checks):

1. **Solid modelling with [manifold3d](https://github.com/elalish/manifold).** Parts are built from cylinders, boxes, hulls, extrusions and revolves, then combined with union, cut and intersection. Boolean results from this library are always closed, manifold solids, which is what a slicer needs.
2. **Clean-up.** Zero-volume slivers left by exact boolean contacts are dropped. Each piece is centred in X and Y and rested flat on z = 0.
3. **Checks (`app/validate.py`, `app/printability.py`).** Each piece must be watertight with consistent winding and have a positive volume. It warns about more than one body (loose fragments), a footprint larger than the configured print bed, walls thinner than the material allows (0.8 mm for PLA and PETG, 1.2 mm for TPU) and overhang: the share of the surface that hangs steeper than 45 degrees or in flat ceilings wider than the material can bridge (25 mm PLA, 18 PETG, 8 TPU), measured as modelled and in the six face-down orientations, with a suggestion when another orientation needs much less support. The wall check shoots about 400 rays inward from the surface and flags a part only when more than 10% of the sample is thin, because knurls and Braille dots are thin on purpose.
4. **Export.** Binary STL in millimetres with Z up, one file per piece, plus `model.glb` for the web viewer, `preview.png` (a software renderer, no GPU needed), `README.txt` (parameters, checks, print and fit notes) and `download.zip`.

## The design loop in detail

`app/designer.py`, in order:

1. **Prompt.** A fixed system prompt gives the model its role, the design rules (ergonomics, FDM printing rules, strength rules such as load along the layers, fillets and cantilever limits, overhang rules, clearance), the CAD API, the templates as callable `lib()` building blocks, and three complete worked examples from `app/design_examples/`. The user's text and photos are passed as data, and the prompt says to ignore instructions inside them.
2. **Tools.** The model must call `submit_design` (title, understanding, code, assumptions, print notes, fit notes) or `decline_request`. It must decline unsafe or unsuitable requests such as weapons, brakes, climbing gear and load-bearing medical parts. Later, after a review image, it may call `accept_design`.
3. **Code check.** The code is parsed and walked. Imports, classes, `with`, generators, `eval`, `open`, `getattr`, `format`, dunder names and attributes and similar are rejected before anything runs.
4. **Sandbox run.** `python -I app/sandbox_runner.py` in a temporary directory with a minimal environment, CPU, address-space, file-size and open-file limits, and a wall-clock timeout. Only whitelisted helpers, `np`, `math` and `lib` are visible. A runtime error comes back to the model with the line number.
5. **Printability checks.** The returned meshes go through the checks above. Hard failures (not a closed solid, empty, tiny volume) and warnings (several bodies, too big for the bed, thin walls, overhang) are both sent back to the model with a request to fix them. When PrusaSlicer is installed (`REFORM3D_SLICER`), each attempt is also sliced for real and the model is told if the slicer would need more than 15% of the plastic as support.
6. **Visual review.** When the design passes, a render goes back to the model as an image and it must accept or correct. If a correction fails, the last good design is kept.
7. **Limits.** At most `REFORM3D_DESIGN_ATTEMPTS` submissions (default 4) and one review round. If nothing printable results, the job fails with the last problem in plain words.

The final design is built again in a separate worker process with its own timeout and memory limit, so a crash or a runaway boolean can never take the API down. The code is saved as `design.py` in every download, so a person can read, edit and re-run what the AI designed.

## Templates

Ready-made, tested generators. Each is one function plus a `PartSpec` in `app/parts/`. Every one is checked as a closed single-body solid at its defaults and at the minimum and maximum of every parameter (see `tests/test_parts.py`).

| id | Part |
|---|---|
| `wing-cap` | Wing-grip bottle cap |
| `cane-tip` | Cane tip |
| `pen-grip` | Chunky pen grip |
| `walker-glide` | Walker glide |
| `braille-tag` | Braille tag (Grade 1 English Braille, up to 16 cells) |
| `jar-grip` | Jar grip ring |
| `key-turner` | Key turner |
| `dial-marker` | Tactile dial marker |
| `lever-wing` | Tap lever wing |
| `utensil-grip` | Utensil grip, two halves with screws |
| `palm-band` | Clip-on palm band with bottle-cap opener, pen tube and fork slot |
| `door-handle-adapter` | Lever that slips over a round door knob |
| `switch-extender` | Paddle extender for a toggle light switch |
| `zipper-pull` | Big flat loop for a zipper tab |
| `button-hook` | Button hook with a thick handle |
| `card-holder` | Upright tray for playing cards or bank cards |
| `pill-funnel` | Funnel with a spout that fits a pill-bottle opening |
| `cable-clip` | Snap-in cable clip with screw flange (trip hazards) |
| `drawer-pull` | Bar handle on two posts, with blind screw holes |
| `can-tab-lifter` | Finger-ring lever with a thin blade that lifts a can's pull tab |
| `plug-puller` | Cap with wide wings that stays on a mains plug so it can be pulled out by hand |
| `keyguard` | Plate with one hole per key that sits above a keypad, for tremor |
| `button-dots` | Adhesive strip with raised tactile dots to mark a button |
| `step-marker` | Bright ridged strip for the edge of a step |
| `cane-table-clip` | Clip for a table edge with a snap-in ring that parks a walking stick |
| `pump-pusher` | Wide cap that turns a soap-pump head into a palm-sized button |
| `keyhole-guide` | Funnel that steers a key to the keyhole |
| `key-id-grip` | Big key cover with a raised shape to tell keys apart by touch |
| `sound-horn` | Passive horn that funnels a phone speaker's sound to the ear |
| `label-holder` | Frame with a top slot for picture or word cards on cupboards (memory, aphasia) |
| `bag-handle` | Wide carrier handle with slots for shopping-bag loops |
| `chair-hook` | Snap-on C-ring with a deep hook for wheelchair or walker frames |
| `plate-guard` | Curved wall that clips on a plate rim for one-handed eating |
| `pill-popper` | Palm-sized plunger that presses tablets out of blister packs |
| `book-stand` | Leaning reading stand for a book, recipe book or tablet |
| `cup-handle` | Snap-on ring with a finger loop for handleless cups |

Beyond the sweep, `tests/test_parts_library.py` checks that every parameter changes the geometry, that a typed measurement becomes the real size, that the keyguard has one hole per key at the right pitch, that the cane ring's mouth is narrower than the cane, that lever and pad parts print with their wide face on the bed, that about 60 realistic requests route to the right part, and that requests outside the catalog (or only sounding like a part) get no part rather than a random one. The offline matcher also has a veto list (`VETO` in `app/planner.py`), so "hinge on my cupboard" can never pick the drawer pull.
| `door-handle-adapter` | Lever that slips over a round door knob |
| `switch-extender` | Paddle extender for a toggle light switch |
| `zipper-pull` | Big flat loop for a zipper tab |
| `button-hook` | Button hook with a thick handle |
| `card-holder` | Upright tray for playing cards or bank cards |
| `pill-funnel` | Funnel with a spout that fits a pill-bottle opening |
| `wall-hook` | Wall hook with screw plate, printed on its side |
| `cable-clip` | Snap-in cable clip with screw flange |
| `phone-stand` | Leaning phone or tablet stand |
| `shelf-bracket` | L bracket with side ribs and screw holes |
| `drawer-pull` | Bar handle on two posts, with blind screw holes |
| `hose-adapter` | Barbed reducer between two hose sizes |
| `snap-box` | Snap-fit box and lid (2 pieces) |
| `living-hinge` | One-piece flexing hinge strip |
| `thread-pair` | Threaded cup and cap with a coarse printable thread (2 pieces) |
| `rail-clamp` | Split rectangular clamp with a bolt and an accessory boss |
| `pipe-clamp` | Two-half pipe clamp with screw ears (2 pieces) |
| `hinge-knuckle` | Knuckle hinge: two leaves and a pin (3 pieces) |

Beyond the sweep, `tests/test_parts_library.py` checks that every parameter changes the geometry, that a typed measurement becomes the real size, that mating pieces fit (the thread screws on at some turn angle, the snap lid seats, the hinge leaves and pin do not collide), that 45 realistic requests route to the right part and that requests outside the catalog get no part rather than a random one.

## Using it from your website

`web/reform3d-client.js` is a dependency-free client. Your existing form already uses the field ids `what`, `dims`, `mat`, `who` and `photos`:

```html
<script src="https://YOUR-BACKEND/web/reform3d-client.js"></script>
<script>
  const rf = new ReForm3D('https://YOUR-BACKEND');
  document.querySelector('#repairForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      const job = await rf.generateFromForm(e.target, { onStatus: (s) => console.log(s) });   // waits for the design, up to 5 minutes
      console.log(job.result.design, job.files.zip, job.files.glb);                           // show these on the page
    } catch (err) { alert(err.message); }                                                    // plain-language message
  });
</script>
```

Set `REFORM3D_CORS_ORIGINS` to your site's origin. `web/index.html` is a complete worked example (form, status, three.js preview with orbit controls, notes and downloads). `web/vendor/` holds three.js r128 (MIT licence), so the demo page needs no CDN.

If you set `REFORM3D_API_KEY`, do not put that key in a public web page. Call the backend from your own server instead, or leave the key unset and rely on rate limiting and CORS.

## Command line

```bash
python -m app.cli templates
python -m app.cli models                            # which models will be called, which pool entries were left out and why
python -m app.cli template wing-cap -p neck_diameter=50 -o out
python -m app.cli export-all -o out                  # every template at its defaults
python -m app.cli design "zipper pull I cannot grip" --dims "hole 4 mm" --who "Weak grip or arthritis" --photo pull.jpg -o out
```

## Configuration

All settings are environment variables, read when the server starts (`.env.example` has every one with comments).

| Variable | Default | Meaning |
|---|---|---|
| `REFORM3D_LLM_PROVIDER` | `anthropic` | `anthropic`, `gemini`, `openrouter`, `groq`, `cerebras`, `nvidia`, `mistral`, `sambanova`, `cloudflare`, `deepseek`, `zai`, `ollama`, or `openai` (any OpenAI-compatible URL). |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` / `GROQ_API_KEY` / `CEREBRAS_API_KEY` / `NVIDIA_API_KEY` / `MISTRAL_API_KEY` / `SAMBANOVA_API_KEY` / `CLOUDFLARE_API_TOKEN` (+ `CLOUDFLARE_ACCOUNT_ID`) / `DEEPSEEK_API_KEY` / `ZAI_API_KEY` | | Key for the chosen provider, and for each provider listed in the pool. `REFORM3D_LLM_API_KEY` overrides the single-model key only. |
| `REFORM3D_LLM_POOL` | empty | Several models, tried in order: `provider=model, provider=model+text` (see above). |
| `REFORM3D_DESIGN_CANDIDATES` | `1` | Pool models that design the same part at once. Multiplies quota use. |
| `REFORM3D_DESIGN_RACE` / `REFORM3D_DESIGN_RACE_GRACE` | `first` / `60` | `first` or `best`, and seconds to wait for the others once one design is valid (`best` only). |
| `REFORM3D_LLM_BASE_URL` | preset | For `openai`-style servers. |
| `REFORM3D_LLM_MODEL` | `claude-sonnet-5-5` for Anthropic; required for the others | Model name. |
| `REFORM3D_ENABLE_LLM` | `true` | `false` forces templates only. |
| `REFORM3D_ENABLE_DESIGN` | `true` | `false` never runs model-written code. |
| `REFORM3D_DESIGN_ATTEMPTS` / `REFORM3D_REVIEW_ROUNDS` | `4` / `1` | Loop limits. |
| `REFORM3D_DESIGN_TIMEOUT` / `REFORM3D_DESIGN_MEMORY_MB` | `40` / `1536` | Limits for running one design's code. |
| `REFORM3D_LLM_TIMEOUT` | `120` | Seconds per model call. |
| `REFORM3D_LLM_VISION` | `true` | `false` for text-only models (see above). |
| `REFORM3D_DATA_DIR` | `./data` | SQLite database, job files. |
| `REFORM3D_API_KEY` | empty | If set, `POST` and `DELETE` need an `X-API-Key` header. |
| `REFORM3D_CORS_ORIGINS` | `*` | Comma-separated allowed origins. Use your site, not `*`, in production. |
| `REFORM3D_RATE_LIMIT` | `20` | Requests per minute per client, 0 = off. In memory, per process. |
| `REFORM3D_TRUST_PROXY` | `false` | Read the client IP from `X-Forwarded-For` (only behind a proxy you control). |
| `REFORM3D_WORKERS` / `REFORM3D_JOB_TIMEOUT` | `2` / `120` | Parallel jobs and the build timeout. |
| `REFORM3D_MAX_UPLOAD_MB` | `8` | Per photo. At most 3 photos. |
| `REFORM3D_RETENTION_DAYS` | `14` | Jobs and files older than this are deleted at start-up. |
| `REFORM3D_BED_X/Y/Z` | `220/220/250` | Print bed in mm, for the size warning. |
| `REFORM3D_RENDER_PREVIEW` | `true` | Write `preview.png`. |
| `REFORM3D_SLICER` | `auto` | PrusaSlicer for real print time, plastic and support numbers: `auto` (use it if it is on the PATH), `off`, or a path to the binary. |
| `REFORM3D_SLICER_LOOP` / `REFORM3D_SLICER_TIMEOUT` | `true` / `60` | Slice every design attempt and tell the model about large support needs; seconds allowed per slice. |
| `REFORM3D_PROMPT_LEAN` | `false` | A standing prompt of about 3.6k tokens instead of 4.9k, for providers with a small tokens-per-minute limit (Groq free tier). |

## Deploying and securing it

**Hosting.** It is one container: a Python process with a SQLite file and a data folder. Any host that runs containers works (Cloud Run, Fly.io, Render, a VM). Keep **one instance** while using the in-memory rate limiter and SQLite; for several instances move the jobs to Postgres and object storage and the limiter to Redis. Mount a persistent volume at `/data`. Run it on at least 1 vCPU and 2 GB RAM; each build is CPU-bound for a second or two, a complex design for longer.

**What protects what:**

- **Model keys** live only in the server's environment. The browser never sees them, and the sandbox subprocess starts with an empty environment.
- **Job ids** are random 128-bit values and act as capability links. Anyone who has one can see that job's files, nobody can list jobs, and file names are matched against a strict pattern.
- **Photos** are re-encoded as plain JPEG (this removes EXIF and GPS data), are downscaled, are used only for planning, and are not stored unless `REFORM3D_KEEP_PHOTOS` is set. Photos are sent to your chosen model provider (every provider in a pool may receive them), so read the data terms of each before accepting photos of people.
- **Input** has length limits, enum validation and clamped parameter ranges. The AI cannot make the server build anything outside what the CAD helpers can express, and every output is re-checked by the server.
- **Retention.** Jobs older than `REFORM3D_RETENTION_DAYS` are deleted at start-up. `DELETE /jobs/{id}` removes one immediately.

**Be honest about the code runner.** The AST check and the subprocess limits make accidents and casual abuse hard, but **they are not a security boundary**, and nobody should treat model-written code as trusted. Before exposing AI design to the public internet:

1. Run the container with the flags above (read-only root, no extra capabilities, no-new-privileges, non-root user, only `/data` and `/tmp` writable).
2. Put no secrets other than the model key in the container, and use a key with a spending cap.
3. Prefer running the design runner as its own service or container with **no network access** and a stronger sandbox (gVisor, Firecracker, nsjail), with the API in a separate container. Today the runner is a child process of the API container.
4. Keep `REFORM3D_RATE_LIMIT` on, set `REFORM3D_CORS_ORIGINS` to your site, and consider `REFORM3D_API_KEY` with a backend-to-backend call.
5. If you cannot do the above, set `REFORM3D_ENABLE_DESIGN=false` and serve templates only.

## What has and has not been tested

**Tested (455 automated tests, `python -m pytest`, about 5 minutes):**

- All 36 accessibility templates at their defaults and at the minimum and maximum of every parameter: closed, watertight, single-body solids. A dead-parameter test fails if a slider changes nothing, a clamping test checks every range, and specific geometry tests check the things each part exists for (keyguard hole pitch, tactile dot height, cane clip mouth narrower than the cane, snap-ring open side, and so on).
- Request routing: about 60 realistic requests must reach the right template, a list of out-of-catalogue requests ("a ramp for my wheelchair", "replace the hinge on my cupboard door") must reach **no** template instead of a wrong one, and measurement parsing (mm, cm, inches, fractions).
- Printability: material profiles (PLA, PETG, ABS/ASA, TPU, nylon), the overhang survey (steep faces, bridge span, shelf versus bridge, best orientation), material-aware wall thresholds, estimates per material, and a guard that no template raises an overhang warning except the known wing-cap bore.
- **PrusaSlicer 2.7.2 in the loop (installed in the test machine, those tests skip if it is missing):** the G-code parser is checked against the slicer's own totals, failures and timeouts of the slicer are reported rather than raised, and **every template is sliced**: none may need more than 25% of its plastic as support, and any template whose print notes say "no supports" must really come out with under 3%. That test found real overhangs in several parts (a pen grip's collar ledge, a cane tip's bead, ridges on a lever, the pill funnel's orientation) and they were fixed.
- The code check (accepts good code, rejects imports, dunders, file access, attribute tricks), the sandbox (runtime errors with line numbers, a 600 mm size cap, an endless loop is stopped, an empty environment) and the whole design loop with a **scripted stand-in for the model**: a coding error fed back and fixed, loose fragments, overhang and support problems fed back with a remedy, a cut-off answer, the render shown to the model, a review correction, a failed late fix keeping the last good design, a decline, a model outage, a model that forgets the tool, exhausted attempts.
- The provider adapters (message translation, retries, 413/429 handling), the model pool (failover, rest periods on a fake clock, waiting out per-minute limits, pictures removed for text-only members, side-by-side mode), and the HTTP API end to end including photos, API key, rate limit, file-name safety and deletion.
- A clean install: the dependencies were installed from `requirements.txt` into an empty virtual environment and the app was run from a copy of just `app/` and `web/`; `/health` and a template job (with a PrusaSlicer estimate) worked.

**Tested over HTTP against a running server (uvicorn, real pool, PrusaSlicer):** health, AI clarifying questions, photo measurement (50 mm marker read as 50.0 mm), a template job (door-knob lever, 12 s including the slice), a rebuild with new sizes (4 s), zip, README and preview downloads, and a 150 kg wheelchair ramp request declined by the AI within seconds. The full AI path with `scripts/e2e_smoke.py` first failed on free tiers (Gemini quota spent, the other free models timed out or returned no code). On 24 October, with two more free Gemini keys (`gemini:2`, `gemini:3`, models `gemini-3.5-flash` and `gemini-3-flash-preview`), **every step passed in 289 s**: clarify 6 s, measure 0.5 s, AI design 39 s (a tap-lever paddle extender with grip ridges and a screw clamp, one pass, checked against its own render, PrusaSlicer 157 min / 32 g PETG), tune 9 s, AI revise 234 s. Gemini returned several 503 "high demand" errors on the way; the pool rested those models and switched keys and models. Note: new Google accounts can no longer use `gemini-2.5-flash`; use `gemini-3.5-flash`.

**Tested live (free tiers, this machine):** see [Live results](#live-results) below. Short version: real designs were produced by real models for requests that are not templates, but free models are slow (3 to 7 minutes per design), often rate limited, and produce plain shapes.

**Not tested, so check these yourself:**

- **Ollama.** It is configured (`ollama=<model>` in the pool) but could not be installed or run in the build environment.
- **The Docker image.** There was no Docker daemon in the build environment, so `docker build` has never been run. The Dockerfile has an optional `--build-arg WITH_SLICER=1` that installs PrusaSlicer; that line is also unrun.
- **Real prints.** The parts are verified by software (closed solid, volume, size, wall estimate, overhang, a slicer run), not test-printed. Dimensions are nominal and clearances are starting values. Measure the real object, do a test print and adjust before relying on a part.

## Live results

Eight requests that are **not** templates were sent through the real model pool on free tiers (Groq gpt-oss-120b and Qwen, NVIDIA gpt-oss-20b, OpenRouter Laguna, lean prompt, PrusaSlicer in the loop), one after another, on 23 to 24 October 2026. Gemini's free daily quota was already used up, so it did not take part.

| Request | Result | Time |
|---|---|---|
| Hook for a guide-dog leash at wheelchair height | Designed. Four passes; the overhang check still reported flat ceilings needing support (23% of the surface) and the warning was delivered with the part | 5.7 min |
| Grip sleeve for a thin toothbrush handle (cerebral palsy) | Designed in three passes, no warnings; the sleeve is large (about 41 g, a 4 hour estimate), so check it before printing | 6.4 min |
| Tactile bump for key 5 on a landline phone | Designed, checked against its own render, no warnings (9 minutes, 0.9 g) | 6.0 min |
| Holder to clip a TV remote to a sofa arm | **Failed**: the model returned no code after four attempts | 2.1 min |
| One-handed screw-top bottle opener | **Failed**: every model in the pool timed out | 3.1 min |
| Foot pedal extender for a sewing machine | **Failed**: every model in the pool timed out | 3.1 min |
| Ramp that carries a 150 kg electric wheelchair | **Declined** with a reason (load-bearing, cannot be verified in printed plastic) | 2 s |
| "asdf qwerty purple monkey" | **Declined**, with a request to say which object is the problem | 2 s |

So: three of six real requests produced a printable design, the two requests that should not be answered were declined at once, and three failures were free-model timeouts or empty answers, not wrong designs. The designs are plain shapes (a bump, a sleeve, a hook). Design times of 5 to 7 minutes are normal on these models. Pre-warm demo requests (an identical request is served from the cache) and put a stronger model first in the pool.

The offline router was also tightened after a 60-request sweep showed that a single loose word could pick a wrong template (a condition such as "arthritis" or "tremor" no longer counts as naming an object, a few common word clashes are vetoed, and simple plurals match). Requests outside the catalogue now return no part unless the AI is available to design them.

## Honest limits

What a judge, a user or a reviewer should know before trusting it:

- **No strength analysis.** There is no finite-element analysis. Strength is handled by rules (load along the layers, walls of 2.4 mm or more where load is carried, fillets, short cantilevers, material choice) that are given to the model and checked loosely, not calculated. A lever that prints cleanly may still snap under load, and printed layers are weaker between layers than along them. Printed parts here are light-duty aids, not safety equipment. Requests for lifting, braking, climbing or load-bearing medical parts are declined.
- **Overhang and support are estimated twice, and the slicer is the better guide.** The geometric check is a fast heuristic (45 degrees, bridge spans of 25 mm in PLA, less in PETG and TPU). The real number comes from PrusaSlicer, which is only used when it is installed. Without it the print time and plastic come from a calculation calibrated against the slicer (plastic within about 10%, time within about 25% on the 36 templates). Your own slicer settings will differ.
- **Free-tier models are the weak link.** Free tiers change without notice, rate limit hard (Groq's free tier allows 8,000 tokens per minute, which a multi-step design cannot fit), time out, or lack tool calling. Designs from small free models are plain, sometimes wrong in shape, and take 3 to 7 minutes. The system survives that (failover, waiting out limits, template fallback, a repeat-request cache) but the quality of an AI design is the quality of the model behind it. A strong model (Claude, Gemini) gives clearly better designs. To avoid waiting during a demo, design the demo requests beforehand: an identical request is served from the cache.
- **LLMs reason poorly about 3D space.** The model writes code and cannot see the result unless it supports pictures; the checks catch printability problems, not "this does not do the job". The review step helps only for models that can look at the render. Always look at the preview.
- **The template catalogue is small (36).** They are hand-checked starting points, not a complete answer to every disability. Anything else relies on the AI.
- **The code sandbox is not a hypervisor.** AI-written code runs in a limited subprocess behind an AST allow-list. Before exposing AI design to the internet run it in its own network-less container (see Deploying and securing it).
- **Single instance.** Job storage is SQLite and the rate limiter and model cooldowns are in memory. Several instances need Postgres and Redis.
- **Sound horn is passive.** It is a horn that shapes a phone's sound; it is not a hearing aid.
- **Not a medical device.** Nothing here replaces advice from an occupational therapist.

## Project layout

```
app/
  api.py            FastAPI routes, auth, rate limit, CORS, uploads, file serving
  jobs.py           job manager: design or template, then build in a subprocess
  designer.py       the AI design loop, code check, sandbox runner wrapper, prompts and tools
  sandbox_runner.py runs checked code with a restricted namespace and resource limits
  design_examples/  worked examples shown to the model (also tested)
  llm.py            model providers behind one interface (Anthropic, OpenAI-compatible), and the failover pool
  planner.py        offline template matcher and optional model template planner
  engine.py         build pipeline: solids → meshes → STL, GLB, PNG, README, zip
  validate.py       printability checks
  geom.py           CAD helpers on top of manifold3d
  parts/            the 29 templates (lathe_parts, plate_parts, wearables, household, mechanical)
  braille.py  preview.py  images.py  store.py  worker.py  config.py  spec.py  cli.py  main.py
web/                demo page, drop-in client, vendored three.js
tests/              pytest suite and the scripted model
```

## Extending it

**Add a template.** Write a function that takes the resolved parameter dict and returns `BuildResult(pieces={name: Manifold}, ...)`, register a `PartSpec` with its `ParamSpec`s in `app/parts/`, and add it to the tests. The sweep test checks it automatically. The AI sees it as a `lib()` building block with no other change.

**Give the AI a new CAD helper.** Add a function to `app/geom.py`, add its name to the `helpers` tuple in `app/sandbox_runner.py`, and document it in `API_DOC` in `app/designer.py`.

**Teach it by example.** Drop a tested `.py` design into `app/design_examples/` (first lines are comments with the request and the idea). It appears in the prompt as a worked example, and `tests/test_designer.py` can check it builds.

**Train your own model.** The realistic way to get a model that needs no third-party API is to fine-tune a small open code model for this one task. The training data comes from this repository: every template at many parameter values, plus every design that passed the checks and was accepted in review, stored with its request, code and assumptions. Serve the result with vLLM or llama.cpp and point `REFORM3D_LLM_PROVIDER=openai` at it. Expect it to handle common objects well and unusual ones poorly compared with a frontier model; the checks and review loop stay in place either way.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `"design": false` in `/health` | No model configured. Set the provider, key and (for non-Anthropic providers) model name. |
| Job fails: "The AI model could not be reached" | Wrong key, no quota, or the provider is down. The server log has the status code. With a pool the message lists every model that was tried and why it failed ("no model could answer"): the free quotas are probably used up for now; add a model or wait. |
| A pool entry seems ignored | Its key variable is not set, or the entry is not `provider=model`. `python -m app.cli models` prints the reason. |
| Job fails: "Could not produce a working design after N attempts" | The model could not produce a printable design. Make the description more specific, give measurements, or try a stronger model. The last problem is in the message. |
| Job fails: "This request was declined" | The model judged it unsafe or unsuitable for a printed part. |
| Browser says CORS error | Add your site's origin to `REFORM3D_CORS_ORIGINS`. |
| `429` | Rate limit; wait `Retry-After` seconds or raise `REFORM3D_RATE_LIMIT`. |
| Slow builds | Raise `REFORM3D_JOB_TIMEOUT`; give the container more CPU. |
| Warning "larger than the configured print bed" | Set `REFORM3D_BED_*` to your printer, or rotate or split the part. |

## Newer features (see `/docs` for the full endpoint list)
- Measure from a photo with a printed 50 mm ArUco marker (`/api/v1/marker.svg`, `/api/v1/measure`); clarifying questions (`/api/v1/clarify`); tune sizes (`/jobs/{id}/tune`) and revise with feedback (`/jobs/{id}/revise`); fit-test print, dimensioned drawing, fit confidence, repeat-request cache, template fallback when no model answers.
- Material modes: name PLA, PETG, ABS/ASA, TPU or nylon in the material field (or in the description) and the model is given that material's rules, wall and overhang thresholds change, and the estimate uses its density and speed.
- Print estimate and support check from PrusaSlicer when installed (`REFORM3D_SLICER`), shown in the API, README.txt and the web page.
- Model pool: `REFORM3D_LLM_POOL="provider=model,..."` (presets: gemini, openrouter, groq, nvidia, cerebras, mistral, sambanova, cloudflare, deepseek, zai, ollama, openai). Rate-limited models rest and are retried; brief per-minute limits are waited out.
- `python scripts/e2e_smoke.py http://localhost:8000 photo.jpg` drives clarify, measure, generate, download, tune and revise against a running server.

## History and statistics

Finished requests are saved in the existing SQLite database at `backend/data/reform3d.db`
(or `REFORM3D_DATA_DIR`). History survives server restarts and job-file retention cleanup.
Entries whose files have expired retain their request, result and statistics and show
“Files no longer available”. Deleting `backend/data` erases the database and generated
files. To back up everything, stop the server and copy the entire folder; restore that
copy before starting the server again.

The browser stores a random client UUID in localStorage and sends `X-Client-Id`.
History and statistics are scoped to that ID; missing IDs use `anonymous`. This is a
browser identifier, not account authentication. Clearing browser storage changes the
identifier. “Clear my history” removes only that identifier's history rows.

The History button appears when a backend is configured. Statistics use saved rows
only and report coverage, exclusions, and sliced versus rough estimates. Counts refer
to requests, not physical prints. Print time and plastic are projected requirements,
not measurements of completed prints. Per-entry impact comparisons are described below.

### Per-design impact analysis

Each completed History card now includes **View Impact** with three comparison
charts (cost, carbon, material consumption), an itemized BOM, editable manufacturing
inputs, source provenance, and reproducible saved report versions. Existing results
and the generation pipeline remain unchanged. Unknown costs and unsupported
commercial/environmental comparisons show **Data unavailable**.

See [the impact methodology and source guide](IMPACT.md) for formulas, reviewed
Indian price references, lifecycle boundaries, source refresh/import commands,
comparison limitations, database tables and tests. Reports and source versions are
stored in the same SQLite database and survive server restarts and job cleanup.


### Current-price web research

The Statistics view can now research saved designs with the configured Gemini
Google Search tool and a configured OpenRouter web-search fallback. Scoped results
and citations are cached in SQLite, with publisher-page verification status,
retail-price bars, filament listings, a known-cost donut and real observation
history. Use **Refresh web research** for an explicit refresh. Provider quotas and
charges still apply; no new key or service account is created. Missing actual
manufacturing or LCA inputs are not invented. See [IMPACT.md](IMPACT.md).
