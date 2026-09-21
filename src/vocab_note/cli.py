"""CLI 진입점. 0단계: init / info 만 동작. 1단계에서 add/list 등을 붙입니다."""

from __future__ import annotations

import argparse

from . import __version__
from .config import DB_PATH
from .db import init_db, list_tables


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vocab-note", description="영단어 학습 노트")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="data/vocab.db 생성 (테이블 초기화)")
    sub.add_parser("info", help="DB 경로와 테이블 목록 출력")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "init":
        path = init_db()
        print(f"DB 초기화 완료: {path}")
        print(f"테이블: {', '.join(list_tables())}")
    elif args.command == "info":
        print(f"DB 경로: {DB_PATH}")
        if DB_PATH.exists():
            print(f"테이블: {', '.join(list_tables())}")
        else:
            print("DB 파일이 없습니다. `vocab-note init`을 먼저 실행하세요.")


if __name__ == "__main__":
    main()
