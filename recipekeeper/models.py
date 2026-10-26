"""Database tables for Recipe Keeper.

Design rules (chosen so the app can be sold to many families):
  * A household is the paying customer. Every recipe, photo and template
    belongs to one household, and every query is filtered by it.
  * A household's `plan` ('free' or 'premium') gates paid features such as
    FatSecret nutrition, whose cost is per use.
  * Timestamps are UTC ISO-8601 text ("2026-10-26T17:30:00Z").
  * Ingredient lines keep the text exactly as typed, next to the parsed
    amount / unit / name / note, so nothing typed is ever lost.

The same definitions create the tables in SQLite (on your computer) and in
Postgres (online).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()


def now_utc_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _id():
    return Column("id", Integer, primary_key=True)


def _household_fk():
    return Column(
        "household_id", Integer, ForeignKey("households.id", ondelete="CASCADE"), nullable=False, index=True
    )


households = Table(
    "households", metadata, _id(),
    Column("name", String(120), nullable=False),
    Column("plan", String(20), nullable=False, default="free", server_default="free"),
    # Family members join with this code
    Column("join_code", String(16), nullable=False, unique=True),
    Column("created_at", String(20), nullable=False, default=now_utc_text),
    CheckConstraint("plan IN ('free','premium')", name="ck_households_plan"),
)

users = Table(
    "users", metadata, _id(), _household_fk(),
    Column("email", String(320), nullable=False, unique=True),
    Column("display_name", String(120), nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("created_at", String(20), nullable=False, default=now_utc_text),
)

recipes = Table(
    "recipes", metadata, _id(), _household_fk(),
    Column("created_by", Integer, ForeignKey("users.id", ondelete="SET NULL")),
    Column("title", String(200), nullable=False),
    Column("source_person", String(120)),  # "Grandma Ruth"
    Column("recipe_yield", String(80)),  # "3 dozen cookies"
    Column("servings", Float),
    Column("prep_minutes", Integer),
    Column("cook_minutes", Integer),
    Column("category", String(60)),
    Column("tags", Text),  # comma separated
    Column("story", Text),
    Column("story_year", String(20)),
    Column("notes", Text),
    Column("hero_photo_id", Integer),
    Column("card_photo_id", Integer),  # photo of the original handwritten card
    Column("created_at", String(20), nullable=False, default=now_utc_text),
    Column("updated_at", String(20), nullable=False, default=now_utc_text),
)

recipe_ingredients = Table(
    "recipe_ingredients", metadata, _id(),
    Column("recipe_id", Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("group_label", String(80)),  # "For the frosting"
    Column("raw_text", Text, nullable=False),
    Column("quantity", Float),
    Column("quantity_max", Float),  # "2-3 cups"
    Column("unit", String(30)),
    Column("name", Text),
    Column("note", Text),
)

recipe_steps = Table(
    "recipe_steps", metadata, _id(),
    Column("recipe_id", Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("position", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("photo_id", Integer),
    Column("timer_minutes", Float),
)

photos = Table(
    "photos", metadata, _id(), _household_fk(),
    Column("content_type", String(40), nullable=False),
    Column("width", Integer),
    Column("height", Integer),
    Column("data", LargeBinary, nullable=False),
    Column("created_at", String(20), nullable=False, default=now_utc_text),
)

# A household's own sentence templates, on top of the built-in ones.
step_templates = Table(
    "step_templates", metadata, _id(), _household_fk(),
    Column("grp", String(40), nullable=False, default="Mine"),
    Column("text", Text, nullable=False),
    UniqueConstraint("household_id", "text", name="uq_templates_household_text"),
)
