"""Nutrition for a recipe, from FatSecret foods.

Each ingredient line ("1/2 cup flour, sifted") is matched to a FatSecret food,
and its amount is converted into that food's servings:

  1. A serving in a unit we can convert to (1 cup, 1 tbsp, 100 g, 1 oz...).
  2. A serving's weight or volume in grams / ml.
  3. For counted things ("3 eggs"), a per-item serving ("1 large").

Cooking effects (baking, frying) are ignored for now.
All functions here are pure: no database, no network.
"""
from __future__ import annotations

import re

from .ingredients import parse_ingredient

NUTRIENTS = ("calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sodium_mg")

VOLUME_ML = {
    "cup": 236.588, "tbsp": 14.787, "tsp": 4.929, "fl oz": 29.574, "pint": 473.176,
    "quart": 946.353, "gallon": 3785.41, "ml": 1.0, "l": 1000.0,
    "pinch": 0.31, "dash": 0.62, "drop": 0.05,
}
MASS_G = {"g": 1.0, "kg": 1000.0, "oz": 28.3495, "lb": 453.592, "stick": 113.4}  # a stick of butter

# Sizes people add to counted things; a "1 medium" serving is the best stand-in.
SIZE_WORDS = ("medium", "large", "small", "extra large", "jumbo", "whole")


def ingredient_key(name: str | None) -> str:
    """'Large Eggs' -> 'large eggs'. How a household's choices are remembered."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())).strip()


def _serving_amount(serving: dict) -> tuple[float, str | None]:
    """'1/2 cup' -> (0.5, 'cup'); '1 large' -> (1, None); '100 g' -> (100, 'g')."""
    p = parse_ingredient(serving.get("description") or "")
    return (p.quantity or 1.0), p.unit


def _scaled(serving: dict, multiplier: float) -> dict:
    return {k: (serving.get(k) or 0.0) * multiplier for k in NUTRIENTS}


def _base_unit(unit: str | None) -> str | None:
    if unit is None:
        return None
    return unit.split(" (")[0]  # "package (8 oz)" -> "package"


def amount_multiplier(quantity: float, unit: str | None, servings: list[dict]) -> tuple[dict, float] | None:
    """Find a serving and how many of it the ingredient amount is. None if we can't convert."""
    unit = _base_unit(unit)
    parsed = [(s, *_serving_amount(s)) for s in servings]

    # 1. Same unit as a serving ("1 cup" serving for "2 cups")
    for s, sq, su in parsed:
        if unit and su == unit and sq:
            return s, quantity / sq

    # 2. Volume: via a serving in a volume unit, or one measured in ml
    if unit in VOLUME_ML:
        ml = quantity * VOLUME_ML[unit]
        for s, sq, su in parsed:
            if su in VOLUME_ML and sq:
                return s, ml / (sq * VOLUME_ML[su])
        for s, _, _ in parsed:
            if s.get("metric_unit") == "ml" and s.get("metric_amount"):
                return s, ml / s["metric_amount"]

    # 3. Weight: via a serving in a weight unit, or one weighed in grams
    if unit in MASS_G:
        grams = quantity * MASS_G[unit]
        for s, _, _ in parsed:
            if s.get("metric_unit") == "g" and s.get("metric_amount"):
                return s, grams / s["metric_amount"]
        for s, sq, su in parsed:
            if su in MASS_G and su != "stick" and sq:
                return s, grams / (sq * MASS_G[su])

    # 4. Counted things: "3 eggs" -> the "1 large" serving
    if unit is None:
        counted = [(s, sq) for s, sq, su in parsed if su is None and sq]
        for size in ("medium", "large"):
            for s, sq in counted:
                if size in (s.get("description") or "").lower():
                    return s, quantity / sq
        if counted:
            s, sq = counted[0]
            return s, quantity / sq
    return None


def line_nutrition(line: dict, match: dict | None, food: dict | None) -> dict:
    """Nutrition for one ingredient line, with a status the screen can explain."""
    out = {"ingredient_id": line.get("id"), "raw_text": line["raw_text"], "name": line.get("name"),
           "food_id": None, "food_name": None, "status": "unmatched", "nutrients": None}
    if match and match.get("skipped"):
        out["status"] = "skipped"
        return out
    if line.get("quantity") is None:
        out["status"] = "no_amount"  # "salt to taste": nothing to count, nothing to match
        return out
    if not match or not match.get("food_id") or not food:
        return out
    out["food_id"] = match["food_id"]
    out["food_name"] = match.get("food_name") or food.get("name")
    found = amount_multiplier(line["quantity"], line.get("unit"), food.get("servings") or [])
    if not found:
        out["status"] = "no_conversion"
        return out
    serving, mult = found
    out["status"] = "ok"
    out["nutrients"] = _scaled(serving, mult)
    out["serving"] = serving.get("description")
    return out


def recipe_nutrition(ingredients: list[dict], matches: dict[str, dict], foods: dict[str, dict],
                     servings: float | None) -> dict:
    """matches: ingredient_key -> match row; foods: food_id -> {name, servings}."""
    lines = []
    total = {k: 0.0 for k in NUTRIENTS}
    for ing in ingredients:
        match = matches.get(ingredient_key(ing.get("name")))
        food = foods.get(match["food_id"]) if match and match.get("food_id") else None
        ln = line_nutrition(ing, match, food)
        lines.append(ln)
        if ln["nutrients"]:
            for k in NUTRIENTS:
                total[k] += ln["nutrients"][k]
    counted = sum(1 for ln in lines if ln["status"] == "ok")
    per_serving = {k: v / servings for k, v in total.items()} if servings else None
    return {
        "total": total,
        "per_serving": per_serving,
        "servings": servings,
        "lines": lines,
        "counted": counted,
        "needs_attention": sum(1 for ln in lines if ln["status"] in ("unmatched", "no_conversion")),
    }


def pick_best(results: list[dict], name: str) -> dict | None:
    """Prefer a generic food (no brand) whose name shares the most words with the ingredient."""
    if not results:
        return None
    words = set(ingredient_key(name).split())

    def score(r):
        name_words = ingredient_key(r.get("name")).split()
        rw = set(name_words)
        overlap = len(words & rw) + len({w.rstrip("s") for w in words} & {w.rstrip("s") for w in rw})
        # "White Flour" is flour; "Flour Tortilla" is a tortilla: the last word names the food
        head = bool(name_words) and name_words[-1].rstrip("s") in {w.rstrip("s") for w in words}
        return (head, r.get("brand") is None, overlap, -len(rw))

    return max(results, key=score)
