"""Move photos that are still stored in the database into Cloudflare R2.

The server runs this every time it starts (see the Dockerfile), so turning R2 on
moves existing photos by itself. Safe to run again: photos already in R2 are skipped.
To run it by hand, with the same DATABASE_URL and R2_* settings as the server:

    python -m scripts.move_photos_to_r2
"""
import sys

from sqlalchemy import select, update

from recipekeeper import storage
from recipekeeper.db import get_engine
from recipekeeper.models import photos


def main() -> int:
    store = storage.backend()
    if store is None:
        print("Photos are kept in the database (R2 isn't set up).")
        return 0
    engine = get_engine()
    with engine.connect() as conn:
        todo = list(conn.execute(
            select(photos.c.id, photos.c.household_id).where(photos.c.storage_key.is_(None))
        ))
    moved = 0
    for photo_id, household_id in todo:
        with engine.begin() as conn:  # one photo at a time, so a failure keeps what's done
            data, content_type = conn.execute(
                select(photos.c.data, photos.c.content_type).where(photos.c.id == photo_id)
            ).one()
            key = storage.new_key(household_id)
            store.put(key, data, content_type)
            conn.execute(update(photos).where(photos.c.id == photo_id).values(storage_key=key, data=b""))
        moved += 1
    if moved:
        print(f"Moved {moved} photo(s) to R2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
