import io
import pytest

from PIL import Image

from conftest import signup

RECIPE = {
    "title": "Grandma's sugar cookies",
    "source_person": "Grandma Ruth",
    "category": "Cookies",
    "tags": ["Christmas"],
    "story": "We made these every Christmas Eve.",
    "ingredients": [{"raw_text": "1/2 cup flour (sifted)"}, {"raw_text": "3 eggs"},
                    {"raw_text": "1 cup powdered sugar", "group_label": "For the frosting"}],
    "steps": [{"text": "Preheat oven to 350°F."}, {"text": "Bake for 10 minutes, or until golden brown."}],
}


def test_needs_login(client):
    assert client.get("/api/recipes").status_code == 401


def test_signup_login_logout(client):
    signup(client)
    me = client.get("/api/me").json()
    assert me["user"]["display_name"] == "Kristen"
    assert me["household"]["plan"] == "free"
    client.post("/api/auth/logout")
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "KRISTEN@example.com", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "KRISTEN@example.com", "password": "cookies-123"}).status_code == 200


def test_duplicate_email(client):
    signup(client)
    r = client.post("/api/auth/signup", json={"email": "kristen@example.com", "password": "cookies-123",
                                              "display_name": "K"})
    assert r.status_code == 400


def test_recipe_round_trip(client):
    signup(client)
    r = client.post("/api/recipes", json=RECIPE)
    assert r.status_code == 200, r.text
    recipe = r.json()
    flour = recipe["ingredients"][0]
    assert (flour["quantity"], flour["unit"], flour["name"], flour["note"]) == (0.5, "cup", "flour", "sifted")
    assert recipe["ingredients"][2]["group_label"] == "For the frosting"
    assert recipe["steps"][1]["timer_minutes"] == 10
    assert recipe["created_by_name"] == "Kristen"

    listing = client.get("/api/recipes", params={"q": "eggs"}).json()
    assert [x["title"] for x in listing["recipes"]] == ["Grandma's sugar cookies"]
    assert listing["categories"] == ["Cookies"]
    assert client.get("/api/recipes", params={"q": "lasagna"}).json()["recipes"] == []

    edited = dict(RECIPE, title="Sugar cookies", steps=[{"text": "Mix."}])
    assert client.put(f"/api/recipes/{recipe['id']}", json=edited).json()["title"] == "Sugar cookies"
    schema = client.get(f"/api/recipes/{recipe['id']}/schema.json").json()
    assert schema["recipeIngredient"][1] == "3 eggs"

    assert client.delete(f"/api/recipes/{recipe['id']}").status_code == 200
    assert client.get(f"/api/recipes/{recipe['id']}").status_code == 404


def test_title_required(client):
    signup(client)
    assert client.post("/api/recipes", json={"title": "  "}).status_code == 400


def test_households_are_separate(client):
    signup(client)
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    client.post("/api/auth/logout")
    signup(client, email="stranger@example.com", name="Stranger")
    assert client.get(f"/api/recipes/{rid}").status_code == 404
    assert client.get("/api/recipes").json()["recipes"] == []
    assert client.put(f"/api/recipes/{rid}", json=RECIPE).status_code == 404


def test_family_join_code(client):
    signup(client)
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    code = client.get("/api/me").json()["household"]["join_code"]
    client.post("/api/auth/logout")
    signup(client, email="sarah@example.com", name="Sarah", join_code=code.lower().replace("-", ""))
    assert client.get(f"/api/recipes/{rid}").status_code == 200
    members = client.get("/api/me").json()["household"]["members"]
    assert [m["display_name"] for m in members] == ["Kristen", "Sarah"]


def test_bad_join_code(client):
    r = client.post("/api/auth/signup", json={"email": "a@b.c", "password": "cookies-123",
                                              "display_name": "A", "join_code": "ZZZZ-ZZZZ"})
    assert r.status_code == 400


def _png(w=3000, h=2000):
    buf = io.BytesIO()
    Image.new("RGBA", (w, h), (200, 100, 50, 255)).save(buf, "PNG")
    return buf.getvalue()


def test_photos(client):
    signup(client)
    r = client.post("/api/photos", files={"file": ("cookie.png", _png(), "image/png")})
    assert r.status_code == 200, r.text
    photo = r.json()
    assert max(photo["width"], photo["height"]) == 1600
    got = client.get(f"/api/photos/{photo['id']}")
    assert got.headers["content-type"] == "image/jpeg"

    recipe = client.post("/api/recipes", json=dict(RECIPE, hero_photo_id=photo["id"])).json()
    assert recipe["hero_photo_id"] == photo["id"]

    assert client.post("/api/photos", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 400

    client.post("/api/auth/logout")
    signup(client, email="stranger@example.com", name="Stranger")
    assert client.get(f"/api/photos/{photo['id']}").status_code == 404
    # Can't attach someone else's photo to your recipe
    assert client.post("/api/recipes", json=dict(RECIPE, hero_photo_id=photo["id"])).status_code == 400


def test_templates(client):
    signup(client)
    data = client.get("/api/templates").json()
    assert "doneness" in data["slots"]
    tid = client.post("/api/templates", json={"text": "Sprinkle with colored sugar."}).json()["id"]
    texts = [t["text"] for t in client.get("/api/templates").json()["templates"]]
    assert "Sprinkle with colored sugar." in texts
    assert client.delete(f"/api/templates/{tid}").status_code == 200


def test_parse_endpoint(client):
    signup(client)
    lines = client.post("/api/ingredients/parse", json={"text": "3 eggs\n2 tsp butter(melted)"}).json()["lines"]
    assert lines[1]["note"] == "melted"


def test_export(client):
    signup(client)
    client.post("/api/recipes", json=RECIPE)
    r = client.get("/api/export")
    assert r.json()[0]["name"] == "Grandma's sugar cookies"


# ---------- nutrition ----------
class FakeFatSecret:
    def __init__(self):
        self.calls = []
        self.foods = {
            "1": {"food_id": "1", "name": "Egg", "brand": None,
                  "servings": [{"description": "1 large", "metric_amount": 50.0, "metric_unit": "g",
                                "calories": 72.0, "protein_g": 6.3, "carbs_g": 0.4, "fat_g": 4.8}]},
            "2": {"food_id": "2", "name": "White Flour", "brand": None,
                  "servings": [{"description": "1 cup", "metric_amount": 125.0, "metric_unit": "g",
                                "calories": 455.0, "protein_g": 12.9, "carbs_g": 95.4, "fat_g": 1.2}]},
            "3": {"food_id": "3", "name": "Powdered Sugar", "brand": None,
                  "servings": [{"description": "1 cup", "metric_amount": 120.0, "metric_unit": "g",
                                "calories": 467.0, "carbs_g": 120.0}]},
            "4": {"food_id": "4", "name": "Butter", "brand": None,
                  "servings": [{"description": "1 tbsp", "metric_amount": 14.2, "metric_unit": "g",
                                "calories": 102.0, "fat_g": 11.5}]},
        }

    def search_foods(self, query, max_results=20, page=0):
        self.calls.append(("search", query))
        by_word = {"eggs": "1", "flour": "2", "powdered sugar": "3", "butter": "4"}
        fid = by_word.get(query)
        return [{"food_id": fid, "name": self.foods[fid]["name"], "brand": None, "summary": ""}] if fid else []

    def get_food(self, food_id):
        self.calls.append(("get", food_id))
        return self.foods[food_id]


def _premium(client, monkeypatch):
    from recipekeeper import nutrition_service, repository
    from recipekeeper.db import get_engine
    monkeypatch.setenv("FATSECRET_CLIENT_ID", "id")
    monkeypatch.setenv("FATSECRET_CLIENT_SECRET", "secret")
    fake = FakeFatSecret()
    nutrition_service.set_client(fake)
    hid = client.get("/api/me").json()["household"]["id"]
    with get_engine().begin() as conn:
        repository.set_plan(conn, hid, "premium")
    return fake


def test_nutrition_is_premium_only(client, monkeypatch):
    signup(client)
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    r = client.get(f"/api/recipes/{rid}/nutrition")
    assert r.status_code == 402
    assert "Premium" in r.json()["detail"]


def test_nutrition_match_and_choose(client, monkeypatch):
    signup(client)
    fake = _premium(client, monkeypatch)
    rid = client.post("/api/recipes", json=dict(RECIPE, servings=4)).json()["id"]

    before = client.get(f"/api/recipes/{rid}/nutrition").json()
    assert before["counted"] == 0 and fake.calls == []  # reading never calls FatSecret

    out = client.post(f"/api/recipes/{rid}/nutrition/match").json()
    assert out["counted"] == 3  # eggs, flour, powdered sugar
    assert out["total"]["calories"] == pytest.approx(3 * 72 + 455 / 2 + 467)
    assert out["per_serving"]["calories"] == pytest.approx(out["total"]["calories"] / 4)

    # Matching again costs no API calls: everything is remembered
    n = len(fake.calls)
    client.post(f"/api/recipes/{rid}/nutrition/match")
    assert len(fake.calls) == n

    # Change "flour" to butter (silly, but proves the choice sticks), then skip eggs
    assert client.put("/api/nutrition/match", json={"name": "flour", "food_id": "4"}).status_code == 200
    assert client.put("/api/nutrition/match", json={"name": "eggs", "skip": True}).status_code == 200
    lines = {ln["name"]: ln for ln in client.get(f"/api/recipes/{rid}/nutrition").json()["lines"]}
    assert lines["flour"]["food_name"] == "Butter"
    assert lines["eggs"]["status"] == "skipped"

    assert client.get("/api/nutrition/search", params={"q": "butter"}).json()["results"][0]["name"] == "Butter"


def test_nutrition_service_down(client, monkeypatch):
    from recipekeeper.fatsecret import FatSecretError
    signup(client)
    fake = _premium(client, monkeypatch)

    def boom(*a, **k):
        raise FatSecretError("Invalid IP address")
    fake.search_foods = boom
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    r = client.post(f"/api/recipes/{rid}/nutrition/match")
    assert r.status_code == 502


def test_me_reports_plan(client, monkeypatch):
    signup(client)
    _premium(client, monkeypatch)
    assert client.get("/api/me").json()["household"]["plan"] == "premium"


def test_lines_without_amount_cost_no_calls(client, monkeypatch):
    signup(client)
    fake = _premium(client, monkeypatch)
    rid = client.post("/api/recipes", json=dict(RECIPE, ingredients=[{"raw_text": "salt to taste"}])).json()["id"]
    out = client.post(f"/api/recipes/{rid}/nutrition/match").json()
    assert fake.calls == []
    assert out["lines"][0]["status"] == "no_amount" and out["needs_attention"] == 0


# ---------- menus and shopping ----------
def test_menu_and_shopping_list(client):
    signup(client)
    r1 = client.post("/api/recipes", json=RECIPE).json()["id"]
    r2 = client.post("/api/recipes", json=dict(RECIPE, title="Pancakes", ingredients=[
        {"raw_text": "1 1/2 cups flour"}, {"raw_text": "2 eggs"}, {"raw_text": "salt to taste"}])).json()["id"]
    menu = client.post("/api/menus", json={"name": "Christmas baking"}).json()
    mid = menu["id"]
    client.put(f"/api/menus/{mid}/recipes/{r1}", json={"multiplier": 2})
    assert len(client.put(f"/api/menus/{mid}/recipes/{r2}", json={"multiplier": 1}).json()["recipes"]) == 2
    assert client.get("/api/menus").json()["menus"][0]["recipe_count"] == 2

    shop = client.get(f"/api/menus/{mid}/shopping").json()
    it = {i["key"]: i for g in shop["aisles"] for i in g["items"]}
    assert it["flour"]["amount"] == "2 1/2 cups"  # 1/2 cup x2 + 1 1/2 cups
    assert it["eggs"]["amount"] == "8"  # 3 x2 + 2
    assert "Christmas baking" in shop["text"]

    client.put("/api/staples", json={"name": "Salt", "on": True})
    shop = client.put(f"/api/menus/{mid}/shopping", json={"key": "eggs", "state": "got"}).json()
    it = {i["key"]: i for g in shop["aisles"] for i in g["items"]}
    assert it["salt"]["state"] == "have" and it["eggs"]["state"] == "got"
    shop = client.post(f"/api/menus/{mid}/shopping/reset").json()
    assert {i["key"]: i for g in shop["aisles"] for i in g["items"]}["eggs"]["state"] == "need"

    client.put(f"/api/menus/{mid}/recipes/{r2}", json={"multiplier": 0})
    assert [r["title"] for r in client.get(f"/api/menus/{mid}").json()["recipes"]] == [RECIPE["title"]]
    assert client.delete(f"/api/menus/{mid}").status_code == 200


def test_menus_are_private(client):
    signup(client)
    rid = client.post("/api/recipes", json=RECIPE).json()["id"]
    mid = client.post("/api/menus", json={"name": "Mine"}).json()["id"]
    client.post("/api/auth/logout")
    signup(client, email="stranger@example.com", name="Stranger")
    assert client.get(f"/api/menus/{mid}").status_code == 404
    assert client.get(f"/api/menus/{mid}/shopping").status_code == 404
    own = client.post("/api/menus", json={"name": "Theirs"}).json()["id"]
    assert client.put(f"/api/menus/{own}/recipes/{rid}", json={"multiplier": 1}).status_code == 404
