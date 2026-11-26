"""End-to-end flow test driven through the real UI screens."""
import os
import shutil
import sys
from datetime import datetime, time

BASE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("KIVY_HOME", os.path.join(BASE, "..", "tmp", "kivy"))
os.environ.setdefault("AUTO_ACCOUNT_DATA_DIR", os.path.join(BASE, "..", "tmp", "e2e"))
sys.path.insert(0, os.path.join(BASE, "src"))

E2E_DIR = os.environ["AUTO_ACCOUNT_DATA_DIR"]
shutil.rmtree(E2E_DIR, ignore_errors=True)

from core.database import get_database  # noqa: E402
from core.services import (  # noqa: E402
    AccountService,
    OCRService,
    SavingsPlanService,
    ScheduledTaskService,
    TransactionService,
)
from models import (  # noqa: E402
    ConfirmationStatus,
    OCRResult,
    TaskFrequency,
    TransactionType,
)
from ui.app import AutoAccountApp  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"  ok - {message}")


def main():
    app = AutoAccountApp()
    app.run = lambda: None
    root = app.build()
    db = get_database()

    accounts = AccountService(db)
    transactions = TransactionService(db)
    savings = SavingsPlanService(db, accounts)
    tasks = ScheduledTaskService(db, transactions)
    ocr = OCRService(db)

    print("[1] 手动记一笔支出")
    screen = root.get_screen("add_txn")
    screen.set_mode("expense")
    screen.on_pre_enter()
    screen.amount.text = "25.5"
    screen.desc.text = "午餐"
    screen.save()
    rows = transactions.get_recent_transactions(5)
    check(len(rows) == 1, "生成了 1 条交易")
    check(abs(rows[0].amount - 25.5) < 1e-6, "金额正确")
    check(rows[0].type == TransactionType.EXPENSE, "类型为支出")
    balance = accounts.get_account(rows[0].account_id).balance
    check(abs(balance + 25.5) < 1e-6, f"账户余额已扣减（{balance}）")

    print("[2] 手动记一笔收入")
    screen.set_mode("income")
    screen.on_pre_enter()
    screen.amount.text = "8000"
    screen.desc.text = "工资"
    screen.save()
    rows = transactions.get_recent_transactions(5)
    check(len(rows) == 2, "生成了第 2 条交易")
    income = [r for r in rows if r.type == TransactionType.INCOME][0]
    check(abs(income.amount - 8000) < 1e-6, "收入金额正确")

    print("[3] 首页汇总")
    home = root.get_screen("home")
    home.refresh()
    summary = home.stats.get_overview()
    check(abs(summary["monthly_income"] - 8000) < 1e-6, "本月收入 8000")
    check(abs(summary["monthly_expense"] - 25.5) < 1e-6, "本月支出 25.5")

    print("[4] 新建攒钱计划并存入")
    add_savings = root.get_screen("add_savings")
    add_savings.on_pre_enter()
    add_savings.name_field.text = "旅行基金"
    add_savings.target_field.text = "5000"
    add_savings.current_field.text = "1000"
    add_savings.save()
    plans = savings.get_all_plans()
    check(len(plans) == 1, "创建了 1 个计划")
    check(abs(plans[0].current_amount - 1000) < 1e-6, "初始已存 1000")
    savings.add_savings(plans[0].id, 500)
    plan = savings.get_plan(plans[0].id)
    check(abs(plan.current_amount - 1500) < 1e-6, "存入后 1500")
    check(abs(plan.progress - 30.0) < 1e-6, "进度 30%")

    print("[5] 定时任务：创建 + 到期执行")
    add_task = root.get_screen("add_task")
    add_task.on_pre_enter()
    add_task.name_field.text = "房租"
    add_task.amount_field.text = "3000"
    add_task.type_choice.text = "支出"
    add_task._refresh_categories()
    add_task.time_field.text = "09:00"
    add_task.save()
    all_tasks = tasks.get_all_tasks()
    check(len(all_tasks) == 1, "创建了 1 个定时任务")
    task = all_tasks[0]
    task.last_executed = None
    tasks.update_task(task)
    executed = tasks.process_due_tasks(datetime.now().replace(hour=10, minute=0))
    check(len(executed) == 1, "到期任务被执行 1 次")
    check(abs(executed[0][1].amount - 3000) < 1e-6, "任务金额正确")

    print("[6] 自动识别 -> 待确认 -> 确认入账")
    text = "支付宝 支付 25.00元 餐饮 美团外卖 订单号: 123456"
    result = ocr.parse_screen_text(text, "alipay")
    check(result.parsed_amount == 25.0, "OCR 解析出金额 25.0")
    check(result.parsed_type == TransactionType.EXPENSE, "识别为支出")
    default_acc = accounts.get_default_account()
    pending = ocr.create_pending_confirmation(result, default_acc.id)
    pendings = db.get_pending_confirmations(ConfirmationStatus.PENDING)
    check(len(pendings) == 1, "生成 1 条待确认")
    before = len(transactions.get_recent_transactions(100))
    txn = ocr.process_confirmation(pending.id)
    check(txn is not None and abs(txn.amount - 25.0) < 1e-6, "确认后入账成功")
    after = len(transactions.get_recent_transactions(100))
    check(after == before + 1, "交易数量 +1")
    check(db.get_pending_confirmation(pending.id).status == ConfirmationStatus.CONFIRMED,
          "待确认状态变更为已确认")

    print("[7] 交易列表页与筛选")
    txn_screen = root.get_screen("transactions")
    txn_screen.on_pre_enter()
    txn_screen._on_filter("支出")
    check(txn_screen.filter_mode == "支出", "筛选切换到支出")
    txn_screen._on_filter("全部")

    print("[8] 设置页与导出")
    settings = root.get_screen("settings")
    settings.on_pre_enter()
    settings._export()
    export_dir = os.path.join(app.data_dir, "exports")
    files = os.listdir(export_dir) if os.path.isdir(export_dir) else []
    check(len(files) == 1, f"导出了 1 个 CSV：{files}")

    print("[9] 自定义目录备份 + 恢复")
    from core import backup

    custom_dir = os.path.join(app.data_dir, "my_backup_folder")
    os.makedirs(custom_dir, exist_ok=True)
    config = backup.load_config(app.data_dir)
    config["directory"] = custom_dir
    backup.save_config(app.data_dir, config)
    check(settings._backup_dir() == custom_dir, "设置页读到自定义备份目录")

    settings._backup_now()
    items = backup.list_backups(custom_dir)
    check(len(items) == 1, "备份文件落在自定义目录")

    before = len(transactions.get_recent_transactions(100))
    saved = items[0]["path"]

    # 再记一笔，然后恢复，应该回到备份时的状态
    transactions.create_transaction(
        account_id=accounts.get_default_account().id,
        amount=99.0,
        type_=TransactionType.EXPENSE,
        category_id=transactions.get_recent_transactions(1)[0].category_id,
        date_=datetime.now(),
        description="备份后新增",
    )
    check(len(transactions.get_recent_transactions(100)) == before + 1,
          "备份后新增 1 笔")

    ok, message = backup.restore(db.db_path, saved, app.data_dir)
    check(ok, f"恢复成功（{message}）")
    from core.database import init_database

    restored = TransactionService(init_database(db.db_path))
    check(len(restored.get_recent_transactions(100)) == before,
          "恢复后回到备份时的交易数")

    print("\nALL E2E CHECKS PASSED")


if __name__ == "__main__":
    main()
