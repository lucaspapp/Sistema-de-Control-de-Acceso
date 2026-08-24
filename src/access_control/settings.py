"""Carga configuración local sin añadir dependencias al entorno virtual."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_local_env() -> None:
    """Carga pares KEY=VALUE de .env sin sobrescribir variables del sistema."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
