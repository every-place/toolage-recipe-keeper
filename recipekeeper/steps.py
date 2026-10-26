"""Instruction helpers: the built-in sentence templates and timer detection.

Templates use {slots} that the editor turns into tap-to-fill blanks:
    "Bake at {temp} for {time}, or until {doneness}."
"""
from __future__ import annotations

import re

# (group, template). Order within a group is the order they're offered.
BUILT_IN_TEMPLATES: list[tuple[str, str]] = [
    ("Prep", "Preheat oven to {temp}."),
    ("Prep", "Grease and flour a {pan}."),
    ("Prep", "Line a {pan} with parchment paper."),
    ("Prep", "Bring {ingredients} to room temperature."),
    ("Prep", "Sift together {ingredients} and set aside."),
    ("Mixing", "In a large bowl, whisk together {ingredients}."),
    ("Mixing", "In a separate bowl, combine {ingredients}."),
    ("Mixing", "Cream {ingredients} until light and fluffy, about {time}."),
    ("Mixing", "Beat in {ingredient}, one at a time."),
    ("Mixing", "Add the dry ingredients to the wet ingredients and stir until just combined."),
    ("Mixing", "Fold in {ingredient}."),
    ("Mixing", "Stir in {ingredient}."),
    ("Mixing", "Whip {ingredient} until {doneness}."),
    ("Dough", "Knead for {time} until smooth and elastic."),
    ("Dough", "Cover and let rise in a warm place until doubled, about {time}."),
    ("Dough", "Cover and chill the dough for {time}."),
    ("Dough", "Roll out to {thickness} thick."),
    ("Dough", "Cut into {shape} and place on {pan}."),
    ("Dough", "Drop by rounded {size} onto {pan}, {spacing} apart."),
    ("Cooking", "Pour into the prepared {pan}."),
    ("Cooking", "Bake at {temp} for {time}, or until {doneness}."),
    ("Cooking", "Bake for {time}, or until {doneness}."),
    ("Cooking", "Bring to a boil, then reduce heat and simmer for {time}."),
    ("Cooking", "Melt {ingredient} in a saucepan over {heat} heat."),
    ("Cooking", "Cook over {heat} heat, stirring constantly, until {doneness}."),
    ("Cooking", "Fry until golden brown, about {time} per side."),
    ("Finishing", "Cool in the pan for {time}, then turn out onto a wire rack."),
    ("Finishing", "Let cool completely before frosting."),
    ("Finishing", "Dust with {ingredient}."),
    ("Finishing", "Store in an airtight container for up to {time}."),
    ("Finishing", "Serve warm."),
]

# Suggestions shown for each slot when it's tapped.
SLOT_SUGGESTIONS: dict[str, list[str]] = {
    "temp": ["325°F", "350°F", "375°F", "400°F", "425°F", "450°F"],
    "time": ["5 minutes", "10 minutes", "12 minutes", "15 minutes", "20 minutes", "25 minutes",
             "30 minutes", "45 minutes", "1 hour", "overnight"],
    "pan": ["9x13-inch pan", "8-inch square pan", "9-inch round cake pan", "loaf pan",
            "muffin tin", "baking sheet", "pie plate", "Bundt pan"],
    "doneness": [
        "golden brown",
        "a toothpick inserted in the center comes out clean",
        "the edges are set",
        "the top springs back when lightly touched",
        "bubbly",
        "thickened",
        "stiff peaks form",
        "soft peaks form",
        "tender when pierced with a fork",
        "the internal temperature reaches 165°F",
    ],
    "heat": ["low", "medium-low", "medium", "medium-high", "high"],
    "thickness": ["1/8 inch", "1/4 inch", "1/2 inch"],
    "size": ["teaspoonfuls", "tablespoonfuls"],
    "spacing": ["1 inch", "2 inches"],
    "shape": ["shapes with cookie cutters", "squares", "strips", "rounds"],
}

DONENESS_PHRASES = SLOT_SUGGESTIONS["doneness"]

_TIME_RE = re.compile(
    r"(?P<n>\d+(?:\.\d+)?)(?:\s*(?:-|–|to)\s*(?P<m>\d+(?:\.\d+)?))?\s*"
    r"(?P<unit>hours?|hrs?|minutes?|mins?)\b",
    re.IGNORECASE,
)


def detect_timer_minutes(text: str) -> float | None:
    """'Bake for 10-12 minutes' -> 10; 'let rise 1 hour' -> 60. First time mentioned wins.

    "per side" and "up to" times are skipped: they aren't a single countdown.
    """
    for m in _TIME_RE.finditer(text):
        before = text[max(0, m.start() - 6): m.start()].lower()
        after = text[m.end(): m.end() + 9].lower()
        if "up to" in before or after.strip().startswith("per side"):
            continue
        minutes = float(m.group("n"))
        if m.group("unit").lower().startswith("h"):
            minutes *= 60
        return minutes
    return None


def template_list(custom: list[dict] | None = None) -> list[dict]:
    """Built-ins plus a household's own, as {group, text, custom}."""
    out = [{"group": g, "text": t, "custom": False} for g, t in BUILT_IN_TEMPLATES]
    for c in custom or []:
        out.append({"id": c["id"], "group": c["grp"], "text": c["text"], "custom": True})
    return out
