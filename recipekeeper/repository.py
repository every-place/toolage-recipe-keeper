"""Every database read and write. Recipe queries are always filtered by household."""
from __future__ import annotations

import json

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.engine import Connection

from . import auth
from .ingredients import parse_ingredient
from .models import (
    menu_recipes,
    menus,
    pantry_staples,
    shopping_checks,
    food_cache,
    ingredient_matches,
    households,
    now_utc_text,
    photos,
    recipe_ingredients,
    recipe_steps,
    recipes,
    step_templates,
    users,
)
from .steps import detect_timer_minutes

RECIPE_FIELDS = (
    "title", "source_person", "recipe_yield", "servings", "prep_minutes", "cook_minutes",
    "category", "tags", "story", "story_year", "notes", "hero_photo_id", "card_photo_id",
)


class NotFound(Exception):
    pass


class Invalid(ValueError):
    pass


# ---------- households and users ----------
def create_household(conn: Connection, name: str) -> int:
    for _ in range(5):
        code = auth.new_join_code()
        if conn.scalar(select(households.c.id).where(households.c.join_code == code)) is None:
            break
    return conn.execute(insert(households).values(name=name, join_code=code)).inserted_primary_key[0]


def household_by_join_code(conn: Connection, code: str):
    code = code.strip().upper().replace(" ", "")
    if len(code) == 8:
        code = code[:4] + "-" + code[4:]
    return conn.execute(select(households).where(households.c.join_code == code)).mappings().first()


def create_user(conn: Connection, household_id: int, email: str, display_name: str, password: str) -> int:
    email = email.strip().lower()
    if conn.scalar(select(users.c.id).where(users.c.email == email)) is not None:
        raise Invalid("An account with that email already exists.")
    return conn.execute(
        insert(users).values(
            household_id=household_id,
            email=email,
            display_name=display_name.strip(),
            password_hash=auth.hash_password(password),
        )
    ).inserted_primary_key[0]


def user_by_email(conn: Connection, email: str):
    return conn.execute(select(users).where(users.c.email == email.strip().lower())).mappings().first()


def user_by_id(conn: Connection, user_id: int):
    return conn.execute(select(users).where(users.c.id == user_id)).mappings().first()


def household(conn: Connection, household_id: int) -> dict:
    h = conn.execute(select(households).where(households.c.id == household_id)).mappings().one()
    members = conn.execute(
        select(users.c.id, users.c.display_name, users.c.email)
        .where(users.c.household_id == household_id)
        .order_by(users.c.id)
    ).mappings().all()
    return {"id": h["id"], "name": h["name"], "plan": h["plan"], "join_code": h["join_code"],
            "members": [dict(m) for m in members]}


# ---------- photos ----------
def add_photo(conn: Connection, household_id: int, data: bytes, width: int, height: int) -> int:
    return conn.execute(
        insert(photos).values(household_id=household_id, content_type="image/jpeg",
                              width=width, height=height, data=data)
    ).inserted_primary_key[0]


def get_photo(conn: Connection, household_id: int, photo_id: int):
    row = conn.execute(
        select(photos.c.data, photos.c.content_type)
        .where(photos.c.id == photo_id, photos.c.household_id == household_id)
    ).mappings().first()
    if row is None:
        raise NotFound
    return row


def _check_photo_ids(conn: Connection, household_id: int, ids: set[int]) -> None:
    ids = {i for i in ids if i is not None}
    if not ids:
        return
    found = set(conn.scalars(
        select(photos.c.id).where(photos.c.id.in_(ids), photos.c.household_id == household_id)
    ))
    if found != ids:
        raise Invalid("One of the photos wasn't found.")


# ---------- recipes ----------
def _clean_recipe(data: dict) -> dict:
    title = (data.get("title") or "").strip()
    if not title:
        raise Invalid("Every recipe needs a title.")
    values = {k: data.get(k) for k in RECIPE_FIELDS}
    values["title"] = title[:200]
    tags = data.get("tags") or []
    if isinstance(tags, str):
        tags = tags.split(",")
    values["tags"] = ",".join(t.strip() for t in tags if t and t.strip()) or None
    for k in ("source_person", "recipe_yield", "category", "story", "story_year", "notes"):
        if isinstance(values[k], str):
            values[k] = values[k].strip() or None
    return values


def _write_children(conn: Connection, recipe_id: int, data: dict) -> None:
    conn.execute(delete(recipe_ingredients).where(recipe_ingredients.c.recipe_id == recipe_id))
    conn.execute(delete(recipe_steps).where(recipe_steps.c.recipe_id == recipe_id))
    rows = []
    for i, item in enumerate(data.get("ingredients") or []):
        raw = (item.get("raw_text") or "").strip()
        if not raw:
            continue
        parsed = parse_ingredient(raw).to_dict()
        parsed["group_label"] = (item.get("group_label") or "").strip() or None
        rows.append({"recipe_id": recipe_id, "position": i, **parsed})
    if rows:
        conn.execute(insert(recipe_ingredients), rows)
    rows = []
    for i, step in enumerate(data.get("steps") or []):
        text = (step.get("text") or "").strip()
        if not text and not step.get("photo_id"):
            continue
        rows.append({"recipe_id": recipe_id, "position": i, "text": text,
                     "photo_id": step.get("photo_id"), "timer_minutes": detect_timer_minutes(text)})
    if rows:
        conn.execute(insert(recipe_steps), rows)


def _photo_ids_in(data: dict) -> set[int]:
    ids = {data.get("hero_photo_id"), data.get("card_photo_id")}
    ids |= {s.get("photo_id") for s in data.get("steps") or []}
    return ids


def create_recipe(conn: Connection, household_id: int, user_id: int, data: dict) -> int:
    values = _clean_recipe(data)
    _check_photo_ids(conn, household_id, _photo_ids_in(data))
    recipe_id = conn.execute(
        insert(recipes).values(household_id=household_id, created_by=user_id, **values)
    ).inserted_primary_key[0]
    _write_children(conn, recipe_id, data)
    return recipe_id


def update_recipe(conn: Connection, household_id: int, recipe_id: int, data: dict) -> None:
    _own_recipe(conn, household_id, recipe_id)
    values = _clean_recipe(data)
    _check_photo_ids(conn, household_id, _photo_ids_in(data))
    conn.execute(update(recipes).where(recipes.c.id == recipe_id)
                 .values(updated_at=now_utc_text(), **values))
    _write_children(conn, recipe_id, data)


def delete_recipe(conn: Connection, household_id: int, recipe_id: int) -> None:
    _own_recipe(conn, household_id, recipe_id)
    conn.execute(delete(recipes).where(recipes.c.id == recipe_id))


def _own_recipe(conn: Connection, household_id: int, recipe_id: int):
    row = conn.execute(
        select(recipes).where(recipes.c.id == recipe_id, recipes.c.household_id == household_id)
    ).mappings().first()
    if row is None:
        raise NotFound
    return row


def get_recipe(conn: Connection, household_id: int, recipe_id: int) -> dict:
    row = _own_recipe(conn, household_id, recipe_id)
    out = dict(row)
    out["tags"] = [t for t in (row["tags"] or "").split(",") if t]
    out["ingredients"] = [dict(r) for r in conn.execute(
        select(recipe_ingredients).where(recipe_ingredients.c.recipe_id == recipe_id)
        .order_by(recipe_ingredients.c.position)
    ).mappings()]
    out["steps"] = [dict(r) for r in conn.execute(
        select(recipe_steps).where(recipe_steps.c.recipe_id == recipe_id)
        .order_by(recipe_steps.c.position)
    ).mappings()]
    author = conn.scalar(select(users.c.display_name).where(users.c.id == row["created_by"]))
    out["created_by_name"] = author
    return out


def list_recipes(conn: Connection, household_id: int, q: str | None = None,
                 category: str | None = None) -> list[dict]:
    stmt = select(
        recipes.c.id, recipes.c.title, recipes.c.source_person, recipes.c.category,
        recipes.c.tags, recipes.c.hero_photo_id, recipes.c.updated_at,
    ).where(recipes.c.household_id == household_id)
    if category:
        stmt = stmt.where(recipes.c.category == category)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        in_ingredients = select(recipe_ingredients.c.recipe_id).where(
            func.lower(recipe_ingredients.c.raw_text).like(like)
        )
        stmt = stmt.where(or_(
            func.lower(recipes.c.title).like(like),
            func.lower(recipes.c.source_person).like(like),
            func.lower(recipes.c.tags).like(like),
            func.lower(recipes.c.story).like(like),
            recipes.c.id.in_(in_ingredients),
        ))
    stmt = stmt.order_by(func.lower(recipes.c.title))
    out = []
    for r in conn.execute(stmt).mappings():
        d = dict(r)
        d["tags"] = [t for t in (r["tags"] or "").split(",") if t]
        out.append(d)
    return out


def categories(conn: Connection, household_id: int) -> list[str]:
    return list(conn.scalars(
        select(recipes.c.category).where(recipes.c.household_id == household_id,
                                         recipes.c.category.is_not(None))
        .distinct().order_by(recipes.c.category)
    ))


# ---------- custom templates ----------
def custom_templates(conn: Connection, household_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        select(step_templates).where(step_templates.c.household_id == household_id)
        .order_by(step_templates.c.id)
    ).mappings()]


def add_template(conn: Connection, household_id: int, text: str, group: str = "Mine") -> int:
    text = text.strip()
    if not text:
        raise Invalid("The template is empty.")
    existing = conn.scalar(select(step_templates.c.id).where(
        step_templates.c.household_id == household_id, step_templates.c.text == text))
    if existing:
        return existing
    return conn.execute(insert(step_templates).values(
        household_id=household_id, text=text, grp=(group or "Mine").strip()[:40]
    )).inserted_primary_key[0]


def delete_template(conn: Connection, household_id: int, template_id: int) -> None:
    res = conn.execute(delete(step_templates).where(
        step_templates.c.id == template_id, step_templates.c.household_id == household_id))
    if res.rowcount == 0:
        raise NotFound


# ---------- plans ----------
def set_plan(conn: Connection, household_id: int, plan: str) -> None:
    if plan not in ("free", "premium"):
        raise Invalid("Plan must be 'free' or 'premium'.")
    conn.execute(update(households).where(households.c.id == household_id).values(plan=plan))


def household_plan(conn: Connection, household_id: int) -> str:
    return conn.scalar(select(households.c.plan).where(households.c.id == household_id))


# ---------- nutrition ----------
def cached_foods(conn: Connection, food_ids: set[str]) -> dict[str, dict]:
    if not food_ids:
        return {}
    rows = conn.execute(select(food_cache).where(food_cache.c.food_id.in_(food_ids))).mappings()
    return {r["food_id"]: {"food_id": r["food_id"], "name": r["name"], "brand": r["brand"],
                           "servings": json.loads(r["servings"])} for r in rows}


def cache_food(conn: Connection, food: dict) -> None:
    exists = conn.scalar(select(food_cache.c.id).where(food_cache.c.food_id == str(food["food_id"])))
    values = {"name": food["name"], "brand": food.get("brand"), "servings": json.dumps(food["servings"]),
              "fetched_at": now_utc_text()}
    if exists:
        conn.execute(update(food_cache).where(food_cache.c.id == exists).values(**values))
    else:
        conn.execute(insert(food_cache).values(food_id=str(food["food_id"]), **values))


def matches_for(conn: Connection, household_id: int, keys: set[str]) -> dict[str, dict]:
    if not keys:
        return {}
    rows = conn.execute(select(ingredient_matches).where(
        ingredient_matches.c.household_id == household_id,
        ingredient_matches.c.ingredient_key.in_(keys),
    )).mappings()
    return {r["ingredient_key"]: dict(r) for r in rows}


def save_match(conn: Connection, household_id: int, key: str, food_id: str | None, food_name: str | None,
               skipped: bool = False, confirmed: bool = False) -> None:
    if not key:
        raise Invalid("That ingredient has no name to match.")
    values = {"food_id": food_id, "food_name": food_name, "skipped": int(skipped), "confirmed": int(confirmed)}
    existing = conn.scalar(select(ingredient_matches.c.id).where(
        ingredient_matches.c.household_id == household_id, ingredient_matches.c.ingredient_key == key))
    if existing:
        conn.execute(update(ingredient_matches).where(ingredient_matches.c.id == existing).values(**values))
    else:
        conn.execute(insert(ingredient_matches).values(household_id=household_id, ingredient_key=key, **values))


# ---------- menus and shopping ----------
def _own_menu(conn: Connection, household_id: int, menu_id: int):
    row = conn.execute(select(menus).where(menus.c.id == menu_id, menus.c.household_id == household_id)
                       ).mappings().first()
    if row is None:
        raise NotFound
    return row


def list_menus(conn: Connection, household_id: int) -> list[dict]:
    rows = conn.execute(
        select(menus.c.id, menus.c.name, menus.c.created_at, func.count(menu_recipes.c.id).label("recipe_count"))
        .select_from(menus.outerjoin(menu_recipes, menu_recipes.c.menu_id == menus.c.id))
        .where(menus.c.household_id == household_id)
        .group_by(menus.c.id, menus.c.name, menus.c.created_at)
        .order_by(menus.c.id.desc())
    ).mappings()
    return [dict(r) for r in rows]


def create_menu(conn: Connection, household_id: int, name: str) -> int:
    name = (name or "").strip()
    if not name:
        raise Invalid("Give the menu a name.")
    return conn.execute(insert(menus).values(household_id=household_id, name=name[:120])).inserted_primary_key[0]


def rename_menu(conn: Connection, household_id: int, menu_id: int, name: str) -> None:
    _own_menu(conn, household_id, menu_id)
    if not (name or "").strip():
        raise Invalid("Give the menu a name.")
    conn.execute(update(menus).where(menus.c.id == menu_id).values(name=name.strip()[:120]))


def delete_menu(conn: Connection, household_id: int, menu_id: int) -> None:
    _own_menu(conn, household_id, menu_id)
    conn.execute(delete(menus).where(menus.c.id == menu_id))


def get_menu(conn: Connection, household_id: int, menu_id: int) -> dict:
    m = dict(_own_menu(conn, household_id, menu_id))
    m["recipes"] = [dict(r) for r in conn.execute(
        select(menu_recipes.c.recipe_id, menu_recipes.c.multiplier, recipes.c.title, recipes.c.hero_photo_id)
        .join(recipes, recipes.c.id == menu_recipes.c.recipe_id)
        .where(menu_recipes.c.menu_id == menu_id)
        .order_by(menu_recipes.c.id)
    ).mappings()]
    return m


def set_menu_recipe(conn: Connection, household_id: int, menu_id: int, recipe_id: int, multiplier: float) -> None:
    """Add a recipe to a menu, or change its batch size. Multiplier 0 removes it."""
    _own_menu(conn, household_id, menu_id)
    _own_recipe(conn, household_id, recipe_id)
    where = (menu_recipes.c.menu_id == menu_id) & (menu_recipes.c.recipe_id == recipe_id)
    if multiplier <= 0:
        conn.execute(delete(menu_recipes).where(where))
        return
    if conn.scalar(select(menu_recipes.c.id).where(where)):
        conn.execute(update(menu_recipes).where(where).values(multiplier=multiplier))
    else:
        conn.execute(insert(menu_recipes).values(menu_id=menu_id, recipe_id=recipe_id, multiplier=multiplier))


def menu_lines(conn: Connection, household_id: int, menu_id: int) -> list[dict]:
    _own_menu(conn, household_id, menu_id)
    rows = conn.execute(
        select(recipe_ingredients.c.raw_text, recipe_ingredients.c.quantity, recipe_ingredients.c.unit,
               recipe_ingredients.c.name, recipes.c.title.label("recipe_title"), menu_recipes.c.multiplier)
        .join(recipes, recipes.c.id == recipe_ingredients.c.recipe_id)
        .join(menu_recipes, menu_recipes.c.recipe_id == recipes.c.id)
        .where(menu_recipes.c.menu_id == menu_id, recipes.c.household_id == household_id)
        .order_by(menu_recipes.c.id, recipe_ingredients.c.position)
    ).mappings()
    return [dict(r) for r in rows]


def staples(conn: Connection, household_id: int) -> set[str]:
    return set(conn.scalars(select(pantry_staples.c.ingredient_key)
                            .where(pantry_staples.c.household_id == household_id)))


def set_staple(conn: Connection, household_id: int, key: str, on: bool) -> None:
    where = (pantry_staples.c.household_id == household_id) & (pantry_staples.c.ingredient_key == key)
    exists = conn.scalar(select(pantry_staples.c.id).where(where))
    if on and not exists:
        conn.execute(insert(pantry_staples).values(household_id=household_id, ingredient_key=key))
    elif not on and exists:
        conn.execute(delete(pantry_staples).where(where))


def checks(conn: Connection, menu_id: int) -> dict[str, str]:
    return {r["item_key"]: r["state"] for r in conn.execute(
        select(shopping_checks.c.item_key, shopping_checks.c.state).where(shopping_checks.c.menu_id == menu_id)
    ).mappings()}


def set_check(conn: Connection, household_id: int, menu_id: int, key: str, state: str | None) -> None:
    """state None clears it (back to the default: 'have' for staples, else 'need')."""
    _own_menu(conn, household_id, menu_id)
    where = (shopping_checks.c.menu_id == menu_id) & (shopping_checks.c.item_key == key)
    conn.execute(delete(shopping_checks).where(where))
    if state is not None:
        if state not in ("have", "got", "need"):
            raise Invalid("Unknown item state.")
        conn.execute(insert(shopping_checks).values(menu_id=menu_id, item_key=key, state=state))


def clear_checks(conn: Connection, household_id: int, menu_id: int) -> None:
    _own_menu(conn, household_id, menu_id)
    conn.execute(delete(shopping_checks).where(shopping_checks.c.menu_id == menu_id))
