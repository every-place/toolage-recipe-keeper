import io

from PIL import Image
from sqlalchemy import create_engine, inspect, select, text

from recipekeeper import storage
from recipekeeper.db import get_engine
from recipekeeper.models import photos
from tests.conftest import signup


class FakeR2:
    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.down = False

    def put(self, key, data, content_type):
        if self.down:
            raise storage.StorageError("down")
        self.files[key] = data

    def get(self, key):
        if self.down:
            raise storage.StorageError("down")
        return self.files[key]

    def delete(self, key):
        self.files.pop(key, None)


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 100, 50)).save(buf, "PNG")
    return buf.getvalue()


def _db_row(tmp_path, photo_id):
    with get_engine(f"sqlite:///{tmp_path / 'test.db'}").connect() as conn:
        return conn.execute(select(photos).where(photos.c.id == photo_id)).mappings().one()


def test_photos_go_to_r2_when_configured(client, tmp_path):
    fake = FakeR2()
    storage.set_backend(fake)
    signup(client)
    photo = client.post("/api/photos", files={"file": ("c.png", _png(), "image/png")}).json()

    row = _db_row(tmp_path, photo["id"])
    assert row["data"] == b""
    assert row["storage_key"].startswith("households/")
    assert fake.files[row["storage_key"]][:2] == b"\xff\xd8"  # a JPEG

    got = client.get(f"/api/photos/{photo['id']}")
    assert got.status_code == 200
    assert got.content == fake.files[row["storage_key"]]

    # Other households still can't see it
    client.post("/api/auth/logout")
    signup(client, email="stranger@example.com", name="Stranger")
    assert client.get(f"/api/photos/{photo['id']}").status_code == 404


def test_r2_outage_is_a_friendly_error(client):
    fake = FakeR2()
    storage.set_backend(fake)
    signup(client)
    photo = client.post("/api/photos", files={"file": ("c.png", _png(), "image/png")}).json()
    fake.down = True
    assert client.get(f"/api/photos/{photo['id']}").status_code == 503
    assert client.post("/api/photos", files={"file": ("c.png", _png(), "image/png")}).status_code == 503


def test_database_photos_still_work_after_turning_r2_on(client, tmp_path):
    signup(client)
    old = client.post("/api/photos", files={"file": ("c.png", _png(), "image/png")}).json()
    assert _db_row(tmp_path, old["id"])["storage_key"] is None
    storage.set_backend(FakeR2())
    assert client.get(f"/api/photos/{old['id']}").status_code == 200


def test_move_script(client, tmp_path, monkeypatch):
    signup(client)
    old = client.post("/api/photos", files={"file": ("c.png", _png(), "image/png")}).json()
    before = client.get(f"/api/photos/{old['id']}").content
    fake = FakeR2()
    storage.set_backend(fake)
    from scripts import move_photos_to_r2
    assert move_photos_to_r2.main() == 0
    row = _db_row(tmp_path, old["id"])
    assert row["data"] == b"" and fake.files[row["storage_key"]] == before
    assert client.get(f"/api/photos/{old['id']}").content == before
    assert move_photos_to_r2.main() == 0  # nothing left; doesn't duplicate
    assert len(fake.files) == 1


def test_old_database_gets_storage_key_column(tmp_path):
    url = f"sqlite:///{tmp_path / 'old.db'}"
    eng = create_engine(url)
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE photos (id INTEGER PRIMARY KEY, household_id INTEGER, "
                          "content_type VARCHAR(40) NOT NULL, width INTEGER, height INTEGER, "
                          "data BLOB NOT NULL, created_at VARCHAR(20) NOT NULL)"))
    eng.dispose()
    cols = {c["name"] for c in inspect(get_engine(url)).get_columns("photos")}
    assert "storage_key" in cols
