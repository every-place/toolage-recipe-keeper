"""Check that your FatSecret keys and IP whitelist work.

    python -m scripts.check_fatsecret

Talks to the real FatSecret API (the tests in tests/ never do).
"""
from recipekeeper.fatsecret import FatSecretClient, FatSecretError
from recipekeeper.nutrition import amount_multiplier, pick_best


def main():
    try:
        c = FatSecretClient()
        results = c.search_foods("all purpose flour", max_results=5)
        best = pick_best(results, "flour")
        print(f"Search OK. Best match for 'flour': {best['name'] if best else 'none'}")
        if best:
            food = c.get_food(best["food_id"])
            found = amount_multiplier(0.5, "cup", food["servings"])
            if found:
                serving, mult = found
                print(f"1/2 cup flour = {serving['calories'] * mult:.0f} calories (from '{serving['description']}')")
        print("All good: FatSecret is connected.")
    except RuntimeError as e:
        print(f"Setup problem: {e}")
    except FatSecretError as e:
        print(f"FatSecret problem: {e}")
        if "IP" in str(e):
            print("Add this server's IP address in the FatSecret dashboard, or set FATSECRET_PROXY_URL.")


if __name__ == "__main__":
    main()
