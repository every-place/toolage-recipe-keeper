# Recipe Keeper by Toolage

A digital recipe box for families. Log Grandma's handwritten cards, your own creations and the stories behind them, on a phone or tablet in the kitchen.

## What it does

- **Recipe box**: every recipe as a card with its photo; search by name, ingredient, person or story; filter by category.
- **Card editor**: type ingredients the way you'd write them (`1/2 cup flour, sifted`) and the app reads the amount, unit, ingredient and note. Steps offer sentence templates as you type ("Bake at ___ for ___, or until ___"), with tap-to-fill blanks. Photos of the finished dish, each step, and the original handwritten card. A place for the story behind the recipe. Unsaved work is kept on the device.
- **Recipe card**: scale the batch (½×, 2×, 3×), print it as a card, or export it.
- **Cooking mode**: big text, one step at a time, the screen stays awake, built-in timers, and an ingredient checklist.
- **Family sharing**: one recipe box per household. Family members join with a code from Settings.
- **Your data**: export every recipe in the schema.org Recipe format, which most recipe apps can import.
- **Nutrition (Premium)**: calories, fat, carbs, sugar, fiber, protein and sodium per serving or for the whole recipe, from [FatSecret](https://www.fatsecret.com). Each ingredient is matched to a FatSecret food once per household and remembered; tap "Change" to pick a different food or leave one out. Cooking effects are ignored.
- **Plans**: each household has a `free` or `premium` plan. Until billing is built, set it by hand: `python -m scripts.set_plan kristen@example.com premium`.

It installs to a phone or tablet home screen from the browser (Share → Add to Home Screen on iPhone/iPad).

## Run it on your computer

You need Python 3.11+ and Node.js 20+.

```
# the server
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # then set SECRET_KEY to a long random string

# the app (once, and after changing anything in web/)
cd web && npm install && npm run build && cd ..

uvicorn recipekeeper.api:app --reload
```

Open http://localhost:8000. Recipes are stored in `data/recipes.db`, which is never committed.
Set `DATABASE_URL` to use Postgres (for example a free [Neon](https://neon.tech) database) instead.

While working on the app's screens, run `npm run dev` in `web/` as well and open http://localhost:5173: changes appear instantly, and API calls are passed to the server on port 8000.

## Put it online

The `Dockerfile` builds one container that serves the app and the API. Any host that runs containers works (Render, Railway, Fly.io, Google Cloud Run).

**On Render (set up already):** `render.yaml` describes the service. In the Render dashboard choose New → Blueprint, pick this repo, and fill in the values it asks for. `SECRET_KEY` is made for you. Use a Neon database for `DATABASE_URL`, because Render's free database is deleted after 30 days. Every merge to `main` redeploys. The free plan sleeps after 15 minutes idle, so the first visit after that takes about a minute.

Set these environment variables on the host:

| Name | Value |
| --- | --- |
| `SECRET_KEY` | A long random string. Changing it logs everyone out |
| `DATABASE_URL` | Your Postgres connection string |
| `PREMIUM_EMAILS` | Optional. Comma-separated emails whose households get Premium when they sign up or log in (until billing exists) |
| `COOKIE_SECURE` | `1` (already set in the Dockerfile; the site must be on https) |
| `FATSECRET_CLIENT_ID`, `FATSECRET_CLIENT_SECRET` | From platform.fatsecret.com → API Keys (OAuth 2.0) |
| `FATSECRET_PROXY_URL` | Optional. See below |

**FatSecret and IP addresses.** FatSecret only answers requests from IP addresses listed in its dashboard. If your host gives the app a fixed outbound IP, list that. If not, send FatSecret calls through a fixed-IP proxy and put its address in `FATSECRET_PROXY_URL` (the same setup as Vitality). Check it with `python -m scripts.check_fatsecret`.

**What nutrition costs.** Showing nutrition never calls FatSecret; it uses foods already saved. Only matching a new ingredient name costs calls (one search and one food lookup), and each food is fetched once for all households.

Photos are stored in the database for now, shrunk to at most 1600 px. Moving them to file storage (S3 or similar) is a later step once there are many households.

## Tests

```
pytest                 # server
cd web && npm test     # app helpers
```

GitHub Actions runs both on every pull request.

## Code layout

| Path | What it is |
| --- | --- |
| `recipekeeper/models.py` | Database tables. Everything belongs to a household; `plan` gates paid features |
| `recipekeeper/repository.py` | Every read and write, always filtered by household |
| `recipekeeper/ingredients.py` | Reads ingredient lines: amounts, fractions, units, notes, groups |
| `recipekeeper/steps.py` | Built-in step templates, fill-in suggestions, timer detection |
| `recipekeeper/fatsecret.py` | FatSecret client (same as Vitality's) |
| `recipekeeper/nutrition.py` | Converts ingredient amounts into FatSecret servings and adds up the totals |
| `recipekeeper/nutrition_service.py` | Matching ingredients to foods, with caching so each food is fetched once |
| `scripts/` | `set_plan` (free/premium by hand) and `check_fatsecret` (live API check) |
| `recipekeeper/schema_org.py` | Export in the schema.org Recipe format |
| `recipekeeper/photos.py` | Photo uploads: fix rotation, shrink, save as JPEG |
| `recipekeeper/auth.py` | Passwords (scrypt) and login cookies |
| `recipekeeper/api.py` | The web server: JSON API under `/api`, and the built app |
| `web/src/pages/` | The screens: box, recipe card, editor, cooking mode, settings, sign in |
| `web/src/templates.ts` | Matching step templates to what's being typed |
| `web/public/` | Home-screen icons, app manifest and offline support |
