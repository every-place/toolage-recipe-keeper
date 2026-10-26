from recipekeeper.shopping import aisle_for, as_text, build_list


def line(name, qty, unit, title="Cookies", mult=1, raw=None):
    return {"name": name, "quantity": qty, "unit": unit, "recipe_title": title, "multiplier": mult,
            "raw_text": raw or name}


def items(data):
    return {i["key"]: i for g in data["aisles"] for i in g["items"]}


def test_combines_across_recipes_and_units():
    data = build_list([
        line("flour", 0.5, "cup"), line("flour", 2, "cup", title="Bread"),
        line("butter", 2, "tbsp"), line("butter", 1, "stick", title="Bread"),
        line("eggs", 3, None), line("eggs", 2, None, title="Bread", mult=2),
        line("milk", 1, "quart"), line("milk", 1, "cup", title="Bread"),
        line("chocolate", 4, "oz"), line("chocolate", 1, "lb", title="Bread"),
        line("salt", None, None),
    ], staples=set(), checks={})
    it = items(data)
    assert it["flour"]["amount"] == "2 1/2 cups"
    assert it["flour"]["recipes"] == ["Cookies", "Bread"]
    assert it["butter"]["amount"] == "1 stick + 2 tbsp"
    assert it["eggs"]["amount"] == "7"
    assert it["milk"]["amount"] == "5 cups"
    assert it["chocolate"]["amount"] == "1 1/4 lb"
    assert it["salt"]["amount"] == ""


def test_staples_and_checks():
    data = build_list([line("salt", 1, "tsp"), line("flour", 1, "cup"), line("sugar", 1, "cup")],
                      staples={"salt", "sugar"}, checks={"sugar": "need", "flour": "got"})
    it = items(data)
    assert (it["salt"]["state"], it["flour"]["state"], it["sugar"]["state"]) == ("have", "got", "need")
    assert data["counts"] == {"need": 1, "got": 1, "have": 1}
    text = as_text(data, "Christmas baking")
    assert "[ ] sugar, 1 cup" in text and "salt" not in text and "flour" not in text


def test_aisles():
    assert aisle_for("powdered sugar") == "Baking"
    assert aisle_for("large eggs") == "Dairy and eggs"
    assert aisle_for("black pepper") == "Spices"
    assert aisle_for("red bell pepper") == "Produce"
    assert aisle_for("cornstarch") == "Baking"
    assert aisle_for("ground cinnamon") == "Spices"
    assert aisle_for("unicorn dust") == "Other"


def test_odd_volumes_read_like_a_cook_would():
    data = build_list([line("butter", 2, "cup"), line("butter", 3, "tbsp", title="Pancakes"),
                       line("blueberries", 1, "cup")], staples=set(), checks={})
    it = items(data)
    assert it["butter"]["amount"] == "2 cups + 3 tbsp"
    assert it["blueberries"]["aisle"] == "Produce"


def test_big_volumes_stay_in_cups():
    it = items(build_list([line("flour", 6.5, "cup")], staples=set(), checks={}))
    assert it["flour"]["amount"] == "6 1/2 cups"
