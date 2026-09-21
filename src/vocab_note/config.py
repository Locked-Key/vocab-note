"""경로 설정: 코드(src)와 데이터(data) 분리.

- 코드: src/vocab_note/
- 데이터: data/ (DB 파일, 백업 — git에 커밋하지 않음)
"""

from pathlib import Path

# src/vocab_note/config.py -> parents[2] = 프로젝트 루트
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "vocab.db"
