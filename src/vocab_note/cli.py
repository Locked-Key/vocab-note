"""CLI 진입점. 2단계: 중복 경고 + 기존 단어에 뜻 추가 선택."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import DB_PATH
from .db import get_connection, init_db, list_tables
from .vocab_service import (
    DuplicateWordError,
    SenseNotFoundError,
    VocabError,
    WordNotFoundError,
    add_sense,
    add_word,
    delete_sense,
    delete_word,
    find_duplicate,
    get_word,
    get_word_by_spelling,
    update_sense,
    update_word_spelling,
)
from .tag_service import (
    TagError,
    get_or_create_tag,
    get_word_tags,
    list_tags,
    search_words,
    tag_word,
    untag_word,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vocab-note", description="영단어 학습 노트")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="data/vocab.db 생성 (테이블 초기화)")
    sub.add_parser("info", help="DB 경로와 테이블 목록 출력")

    a = sub.add_parser("add", help="단어 + 첫 뜻 등록 (중복이면 경고)")
    a.add_argument("spelling", help="영어 철자 (예: apple)")
    a.add_argument("--pos", default="", help="품사 (예: noun)")
    a.add_argument("--meaning", required=True, help="한국어 뜻 (예: 사과)")
    a.add_argument("--ex-en", default="", help="영어 예문")
    a.add_argument("--ex-ko", default="", help="예문 해석")
    a.add_argument(
        "--add-sense",
        action="store_true",
        help="중복이면 기존 단어에 다른 뜻으로 바로 추가",
    )

    li = sub.add_parser("list", help="단어 목록 (검색·태그필터·정렬)")
    li.add_argument("--search", default="", help="검색어 (철자·뜻 부분 일치)")
    li.add_argument("--tag", default="", help="태그 필터 (예: --tag 과일)")
    li.add_argument("--order", default="alpha", choices=["alpha", "recent"],
                    help="정렬 (기본: alpha)")

    s = sub.add_parser("show", help="단어 상세")
    s.add_argument("key", help="word id 또는 철자")

    m = sub.add_parser("add-sense", help="기존 단어에 다른 뜻 추가 (동음이의어)")
    m.add_argument("key", help="word id 또는 철자")
    m.add_argument("--pos", default="")
    m.add_argument("--meaning", required=True)
    m.add_argument("--ex-en", default="")
    m.add_argument("--ex-ko", default="")

    e = sub.add_parser("edit-sense", help="뜻 수정")
    e.add_argument("sense_id", type=int)
    e.add_argument("--pos")
    e.add_argument("--meaning")
    e.add_argument("--ex-en")
    e.add_argument("--ex-ko")

    d = sub.add_parser("del-sense", help="뜻 삭제")
    d.add_argument("sense_id", type=int)

    w = sub.add_parser("del-word", help="단어 삭제 (뜻도 함께 삭제)")
    w.add_argument("key", help="word id 또는 철자")
    w.add_argument("--yes", action="store_true", help="확인 없이 삭제")

    r = sub.add_parser("rename", help="철자 수정")
    r.add_argument("key", help="word id 또는 철자")
    r.add_argument("new_spelling", help="새 철자")

    t = sub.add_parser("tag", help="태그 만들기")
    t.add_argument("name", help="태그명 (예: 과일)")

    sub.add_parser("tags", help="태그 목록 (단어 수 포함)")

    tw = sub.add_parser("tag-word", help="단어에 태그 붙이기")
    tw.add_argument("key", help="word id 또는 철자")
    tw.add_argument("names", nargs="+", help="태그명 1개 이상")

    uw = sub.add_parser("untag-word", help="단어에서 태그 떼기")
    uw.add_argument("key", help="word id 또는 철자")
    uw.add_argument("name", help="태그명")

    sub.add_parser("gui", help="데스크톱 UI 실행 (PySide6)")
    return p


def _resolve_word(conn, key: str):
    """id(숫자) 또는 철자로 Word 조회."""
    if key.isdigit():
        return get_word(conn, int(key))
    word = get_word_by_spelling(conn, key)
    if word is None:
        raise WordNotFoundError(f"단어 없음: {key}")
    return word


def _print_word_detail(conn, key: str) -> None:
    word = _resolve_word(conn, key)
    tags = get_word_tags(conn, word.id)
    print(f"[{word.id}] {word.spelling}")
    if tags:
        print(f"  태그: {', '.join(t.name for t in tags)}")
    if not word.senses:
        print("  (뜻 없음 — add-sense로 추가)")
        return
    for s in word.senses:
        pos = f"({s.part_of_speech}) " if s.part_of_speech else ""
        print(f"  - sense {s.id}: {pos}{s.meaning_ko}")
        if s.example_en:
            print(f"      ex: {s.example_en}")
        if s.example_ko:
            print(f"          {s.example_ko}")


def _format_word_line(w) -> str:
    meanings = "; ".join(
        f"({s.part_of_speech}) {s.meaning_ko}" if s.part_of_speech else s.meaning_ko
        for s in w.senses
    ) or "(뜻 없음)"
    tags = f" #{' #'.join(t.name for t in w.tags)}" if w.tags else ""
    return f"[{w.id}] {w.spelling} — {meanings}{tags}"


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            path = init_db()
            print(f"DB init: {path}")
            print(f"tables: {', '.join(list_tables())}")
        elif args.command == "info":
            print(f"DB: {DB_PATH}")
            if DB_PATH.exists():
                print(f"tables: {', '.join(list_tables())}")
            else:
                print("No DB. Run `vocab-note init` first.")
        elif args.command == "add":
            conn = get_connection()
            try:
                # 2단계: 먼저 중복(대소문자·공백 무시)을 확인하고 경고
                existing = find_duplicate(conn, args.spelling)
                if existing is not None:
                    print(f"중복 경고: '{args.spelling.strip()}'은(는) 이미 등록됨")
                    _print_word_detail(conn, str(existing.id))
                    if args.add_sense:
                        sense = add_sense(
                            conn,
                            existing.id,
                            args.pos,
                            args.meaning,
                            args.ex_en,
                            args.ex_ko,
                        )
                        print(f"추가: [{existing.spelling}] sense {sense.id} ({sense.meaning_ko})")
                        return
                    if sys.stdin.isatty():
                        try:
                            ok = input("기존 단어에 다른 뜻으로 추가할까요? (y/N) ")
                        except EOFError:
                            ok = "n"
                        if ok.strip().lower() == "y":
                            sense = add_sense(
                                conn,
                                existing.id,
                                args.pos,
                                args.meaning,
                                args.ex_en,
                                args.ex_ko,
                            )
                            print(f"추가: [{existing.spelling}] sense {sense.id} ({sense.meaning_ko})")
                            return
                    print("취소됨. 다른 뜻이면 `--add-sense`를 붙이거나 `add-sense`를 쓰세요.")
                    print(f"예: vocab-note add {args.spelling.strip()} --meaning {args.meaning} --add-sense")
                    return
                try:
                    word = add_word(conn, args.spelling)
                except DuplicateWordError as e:  # 레이스 등 DB UNIQUE 충돌 시
                    print(f"중복: {e}")
                    return
                sense = add_sense(
                    conn, word.id, args.pos, args.meaning, args.ex_en, args.ex_ko
                )
                print(f"등록: [{word.id}] {word.spelling} / sense {sense.id}")
            finally:
                conn.close()
        elif args.command == "list":
            conn = get_connection()
            try:
                words = search_words(conn, args.search, args.tag, args.order)
                if not words:
                    print("(비어 있음)")
                    return
                for w in words:
                    print(_format_word_line(w))
            finally:
                conn.close()
        elif args.command == "show":
            conn = get_connection()
            try:
                _print_word_detail(conn, args.key)
            finally:
                conn.close()
        elif args.command == "add-sense":
            conn = get_connection()
            try:
                word = _resolve_word(conn, args.key)
                sense = add_sense(
                    conn, word.id, args.pos, args.meaning, args.ex_en, args.ex_ko
                )
                print(f"추가: [{word.spelling}] sense {sense.id} ({sense.meaning_ko})")
            finally:
                conn.close()
        elif args.command == "edit-sense":
            conn = get_connection()
            try:
                sense = update_sense(
                    conn,
                    args.sense_id,
                    part_of_speech=args.pos,
                    meaning_ko=args.meaning,
                    example_en=getattr(args, "ex_en"),
                    example_ko=getattr(args, "ex_ko"),
                )
                print(f"수정: sense {sense.id} ({sense.meaning_ko})")
            finally:
                conn.close()
        elif args.command == "del-sense":
            conn = get_connection()
            try:
                delete_sense(conn, args.sense_id)
                print(f"삭제: sense {args.sense_id}")
            finally:
                conn.close()
        elif args.command == "del-word":
            conn = get_connection()
            try:
                word = _resolve_word(conn, args.key)
                if not args.yes:
                    try:
                        ok = input(f"[{word.spelling}] + 뜻 {len(word.senses)}개 삭제? (y/N) ")
                    except EOFError:
                        ok = "n"
                    if ok.strip().lower() != "y":
                        print("취소")
                        return
                delete_word(conn, word.id)
                print(f"삭제: [{word.spelling}]")
            finally:
                conn.close()
        elif args.command == "rename":
            conn = get_connection()
            try:
                word = _resolve_word(conn, args.key)
                updated = update_word_spelling(conn, word.id, args.new_spelling)
                print(f"수정: {word.spelling} -> {updated.spelling}")
            finally:
                conn.close()
        elif args.command == "tag":
            conn = get_connection()
            try:
                tag = get_or_create_tag(conn, args.name)
                print(f"태그: [{tag.id}] {tag.name}")
            finally:
                conn.close()
        elif args.command == "tags":
            conn = get_connection()
            try:
                items = list_tags(conn)
                if not items:
                    print("(태그 없음)")
                    return
                for tag, count in items:
                    print(f"[{tag.id}] {tag.name} ({count})")
            finally:
                conn.close()
        elif args.command == "tag-word":
            conn = get_connection()
            try:
                word = _resolve_word(conn, args.key)
                for name in args.names:
                    tag = tag_word(conn, word.id, name)
                    print(f"태그 추가: [{word.spelling}] #{tag.name}")
            finally:
                conn.close()
        elif args.command == "untag-word":
            conn = get_connection()
            try:
                word = _resolve_word(conn, args.key)
                untag_word(conn, word.id, args.name)
                print(f"태그 제거: [{word.spelling}] #{args.name.strip()}")
            finally:
                conn.close()
        elif args.command == "gui":
            try:
                from .ui.app import run
            except ImportError:
                print("PySide6이 없습니다. `pip install -r requirements.txt`를 실행하세요.")
                return
            raise SystemExit(run())
    except (VocabError, WordNotFoundError, SenseNotFoundError, TagError) as e:
        print(f"오류: {e}")


if __name__ == "__main__":
    main()
