"""Tests for the backup / restore feature."""
import os
import shutil
import sys
from datetime import datetime, time

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, "src"))

from core import backup  # noqa: E402
from core.database import init_database  # noqa: E402
from core.services import (  # noqa: E402
    AccountService,
    CategoryService,
    TransactionService,
)
from models import TransactionType  # noqa: E402

WORK = os.path.join(BASE, "..", "tmp", "backup_test")
DB = os.path.join(WORK, "auto_account.db")
DATA = os.path.join(WORK, "data")
CUSTOM = os.path.join(WORK, "my_backups")


def check(cond, message):
    if not cond:
        raise AssertionError(message)
    print(f"  ok - {message}")


def fresh():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    db = init_database(DB)
    accounts = AccountService(db)
    acc = accounts.create_account("现金", 1000.0, is_default=True)
    return db, acc


def add_expense(db, acc, amount, desc):
    cats = CategoryService(db)
    txn = TransactionService(db)
    cat = cats.find_category_by_name("餐饮", TransactionType.EXPENSE)
    return txn.create_transaction(
        account_id=acc.id, amount=amount, type_=TransactionType.EXPENSE,
        category_id=cat.id, date_=datetime.now(), description=desc)


def main():
    print("[1] 自定义目录备份")
    db, acc = fresh()
    add_expense(db, acc, 25.0, "午餐")

    config = backup.load_config(DATA)
    config["directory"] = CUSTOM
    config["include_csv"] = True
    backup.save_config(DATA, config)
    check(backup.resolved_dir(DATA) == CUSTOM, "自定义目录被记住")

    path = backup.backup_now(DB, DATA)
    check(os.path.isfile(path), f"生成备份文件 {os.path.basename(path)}")
    check(os.path.isfile(path.replace(".db", ".csv")), "同时导出了 CSV")
    check(os.path.getsize(path) > 4096, "备份文件大小合理")

    items = backup.list_backups(CUSTOM)
    check(len(items) == 1, "列表能查到 1 个备份")

    print("[2] 备份后改数据，再恢复")
    add_expense(db, acc, 80.0, "晚餐")
    txn = TransactionService(db)
    check(len(txn.get_recent_transactions(10)) == 2, "备份后有 2 笔交易")

    ok, message = backup.restore(DB, path, DATA)
    check(ok, f"恢复成功（{message}）")

    db2 = init_database(DB)
    txn2 = TransactionService(db2)
    rows = txn2.get_recent_transactions(10)
    check(len(rows) == 1, "恢复后回到 1 笔交易")
    check(abs(rows[0].amount - 25.0) < 1e-6, "恢复的是备份时的数据")
    check(os.path.isfile(DB + ".before-restore"), "恢复了安全留底文件")

    print("[3] 非法文件不允许覆盖")
    bogus = os.path.join(CUSTOM, "garbage.db")
    with open(bogus, "wb") as fh:
        fh.write(b"not a database" * 1000)
    ok, message = backup.restore(DB, bogus, DATA)
    check(not ok, f"拒绝恢复非法文件（{message}）")
    rows = TransactionService(init_database(DB)).get_recent_transactions(10)
    check(len(rows) == 1, "拒绝后数据未被破坏")

    print("[4] 自动备份策略")
    config = backup.load_config(DATA)
    config["auto"] = True
    config["last_backup"] = ""
    backup.save_config(DATA, config)
    check(backup.should_auto_backup(DATA) is True, "从未备份时应自动备份")

    backup.backup_now(DB, DATA)
    check(backup.should_auto_backup(DATA) is False, "刚备份完不应再备份")

    config = backup.load_config(DATA)
    config["last_backup"] = "2020-01-01T00:00:00"
    backup.save_config(DATA, config)
    check(backup.should_auto_backup(DATA) is True, "超过间隔后应再次备份")

    config["auto"] = False
    backup.save_config(DATA, config)
    check(backup.should_auto_backup(DATA) is False, "关闭开关后不自动备份")

    print("[5] 保留数量裁剪")
    # 直接构造带不同时间戳的备份，验证按“最新保留”裁剪
    prune_dir = os.path.join(WORK, "prune_test")
    os.makedirs(prune_dir, exist_ok=True)
    created = []
    for i in range(6):
        stem = f"auto_account_backup_2026010{i + 1}_120000"
        db_file = os.path.join(prune_dir, stem + ".db")
        with open(db_file, "wb") as fh:
            fh.write(b"x" * 8192)
        with open(os.path.join(prune_dir, stem + ".csv"), "w", encoding="utf-8") as fh:
            fh.write("h\n")
        os.utime(db_file, (1_700_000_000 + i * 100, 1_700_000_000 + i * 100))
        created.append(stem)

    backup._prune(prune_dir, 3)
    left = sorted(i for i in os.listdir(prune_dir) if i.endswith(".db"))
    check(len(left) == 3, f"只保留最新 3 个（实际 {len(left)}）")
    check(created[-1] + ".db" in left, "最新的备份被保留")
    check(created[0] + ".db" not in left, "最旧的备份被删除")
    check(not os.path.exists(os.path.join(prune_dir, created[0] + ".csv")),
          "对应的 CSV 一并删除")

    print("\nALL BACKUP CHECKS PASSED")


if __name__ == "__main__":
    main()
