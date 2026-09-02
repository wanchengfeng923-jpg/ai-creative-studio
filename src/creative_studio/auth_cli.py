"""One-time account bootstrap commands."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .auth import AuthDataError, AuthService
from .repository import StudioDataError, StudioRepository


def default_database_path() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "creative_studio.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="creative-studio-auth")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init-admin", help="create the first administrator")
    init.add_argument("--username", required=True)
    init.add_argument("--password-stdin", action="store_true", required=True)
    init.add_argument("--database", type=Path, default=default_database_path())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        print("password is required", file=sys.stderr)
        return 2
    try:
        repository = StudioRepository(args.database)
        if repository.list_users():
            print("database is already initialized", file=sys.stderr)
            return 2
        user = AuthService(repository).init_admin(args.username, password)
    except (AuthDataError, StudioDataError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"created administrator: {user['username']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
