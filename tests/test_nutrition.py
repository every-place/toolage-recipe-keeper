import pytest

from recipekeeper.nutrition import amount_multiplier, ingredient_key, pick_best, recipe_nutrition

FLOUR = [
    {"description": "1 cup", "metric_amount": 125.0, "metric_unit": "g", "calories": 455.0, "protein_g": 12.9,
     "carbs_g": 95.4, "fat_g": 1.2},
    {"description": "100 g", "metric_amount": 100.0, "metric_unit": "g", "calories": 364.0, "protein_g": 10.3,
     "carbs_g": 76.3, "fat_g": 1.0},
]
EGG = [
    {"description": "1 large", "metric_amount": 50.0, "metric_unit": "g", "calories": 72.0},
    {"description": "1 medium", "metric_amount": 44.0, "metric_unit": "g", "calories": 63.0},
    {"description": "100 g", "metric_amount": 100.0, "metric_unit": "g", "calories": 143.0},
]
BUTTER = [
    {"description": "1 tbsp", "metric_amount": 14.2, "metric_unit": "g", "calories": 102.0},
    {"description": "1 pat", "metric_amount": 5.0, "metric_unit": "g", "calories": 36.0},
]
MILK = [{"description": "1 serving", "metric_amount": 244.0, "metric_unit": "ml", "calories": 122.0}]


def cals(qty, unit, servings):
    s, mult = amount_multiplier(qty, unit, servings)
    return s["calories"] * mult


def test_same_unit():
    assert cals(0.5, "cup", FLOUR) == pytest.approx(227.5)


def test_volume_conversion():
    # 2 tsp = 2/3 tbsp
    assert cals(2, "tsp", BUTTER) == pytest.approx(68.0, rel=0.01)
    assert cals(1, "cup", MILK) == pytest.approx(122 * 236.588 / 244, rel=0.01)


def test_weight_conversion():
    assert cals(1, "lb", FLOUR) == pytest.approx(455 * 453.592 / 125, rel=0.01)
    assert cals(2, "stick", BUTTER) == pytest.approx(102 * 226.8 / 14.2, rel=0.01)


def test_counted_prefers_medium():
    assert cals(3, None, EGG) == pytest.approx(189.0)


def test_cannot_convert():
    assert amount_multiplier(1, "can", FLOUR) is None
    assert amount_multiplier(2, None, FLOUR) is None


def test_recipe_totals_and_statuses():
    ingredients = [
        {"id": 1, "raw_text": "3 eggs", "quantity": 3, "unit": None, "name": "eggs"},
        {"id": 2, "raw_text": "1/2 cup flour", "quantity": 0.5, "unit": "cup", "name": "flour"},
        {"id": 3, "raw_text": "salt to taste", "quantity": None, "unit": None, "name": "salt"},
        {"id": 4, "raw_text": "1 cup water", "quantity": 1, "unit": "cup", "name": "water"},
        {"id": 5, "raw_text": "1 tsp magic", "quantity": 1, "unit": "tsp", "name": "magic"},
    ]
    matches = {
        "eggs": {"food_id": "e", "food_name": "Egg"},
        "flour": {"food_id": "f", "food_name": "Flour"},
        "salt": {"food_id": "s", "food_name": "Salt"},
        "water": {"food_id": None, "skipped": 1},
    }
    foods = {"e": {"servings": EGG}, "f": {"servings": FLOUR}, "s": {"servings": FLOUR}}
    out = recipe_nutrition(ingredients, matches, foods, servings=4)
    assert [ln["status"] for ln in out["lines"]] == ["ok", "ok", "no_amount", "skipped", "unmatched"]
    assert out["total"]["calories"] == pytest.approx(189 + 227.5)
    assert out["per_serving"]["calories"] == pytest.approx((189 + 227.5) / 4)
    assert out["needs_attention"] == 1
    assert recipe_nutrition(ingredients, matches, foods, servings=None)["per_serving"] is None


def test_pick_best_prefers_generic_and_overlap():
    results = [
        {"food_id": "1", "name": "Flour Tortilla", "brand": None},
        {"food_id": "2", "name": "All Purpose Flour", "brand": "Gold Medal"},
        {"food_id": "3", "name": "White Flour", "brand": None},
    ]
    assert pick_best(results, "flour")["food_id"] == "3"
    assert pick_best([], "flour") is None


def test_ingredient_key():
    assert ingredient_key("  Large  Eggs!") == "large eggs"
