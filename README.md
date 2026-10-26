# Recipe Keeper by Toolage

A digital recipe box for families. Log Grandma's handwritten cards, your own creations and the stories behind them, on a phone or tablet in the kitchen.

## What it does

- **Recipe box**: every recipe as a card with its photo; search by name, ingredient, person or story; filter by category.
- **Card editor**: type ingredients the way you'd write them (`1/2 cup flour, sifted`) and the app reads the amount, unit, ingredient and note. Steps offer sentence templates as you type ("Bake at ___ for ___, or until ___"), with tap-to-fill blanks. Photos of the finished dish, each step, and the original handwritten card. A place for the story behind the recipe. Unsaved work is kept on the device.
- **Recipe card**: scale the batch (½×, 2×, 3×), print it as a card, or export it.
- **Cooking mode**: big text, one step at a time, the screen stays awake, built-in timers, and an ingredient checklist.
- **Family sharing**: one recipe box per household. Family members join with a code from Settings.
- **Your data**: export every recipe in the schema.org Recipe format, which most recipe apps can import.
- **Plans**: each household has a `free` or `premium` plan. Paid features (FatSecret nutrition, next) will check it.

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

The `Dockerfile` builds one container that serves the app and the API. Any host that runs containers works (Render, Railway, Fly.io, Google Cloud Run). Set these environment variables there:

| Name | Value |
| --- | --- |
| `SECRET_KEY` | A long random string. Changing it logs everyone out |
| `DATABASE_URL` | Your Postgres connection string |
| `COOKIE_SECURE` | `1` (already set in the Dockerfile; the site must be on https) |

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
| `recipekeeper/schema_org.py` | Export in the schema.org Recipe format |
| `recipekeeper/photos.py` | Photo uploads: fix rotation, shrink, save as JPEG |
| `recipekeeper/auth.py` | Passwords (scrypt) and login cookies |
| `recipekeeper/api.py` | The web server: JSON API under `/api`, and the built app |
| `web/src/pages/` | The screens: box, recipe card, editor, cooking mode, settings, sign in |
| `web/src/templates.ts` | Matching step templates to what's being typed |
| `web/public/` | Home-screen icons, app manifest and offline support |
