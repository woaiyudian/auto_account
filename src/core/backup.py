"""
Backup / restore of the local database to a user-chosen folder.

Design notes
------------
* A backup is a consistent SQLite snapshot produced with the sqlite3 backup
  API (not a raw file copy), so an in-flight write cannot corrupt it.
* The chosen folder and the auto-backup settings live in a small JSON file
  next to the database, so restoring an old database does not reset them.
* Restore validates the file first (integrity check + expected tables) and
  only then swaps it in.
"""
import json
import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

BACKUP_PREFIX = "auto_account_backup_"
SETTINGS_FILE = "backup_config.json"

DEFAULT_CONFIG = {
    "directory": "",
    "auto": True,
    "interval_hours": 24,
    "last_backup": "",
    "keep": 20,          # 最多保留多少个备份文件
    "include_csv": True,  # 同时导出一份 csv 方便查看
}

REQUIRED_TABLES = {"accounts", "transactions", "categories"}


def _config_path(data_dir: str) -> str:
    return os.path.join(data_dir, SETTINGS_FILE)


def load_config(data_dir: str) -> dict:
    config = dict(DEFAULT_CONFIG)
    path = _config_path(data_dir)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            config.update(json.load(fh) or {})
    except Exception:
        pass
    return config


def save_config(data_dir: str, config: dict) -> None:
    path = _config_path(data_dir)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def default_backup_dir(data_dir: str) -> str:
    """Pick a sensible default folder, preferring something the user can find."""
    candidates = []
    if os.name == "posix" and os.path.isdir("/sdcard"):
        candidates.append("/sdcard/Download/AutoAccount")
        candidates.append("/sdcard/AutoAccount")
    candidates.append(os.path.join(data_dir, "backups"))
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            return path
        except Exception:
            continue
    return data_dir


def resolved_dir(data_dir: str, config: Optional[dict] = None) -> str:
    config = config or load_config(data_dir)
    directory = (config.get("directory") or "").strip()
    if directory:
        return os.path.expanduser(directory)
    return default_backup_dir(data_dir)


def snapshot(db_path: str, target_path: str) -> None:
    """Write a consistent copy of the database using the sqlite backup API."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    source = sqlite3.connect(db_path)
    try:
        dest = sqlite3.connect(target_path)
        try:
            source.backup(dest)
            dest.commit()
        finally:
            dest.close()
    finally:
        source.close()


def backup_now(db_path: str, data_dir: str, target_dir: Optional[str] = None,
               include_csv: bool = True) -> str:
    """Create one backup file and return its path."""
    config = load_config(data_dir)
    directory = target_dir or resolved_dir(data_dir, config)
    os.makedirs(directory, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{BACKUP_PREFIX}{stamp}.db"
    target = os.path.join(directory, filename)
    snapshot(db_path, target)

    if include_csv:
        try:
            from core.database import Database
            from core.services import TransactionService

            rows = TransactionService(Database(db_path)).get_transactions(limit=100000)
            csv_path = os.path.join(directory, f"{BACKUP_PREFIX}{stamp}.csv")
            _write_csv(csv_path, rows)
        except Exception:
            pass

    config["last_backup"] = datetime.now().isoformat(timespec="seconds")
    config["directory"] = directory
    save_config(data_dir, config)

    _prune(directory, int(config.get("keep") or 20))
    return target


def _write_csv(path: str, rows) -> None:
    import csv

    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(["日期", "类型", "金额", "账户ID", "分类ID", "备注", "来源"])
        for txn in rows:
            writer.writerow([
                txn.date.strftime("%Y-%m-%d %H:%M"),
                "支出" if getattr(txn.type, "value", "") == "expense" else "收入",
                f"{txn.amount:.2f}",
                txn.account_id,
                txn.category_id,
                txn.description,
                txn.source,
            ])


def _prune(directory: str, keep: int) -> None:
    """Keep only the newest `keep` backups (db + csv pairs), by mtime."""
    if keep <= 0:
        return
    entries = []
    try:
        names = os.listdir(directory)
    except Exception:
        return

    for name in names:
        if not (name.startswith(BACKUP_PREFIX) and name.endswith(".db")):
            continue
        path = os.path.join(directory, name)
        try:
            entries.append((os.path.getmtime(path), name))
        except OSError:
            continue

    entries.sort(reverse=True)  # newest first
    for _, name in entries[keep:]:
        stem = name[:-3]  # strip ".db"
        for ext in (".db", ".csv", ".db-wal", ".db-shm"):
            victim = os.path.join(directory, stem + ext)
            if os.path.exists(victim):
                try:
                    os.remove(victim)
                except Exception:
                    pass


def list_backups(directory: str) -> List[dict]:
    """Newest first, with size and mtime for display."""
    items = []
    try:
        names = os.listdir(directory)
    except Exception:
        return items

    for name in names:
        if not (name.startswith(BACKUP_PREFIX) and name.endswith(".db")):
            continue
        path = os.path.join(directory, name)
        try:
            stat = os.stat(path)
        except Exception:
            continue
        items.append({
            "path": path,
            "name": name,
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime),
        })
    items.sort(key=lambda item: item["mtime"], reverse=True)
    return items


def _looks_like_db(path: str) -> Tuple[bool, str]:
    if not os.path.isfile(path):
        return False, "文件不存在"
    if os.path.getsize(path) < 4096:
        return False, "文件太小，不是有效数据库"

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except Exception as exc:
        return False, f"无法打开：{exc}"

    try:
        check = conn.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            return False, "数据库完整性检查未通过"
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            return False, f"缺少数据表：{', '.join(sorted(missing))}"
        return True, "ok"
    except Exception as exc:
        return False, f"读取失败：{exc}"
    finally:
        conn.close()


def restore(db_path: str, backup_path: str, data_dir: str) -> Tuple[bool, str]:
    """Replace the live database with a backup. Returns (ok, message)."""
    ok, message = _looks_like_db(backup_path)
    if not ok:
        return False, message

    # Flush the WAL so the live file holds every committed transaction.
    try:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

    safety = db_path + ".before-restore"
    try:
        if os.path.exists(db_path):
            shutil.copy2(db_path, safety)
        shutil.copy2(backup_path, db_path)
    except Exception as exc:
        return False, f"恢复失败：{exc}"

    for suffix in ("-wal", "-shm"):
        leftover = db_path + suffix
        if os.path.exists(leftover):
            try:
                os.remove(leftover)
            except Exception:
                pass

    # Re-open through the app's global handle so services see the new data.
    try:
        from core.database import init_database

        init_database(db_path)
    except Exception as exc:
        return False, f"恢复后重新打开失败：{exc}"

    return True, "已恢复，页面数据将刷新"


def should_auto_backup(data_dir: str) -> bool:
    config = load_config(data_dir)
    if not config.get("auto"):
        return False
    last = config.get("last_backup") or ""
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    hours = float(config.get("interval_hours") or 24)
    return datetime.now() - last_dt >= timedelta(hours=hours)
