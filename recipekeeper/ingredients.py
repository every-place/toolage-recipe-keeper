"""Turn an ingredient line, typed the way it's written on a recipe card,
into amount, unit, ingredient name and note.

    "1/2 cup flour (sifted)"   -> 0.5, "cup", "flour", "sifted"
    "2 tsp butter, melted"     -> 2, "tsp", "butter", "melted"
    "1 (8 oz) pkg cream cheese" -> 1, "package (8 oz)", "cream cheese", None
    "salt to taste"            -> None, None, "salt", "to taste"

Anything the parser can't make sense of is kept as the name, and the
original text is always stored too, so nothing typed is ever lost.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

# Canonical unit -> spellings people use. Matching is case-insensitive except
# for the single letters "T" (tablespoon) and "t" (teaspoon).
UNIT_ALIASES: dict[str, list[str]] = {
    "cup": ["cups", "cup", "c"],
    "tbsp": ["tablespoons", "tablespoon", "tbsp", "tbs", "tbl", "tb"],
    "tsp": ["teaspoons", "teaspoon", "tsp", "ts"],
    "fl oz": ["fluid ounces", "fluid ounce", "fl oz", "fl. oz"],
    "oz": ["ounces", "ounce", "oz"],
    "lb": ["pounds", "pound", "lbs", "lb"],
    "g": ["grams", "gram", "g"],
    "kg": ["kilograms", "kilogram", "kg"],
    "ml": ["milliliters", "millilitres", "milliliter", "millilitre", "ml"],
    "l": ["liters", "litres", "liter", "litre", "l"],
    "pint": ["pints", "pint", "pt"],
    "quart": ["quarts", "quart", "qt"],
    "gallon": ["gallons", "gallon", "gal"],
    "stick": ["sticks", "stick"],
    "can": ["cans", "can"],
    "jar": ["jars", "jar"],
    "package": ["packages", "package", "pkgs", "pkg", "packets", "packet", "envelopes", "envelope"],
    "box": ["boxes", "box"],
    "bag": ["bags", "bag"],
    "pinch": ["pinches", "pinch"],
    "dash": ["dashes", "dash"],
    "drop": ["drops", "drop"],
    "clove": ["cloves", "clove"],
    "slice": ["slices", "slice"],
    "piece": ["pieces", "piece"],
    "bunch": ["bunches", "bunch"],
    "head": ["heads", "head"],
    "sprig": ["sprigs", "sprig"],
    "handful": ["handfuls", "handful"],
    "square": ["squares", "square"],  # baking chocolate
}

CASE_SENSITIVE_UNITS = {"T": "tbsp", "t": "tsp"}

# Longest spellings first so "fl oz" wins over "oz" and "tablespoons" over "t".
_ALIAS_TO_UNIT = sorted(
    ((alias, unit) for unit, aliases in UNIT_ALIASES.items() for alias in aliases),
    key=lambda pair: -len(pair[0]),
)

UNICODE_FRACTIONS = {
    "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75, "⅕": 0.2, "⅖": 0.4,
    "⅗": 0.6, "⅘": 0.8, "⅙": 1 / 6, "⅚": 5 / 6, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}

WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12, "half": 0.5, "a half": 0.5, "dozen": 12,
}

TRAILING_NOTES = ("to taste", "as needed", "for garnish", "optional", "or to taste", "for dusting", "for serving")

_NUM = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+(?:\s*[½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])?|[½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])"
_QTY_RE = re.compile(rf"^\s*(?P<q1>{_NUM})(?:\s*(?:-|–|to)\s*(?P<q2>{_NUM}))?\s*")
_SIZE_RE = re.compile(r"^\((?P<size>[^)]*)\)\s*")


@dataclass
class ParsedIngredient:
    raw_text: str
    quantity: float | None = None
    quantity_max: float | None = None
    unit: str | None = None
    name: str | None = None
    note: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def parse_number(text: str) -> float | None:
    """'1 1/2' -> 1.5, '1/2' -> 0.5, '½' -> 0.5, '1½' -> 1.5, '0.25' -> 0.25."""
    text = text.strip()
    if not text:
        return None
    total = 0.0
    for ch, value in UNICODE_FRACTIONS.items():
        if ch in text:
            total += value
            text = text.replace(ch, "").strip()
    for part in text.split():
        if "/" in part:
            num, _, den = part.partition("/")
            try:
                if float(den) == 0:
                    return None
                total += float(num) / float(den)
            except ValueError:
                return None
        else:
            try:
                total += float(part)
            except ValueError:
                return None
    return total


def _match_unit(text: str) -> tuple[str | None, str]:
    """If text starts with a unit, return (unit, rest)."""
    m = re.match(r"^([A-Za-z]+\.?)(?=[\s(,]|$)", text)
    if m and m.group(1).rstrip(".") in CASE_SENSITIVE_UNITS:
        return CASE_SENSITIVE_UNITS[m.group(1).rstrip(".")], text[m.end():]
    lower = text.lower()
    for alias, unit in _ALIAS_TO_UNIT:
        if lower.startswith(alias):
            after = text[len(alias):]
            if after.startswith("."):
                after = after[1:]
            # The alias must end at a word boundary: "can" not "candied"
            if after == "" or after[0] in " ,(":
                return unit, after
    return None, text


def _split_note(name: str) -> tuple[str, str | None]:
    """Pull a preparation note off the name: after a comma, or in parentheses."""
    notes = []
    # "(sifted)" anywhere, including "flour(sifted)"
    for m in re.finditer(r"\(([^)]*)\)", name):
        notes.append(m.group(1).strip())
    name = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
    if "," in name:
        name, _, rest = name.partition(",")
        notes.insert(0, rest.strip())
    lowered = name.lower()
    for phrase in TRAILING_NOTES:
        if lowered.endswith(" " + phrase):
            name = name[: -len(phrase)].strip()
            notes.append(phrase)
            break
    note = ", ".join(n for n in notes if n) or None
    return name.strip(" ,"), note


def parse_ingredient(line: str) -> ParsedIngredient:
    raw = line.strip()
    result = ParsedIngredient(raw_text=raw)
    if not raw:
        return result
    rest = raw.lstrip("-•* \t")

    m = _QTY_RE.match(rest)
    if m and m.group("q1"):
        result.quantity = parse_number(m.group("q1"))
        if m.group("q2"):
            result.quantity_max = parse_number(m.group("q2"))
        rest = rest[m.end():]
    else:
        wm = re.match(r"^(a half|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|half)\s+", rest, re.I)
        if wm:
            unit, after = _match_unit(rest[wm.end():])
            word = wm.group(1).lower()
            # "a pinch of salt" yes; "a few apples" and "an apple" no unit needed
            if unit or word not in ("a", "an"):
                result.quantity = float(WORD_NUMBERS[word])
                rest = rest[wm.end():]

    # "1 (8 oz) package cream cheese"
    size = None
    sm = _SIZE_RE.match(rest)
    if sm and result.quantity is not None:
        size = sm.group("size").strip()
        rest = rest[sm.end():]

    if result.quantity is not None or size:
        unit, rest = _match_unit(rest.lstrip())
        if unit:
            result.unit = unit
        rest = rest.lstrip()
        if rest.lower().startswith("of "):
            rest = rest[3:]
    if size:
        result.unit = f"{result.unit} ({size})" if result.unit else f"({size})"

    name, note = _split_note(rest)
    result.name = name or None
    result.note = note
    return result


def is_group_header(line: str) -> str | None:
    """'For the frosting:' -> 'For the frosting'."""
    s = line.strip()
    if s.endswith(":") and len(s) > 1 and not _QTY_RE.match(s):
        return s[:-1].strip()
    return None


def parse_lines(text: str) -> list[dict]:
    """Parse a block of ingredient lines. Group headers set group_label for the lines after them."""
    out = []
    group = None
    for line in text.splitlines():
        if not line.strip():
            continue
        header = is_group_header(line)
        if header:
            group = header
            continue
        item = parse_ingredient(line).to_dict()
        item["group_label"] = group
        out.append(item)
    return out


_NICE_FRACTIONS = [(1 / 8, "1/8"), (1 / 4, "1/4"), (1 / 3, "1/3"), (3 / 8, "3/8"), (1 / 2, "1/2"),
                   (5 / 8, "5/8"), (2 / 3, "2/3"), (3 / 4, "3/4"), (7 / 8, "7/8")]


def format_quantity(value: float | None) -> str:
    """1.5 -> '1 1/2', 0.333 -> '1/3', 2.0 -> '2', 0.4 -> '0.4'."""
    if value is None:
        return ""
    whole = int(value)
    frac = value - whole
    if frac < 0.02:
        return str(whole)
    if frac > 0.98:
        return str(whole + 1)
    for target, label in _NICE_FRACTIONS:
        if abs(frac - target) < 0.02:
            return f"{whole} {label}" if whole else label
    return f"{value:.2f}".rstrip("0").rstrip(".")
