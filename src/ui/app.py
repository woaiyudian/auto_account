"""
Kivy application entry point for 全自动记账本 (Auto Account).
"""
import os
import sys

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, SlideTransition

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
SRC_DIR = os.path.join(BASE_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.database import get_database, init_database  # noqa: E402
from core.services import (  # noqa: E402
    AccountService,
    CategoryService,
    OCRService,
    SavingsPlanService,
    ScheduledTaskService,
    TransactionService,
)
from models import OCRResult, TransactionType  # noqa: E402
from . import widgets  # noqa: E402
from .screens import (  # noqa: E402
    AddSavingsScreen,
    AddScheduledScreen,
    AddTransactionScreen,
    HomeScreen,
    SavingsScreen,
    ScheduledScreen,
    SettingsScreen,
    TransactionsScreen,
)

try:  # Android only
    from jnius import autoclass
    from android import activity as android_activity

    ANDROID = True
except Exception:  # pragma: no cover - desktop
    ANDROID = False


class AutoAccountApp(App):
    title = "全自动记账本"

    def build(self):
        Window.clearcolor = widgets.rgba(widgets.BG)
        widgets.register_app_font(BASE_DIR)

        self.data_dir = self._resolve_data_dir()
        db_path = os.path.join(self.data_dir, "auto_account.db")
        init_database(db_path)
        self._seed_default_data()

        manager = ScreenManager(transition=SlideTransition(duration=0.2))
        for screen_cls in (
            HomeScreen,
            AddTransactionScreen,
            TransactionsScreen,
            SavingsScreen,
            AddSavingsScreen,
            ScheduledScreen,
            AddScheduledScreen,
            SettingsScreen,
        ):
            manager.add_widget(screen_cls())

        self.sm = manager
        return manager

    def _resolve_data_dir(self):
        """Pick the first writable data directory."""
        candidates = [
            os.environ.get("AUTO_ACCOUNT_DATA_DIR"),
            os.path.join(BASE_DIR, "data"),
        ]
        try:
            candidates.insert(1, self.user_data_dir)
        except Exception:
            pass

        for path in candidates:
            if not path:
                continue
            try:
                os.makedirs(path, exist_ok=True)
                probe = os.path.join(path, ".write_test")
                with open(probe, "w", encoding="utf-8") as fh:
                    fh.write("ok")
                os.remove(probe)
                return path
            except Exception:
                continue
        return BASE_DIR

    def _seed_default_data(self):
        db = get_database()
        accounts = AccountService(db)
        if not accounts.get_all_accounts():
            accounts.create_account(name="现金", balance=0.0, icon="cash",
                                    color="#16A34A", is_default=True)
            accounts.create_account(name="支付宝", balance=0.0,
                                    icon="alipay", color="#1677FF")

    def on_start(self):
        Clock.schedule_interval(self._background_tick, 30)
        self._maybe_auto_backup()
        if ANDROID:
            self._setup_android_callback()

    # -------------------------------------------------------------- backups
    def _maybe_auto_backup(self):
        """Backup once per configured interval (default: daily)."""
        try:
            from core import backup

            if not backup.should_auto_backup(self.data_dir):
                return
            path = backup.backup_now(get_database().db_path, self.data_dir)
            print(f"[auto_account] auto backup -> {path}")
        except Exception as exc:  # pragma: no cover
            print(f"[auto_account] auto backup skipped: {exc}")

    # ------------------------------------------------------------- Android
    #: Java sends english category keys; map them onto the built-in categories.
    CATEGORY_KEYS = {
        "food": "餐饮",
        "transport": "交通",
        "shopping": "购物",
        "entertainment": "娱乐",
        "medical": "医疗",
        "housing": "居住",
        "communication": "通讯",
    }

    #: friendly names for the apps we capture from
    APP_LABELS = {
        "com.tencent.mm": "微信",
        "com.eg.android.AlipayGphone": "支付宝",
        "com.alibaba.android.rimet": "钉钉",
        "com.tencent.mobileqq": "QQ",
        "com.unionpay.uppay": "云闪付",
        "com.jd.mobile": "京东金融",
        "com.taobao.taobao": "淘宝",
        "com.xunmeng.pinduoduo": "拼多多",
    }

    def _setup_android_callback(self):
        try:
            handler_cls = autoclass("com.autoaccount.PythonCallbackHandler")

            class _Callback(handler_cls.TransactionCallback):
                def onTransactionDetected(self, amount, kind, merchant, category,
                                          package_name, raw_text, timestamp,
                                          channel):
                    Clock.schedule_once(
                        lambda _dt: app._on_auto_transaction(
                            amount, kind, merchant, category,
                            package_name, raw_text, channel),
                        0,
                    )

            app = self
            handler_cls.setCallback(_Callback())
        except Exception as exc:  # pragma: no cover
            print(f"[auto_account] android callback setup failed: {exc}")

    def _on_auto_transaction(self, amount, kind, merchant, category,
                             package_name, raw_text, channel="accessibility"):
        """A capture channel detected a transaction -> queue a confirmation."""
        try:
            db = get_database()
            accounts = AccountService(db)
            categories = CategoryService(db)
            ocr = OCRService(db, categories, accounts)

            txn_type = (TransactionType.EXPENSE if kind == "expense"
                        else TransactionType.INCOME)

            # map the english category key to a real category id
            category_id = None
            name = self.CATEGORY_KEYS.get(category or "")
            if name:
                found = categories.find_category_by_name(name, txn_type)
                if found:
                    category_id = found.id

            app_label = self.APP_LABELS.get(package_name, package_name or "未知来源")
            channel_label = "通知" if channel == "notification" else "读屏"
            confidence = 0.95 if channel == "notification" else 0.85

            result = OCRResult(
                raw_text=raw_text or "",
                parsed_amount=float(amount),
                parsed_type=txn_type,
                parsed_merchant=merchant,
                parsed_category=category_id,
                confidence=confidence,
                source_app=f"{app_label}·{channel_label}",
            )
            default_account = accounts.get_default_account()
            if not default_account:
                return
            ocr.create_pending_confirmation(result, default_account.id)

            if self.sm.current == "home":
                Clock.schedule_once(lambda _dt: self.sm.get_screen("home").refresh(), 0)
        except Exception as exc:  # pragma: no cover
            print(f"[auto_account] auto transaction failed: {exc}")

    # ------------------------------------------------------------ periodic
    def _background_tick(self, _dt):
        """Run scheduled tasks and savings auto-transfers."""
        try:
            db = get_database()
            TransactionService(db)
            tasks = ScheduledTaskService(db)
            savings = SavingsPlanService(db)

            tasks.process_due_tasks()
            savings.process_auto_transfers()

            # daily-ish snapshot of the database
            self._maybe_auto_backup()

            if self.sm and self.sm.current == "home":
                Clock.schedule_once(
                    lambda _dt2: self.sm.get_screen("home").refresh(), 0)
        except Exception as exc:
            print(f"[auto_account] background tick failed: {exc}")


def main():
    AutoAccountApp().run()


if __name__ == "__main__":
    main()
