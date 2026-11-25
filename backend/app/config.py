from __future__ import annotations

from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    airlock_host: str = "127.0.0.1"
    airlock_port: int = 8000
    airlock_demo_mode: bool = True
    airlock_prod_db_path: Path = Path("./data/airlock_prod.db")
    airlock_meta_db_path: Path = Path("./data/airlock_meta.db")
    airlock_speculative_dir: Path = Path("./data/speculative_dbs")
    airlock_contracts_dir: Path = Path("./contracts")
    airlock_agent_token: str = "change-me-agent-token-generate-a-random-value"
    airlock_reviewer_token: str = "change-me-reviewer-token-generate-a-different-value"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def allowed_origins(self) -> set[str]:
        origins = self.cors_origins.split(",")
        if not origins or any(not item.strip() for item in origins):
            raise ValueError("CORS_ORIGINS must not contain empty origins")

        normalized = set()
        for item in origins:
            origin = item.strip().rstrip("/")
            if ("*" in origin or "%" in origin or any(char.isspace() for char in origin)
                    or "\\" in origin):
                raise ValueError("CORS_ORIGINS must contain exact HTTP/HTTPS origins")
            try:
                parsed = urlsplit(origin)
                hostname = parsed.hostname
                port = parsed.port
            except ValueError as exc:
                raise ValueError("CORS_ORIGINS must contain valid HTTP/HTTPS origins") from exc
            if (
                parsed.scheme.lower() not in {"http", "https"}
                or not parsed.netloc
                or parsed.netloc.endswith(":")
                or not hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "?" in origin
                or "#" in origin
            ):
                raise ValueError("CORS_ORIGINS must contain exact HTTP/HTTPS origins")
            try:
                host_address = ip_address(hostname)
                normalized_host = host_address.compressed
            except ValueError:
                domain = hostname[:-1] if hostname.endswith(".") else hostname
                try:
                    normalized_host = domain.encode("idna").decode("ascii").lower()
                except UnicodeError as exc:
                    raise ValueError("CORS_ORIGINS must contain valid HTTP/HTTPS origins") from exc
                if not all(label and len(label) <= 63 and label[0] != "-" and label[-1] != "-"
                           and all(char.isalnum() or char == "-" for char in label)
                           for label in normalized_host.split(".")):
                    raise ValueError("CORS_ORIGINS must contain valid HTTP/HTTPS origins")
            host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
            normalized.add(f"{parsed.scheme.lower()}://{host}" + (f":{port}" if port is not None else ""))
        return normalized

    @model_validator(mode="after")
    def validate_security_settings(self):
        if not self.airlock_agent_token or not self.airlock_reviewer_token:
            raise ValueError("Agent and reviewer tokens must both be configured")
        if self.airlock_agent_token == self.airlock_reviewer_token:
            raise ValueError("Agent and reviewer tokens must be different")
        try:
            is_loopback = ip_address(self.airlock_host).is_loopback
        except ValueError:
            is_loopback = self.airlock_host.lower() == "localhost"
        if self.airlock_demo_mode and not is_loopback:
            raise ValueError("AIRLOCK_DEMO_MODE=true requires AIRLOCK_HOST to be loopback")
        self.allowed_origins
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
