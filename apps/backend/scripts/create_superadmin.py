#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

# Allow direct execution from the project root: python scripts/create_superadmin.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_

from core.security import hash_password
from database.models.enums import UserRole
from database.models.person import Person
from database.models.user import User
from database.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the first LoanHub platform administrator."
    )
    parser.add_argument("--phone", required=True)
    parser.add_argument("--email")
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--middle-name")
    parser.add_argument("--last-name", required=True)
    parser.add_argument(
        "--password",
        help="Avoid this option on shared shells; omit it for a hidden prompt.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass("Password: ")
    confirmation = args.password or getpass.getpass("Confirm password: ")

    if not password or len(password) < 10:
        print("Password must contain at least 10 characters.", file=sys.stderr)
        return 2
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    phone = args.phone.strip()
    email = args.email.strip().lower() if args.email else None

    db = SessionLocal()
    try:
        duplicate = (
            db.query(User)
            .filter(or_(User.phone == phone, User.email == email if email else False))
            .first()
        )
        if duplicate:
            print("A user with that phone or email already exists.", file=sys.stderr)
            return 1

        user = User(
            phone=phone,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.SUPERADMIN,
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()

        db.add(
            Person(
                user_id=user.id,
                first_name=args.first_name.strip(),
                middle_name=args.middle_name.strip() if args.middle_name else None,
                last_name=args.last_name.strip(),
                nationality="Mosotho",
            )
        )
        db.commit()
        print(f"SuperAdmin created successfully: {user.id}")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
