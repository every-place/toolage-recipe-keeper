"""Export a recipe in the schema.org Recipe format (JSON-LD).

This is the format Google and most recipe apps (Paprika, Mealie and others)
read, so exported recipes can be imported elsewhere.
"""
from __future__ import annotations


def iso_duration(minutes: int | float | None) -> str | None:
    """95 -> 'PT1H35M'."""
    if not minutes:
        return None
    minutes = int(round(minutes))
    hours, mins = divmod(minutes, 60)
    return "PT" + (f"{hours}H" if hours else "") + (f"{mins}M" if mins else "")


def to_schema_org(recipe: dict, photo_url=None) -> dict:
    """photo_url: optional function photo_id -> absolute URL."""
    out = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": recipe["title"],
        "recipeIngredient": [i["raw_text"] for i in recipe.get("ingredients", [])],
        "recipeInstructions": [],
    }
    if recipe.get("source_person"):
        out["author"] = {"@type": "Person", "name": recipe["source_person"]}
    if recipe.get("story"):
        out["description"] = recipe["story"]
    if recipe.get("recipe_yield"):
        out["recipeYield"] = recipe["recipe_yield"]
    elif recipe.get("servings"):
        out["recipeYield"] = f"{recipe['servings']:g} servings"
    for key, field in (("prep_minutes", "prepTime"), ("cook_minutes", "cookTime")):
        d = iso_duration(recipe.get(key))
        if d:
            out[field] = d
    total = (recipe.get("prep_minutes") or 0) + (recipe.get("cook_minutes") or 0)
    if total:
        out["totalTime"] = iso_duration(total)
    if recipe.get("category"):
        out["recipeCategory"] = recipe["category"]
    if recipe.get("tags"):
        out["keywords"] = ", ".join(recipe["tags"])
    if photo_url and recipe.get("hero_photo_id"):
        out["image"] = [photo_url(recipe["hero_photo_id"])]
    for step in recipe.get("steps", []):
        item = {"@type": "HowToStep", "text": step["text"]}
        if photo_url and step.get("photo_id"):
            item["image"] = photo_url(step["photo_id"])
        out["recipeInstructions"].append(item)
    return out
