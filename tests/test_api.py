import io

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
