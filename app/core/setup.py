"""Create disposable local-only configuration without overwriting an existing file."""

import secrets
from pathlib import Path
from urllib.parse import quote


def main() -> None:
    destination = Path(".env")
    if destination.exists():
        print(".env already exists; leaving it unchanged")
        return
    password = secrets.token_urlsafe(24)
    jwt_secret = secrets.token_urlsafe(48)
    demo_key = secrets.token_urlsafe(32)
    database_url = f"postgresql+psycopg://gateway:{quote(password, safe='')}@postgres:5432/gateway"
    content = (
        f"POSTGRES_PASSWORD={password}\n"
        f"DATABASE_URL={database_url}\n"
        "REDIS_URL=redis://redis:6379/0\n"
        f"JWT_SECRET={jwt_secret}\n"
        f"DEMO_ACCESS_KEY={demo_key}\n"
        "LOG_LEVEL=INFO\n"
    )
    with destination.open("x", encoding="utf-8") as handle:
        handle.write(content)
    print("Created local .env; keep it private and out of version control")


if __name__ == "__main__":
    main()

