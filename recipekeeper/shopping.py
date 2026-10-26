"""Turn a menu's recipes into one shopping list.

Ingredients with the same name are combined: amounts in the same unit are
added, cups and tablespoons are added through milliliters, ounces and pounds
through grams. Amounts that can't be combined ("1 can" and "2 cups") stay as
separate parts of the same item. Items are grouped by store aisle.
Pure functions: no database.
"""
from __future__ import annotations

from .ingredients import format_quantity
from .nutrition import MASS_G, VOLUME_ML, ingredient_key

AISLES = [
    ("Produce", ["apple", "banana", "lemon", "lime", "orange", "berr", "blueberr", "strawberr", "raspberr",
                 "blackberr", "cranberr", "onion", "garlic", "potato", "carrot",
                 "celery", "tomato", "lettuce", "spinach", "pepper", "zucchini", "squash", "herb", "parsley",
                 "cilantro", "basil", "mint", "ginger", "avocado", "mushroom", "cucumber", "peach", "pear",
                 "cherr", "grape", "pumpkin", "scallion", "shallot", "kale", "broccoli", "cabbage", "corn"]),
    ("Dairy and eggs", ["milk", "butter", "cream", "cheese", "yogurt", "egg", "buttermilk", "sour cream"]),
    ("Meat and seafood", ["chicken", "beef", "pork", "turkey", "bacon", "sausage", "ham", "fish", "salmon",
                          "shrimp", "tuna", "lamb"]),
    ("Baking", ["flour", "sugar", "baking", "yeast", "vanilla", "cocoa", "chocolate", "sprinkle", "shortening",
                "molasses", "corn syrup", "cornstarch", "powdered", "extract", "chips", "oats", "coconut"]),
    ("Spices", ["salt", "cinnamon", "nutmeg", "clove", "allspice", "paprika", "cumin", "oregano", "thyme",
                "rosemary", "spice", "pepper flakes", "chili powder", "black pepper", "seasoning"]),
    ("Pantry", ["oil", "vinegar", "rice", "pasta", "noodle", "bean", "broth", "stock", "sauce", "honey",
                "syrup", "peanut", "nut", "almond", "pecan", "walnut", "raisin", "jam", "mustard", "ketchup",
                "mayonnaise", "bread", "crumb", "cracker", "tortilla", "can"]),
    ("Frozen", ["frozen", "ice cream"]),
]
AISLE_ORDER = [a for a, _ in AISLES] + ["Other"]

# Spices aisle wins for "black pepper"; Produce wins for "bell pepper".
_SPECIFIC = {"black pepper": "Spices", "bell pepper": "Produce", "peanut butter": "Pantry",
             "cream of tartar": "Spices", "baking soda": "Baking", "baking powder": "Baking",
             "brown sugar": "Baking", "cream cheese": "Dairy and eggs", "coconut milk": "Pantry",
             "cornstarch": "Baking", "corn syrup": "Baking", "ice cream": "Frozen", "eggplant": "Produce",
             "ground cinnamon": "Spices", "ground ginger": "Spices", "chocolate chips": "Baking"}


def aisle_for(name: str) -> str:
    key = ingredient_key(name)
    for phrase, aisle in _SPECIFIC.items():
        if phrase in key:
            return aisle
    words_in = key.split()

    def hit(kw: str) -> bool:  # "berr" matches "berries"; "corn" doesn't match "unicorn"
        return kw in key if " " in kw else any(w.startswith(kw) for w in words_in)

    for aisle, keywords in AISLES:
        if any(hit(kw) for kw in keywords):
            return aisle
    return "Other"


def _family(unit: str | None) -> tuple[str, float] | None:
    if unit in VOLUME_ML and unit not in ("pinch", "dash", "drop"):
        return "volume", VOLUME_ML[unit]
    if unit in MASS_G and unit != "stick":
        return "mass", MASS_G[unit]
    return None


def _best_volume(ml: float) -> tuple[float, str]:
    # Cups, even for big amounts: "7 1/2 cups flour" is how a baker thinks, not "1 7/8 quarts"
    if ml >= VOLUME_ML["cup"] / 4:
        return ml / VOLUME_ML["cup"], "cup"
    if ml >= VOLUME_ML["tbsp"]:
        return ml / VOLUME_ML["tbsp"], "tbsp"
    return ml / VOLUME_ML["tsp"], "tsp"


def _best_mass(g: float, metric: bool) -> tuple[float, str]:
    if metric:
        return (g / 1000, "kg") if g >= 1000 else (g, "g")
    return (g / MASS_G["lb"], "lb") if g >= MASS_G["lb"] else (g / MASS_G["oz"], "oz")


def _volume_text(ml: float) -> str:
    """Kitchen-friendly volume: '2 1/4 cups', or '2 cups + 3 tbsp' when cups alone come out odd."""
    qty, unit = _best_volume(ml)
    text = _amount_text(qty, unit)
    if unit != "cup" or "." not in text:
        return text
    quarters = int(qty * 4) / 4
    rest_tbsp = round((ml - quarters * VOLUME_ML["cup"]) / VOLUME_ML["tbsp"] * 2) / 2
    if not rest_tbsp:
        return _amount_text(quarters, "cup")
    return f"{_amount_text(quarters, 'cup')} + {_amount_text(rest_tbsp, 'tbsp')}"


_PLURAL = {"cup": "cups", "quart": "quarts", "gallon": "gallons", "pint": "pints", "stick": "sticks",
           "can": "cans", "package": "packages", "clove": "cloves", "jar": "jars", "box": "boxes", "bag": "bags",
           "slice": "slices", "bunch": "bunches", "head": "heads", "pinch": "pinches"}


def _amount_text(qty: float, unit: str | None) -> str:
    amount = format_quantity(round(qty, 3))
    if unit and qty > 1 and unit in _PLURAL:
        unit = _PLURAL[unit]
    return f"{amount} {unit}" if unit else amount


def build_list(lines: list[dict], staples: set[str], checks: dict[str, str]) -> dict:
    """lines: ingredient rows with quantity/unit/name plus 'recipe_title' and 'multiplier'.

    Returns {"aisles": [{"aisle", "items": [...]}], "counts": {...}}.
    """
    items: dict[str, dict] = {}
    for ln in lines:
        name = (ln.get("name") or ln.get("raw_text") or "").strip()
        key = ingredient_key(name)
        if not key:
            continue
        item = items.setdefault(key, {
            "key": key, "name": name, "recipes": [], "volume_ml": 0.0, "mass_g": 0.0, "metric_mass": False,
            "units": {}, "loose": False,
        })
        title = ln.get("recipe_title")
        if title and title not in item["recipes"]:
            item["recipes"].append(title)
        qty = ln.get("quantity")
        if qty is None:
            item["loose"] = True  # "salt to taste": buy some, no amount
            continue
        qty *= ln.get("multiplier") or 1
        unit = (ln.get("unit") or None)
        fam = _family(unit)
        if fam and fam[0] == "volume":
            item["volume_ml"] += qty * fam[1]
        elif fam and fam[0] == "mass":
            item["mass_g"] += qty * fam[1]
            item["metric_mass"] = item["metric_mass"] or unit in ("g", "kg")
        else:
            item["units"][unit] = item["units"].get(unit, 0.0) + qty

    out_items = []
    for item in items.values():
        parts = []
        for unit, qty in item["units"].items():
            parts.append(_amount_text(qty, unit))
        if item["volume_ml"]:
            parts.append(_volume_text(item["volume_ml"]))
        if item["mass_g"]:
            parts.append(_amount_text(*_best_mass(item["mass_g"], item["metric_mass"])))
        state = checks.get(item["key"])
        if state is None:
            state = "have" if item["key"] in staples else "need"
        out_items.append({
            "key": item["key"],
            "name": item["name"],
            "amount": " + ".join(parts),
            "recipes": item["recipes"],
            "aisle": aisle_for(item["name"]),
            "state": state,
            "staple": item["key"] in staples,
        })

    aisles = []
    for aisle in AISLE_ORDER:
        group = sorted((i for i in out_items if i["aisle"] == aisle), key=lambda i: i["name"].lower())
        if group:
            aisles.append({"aisle": aisle, "items": group})
    counts = {s: sum(1 for i in out_items if i["state"] == s) for s in ("need", "got", "have")}
    return {"aisles": aisles, "counts": counts}


def as_text(shopping: dict, title: str) -> str:
    """The list as plain text for a text message or email: only what's still needed."""
    lines = [f"Shopping list: {title}", ""]
    for group in shopping["aisles"]:
        need = [i for i in group["items"] if i["state"] == "need"]
        if not need:
            continue
        lines.append(group["aisle"].upper())
        for i in need:
            lines.append(f"[ ] {i['name']}" + (f", {i['amount']}" if i["amount"] else ""))
        lines.append("")
    return "\n".join(lines).strip() + "\n"
