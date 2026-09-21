# vocab-note — 영단어 학습 노트

2단계 중복 검사 상태입니다.

## 구조 (코드/데이터 분리)

```text
src/vocab_note/   # 코드 (cli.py=UI, vocab_service.py=데이터 로직, db.py=연결)
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

# 단어 CRUD (1단계)
python -m vocab_note add apple --pos noun --meaning 사과 --ex-en "I eat an apple." --ex-ko "나는 사과를 먹는다."
python -m vocab_note list
python -m vocab_note show apple
python -m vocab_note add-sense bank --pos noun --meaning 둑
python -m vocab_note edit-sense 1 --meaning 사과_과일
python -m vocab_note rename apple apple2
python -m vocab_note del-sense 3
python -m vocab_note del-word bank --yes

# 중복 검사 (2단계: 대소문자·공백 무시)
python -m vocab_note add apple --pos noun --meaning 사과
python -m vocab_note add "  APPLE " --pos noun --meaning 둑
# → 중복 경고 + 기존 뜻 출력 + 대화형 선택 (y면 뜻으로 추가)
python -m vocab_note add "  APPLE " --pos noun --meaning 둑 --add-sense
# → 바로 기존 단어에 뜻 추가 (단어 행은 1개 유지)

# 4) 테스트
pytest -q
```

## 배운 내용 체크 (0단계)

- [x] Git 저장소 (`git init`)
- [x] 가상환경 (`.venv`)
- [x] 기본 프로젝트 실행 (`python -m vocab_note init`)
- [x] 코드/데이터 분리 (`src/` vs `data/`, `.gitignore`)
- [x] VS Code 디버거 (`.vscode/launch.json` → F5)

## 배운 내용 체크 (1단계)

- [x] Word/Sense 분리 → 동음이의어 (`bank=은행/둑`) 지원
- [x] Python 클래스 (`models.py`의 `@dataclass`), 함수, 예외 (`VocabError/DuplicateWordError/...`)
- [x] SQLite 기초 (`INSERT/SELECT/UPDATE/DELETE`, `ON DELETE CASCADE`)
- [x] UI/로직 분리 (`cli.py`는 출력만, `vocab_service.py`는 DB 로직만)

## 배운 내용 체크 (2단계)

- [x] `normalized_spelling` (소문자·공백 정리) + `UNIQUE`로 중복 방지
- [x] 문자열 처리 (`strip/lower/정규식 공백 정리` → `normalize_spelling`)
- [x] 데이터 검증 (빈 철자·빈 뜻 거부 → `VocabError`)
- [x] 중복 UX (경고 + 기존 뜻 표시 + `--add-sense`/대화형 선택)
