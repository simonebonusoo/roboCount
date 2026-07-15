from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
_ENV_LOADED = False


class ConfigError(RuntimeError):
    """Raised when the project configuration is missing or malformed."""


@dataclass(frozen=True)
class DatabaseTarget:
    scheme: str
    username: str
    host: str
    port: int
    database: str


@dataclass(frozen=True)
class RuntimeConfig:
    database_url: str
    session_secret: str
    cookie_secure_override: str
    configured_origins: tuple[str, ...]
    database_target: DatabaseTarget | None


def load_project_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_dotenv(ENV_FILE, override=False)
    _ENV_LOADED = True


def _getenv(name: str) -> str:
    import os

    return os.getenv(name, "").strip()


def _parse_csv_env(name: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in _getenv(name).split(",")
        if item.strip()
    )


def _parse_database_target(database_url: str) -> DatabaseTarget:
    clean_url = database_url.strip()
    if not clean_url:
        raise ConfigError("DATABASE_URL non impostata.")

    if "://" not in clean_url:
        raise ConfigError("DATABASE_URL non valida: schema mancante.")

    scheme, remainder = clean_url.split("://", 1)
    if scheme not in {"postgresql", "postgres"}:
        raise ConfigError("DATABASE_URL non valida: usa uno schema PostgreSQL.")

    credentials, separator, location = remainder.rpartition("@")
    if not separator or not credentials or not location:
        raise ConfigError("DATABASE_URL non valida: credenziali o host mancanti.")

    username, password_separator, _password = credentials.partition(":")
    if not password_separator or not username:
        raise ConfigError("DATABASE_URL non valida: username o password mancanti.")

    host_port, path_separator, database = location.partition("/")
    if not path_separator or not database:
        raise ConfigError("DATABASE_URL non valida: database mancante.")

    host, port_separator, port_text = host_port.rpartition(":")
    if not port_separator or not host or not port_text:
        raise ConfigError("DATABASE_URL non valida: host o porta mancanti.")

    try:
        port = int(port_text)
    except ValueError as exc:
        raise ConfigError("DATABASE_URL non valida: porta PostgreSQL non numerica.") from exc

    return DatabaseTarget(
        scheme=scheme,
        username=username,
        host=host,
        port=port,
        database=database,
    )


def _validate_database_target(target: DatabaseTarget) -> None:
    if target.username == "postgres":
        raise ConfigError(
            "DATABASE_URL non valida: per il Supabase pooler usa lo username completo "
            "nel formato postgres.PROJECT_REF."
        )
    if not target.username.startswith("postgres."):
        raise ConfigError(
            "DATABASE_URL non valida: username inatteso per il Supabase pooler."
        )
    if not target.host.endswith(".pooler.supabase.com"):
        raise ConfigError(
            "DATABASE_URL non valida: host inatteso. Atteso il Supabase Shared Pooler."
        )
    if target.port != 6543:
        raise ConfigError(
            "DATABASE_URL non valida: per RoboCount e richiesto il Supabase Shared Pooler "
            "in transaction mode sulla porta 6543."
        )
    if target.database != "postgres":
        raise ConfigError("DATABASE_URL non valida: database inatteso.")


def format_database_target(target: DatabaseTarget) -> str:
    return (
        f"host={target.host} port={target.port} "
        f"database={target.database} username={target.username}"
    )


def get_runtime_config(*, require_database: bool = True, require_session_secret: bool = True) -> RuntimeConfig:
    load_project_env()

    database_url = _getenv("DATABASE_URL")
    legacy_database_url = _getenv("PYDATABASE_URL")
    session_secret = _getenv("SESSION_SECRET")
    cookie_secure_override = _getenv("MONITOR_SPESE_COOKIE_SECURE")
    configured_origins = _parse_csv_env("ALLOWED_ORIGINS") or _parse_csv_env("CORS_ORIGINS")

    database_target = None
    if database_url:
        database_target = _parse_database_target(database_url)
        _validate_database_target(database_target)
    elif legacy_database_url:
        raise ConfigError(
            "Variabile non valida: e stata trovata PYDATABASE_URL. "
            "Rinominala in DATABASE_URL per consentire a RoboCount di connettersi a Supabase."
        )
    elif require_database:
        raise ConfigError(
            "DATABASE_URL non impostata. Configura la stringa di connessione "
            "PostgreSQL di Supabase nella variabile d'ambiente DATABASE_URL."
        )

    if require_session_secret and not session_secret:
        raise ConfigError(
            "SESSION_SECRET non impostata. Configura una stringa lunga casuale "
            "nella variabile d'ambiente SESSION_SECRET."
        )

    return RuntimeConfig(
        database_url=database_url,
        session_secret=session_secret,
        cookie_secure_override=cookie_secure_override,
        configured_origins=configured_origins,
        database_target=database_target,
    )
