"""
Automated backup of ChatDB — esegue backup sicuro con gestione WAL.
Usage:
  python scripts/backup_db.py                    # backup nel default dir
  python scripts/backup_db.py --dir /custom/path  # backup custom dir
  python scripts/backup_db.py --retain 30         # retention giorni
"""

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backup")

DB_PATH = Path("/app/data/chats.db")
DEFAULT_BACKUP_DIR = Path("/app/data/backups")
DEFAULT_RETENTION_DAYS = 30


def backup_database(db_path: Path, backup_dir: Path, retention_days: int) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"chats_{timestamp}.db"

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    logger.info(f"Backing up {db_path} → {backup_path}")
    conn = sqlite3.connect(str(db_path))
    try:
        backup_conn = sqlite3.connect(str(backup_path))
        conn.backup(backup_conn, pages=4096)
        backup_conn.close()
    finally:
        conn.close()

    backup_size = backup_path.stat().st_size
    logger.info(f"Backup completato: {backup_path} ({backup_size / 1024:.0f} KB)")

    _cleanup_old_backups(backup_dir, retention_days)
    return backup_path


def _cleanup_old_backups(backup_dir: Path, retention_days: int):
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for f in sorted(backup_dir.glob("chats_*.db")):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    if removed:
        logger.info(f"Puliti {removed} backup più vecchi di {retention_days} giorni")


def periodic_backup(interval_minutes: int = 60):
    logger.info(f"Backup periodico avviato (ogni {interval_minutes} min)")
    while True:
        backup_database(DB_PATH, DEFAULT_BACKUP_DIR, DEFAULT_RETENTION_DAYS)
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ChatDB backup tool")
    parser.add_argument("--dir", type=str, default=str(DEFAULT_BACKUP_DIR), help="Backup directory")
    parser.add_argument("--retain", type=int, default=DEFAULT_RETENTION_DAYS, help="Retention in days")
    parser.add_argument("--periodic", type=int, default=0, help="Run periodically every N minutes")
    args = parser.parse_args()

    backup_dir = Path(args.dir)
    if args.periodic:
        periodic_backup(args.periodic)
    else:
        backup_database(DB_PATH, backup_dir, args.retain)
