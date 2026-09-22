# vocab-note — 영단어 학습 노트

6단계 학습 기록 상태입니다.

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

# 태그·검색·정렬 (3단계: 다대다)
python -m vocab_note tag 과일
python -m vocab_note tag-word apple 과일
python -m vocab_note tags
python -m vocab_note list --tag 과일
python -m vocab_note list --search 사과
python -m vocab_note list --order recent
python -m vocab_note untag-word apple 과일

# 데스크톱 UI (4단계 + GUI 퀴즈)
python -m vocab_note gui
# 또는 VS Code에서 F5 → "Vocab GUI"
# 상단 [퀴즈] 버튼: 태그 범위·방향·문제 수 선택 → 객관식 풀이 → 결과

# 퀴즈 (5단계: 객관식, 풀이는 quiz_attempt에 저장)
python -m vocab_note quiz
python -m vocab_note quiz --tag 과일 --direction en_to_ko --num 5
python -m vocab_note quiz --direction ko_to_en

# 학습 기록 (6단계: quiz_attempt 집계)
python -m vocab_note stats
python -m vocab_note stats --days 7 --wrong 10 --recent 10

# 4) 테스트
pytest -q
```

## 명령어 레퍼런스 (전체 17개)

실행 전: `.\.venv\Scripts\Activate.ps1` / 명령별 도움말: `python -m vocab_note <명령> --help`

```powershell
# DB 관리
python -m vocab_note init     # data/vocab.db 생성
python -m vocab_note info     # DB 경로·테이블 확인

# 단어 CRUD
python -m vocab_note add apple --pos noun --meaning 사과 --ex-en "I eat an apple." --ex-ko "나는 사과를 먹는다."
python -m vocab_note add "  APPLE " --meaning 둑 --add-sense  # 중복이면 기존 단어에 뜻 추가
python -m vocab_note list
python -m vocab_note show apple        # id(숫자)도 가능: show 4
python -m vocab_note add-sense bank --pos noun --meaning 둑  # 동음이의어
python -m vocab_note edit-sense 1 --meaning 사과_과일
python -m vocab_note del-sense 3
python -m vocab_note rename apple apple2
python -m vocab_note del-word bank --yes  # --yes 없으면 확인 질문

# 태그·검색·정렬
python -m vocab_note tag 과일
python -m vocab_note tags                              # 태그 목록 (단어 수 포함)
python -m vocab_note tag-word apple 과일 토익          # 여러 개 한 번에
python -m vocab_note untag-word apple 토익
python -m vocab_note list --tag 과일 --search 바 --order recent
# --order: alpha(기본) / recent

# 퀴즈·학습 기록 (풀이는 quiz_attempt에 자동 저장, q 입력 시 종료)
python -m vocab_note quiz --tag 과일 --direction en_to_ko --num 10
# --direction: en_to_ko(영어 보고 뜻) / ko_to_en(뜻 보고 영어) / both(기본)
python -m vocab_note stats --days 7 --wrong 10 --recent 10

# 데스크톱 UI + 기타
python -m vocab_note gui        # 목록/상세/퀴즈/다크모드 (VS Code F5 → "Vocab GUI")
python -m vocab_note --version
```

## 데이터베이스 구조 (`data/vocab.db`, SQLite)

```mermaid
erDiagram
    word ||--o{ sense : "1:N 동음이의어"
    word ||--o{ word_tag : ""
    tag ||--o{ word_tag : "N:M"
    sense ||--o{ quiz_attempt : "풀이 기록"

    word {
        INTEGER id PK
        TEXT spelling
        TEXT normalized_spelling UK "소문자·공백 정리"
        TEXT created_at
    }
    sense {
        INTEGER id PK
        INTEGER word_id FK "CASCADE"
        TEXT part_of_speech
        TEXT meaning_ko
        TEXT example_en
        TEXT example_ko
    }
    tag {
        INTEGER id PK
        TEXT name UK
    }
    word_tag {
        INTEGER word_id PK_FK "CASCADE"
        INTEGER tag_id PK_FK "CASCADE"
    }
    quiz_attempt {
        INTEGER id PK
        INTEGER sense_id FK "CASCADE"
        TEXT direction "en_to_ko / ko_to_en"
        INTEGER is_correct "1 / 0"
        TEXT answered_at
    }
```

- 단어 삭제 → 뜻·연결·풀이 기록까지 `ON DELETE CASCADE`로 함께 삭제
- 인덱스: `idx_sense_word_id`, `idx_quiz_attempt_sense` (조인 속도용)
- 스키마 원본: `src/vocab_note/db.py`의 `SCHEMA`

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

## 배운 내용 체크 (3단계)

- [x] 다대다 관계 (`word_tag` 조인 테이블, `INSERT OR IGNORE`, `ON DELETE CASCADE`)
- [x] SQL 조인 (`JOIN word_tag/tag`, `LEFT JOIN` + `GROUP BY`로 태그별 개수)
- [x] 검색 조건 (철자·뜻 `LIKE`, 태그 필터 `COLLATE NOCASE`, `alpha/recent` 정렬)
- [x] 리스트/딕셔너리 (결과를 `Word(senses, tags)` 객체 리스트로 조립)

## 배운 내용 체크 (4단계)

- [x] PySide6 위젯 (`QListWidget/QLineEdit/QComboBox/QDialog`, `ui/` 패키지)
- [x] Signal/Slot (`textChanged/currentTextChanged/currentItemChanged/toggled`)
- [x] 레이아웃 (`QSplitter` 좌우 분할 + `QVBox/QHBox`)
- [x] UI-로직 분리 (화면은 서비스 함수만 호출, SQL 없음 — `test_ui_has_no_sql`)
- [x] 다크 모드 (체크박스 토글 + QSS, `ui/theme.py`)

## 배운 내용 체크 (5단계)

- [x] `random` (셔플·샘플·`seed` 재현 — `quiz_service.py`)
- [x] 상태 관리 (`QuizSession`: 현재 문제·점수·풀이 결과)
- [x] 단위 테스트 기초 (`seed` 고정으로 랜덤 로직 검증)
- [x] 문제 생성 로직의 UI 독립 (같은 서비스를 CLI·GUI가 공유)

## 배운 내용 체크 (6단계)

- [x] 날짜 처리 (`answered_at` UTC 문자열 → `substr` 일자 집계)
- [x] 집계 SQL (`COUNT/SUM/GROUP BY/HAVING` 역할의 파이썬 정렬)
- [x] 간단한 통계 (전체·방향별·일자별 정답률, 오답 많은 순, 최신순)
