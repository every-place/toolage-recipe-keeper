import pytest

from recipekeeper.ingredients import format_quantity, parse_ingredient, parse_lines, parse_number


def p(line):
    r = parse_ingredient(line)
    return r.quantity, r.unit, r.name, r.note


@pytest.mark.parametrize("line,expected", [
    ("3 eggs", (3, None, "eggs", None)),
    ("1/2 cup flour(sifted)", (0.5, "cup", "flour", "sifted")),
    ("1/2 cup flour (sifted)", (0.5, "cup", "flour", "sifted")),
    ("2 tsp butter(melted)", (2, "tsp", "butter", "melted")),
    ("2 tsp butter, melted", (2, "tsp", "butter", "melted")),
    ("1 1/2 cups sugar", (1.5, "cup", "sugar", None)),
    ("1½ cups sugar", (1.5, "cup", "sugar", None)),
    ("½ tsp salt", (0.5, "tsp", "salt", None)),
    ("1 T vanilla", (1, "tbsp", "vanilla", None)),
    ("1 t vanilla", (1, "tsp", "vanilla", None)),
    ("2 Tbsp. cocoa", (2, "tbsp", "cocoa", None)),
    ("1 cup of milk", (1, "cup", "milk", None)),
    ("2 large eggs, beaten", (2, None, "large eggs", "beaten")),
    ("salt to taste", (None, None, "salt", "to taste")),
    ("a pinch of nutmeg", (1, "pinch", "nutmeg", None)),
    ("2 sticks butter, softened", (2, "stick", "butter", "softened")),
    ("1 can sweetened condensed milk", (1, "can", "sweetened condensed milk", None)),
    ("1 cup candied pecans", (1, "cup", "candied pecans", None)),
    ("8 oz cream cheese", (8, "oz", "cream cheese", None)),
    ("1 c. brown sugar, packed", (1, "cup", "brown sugar", "packed")),
    ("Powdered sugar for dusting", (None, None, "Powdered sugar", "for dusting")),
    ("an apple", (None, None, "an apple", None)),
])
def test_parse(line, expected):
    q, unit, name, note = p(line)
    assert (q if q is None else pytest.approx(q), unit, name, note) == (
        expected[0] if expected[0] is None else pytest.approx(expected[0]), *expected[1:])


def test_package_size():
    r = parse_ingredient("1 (8 oz) pkg cream cheese, softened")
    assert (r.quantity, r.unit, r.name, r.note) == (1, "package (8 oz)", "cream cheese", "softened")


def test_range():
    r = parse_ingredient("2-3 cups flour")
    assert (r.quantity, r.quantity_max, r.unit) == (2, 3, "cup")


def test_raw_text_kept():
    assert parse_ingredient("  a little love  ").raw_text == "a little love"


def test_groups():
    lines = parse_lines("2 cups flour\n\nFor the frosting:\n1 cup powdered sugar\n2 T milk")
    assert [l["group_label"] for l in lines] == [None, "For the frosting", "For the frosting"]


@pytest.mark.parametrize("text,value", [("1/2", 0.5), ("1 1/2", 1.5), ("¾", 0.75), ("2½", 2.5), ("1/0", None)])
def test_parse_number(text, value):
    assert parse_number(text) == (value if value is None else pytest.approx(value))


@pytest.mark.parametrize("value,text", [(1.5, "1 1/2"), (1 / 3, "1/3"), (2.0, "2"), (0.4, "0.4"), (2.99, "3")])
def test_format_quantity(value, text):
    assert format_quantity(value) == text
