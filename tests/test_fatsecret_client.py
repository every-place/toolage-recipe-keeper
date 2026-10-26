"""Offline tests for the FatSecret client: requests.post is replaced with fakes."""
from unittest.mock import patch

import pytest
import requests

from recipekeeper.fatsecret import FatSecretClient, FatSecretError


class FakeResp:
    def __init__(self, status=200, json_data=None, text=""):
        self.status_code = status
        self._json = json_data or {}
        self.text = text or str(json_data)

    def json(self):
        return self._json


TOKEN = FakeResp(json_data={"access_token": "tok", "expires_in": 86400})


def client():
    return FatSecretClient("id", "secret", scope="basic")


def test_search_handles_single_result_as_dict():
    one = {"foods": {"food": {"food_id": "1", "food_name": "Egg", "food_description": "Per 1 large"}}}
    with patch("recipekeeper.fatsecret.requests.post", side_effect=[TOKEN, FakeResp(json_data=one)]):
        results = client().search_foods("egg")
    assert results == [{"food_id": "1", "name": "Egg", "brand": None, "summary": "Per 1 large"}]


def test_search_with_no_results():
    empty = {"foods": {"max_results": "20", "total_results": "0", "page_number": "0"}}
    with patch("recipekeeper.fatsecret.requests.post", side_effect=[TOKEN, FakeResp(json_data=empty)]):
        assert client().search_foods("zzzz") == []


def test_get_food_parses_servings():
    food = {"food": {"food_id": "33691", "food_name": "Chicken Breast", "servings": {"serving": [
        {"serving_id": "1", "serving_description": "100 g", "metric_serving_amount": "100.000",
         "metric_serving_unit": "g", "calories": "165", "protein": "31.02", "carbohydrate": "0",
         "fat": "3.57", "sodium": "74"},
        {"serving_id": "2", "serving_description": "1 oz", "calories": "47", "protein": "8.8",
         "carbohydrate": "0", "fat": "1.01"},
    ]}}}
    with patch("recipekeeper.fatsecret.requests.post", side_effect=[TOKEN, FakeResp(json_data=food)]):
        result = client().get_food("33691")
    assert [s["description"] for s in result["servings"]] == ["100 g", "1 oz"]
    assert result["servings"][0]["protein_g"] == pytest.approx(31.02)
    assert result["servings"][1]["sodium_mg"] is None  # missing stays missing, not 0


def test_token_is_reused():
    ok = {"foods": {}}
    with patch("recipekeeper.fatsecret.requests.post", side_effect=[TOKEN, FakeResp(json_data=ok), FakeResp(json_data=ok)]) as post:
        c = client()
        c.search_foods("a")
        c.search_foods("b")
    assert post.call_count == 3  # one token request, two searches


def test_expired_token_is_refreshed_once():
    expired = {"error": {"code": 14, "message": "Expired token"}}
    ok = {"foods": {}}
    with patch("recipekeeper.fatsecret.requests.post",
               side_effect=[TOKEN, FakeResp(json_data=expired), TOKEN, FakeResp(json_data=ok)]):
        assert client().search_foods("a") == []


def test_ip_error_is_reported():
    bad_ip = {"error": {"code": 21, "message": "Invalid IP address detected: '1.2.3.4'"}}
    with patch("recipekeeper.fatsecret.requests.post", side_effect=[TOKEN, FakeResp(json_data=bad_ip)]):
        with pytest.raises(FatSecretError, match="IP"):
            client().search_foods("a")


def test_network_failure_becomes_fatsecret_error():
    with patch("recipekeeper.fatsecret.requests.post", side_effect=requests.ConnectionError("offline")):
        with pytest.raises(FatSecretError, match="Could not reach"):
            client().search_foods("a")


def test_bad_credentials():
    with patch("recipekeeper.fatsecret.requests.post", return_value=FakeResp(401, text="invalid_client")):
        with pytest.raises(FatSecretError, match="Token request failed"):
            client().search_foods("a")
