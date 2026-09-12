from __future__ import annotations

import argparse
from datetime import datetime, timezone

from database.models.notification import Notification
from database.session import SessionLocal


PRESENCE_FIELDS = {"last_seen_at", "updated_at"}


def is_presence_only(notification: Notification) -> bool:
    if notification.event_type != "users.updated":
        return False

    data = notification.data or {}
    changed_fields = {
        str(item)
        for item in data.get("changed_fields", [])
    }

    return bool(changed_fields) and changed_fields.issubset(
        PRESENCE_FIELDS,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Archive unread notifications created by historical "
            "WebSocket last-seen updates."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the archive operation. Without this flag the script is a dry run.",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        candidates = (
            db.query(Notification)
            .filter(
                Notification.event_type == "users.updated",
                Notification.is_archived.is_(False),
            )
            .all()
        )
        matches = [
            item
            for item in candidates
            if is_presence_only(item)
        ]

        print(
            f"Presence-only notifications found: {len(matches)}",
        )

        if not args.apply:
            print("Dry run only. Re-run with --apply to archive them.")
            return

        now = datetime.now(timezone.utc)

        for item in matches:
            item.is_read = True
            item.read_at = item.read_at or now
            item.is_archived = True
            item.archived_at = now

        db.commit()
        print(f"Archived {len(matches)} notifications.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
