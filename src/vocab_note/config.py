"""경로 설정: 코드(src)와 데이터(data) 분리.

- 개발 시: data/ 디렉터리 (프로젝트 루트 아래)
- exe 배포 시: exe 옆 data/ 디렉터리 (USB·이동식으로도 관리 가능)
"""

import sys
from pathlib import Path

_frozen = getattr(sys, "frozen", False)

if _frozen:
    # PyInstaller exe: exe 파일이 있는 디렉터리에 data/ 생성
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    # 개발 환경: src/vocab_note/config.py → parents[2] = 프로젝트 루트
    BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "vocab.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
ENV_PATH = BASE_DIR / ".env"
