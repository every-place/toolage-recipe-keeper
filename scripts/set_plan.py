"""Move a household to the free or premium plan (until billing is built).

    python -m scripts.set_plan kristen@example.com premium
"""
import sys

from recipekeeper import repository as repo
from recipekeeper.db import get_engine


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in ("free", "premium"):
        print(__doc__)
        return 1
    email, plan = argv
    with get_engine().begin() as conn:
        user = repo.user_by_email(conn, email)
        if user is None:
            print(f"No account with the email {email}.")
            return 1
        repo.set_plan(conn, user["household_id"], plan)
        name = repo.household(conn, user["household_id"])["name"]
    print(f"{name} is now on the {plan} plan.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
