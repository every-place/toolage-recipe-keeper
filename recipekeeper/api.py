"""The web server: a JSON API under /api, plus the phone/tablet app built into web/dist.

Run on your computer:   uvicorn recipekeeper.api:app --reload
"""
from __future__ import annotations

import json
from typing import Iterator

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.engine import Connection

from . import auth, config, nutrition_service, photos, repository as repo
from .fatsecret import FatSecretError
from .db import get_engine
from .ingredients import parse_lines
from .schema_org import to_schema_org
from .steps import SLOT_SUGGESTIONS, template_list

app = FastAPI(title="Recipe Keeper", docs_url="/api/docs", openapi_url="/api/openapi.json")


# ---------- plumbing ----------
def get_conn() -> Iterator[Connection]:
    with get_engine().begin() as conn:
        yield conn


class CurrentUser(BaseModel):
    id: int
    household_id: int
    display_name: str
    email: str


def current_user(request: Request, conn: Connection = Depends(get_conn)) -> CurrentUser:
    uid = auth.read_session(request.cookies.get(auth.COOKIE_NAME))
    user = repo.user_by_id(conn, uid) if uid else None
    if user is None:
        raise HTTPException(401, "Please log in.")
    return CurrentUser(id=user["id"], household_id=user["household_id"],
                       display_name=user["display_name"], email=user["email"])


def _set_login(response: Response, user_id: int) -> None:
    response.set_cookie(
        auth.COOKIE_NAME, auth.make_session(user_id), max_age=auth.SESSION_MAX_AGE,
        httponly=True, samesite="lax", secure=config.cookie_secure(),
    )


@app.exception_handler(repo.NotFound)
def _not_found(request, exc):
    return JSONResponse({"detail": "Not found."}, status_code=404)


@app.exception_handler(repo.Invalid)
def _invalid(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=400)


# ---------- accounts ----------
class SignupIn(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    household_name: str | None = Field(default=None, max_length=120)
    join_code: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/signup")
def signup(body: SignupIn, response: Response, conn: Connection = Depends(get_conn)):
    if "@" not in body.email:
        raise HTTPException(400, "Please enter a valid email address.")
    if body.join_code and body.join_code.strip():
        h = repo.household_by_join_code(conn, body.join_code)
        if h is None:
            raise HTTPException(400, "That family code wasn't found. Check it and try again.")
        household_id = h["id"]
    else:
        name = (body.household_name or "").strip() or f"{body.display_name.strip()}'s kitchen"
        household_id = repo.create_household(conn, name)
    user_id = repo.create_user(conn, household_id, body.email, body.display_name, body.password)
    _set_login(response, user_id)
    return {"ok": True}


@app.post("/api/auth/login")
def login(body: LoginIn, response: Response, conn: Connection = Depends(get_conn)):
    user = repo.user_by_email(conn, body.email)
    if user is None or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "That email and password don't match.")
    _set_login(response, user["id"])
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME)
    return {"ok": True}


@app.get("/api/me")
def me(user: CurrentUser = Depends(current_user), conn: Connection = Depends(get_conn)):
    return {"user": user.model_dump(), "household": repo.household(conn, user.household_id)}


# ---------- recipes ----------
class IngredientIn(BaseModel):
    raw_text: str = Field(max_length=500)
    group_label: str | None = Field(default=None, max_length=80)


class StepIn(BaseModel):
    text: str = Field(default="", max_length=2000)
    photo_id: int | None = None


class RecipeIn(BaseModel):
    title: str = Field(max_length=200)
    source_person: str | None = Field(default=None, max_length=120)
    recipe_yield: str | None = Field(default=None, max_length=80)
    servings: float | None = Field(default=None, ge=0, le=1000)
    prep_minutes: int | None = Field(default=None, ge=0, le=100000)
    cook_minutes: int | None = Field(default=None, ge=0, le=100000)
    category: str | None = Field(default=None, max_length=60)
    tags: list[str] = []
    story: str | None = Field(default=None, max_length=20000)
    story_year: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=5000)
    hero_photo_id: int | None = None
    card_photo_id: int | None = None
    ingredients: list[IngredientIn] = []
    steps: list[StepIn] = []


@app.get("/api/recipes")
def list_recipes(q: str | None = None, category: str | None = None,
                 user: CurrentUser = Depends(current_user), conn: Connection = Depends(get_conn)):
    return {"recipes": repo.list_recipes(conn, user.household_id, q, category),
            "categories": repo.categories(conn, user.household_id)}


@app.post("/api/recipes")
def create_recipe(body: RecipeIn, user: CurrentUser = Depends(current_user),
                  conn: Connection = Depends(get_conn)):
    recipe_id = repo.create_recipe(conn, user.household_id, user.id, body.model_dump())
    return repo.get_recipe(conn, user.household_id, recipe_id)


@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int, user: CurrentUser = Depends(current_user),
               conn: Connection = Depends(get_conn)):
    return repo.get_recipe(conn, user.household_id, recipe_id)


@app.put("/api/recipes/{recipe_id}")
def update_recipe(recipe_id: int, body: RecipeIn, user: CurrentUser = Depends(current_user),
                  conn: Connection = Depends(get_conn)):
    repo.update_recipe(conn, user.household_id, recipe_id, body.model_dump())
    return repo.get_recipe(conn, user.household_id, recipe_id)


@app.delete("/api/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, user: CurrentUser = Depends(current_user),
                  conn: Connection = Depends(get_conn)):
    repo.delete_recipe(conn, user.household_id, recipe_id)
    return {"ok": True}


def _photo_url(request: Request):
    base = str(request.base_url).rstrip("/")
    return lambda pid: f"{base}/api/photos/{pid}"


@app.get("/api/recipes/{recipe_id}/schema.json")
def recipe_schema(recipe_id: int, request: Request, user: CurrentUser = Depends(current_user),
                  conn: Connection = Depends(get_conn)):
    recipe = repo.get_recipe(conn, user.household_id, recipe_id)
    return to_schema_org(recipe, _photo_url(request))


@app.get("/api/export")
def export_all(request: Request, user: CurrentUser = Depends(current_user),
               conn: Connection = Depends(get_conn)):
    """Every recipe in the box as schema.org JSON: a backup, and importable elsewhere."""
    items = repo.list_recipes(conn, user.household_id)
    data = [to_schema_org(repo.get_recipe(conn, user.household_id, r["id"]), _photo_url(request))
            for r in items]
    return Response(
        content=json.dumps(data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="recipe-box.json"'},
    )


# ---------- editor helpers ----------
class ParseIn(BaseModel):
    text: str = Field(max_length=20000)


@app.post("/api/ingredients/parse")
def parse_ingredients(body: ParseIn, user: CurrentUser = Depends(current_user)):
    return {"lines": parse_lines(body.text)}


@app.get("/api/templates")
def templates(user: CurrentUser = Depends(current_user), conn: Connection = Depends(get_conn)):
    return {"templates": template_list(repo.custom_templates(conn, user.household_id)),
            "slots": SLOT_SUGGESTIONS}


class TemplateIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    group: str = "Mine"


@app.post("/api/templates")
def add_template(body: TemplateIn, user: CurrentUser = Depends(current_user),
                 conn: Connection = Depends(get_conn)):
    return {"id": repo.add_template(conn, user.household_id, body.text, body.group)}


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: int, user: CurrentUser = Depends(current_user),
                    conn: Connection = Depends(get_conn)):
    repo.delete_template(conn, user.household_id, template_id)
    return {"ok": True}


# ---------- nutrition (premium) ----------
def premium_user(user: CurrentUser = Depends(current_user), conn: Connection = Depends(get_conn)) -> CurrentUser:
    if repo.household_plan(conn, user.household_id) != "premium":
        raise HTTPException(402, "Nutrition facts are part of Recipe Keeper Premium.")
    if not config.fatsecret_configured():
        raise HTTPException(503, "Nutrition isn't set up on this server yet.")
    return user


@app.exception_handler(FatSecretError)
def _fatsecret_down(request, exc):
    return JSONResponse({"detail": "The nutrition service didn't answer. Please try again in a minute."},
                        status_code=502)


@app.get("/api/recipes/{recipe_id}/nutrition")
def recipe_nutrition(recipe_id: int, user: CurrentUser = Depends(premium_user),
                     conn: Connection = Depends(get_conn)):
    recipe = repo.get_recipe(conn, user.household_id, recipe_id)
    return nutrition_service.nutrition_for(conn, user.household_id, recipe)


@app.post("/api/recipes/{recipe_id}/nutrition/match")
def match_nutrition(recipe_id: int, user: CurrentUser = Depends(premium_user),
                    conn: Connection = Depends(get_conn)):
    recipe = repo.get_recipe(conn, user.household_id, recipe_id)
    nutrition_service.auto_match(conn, user.household_id, recipe)
    return nutrition_service.nutrition_for(conn, user.household_id, recipe)


@app.get("/api/nutrition/search")
def nutrition_search(q: str, user: CurrentUser = Depends(premium_user)):
    if not q.strip():
        return {"results": []}
    return {"results": nutrition_service.search(q.strip()[:100])}


class MatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    food_id: str | None = Field(default=None, max_length=64)
    skip: bool = False


@app.put("/api/nutrition/match")
def set_match(body: MatchIn, user: CurrentUser = Depends(premium_user),
              conn: Connection = Depends(get_conn)):
    nutrition_service.choose(conn, user.household_id, body.name, body.food_id, body.skip)
    return {"ok": True}


# ---------- photos ----------
@app.post("/api/photos")
async def upload_photo(file: UploadFile = File(...), user: CurrentUser = Depends(current_user),
                       conn: Connection = Depends(get_conn)):
    data = await file.read(photos.MAX_UPLOAD_BYTES + 1)
    try:
        jpeg, w, h = photos.prepare(data)
    except photos.PhotoError as e:
        raise HTTPException(400, str(e))
    return {"id": repo.add_photo(conn, user.household_id, jpeg, w, h), "width": w, "height": h}


@app.get("/api/photos/{photo_id}")
def get_photo(photo_id: int, user: CurrentUser = Depends(current_user),
              conn: Connection = Depends(get_conn)):
    row = repo.get_photo(conn, user.household_id, photo_id)
    return Response(row["data"], media_type=row["content_type"],
                    headers={"Cache-Control": "private, max-age=31536000, immutable"})


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- the app itself (built from web/) ----------
DIST = config.ROOT / "web" / "dist"

if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "Not found.")
    candidate = (DIST / path).resolve()
    if path and candidate.is_file() and DIST.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = DIST / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return Response("The app hasn't been built yet. Run: cd web && npm install && npm run build",
                    media_type="text/plain", status_code=503)
