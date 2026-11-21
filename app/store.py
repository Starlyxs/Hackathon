"""Archivo JSON local. No hay servidor ni cuentas: la laptop del maestro es la base."""

import json
import os
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _default_data():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "datos"
    return ROOT / "data"


if os.environ.get("EDU_STORE"):
    STORE = Path(os.environ["EDU_STORE"])
    SHEETS = Path(os.environ.get("EDU_SHEETS", str(STORE.parent / "sheets")))
    DEBUG = STORE.parent / "debug"
else:
    DATA = _default_data()
    STORE = DATA / "store.json"
    SHEETS = DATA / "sheets"
    DEBUG = DATA / "debug"

_lock = threading.Lock()


def ensure_dirs():
    SHEETS.mkdir(parents=True, exist_ok=True)
    DEBUG.mkdir(parents=True, exist_ok=True)


def _empty():
    return {"forms": {}, "sheets": {}, "results": [], "authored": [], "groups": {}}


def load():
    ensure_dirs()
    if not STORE.exists():
        return _empty()
    db = json.loads(STORE.read_text(encoding="utf-8"))
    for key, value in _empty().items():
        db.setdefault(key, value)
    return db


def save(db):
    ensure_dirs()
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE)


BACKUPS = STORE.parent / "copias"
KEEP_BACKUPS = 14


def _daily_backup():
    """Una copia por día del estado anterior al primer cambio. Se guardan las últimas 14."""
    if os.environ.get("EDU_STORE") or not STORE.exists():
        return
    try:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        target = BACKUPS / f"store-{datetime.now():%Y-%m-%d}.json"
        if target.exists():
            return
        shutil.copy2(STORE, target)
        for old in sorted(BACKUPS.glob("store-*.json"))[:-KEEP_BACKUPS]:
            old.unlink(missing_ok=True)
    except OSError:
        pass


def last_backup():
    if not BACKUPS.exists():
        return ""
    found = sorted(BACKUPS.glob("store-*.json"))
    return found[-1].stem.replace("store-", "") if found else ""


def update(mutator):
    # Cargar, cambiar y guardar van juntos. Si no, dos peticiones a la vez se pisan y se pierden datos.
    with _lock:
        _daily_backup()
        db = load()
        result = mutator(db)
        save(db)
        return result
