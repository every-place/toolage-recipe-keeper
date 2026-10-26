"""FatSecret Platform API client (OAuth 2.0, client credentials).

Gets an app-level token, caches it until shortly before it expires,
and wraps the two calls we need first: food search and food details.
"""
import time

import requests

from . import config

TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
API_URL = "https://platform.fatsecret.com/rest/server.api"
# Error codes FatSecret uses for an invalid or expired access token.
TOKEN_ERROR_CODES = {"13", "14"}


class FatSecretError(Exception):
    pass


def _as_list(value):
    """FatSecret returns a dict when there is one item and a list when many."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class FatSecretClient:
    def __init__(self, client_id=None, client_secret=None, scope=None, proxy=None):
        if client_id is None or client_secret is None:
            client_id, client_secret = config.fatsecret_credentials()
        scope = scope or config.fatsecret_scope()
        proxy = proxy or config.fatsecret_proxy()
        # FatSecret only answers whitelisted IP addresses. On hosts whose IP changes
        # (like Streamlit Cloud), route calls through a fixed-IP proxy.
        self._proxies = {"http": proxy, "https": proxy} if proxy else None
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._token = None
        self._token_expires = 0.0

    # ---------- auth ----------
    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        resp = self._post(
            TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": self._scope},
            auth=(self._client_id, self._client_secret),
        )
        if resp.status_code != 200:
            raise FatSecretError(
                f"Token request failed ({resp.status_code}): {resp.text[:300]}"
            )
        data = resp.json()
        self._token = data["access_token"]
        self._token_expires = time.time() + int(data.get("expires_in", 3600))
        return self._token

    def _post(self, url, **kwargs):
        """POST with a timeout, turning network failures into FatSecretError."""
        try:
            return requests.post(url, timeout=15, proxies=self._proxies, **kwargs)
        except requests.RequestException as e:
            raise FatSecretError(f"Could not reach FatSecret: {e}") from e

    def _call(self, method: str, **params) -> dict:
        for attempt in (1, 2):
            resp = self._post(
                API_URL,
                headers={"Authorization": f"Bearer {self._get_token()}"},
                data={"method": method, "format": "json", **params},
            )
            if resp.status_code == 401 and attempt == 1:
                self._token = None  # token rejected: fetch a fresh one and retry once
                continue
            if resp.status_code != 200:
                raise FatSecretError(f"{method} failed ({resp.status_code}): {resp.text[:300]}")
            data = resp.json()
            # FatSecret reports errors (bad IP, bad scope...) inside a 200 response
            if "error" in data:
                err = data["error"]
                if str(err.get("code")) in TOKEN_ERROR_CODES and attempt == 1:
                    self._token = None
                    continue
                raise FatSecretError(f"FatSecret error {err.get('code')}: {err.get('message')}")
            return data
        raise FatSecretError(f"{method} failed after refreshing the access token")

    # ---------- endpoints ----------
    def search_foods(self, query: str, max_results: int = 20, page: int = 0) -> list[dict]:
        data = self._call(
            "foods.search",
            search_expression=query,
            max_results=max_results,
            page_number=page,
        )
        foods = _as_list(data.get("foods", {}).get("food"))
        return [
            {
                "food_id": f.get("food_id"),
                "name": f.get("food_name"),
                "brand": f.get("brand_name"),
                "summary": f.get("food_description"),  # e.g. "Per 100g - Calories: ..."
            }
            for f in foods
        ]

    def get_food(self, food_id: str) -> dict:
        # If FatSecret ever retires this version, check their docs for the
        # current food.get version and change the method name here only.
        data = self._call("food.get.v2", food_id=food_id)
        food = data.get("food", {})
        servings = []
        for s in _as_list(food.get("servings", {}).get("serving")):
            servings.append(
                {
                    "serving_id": s.get("serving_id"),
                    "description": s.get("serving_description"),
                    "metric_amount": _num(s.get("metric_serving_amount")),
                    "metric_unit": s.get("metric_serving_unit"),
                    "calories": _num(s.get("calories")) or 0.0,
                    "protein_g": _num(s.get("protein")) or 0.0,
                    "carbs_g": _num(s.get("carbohydrate")) or 0.0,
                    "fat_g": _num(s.get("fat")) or 0.0,
                    "fiber_g": _num(s.get("fiber")),
                    "sugar_g": _num(s.get("sugar")),
                    "sodium_mg": _num(s.get("sodium")),
                }
            )
        return {
            "food_id": food.get("food_id"),
            "name": food.get("food_name"),
            "brand": food.get("brand_name"),
            "servings": servings,
        }
