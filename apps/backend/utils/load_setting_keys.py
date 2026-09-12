from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_key_path(
    configured_path: str | None,
    key_name: str,
) -> Path:
    if not configured_path:
        raise ValueError(
            f"{key_name} path is not configured"
        )

    path = Path(
        configured_path,
    ).expanduser()

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    path = path.resolve()

    if not path.exists():
        raise ValueError(
            f"{key_name} file was not found: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"{key_name} path is not a file: {path}"
        )

    return path


def load_keys(settings):
    has_private_key = bool(
        settings.JWT_PRIVATE_KEY
    )

    has_public_key = bool(
        settings.JWT_PUBLIC_KEY
    )

    if has_private_key != has_public_key:
        raise ValueError(
            "JWT_PRIVATE_KEY and JWT_PUBLIC_KEY "
            "must be configured together"
        )

    if has_private_key and has_public_key:
        return (
            settings.JWT_PRIVATE_KEY.encode(
                "utf-8",
            ),
            settings.JWT_PUBLIC_KEY.encode(
                "utf-8",
            ),
        )

    private_path = resolve_key_path(
        settings.JWT_PRIVATE_KEY_PATH,
        "JWT private key",
    )

    public_path = resolve_key_path(
        settings.JWT_PUBLIC_KEY_PATH,
        "JWT public key",
    )

    try:
        private_key = private_path.read_bytes()
        public_key = public_path.read_bytes()

    except PermissionError as error:
        raise ValueError(
            "Permission was denied while reading "
            "the JWT key files"
        ) from error

    if not private_key.strip():
        raise ValueError(
            f"JWT private key is empty: {private_path}"
        )

    if not public_key.strip():
        raise ValueError(
            f"JWT public key is empty: {public_path}"
        )

    return private_key, public_key