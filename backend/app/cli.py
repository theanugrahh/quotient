from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.database import SessionLocal, engine
from app.models import Base, User, UserRole
from app.security import hash_password, password_problems


def create_admin(email: str, password: str, name: str) -> int:
    Base.metadata.create_all(bind=engine)
    problems = password_problems(password)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 1

    normalized = email.strip().lower()
    with SessionLocal() as db:
        existing = db.execute(select(User).where(User.email == normalized)).scalar_one_or_none()
        if existing is not None:
            existing.role = UserRole.ADMIN
            existing.is_active = True
            db.commit()
            print(f"promoted existing account {normalized} to administrator")
            return 0

        db.add(
            User(
                email=normalized,
                name=name.strip() or "Administrator",
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
            )
        )
        db.commit()
        print(f"created administrator {normalized}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="quotient", description="Quotient administrative commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    admin_parser = subparsers.add_parser("create-admin", help="Create or promote an administrator account")
    admin_parser.add_argument("--email", required=True)
    admin_parser.add_argument("--password", required=True)
    admin_parser.add_argument("--name", default="Administrator")

    args = parser.parse_args()
    if args.command == "create-admin":
        return create_admin(args.email, args.password, args.name)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
