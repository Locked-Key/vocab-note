# vocab-note — 영단어 학습 노트

0단계 개발 준비 상태입니다.

## 구조 (코드/데이터 분리)

```text
src/vocab_note/   # 코드
data/             # 데이터 (vocab.db, git 미커밋)
tests/            # 테스트
```

## 시작 (Windows PowerShell)

```powershell
# 1) 가상환경 (이미 .venv 생성됨)
.\.venv\Scripts\Activate.ps1

# 2) 설치
pip install -r requirements.txt

# 3) 실행
python -m vocab_note init   # DB 생성
python -m vocab_note info   # DB 상태 확인

# 4) 테스트
pytest -q
```

## 배운 내용 체크 (0단계)

- [x] Git 저장소 (`git init`)
- [x] 가상환경 (`.venv`)
- [x] 기본 프로젝트 실행 (`python -m vocab_note init`)
- [x] 코드/데이터 분리 (`src/` vs `data/`, `.gitignore`)
- [x] VS Code 디버거 (`.vscode/launch.json` → F5)
