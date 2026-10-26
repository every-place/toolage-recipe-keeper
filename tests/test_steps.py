from recipekeeper.steps import detect_timer_minutes, template_list


def test_timer_minutes():
    assert detect_timer_minutes("Bake at 350°F for 10-12 minutes, or until golden") == 10
    assert detect_timer_minutes("Let rise about 1 hour") == 60
    assert detect_timer_minutes("Preheat oven to 350°F.") is None


def test_timer_skips_storage_and_per_side():
    assert detect_timer_minutes("Store for up to 5 days") is None
    assert detect_timer_minutes("Fry 3 minutes per side") is None


def test_templates_include_custom():
    out = template_list([{"id": 4, "grp": "Mine", "text": "Sprinkle with love."}])
    assert out[-1] == {"id": 4, "group": "Mine", "text": "Sprinkle with love.", "custom": True}
    assert any("Preheat oven" in t["text"] for t in out)
