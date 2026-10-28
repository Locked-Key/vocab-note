"""9단계: 데이터 백업/복원 서비스.

- 백업: vocab.db + settings.json을 타임스탬프가 붙은 zip 파일로 data/backups/에 저장
  (.env는 비밀키가 있어 제외)
- 복원: 지정된 zip 파일을 풀어 vocab.db를 덮어씀 (확인 필수)
"""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR

BACKUP_DIR = DATA_DIR / "backups"


class BackupError(Exception):
    pass


def create_backup(
    backup_dir: Path | None = None,
    db_path: Path | None = None,
    settings_path: Path | None = None,
) -> Path:
    """vocab.db + settings.json을 zip으로 백업. 생성된 zip 경로를 반환."""
    from .config import DB_PATH, SETTINGS_PATH  # from service module

    bdir = backup_dir or BACKUP_DIR
    db = db_path or DB_PATH
    settings = settings_path or (DATA_DIR / "settings.json")
    bdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    zip_path = bdir / f"vocab-backup-{ts}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        if db.exists():
            zf.write(db, "vocab.db")
        if settings.exists():
            zf.write(settings, "settings.json")
    return zip_path


def list_backups(backup_dir: Path | None = None) -> list[tuple[Path, str, int]]:
    """(경로, 파일명, 크기) 내림차순."""
    bdir = backup_dir or BACKUP_DIR
    if not bdir.exists():
        return []
    files = sorted(bdir.glob("vocab-backup-*.zip"), reverse=True)
    return [(f, f.name, f.stat().st_size) for f in files]


def restore_backup(
    zip_path: Path,
    db_path: Path | None = None,
    settings_path: Path | None = None,
) -> None:
    """지정된 zip에서 vocab.db와 settings.json을 복원 (덮어쓰기)."""
    from .config import DB_PATH

    db = db_path or DB_PATH
    settings = settings_path or (DATA_DIR / "settings.json")
    if not zip_path.exists():
        raise BackupError(f"백업 파일이 없습니다: {zip_path}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if "vocab.db" in names:
            db.parent.mkdir(parents=True, exist_ok=True)
            # 복원 전 현재 DB를 임시 백업
            if db.exists():
                shutil.copy2(db, db.with_suffix(".db.bak"))
            with zf.open("vocab.db") as src, open(db, "wb") as dst:
                shutil.copyfileobj(src, dst)
        if "settings.json" in names:
            with zf.open("settings.json") as src, open(settings, "wb") as dst:
                shutil.copyfileobj(src, dst)