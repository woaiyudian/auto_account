#!/usr/bin/env python3
"""Render a few screenshots of the app with demo data (desktop only)."""
import os
import shutil
import sys
from datetime import datetime, time, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "docs", "screenshots")
DATA = os.path.join(BASE, "..", "tmp", "demo_data")

os.environ.setdefault("KIVY_HOME", os.path.join(BASE, "..", "tmp", "kivy"))
os.environ["AUTO_ACCOUNT_DATA_DIR"] = DATA
os.environ["KIVY_NO_ARGS"] = "1"
sys.path.insert(0, os.path.join(BASE, "src"))

shutil.rmtree(DATA, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "420")
Config.set("graphics", "height", "860")
Config.set("graphics", "resizable", "0")
Config.set("graphics", "multisamples", "0")
# Windows tablet-pen provider crashes on shutdown in some environments
Config.set("input", "wm_pen", "")
Config.set("input", "wm_touch", "")

from kivy.clock import Clock  # noqa: E402

from core.database import get_database  # noqa: E402
from core.services import (  # noqa: E402
    AccountService,
    CategoryService,
    OCRService,
    SavingsPlanService,
    ScheduledTaskService,
    TransactionService,
)
from models import TaskFrequency, TransactionType  # noqa: E402
from ui.app import AutoAccountApp  # noqa: E402

STEPS = ["home", "add_txn", "savings", "scheduled", "settings"]


class DemoApp(AutoAccountApp):
    def on_start(self):
        super().on_start()
        self._seed()
        self.sm.get_screen("home").refresh()
        self._index = 0
        Clock.schedule_once(self._step, 1.0)

    def _seed(self):
        db = get_database()
        accounts = AccountService(db)
        categories = CategoryService(db)
        txn = TransactionService(db)
        savings = SavingsPlanService(db, accounts)
        tasks = ScheduledTaskService(db, txn)
        ocr = OCRService(db, categories, accounts)

        wallets = accounts.get_all_accounts()
        alipay = wallets[-1]
        cash = accounts.get_default_account()
        alipay.balance = 3246.80
        accounts.update_account(alipay)

        def cat_id(name, kind):
            return categories.find_category_by_name(name, kind).id

        samples = [
            ("expense", 28.0, "午餐 外卖", "餐饮", 0),
            ("expense", 6.0, "地铁通勤", "交通", 0),
            ("expense", 128.0, "超市采购", "购物", 1),
            ("expense", 45.0, "电影票", "娱乐", 2),
            ("income", 8600.0, "10月工资", "工资", 3),
            ("expense", 2200.0, "房租", "居住", 4),
            ("expense", 32.5, "咖啡", "餐饮", 5),
        ]
        for kind, amount, desc, category, days_ago in samples:
            is_expense = kind == "expense"
            txn.create_transaction(
                account_id=alipay.id,
                amount=amount,
                type_=TransactionType.EXPENSE if is_expense else TransactionType.INCOME,
                category_id=cat_id(
                    category,
                    TransactionType.EXPENSE if is_expense else TransactionType.INCOME,
                ),
                date_=datetime.now() - timedelta(days=days_ago, hours=2),
                description=desc,
            )

        plan = savings.create_plan(
            name="买 MacBook",
            target_amount=12000.0,
            target_date=(datetime.now() + timedelta(days=180)).date(),
            account_id=alipay.id,
            auto_transfer_amount=500.0,
            auto_transfer_frequency="monthly",
            icon="laptop",
            color="#16A34A",
            description="换一台工作机",
        )
        savings.add_savings(plan.id, 4600.0)
        savings.create_plan(
            name="应急备用金",
            target_amount=20000.0,
            icon="shield",
            color="#2563EB",
            description="6 个月生活费",
        )

        tasks.create_task(
            name="每月房租",
            amount=2200.0,
            type_=TransactionType.EXPENSE,
            category_id=cat_id("居住", TransactionType.EXPENSE),
            account_id=alipay.id,
            frequency=TaskFrequency.MONTHLY,
            execute_time=time(9, 0),
        )

        result = ocr.parse_screen_text(
            "支付宝 支付 38.50元 餐饮 肯德基 订单号 2026112622001", "alipay"
        )
        ocr.create_pending_confirmation(result, alipay.id)

    def _step(self, _dt):
        if self._index >= len(STEPS):
            self.stop()
            return
        name = STEPS[self._index]
        self.sm.current = name
        Clock.schedule_once(lambda dt: self._grab(name), 1.0)
        self._index += 1
        Clock.schedule_once(self._step, 1.7)

    def _grab(self, name):
        screen = self.sm.get_screen(name)
        path = os.path.join(OUT, f"{name}.png")
        screen.export_to_png(path)
        print(f"captured {name} -> {path}")


if __name__ == "__main__":
    DemoApp().run()
