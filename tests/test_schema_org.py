from recipekeeper.schema_org import iso_duration, to_schema_org


def test_iso_duration():
    assert iso_duration(95) == "PT1H35M"
    assert iso_duration(20) == "PT20M"
    assert iso_duration(None) is None


def test_to_schema_org():
    recipe = {"title": "Sugar cookies", "source_person": "Grandma", "prep_minutes": 20, "cook_minutes": 10,
              "tags": ["Christmas"], "story": "Every Christmas Eve.", "hero_photo_id": 7,
              "ingredients": [{"raw_text": "1 cup sugar"}], "steps": [{"text": "Mix.", "photo_id": None}]}
    out = to_schema_org(recipe, lambda pid: f"https://x/api/photos/{pid}")
    assert out["@type"] == "Recipe"
    assert out["totalTime"] == "PT30M"
    assert out["author"]["name"] == "Grandma"
    assert out["image"] == ["https://x/api/photos/7"]
    assert out["recipeInstructions"] == [{"@type": "HowToStep", "text": "Mix."}]
