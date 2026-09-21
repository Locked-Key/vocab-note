"""CLI 진입점. 1단계: Word/Sense CRUD."""

from __future__ import annotations

import argparse

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
    get_word,
    get_word_by_spelling,
    list_words,
    update_sense,
    update_word_spelling,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vocab-note", description="영단어 학습 노트")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="data/vocab.db 생성 (테이블 초기화)")
    sub.add_parser("info", help="DB 경로와 테이블 목록 출력")

    a = sub.add_parser("add", help="단어 + 첫 뜻 등록")
    a.add_argument("spelling", help="영어 철자 (예: apple)")
    a.add_argument("--pos", default="", help="품사 (예: noun)")
    a.add_argument("--meaning", required=True, help="한국어 뜻 (예: 사과)")
    a.add_argument("--ex-en", default="", help="영어 예문")
    a.add_argument("--ex-ko", default="", help="예문 해석")

    sub.add_parser("list", help="단어 목록 (뜻 포함)")

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
    print(f"[{word.id}] {word.spelling}")
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
                try:
                    word = add_word(conn, args.spelling)
                except DuplicateWordError as e:
                    print(f"중복: {e}")
                    print("다른 뜻이면 `add-sense`로 추가하세요.")
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
                words = list_words(conn)
                if not words:
                    print("(비어 있음)")
                    return
                for w in words:
                    meanings = "; ".join(
                        f"({s.part_of_speech}) {s.meaning_ko}" if s.part_of_speech
                        else s.meaning_ko
                        for s in w.senses
                    ) or "(뜻 없음)"
                    print(f"[{w.id}] {w.spelling} — {meanings}")
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
                    ok = input(f"[{word.spelling}] + 뜻 {len(word.senses)}개 삭제? (y/N) ")
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
    except (VocabError, WordNotFoundError, SenseNotFoundError) as e:
        print(f"오류: {e}")


if __name__ == "__main__":
    main()
