import shutil
import zipfile
from pathlib import Path

from vocab_note.backup_service import (
    BackupError,
    create_backup,
    list_backups,
    restore_backup,
)
from vocab_note.config import DB_PATH  # needed for the config mock path


def test_create_backup_zip_has_db(tmp_path):
    db = tmp_path / "vocab.db"
    db.write_text("fake db")
    zip_p = create_backup(backup_dir=tmp_path, db_path=db, settings_path=tmp_path / "nonexistent.json")
    assert zip_p.exists() and zip_p.suffix == ".zip"
    with zipfile.ZipFile(zip_p, "r") as zf:
        assert "vocab.db" in zf.namelist()


def test_list_and_restore(tmp_path):
    db = tmp_path / "vocab.db"
    db.write_bytes(b"original")
    settings = tmp_path / "settings.json"
    settings.write_text('{"a":1}')
    zip_p = create_backup(backup_dir=tmp_path, db_path=db, settings_path=settings)
    files = list_backups(backup_dir=tmp_path)
    assert len(files) == 1 and files[0][0] == zip_p

    # 새 DB를 덮어쓰는 복원
    db.write_bytes(b"modified")
    restore_backup(zip_p, db_path=db, settings_path=settings)
    assert db.read_bytes() == b"original"
    assert db.with_suffix(".db.bak").read_bytes() == b"modified"
    assert settings.read_text() == '{"a":1}'


def test_restore_missing_zip_raises(tmp_path):
    try:
        restore_backup(tmp_path / "no.zip", db_path=tmp_path / "db")
        assert False, "should have raised"
    except BackupError:
        pass


def test_empty_backup_list(tmp_path):
    assert list_backups(backup_dir=tmp_path) == []