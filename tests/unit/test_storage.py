import os
import threading

import pytest

from server import storage


@pytest.fixture(autouse=True)
def setup_storage_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KAYENDAR_DATA_DIR", str(tmp_path))
    storage.set_data_dir(str(tmp_path))


def test_create_and_list_collections():
    meta = storage.create_collection("alice", "Personal", "calendar", slug="personal")
    assert meta.slug == "personal"
    assert meta.display_name == "Personal"
    assert meta.collection_type == "calendar"

    cols = storage.list_collections("alice")
    assert len(cols) == 1
    assert cols[0].slug == "personal"


def test_create_collection_unique_slug():
    storage.create_collection("alice", "Work", "calendar", slug="work")
    second = storage.create_collection("alice", "Work", "calendar", slug="work")
    assert second.slug == "work-1"


def test_collection_crud():
    storage.create_collection("alice", "Personal", "calendar", slug="personal")
    storage.create_collection("alice", "Work", "calendar", slug="work")

    cols = storage.list_collections("alice")
    assert {c.slug for c in cols} == {"personal", "work"}

    updated = storage.update_collection("alice", "personal", display_name="My Calendar")
    assert updated is not None
    assert updated.display_name == "My Calendar"

    assert storage.delete_collection("alice", "personal") is True
    assert storage.delete_collection("alice", "personal") is False
    assert {c.slug for c in storage.list_collections("alice")} == {"work"}


def test_invalid_slug_rejected():
    with pytest.raises(ValueError):
        storage.get_collection("alice", "../etc")
    with pytest.raises(ValueError):
        storage.put_item("alice", "bad slug!", "event.ics", "content")


def test_items_crud():
    storage.create_collection("bob", "Friends", "addressbook", slug="friends")

    content = "BEGIN:VCARD\nFN:John Doe\nEND:VCARD"
    item = storage.put_item("bob", "friends", "john.vcf", content)
    assert item.filename == "john.vcf"
    assert item.content == content
    assert item.etag

    fetched = storage.get_item("bob", "friends", "john.vcf")
    assert fetched is not None
    assert fetched.content == content

    items = storage.list_items("bob", "friends")
    assert len(items) == 1
    assert items[0].filename == "john.vcf"

    updated = storage.put_item("bob", "friends", "john.vcf", "BEGIN:VCARD\nFN:Jane\nEND:VCARD")
    assert "Jane" in updated.content

    assert storage.delete_item("bob", "friends", "john.vcf") is True
    assert storage.delete_item("bob", "friends", "john.vcf") is False
    assert storage.get_item("bob", "friends", "john.vcf") is None


def test_put_item_missing_collection():
    with pytest.raises(FileNotFoundError):
        storage.put_item("alice", "missing", "event.ics", "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:test\nEND:VEVENT\nEND:VCALENDAR")


def test_invalid_filename_rejected():
    storage.create_collection("alice", "Personal", "calendar", slug="personal")
    with pytest.raises(ValueError):
        storage.put_item("alice", "personal", "../event.ics", "content")
    with pytest.raises(ValueError):
        storage.put_item("alice", "personal", "event.txt", "content")


def test_list_items_skips_non_conforming_files(tmp_path):
    storage.create_collection("grace", "Personal", "calendar", slug="personal")
    storage.put_item("grace", "personal", "valid.ics", "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:test\nEND:VEVENT\nEND:VCALENDAR")

    col_dir = tmp_path / "collections" / "grace" / "personal"
    (col_dir / "README.txt").write_text("notes", encoding="utf-8")
    (col_dir / "corrupt.ics").write_bytes(b"\xff\xfe\xfd")

    items = storage.list_items("grace", "personal")
    assert len(items) == 1
    assert items[0].filename == "valid.ics"


def test_atomic_writes(monkeypatch):
    storage.create_collection("atomic", "Personal", "calendar", slug="personal")
    original_replace = os.replace
    replace_calls = []

    def mock_replace(src, dst):
        if dst.endswith(".meta.json"):
            original_replace(src, dst)
            return
        assert dst.endswith("test.ics")
        assert ".tmp" in src
        with open(src, encoding="utf-8") as f:
            assert f.read() == "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:test\nEND:VEVENT\nEND:VCALENDAR"
        replace_calls.append((src, dst))
        original_replace(src, dst)

    monkeypatch.setattr(os, "replace", mock_replace)
    storage.put_item("atomic", "personal", "test.ics", "BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:test\nEND:VEVENT\nEND:VCALENDAR")
    assert len(replace_calls) == 1


def test_concurrent_writes():
    storage.create_collection("thread_user", "Friends", "addressbook", slug="friends")
    errors = []

    def worker(idx):
        try:
            storage.put_item(
                "thread_user",
                "friends",
                f"contact_{idx}.vcf",
                f"BEGIN:VCARD\nFN:Contact {idx}\nEND:VCARD",
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert len(storage.list_items("thread_user", "friends")) == 20


def test_ensure_default_collections():
    storage.ensure_default_collections("newuser")
    cols = storage.list_collections("newuser")
    assert {c.slug for c in cols} == {"personal", "contacts"}
    assert {c.collection_type for c in cols} == {"calendar", "addressbook"}

    storage.ensure_default_collections("newuser")
    assert len(storage.list_collections("newuser")) == 2


def test_delete_user_data(tmp_path):
    storage.create_collection("gone", "Personal", "calendar", slug="personal")
    user_dir = tmp_path / "collections" / "gone"
    assert user_dir.is_dir()

    storage.delete_user_data("gone")
    assert not user_dir.exists()


def test_collection_share_lifecycle():
    storage.create_collection("alice", "Personal", "calendar", slug="personal")
    assert storage.get_collection_share("alice", "personal") is None

    share = storage.create_collection_share("alice", "personal")
    assert share is not None
    assert "token" in share
    token = share["token"]
    assert len(token) >= 20

    # Verify lookup by token
    found = storage.get_share_by_token(token)
    assert found is not None
    assert found["username"] == "alice"
    assert found["slug"] == "personal"

    # Revoke share
    revoked = storage.revoke_collection_share("alice", "personal")
    assert revoked is True
    assert storage.get_collection_share("alice", "personal") is None
    assert storage.get_share_by_token(token) is None


def test_export_and_import_collection():
    storage.create_collection("alice", "Personal", "calendar", slug="personal")
    storage.create_collection("bob", "Work", "calendar", slug="work")

    ev1 = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:ev-1\r\nSUMMARY:Meeting 1\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ev2 = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:ev-2\r\nSUMMARY:Meeting 2\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    storage.put_item("alice", "personal", "ev-1.ics", ev1)
    storage.put_item("alice", "personal", "ev-2.ics", ev2)

    # Export alice's collection
    exported = storage.export_collection_ics("alice", "personal")
    assert "BEGIN:VCALENDAR" in exported
    assert "Meeting 1" in exported
    assert "Meeting 2" in exported
    assert exported.count("BEGIN:VEVENT") == 2

    # Import into bob's collection
    count = storage.import_collection_ics("bob", "work", exported)
    assert count == 2
    bob_items = storage.list_items("bob", "work")
    assert len(bob_items) == 2
    assert {i.filename for i in bob_items} == {"ev-1.ics", "ev-2.ics"}

