"""Glue between recipes, FatSecret and the database for the nutrition panel.

Reading nutrition never calls FatSecret: it uses foods already cached.
Only matching new ingredients (and searching) costs API calls.
"""
from __future__ import annotations

from sqlalchemy.engine import Connection

from . import repository as repo
from .fatsecret import FatSecretClient, FatSecretError
from .nutrition import ingredient_key, pick_best, recipe_nutrition

MAX_AUTO_MATCH = 40  # API calls per click stay bounded, even for a huge recipe

_client: FatSecretClient | None = None


def client() -> FatSecretClient:
    global _client
    if _client is None:
        _client = FatSecretClient()
    return _client


def set_client(c) -> None:
    """Tests swap in a fake."""
    global _client
    _client = c


def _keys(recipe: dict) -> set[str]:
    return {k for k in (ingredient_key(i.get("name")) for i in recipe["ingredients"]) if k}


def nutrition_for(conn: Connection, household_id: int, recipe: dict) -> dict:
    matches = repo.matches_for(conn, household_id, _keys(recipe))
    food_ids = {m["food_id"] for m in matches.values() if m.get("food_id")}
    foods = repo.cached_foods(conn, food_ids)
    return recipe_nutrition(recipe["ingredients"], matches, foods, recipe.get("servings"))


def _ensure_food(conn: Connection, food_id: str) -> dict:
    cached = repo.cached_foods(conn, {food_id})
    if food_id in cached:
        return cached[food_id]
    food = client().get_food(food_id)
    if not food.get("food_id"):
        raise FatSecretError("FatSecret didn't return that food.")
    repo.cache_food(conn, food)
    return food


def auto_match(conn: Connection, household_id: int, recipe: dict) -> int:
    """Match ingredients this household hasn't matched before. Returns how many were matched.

    Lines without an amount ("salt to taste") aren't counted, so they cost no API calls.
    """
    keys = {k for k in (ingredient_key(i.get("name")) for i in recipe["ingredients"]
                        if i.get("quantity") is not None) if k}
    known = repo.matches_for(conn, household_id, keys)
    todo = [k for k in sorted(keys) if k not in known][:MAX_AUTO_MATCH]
    matched = 0
    for key in todo:
        best = pick_best(client().search_foods(key, max_results=10), key)
        if best is None:
            continue
        food = _ensure_food(conn, str(best["food_id"]))
        repo.save_match(conn, household_id, key, str(food["food_id"]), food["name"])
        matched += 1
    return matched


def choose(conn: Connection, household_id: int, name: str, food_id: str | None, skip: bool = False) -> None:
    key = ingredient_key(name)
    if skip:
        repo.save_match(conn, household_id, key, None, None, skipped=True, confirmed=True)
        return
    if not food_id:
        raise repo.Invalid("Pick a food, or choose to skip this ingredient.")
    food = _ensure_food(conn, str(food_id))
    repo.save_match(conn, household_id, key, str(food["food_id"]), food["name"], confirmed=True)


def search(query: str) -> list[dict]:
    return client().search_foods(query, max_results=12)
