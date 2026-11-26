"""
All application screens.
"""
import csv
import os
from datetime import datetime, date, time

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from core.database import get_database
from core.services import (
    AccountService,
    CategoryService,
    OCRService,
    SavingsPlanService,
    ScheduledTaskService,
    StatisticsService,
    TransactionService,
)
from models import (
    ConfirmationStatus,
    SavingsPlanStatus,
    TaskFrequency,
    TransactionType,
)

from .widgets import (
    AppButton,
    AppLabel,
    Choice,
    CARD_BG,
    EXPENSE,
    EmptyHint,
    Field,
    HeaderBar,
    INCOME,
    ListRow,
    PendingCard,
    PRIMARY,
    ProgressCard,
    RoundedBox,
    Segmented,
    TEXT,
    TEXT_MUTED,
    toast,
    text_prompt,
    primary_button,
    scroll_column,
    rgba,
)


def money(value: float) -> str:
    return f"¥{value:,.2f}"


class BaseScreen(Screen):
    """Common service wiring + helpers."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = get_database()
        self.accounts = AccountService(self.db)
        self.categories = CategoryService(self.db)
        self.transactions = TransactionService(self.db)
        self.savings = SavingsPlanService(self.db, self.accounts)
        self.tasks = ScheduledTaskService(self.db, self.transactions)
        self.ocr = OCRService(self.db, self.categories, self.accounts)
        self.stats = StatisticsService(self.db)

        self.root_box = BoxLayout(orientation="vertical")
        self.add_widget(self.root_box)

        self.header_slot = BoxLayout(orientation="vertical", size_hint_y=None,
                                     height=dp(58))
        self.root_box.add_widget(self.header_slot)

        self.content = BoxLayout(orientation="vertical")
        self.root_box.add_widget(self.content)

    def set_header(self, header):
        self.header_slot.clear_widgets()
        self.header_slot.height = getattr(header, "height", dp(58))
        self.header_slot.add_widget(header)
        return header

    # -- helpers ---------------------------------------------------------
    def category_name(self, category_id):
        cat = self.categories.get_category(category_id)
        return cat.name if cat else "未分类"

    def account_name(self, account_id):
        acc = self.accounts.get_account(account_id)
        return acc.name if acc else "未知账户"

    def category_values(self, txn_type):
        return [c.name for c in self.categories.get_categories_by_type(txn_type)]

    def account_values(self):
        return [a.name for a in self.accounts.get_all_accounts()]

    def resolve_category(self, name, txn_type):
        cat = self.categories.find_category_by_name(name, txn_type)
        if cat:
            return cat.id
        cats = self.categories.get_categories_by_type(txn_type)
        return cats[0].id if cats else None

    def resolve_account(self, name):
        for acc in self.accounts.get_all_accounts():
            if acc.name == name:
                return acc.id
        default = self.accounts.get_default_account()
        return default.id if default else None

    def go(self, screen_name):
        self.manager.current = screen_name


# ------------------------------------------------------------------ 首页 ---
class HomeScreen(BaseScreen):
    name = "home"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_header(
            HeaderBar("全自动记账本", action_text="设置",
                      on_action=lambda: self.go("settings"))
        )

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.column.clear_widgets()
        summary = self.stats.get_overview()

        # balance card
        card = RoundedBox(orientation="vertical", size_hint_y=None,
                          height=dp(120), padding=dp(16), spacing=dp(6))
        card.add_widget(AppLabel(text="总资产", font_size=sp(13),
                                 color=TEXT_MUTED, size_hint_y=None, height=dp(18)))
        card.add_widget(AppLabel(text=money(summary["total_balance"]),
                                 bold=True, font_size=sp(30),
                                 size_hint_y=None, height=dp(42)))
        month_row = BoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(24))
        month_row.add_widget(AppLabel(
            text=f"本月收入 +{money(summary['monthly_income'])}",
            font_size=sp(13), color=rgba(INCOME)))
        month_row.add_widget(AppLabel(
            text=f"本月支出 -{money(summary['monthly_expense'])}",
            font_size=sp(13), color=rgba(EXPENSE), halign="right"))
        card.add_widget(month_row)
        self.column.add_widget(card)

        # quick actions
        actions = BoxLayout(orientation="horizontal", spacing=dp(10),
                            size_hint_y=None, height=dp(48))
        actions.add_widget(primary_button(
            "记支出", on_press=lambda: self._open_add("expense"), color=EXPENSE))
        actions.add_widget(primary_button(
            "记收入", on_press=lambda: self._open_add("income"), color=INCOME))
        actions.add_widget(primary_button(
            "攒钱", on_press=lambda: self.go("savings"), color=PRIMARY))
        self.column.add_widget(actions)

        # pending confirmations
        pendings = self.db.get_pending_confirmations(ConfirmationStatus.PENDING)
        self.column.add_widget(AppLabel(
            text=f"待确认（{len(pendings)}）", bold=True, font_size=sp(15),
            size_hint_y=None, height=dp(28)))
        if not pendings:
            self.column.add_widget(EmptyHint("暂无自动识别的待确认记录"))
        for pending in pendings[:5]:
            ocr = pending.ocr_result
            kind = "expense" if ocr.parsed_type == TransactionType.EXPENSE else "income"
            self.column.add_widget(PendingCard(
                amount=ocr.parsed_amount or 0,
                kind=kind,
                merchant=ocr.parsed_merchant,
                source=ocr.source_app or "手动导入",
                category=self.category_name(pending.suggested_category_id)
                if pending.suggested_category_id else "未分类",
                account=self.account_name(pending.suggested_account_id),
                confidence=ocr.confidence,
                on_confirm=lambda p=pending: self._confirm(p),
                on_reject=lambda p=pending: self._reject(p),
            ))

        # savings
        plans = self.savings.get_active_plans()
        head = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(28))
        head.add_widget(AppLabel(text=f"攒钱计划（{len(plans)}）", bold=True,
                                 font_size=sp(15)))
        head.add_widget(AppButton(text="管理", bg_color="#E5E7EB", color=TEXT,
                                  size_hint_x=None, width=dp(70),
                                  height=dp(30), font_size=sp(13)))
        head.children[0].bind(on_press=lambda *_: self.go("savings"))
        self.column.add_widget(head)
        if not plans:
            self.column.add_widget(EmptyHint("还没有攒钱计划，去建一个吧"))
        for plan in plans[:3]:
            self.column.add_widget(ProgressCard(
                name=plan.name, current=plan.current_amount,
                target=plan.target_amount, color=INCOME,
                on_add=lambda p=plan: self.go("savings")))

        # recent transactions
        recent = self.transactions.get_recent_transactions(8)
        self.column.add_widget(AppLabel(text="最近交易", bold=True,
                                        font_size=sp(15), size_hint_y=None,
                                        height=dp(28)))
        if not recent:
            self.column.add_widget(EmptyHint("还没有交易记录"))
        for txn in recent:
            cat = self.categories.get_category(txn.category_id)
            color = EXPENSE if txn.type == TransactionType.EXPENSE else INCOME
            sign = "-" if txn.type == TransactionType.EXPENSE else "+"
            self.column.add_widget(ListRow(
                title=txn.description or (cat.name if cat else "未分类"),
                subtitle=f"{txn.date:%m-%d %H:%M} · {self.account_name(txn.account_id)}",
                value=f"{sign}{money(txn.amount)}", value_color=rgba(color),
                badge_text=(cat.name[:1] if cat else "?"),
                badge_color=cat.color if cat else "#9CA3AF",
            ))

        if recent:
            more = AppButton(text="查看全部交易", bg_color="#E5E7EB", color=TEXT)
            more.bind(on_press=lambda *_: self.go("transactions"))
            self.column.add_widget(more)

    def _open_add(self, mode):
        screen = self.manager.get_screen("add_txn")
        screen.set_mode(mode)
        self.go("add_txn")

    def _confirm(self, pending):
        txn = self.ocr.process_confirmation(pending.id)
        if txn:
            toast("已记账：" + money(txn.amount))
        else:
            toast("确认失败：缺少分类或账户信息")
        self.refresh()

    def _reject(self, pending):
        self.ocr.reject_confirmation(pending.id)
        self.refresh()


# -------------------------------------------------------------- 记一笔 ---
class AddTransactionScreen(BaseScreen):
    name = "add_txn"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mode = "expense"
        self.header = HeaderBar("记一笔", on_back=lambda: self.go("home"))
        self.set_header(self.header)

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

        self.seg = Segmented(["支出", "收入"], selected="支出",
                             on_change=self._on_seg)
        self.column.add_widget(self.seg)

        self.amount = Field("金额", hint="0.00", input_filter="float")
        self.column.add_widget(self.amount)

        self.desc = Field("备注", hint="例如：午餐、地铁、工资")
        self.column.add_widget(self.desc)

        self.category = Choice("分类", self.category_values(TransactionType.EXPENSE))
        self.column.add_widget(self.category)

        self.account = Choice("账户", self.account_values() or ["请先在设置中添加账户"])
        self.column.add_widget(self.account)
        default_acc = self.accounts.get_default_account()
        if default_acc:
            self.account.text = default_acc.name

        self.date_field = Field("日期", hint="YYYY-MM-DD",
                                text=datetime.now().strftime("%Y-%m-%d"))
        self.column.add_widget(self.date_field)

        self.save_btn = primary_button("保存", on_press=self.save)
        self.column.add_widget(self.save_btn)

    def set_mode(self, mode):
        self.mode = mode
        self.seg.select("支出" if mode == "expense" else "收入")

    def _current_type(self):
        return TransactionType.EXPENSE if self.mode == "expense" else TransactionType.INCOME

    def _on_seg(self, option):
        self.mode = "expense" if option == "支出" else "income"
        values = self.category_values(self._current_type())
        self.category.spinner.values = values
        if values:
            self.category.text = values[0]
        self.header.title_label.text = "记一笔支出" if self.mode == "expense" else "记一笔收入"
        self.save_btn.set_bg(EXPENSE if self.mode == "expense" else INCOME)

    def on_pre_enter(self, *args):
        accounts = self.account_values()
        self.account.spinner.values = accounts or ["请先在设置中添加账户"]
        values = self.category_values(self._current_type())
        self.category.spinner.values = values
        if values and self.category.text not in values:
            self.category.text = values[0]
        self.amount.text = ""
        self.desc.text = ""
        self.date_field.text = datetime.now().strftime("%Y-%m-%d")

    def save(self):
        if not self.accounts.get_all_accounts():
            toast("请先在设置中添加一个账户")
            return
        try:
            amount = float(self.amount.text)
        except ValueError:
            toast("请输入正确的金额")
            return
        if amount <= 0:
            toast("金额必须大于 0")
            return

        category_id = self.resolve_category(self.category.text, self._current_type())
        account_id = self.resolve_account(self.account.text)
        if not category_id or not account_id:
            toast("请选择分类和账户")
            return

        try:
            when = datetime.strptime(self.date_field.text, "%Y-%m-%d")
        except ValueError:
            when = datetime.now()

        self.transactions.create_transaction(
            account_id=account_id,
            amount=amount,
            type_=self._current_type(),
            category_id=category_id,
            date_=when,
            description=self.desc.text,
        )
        toast("已保存：" + money(amount))
        self.go("home")


# ------------------------------------------------------------ 交易列表 ---
class TransactionsScreen(BaseScreen):
    name = "transactions"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.filter_mode = "全部"
        self.set_header(
            HeaderBar("交易记录", on_back=lambda: self.go("home"))
        )

        self.seg = Segmented(["全部", "支出", "收入"], selected="全部",
                             on_change=self._on_filter)
        self.content.add_widget(self.seg)
        self.content.padding = [dp(12), dp(8)]

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

    def _on_filter(self, option):
        self.filter_mode = option
        self.refresh()

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.column.clear_widgets()
        type_filter = {
            "全部": None,
            "支出": TransactionType.EXPENSE,
            "收入": TransactionType.INCOME,
        }[self.filter_mode]

        rows = self.transactions.get_transactions(type_=type_filter, limit=300)
        if not rows:
            self.column.add_widget(EmptyHint("没有符合条件的记录"))
            return

        total_expense = sum(r.amount for r in rows if r.type == TransactionType.EXPENSE)
        total_income = sum(r.amount for r in rows if r.type == TransactionType.INCOME)
        summary = RoundedBox(orientation="horizontal", size_hint_y=None,
                             height=dp(54), padding=dp(12))
        summary.add_widget(AppLabel(
            text=f"共 {len(rows)} 笔", font_size=sp(13), color=TEXT_MUTED))
        summary.add_widget(AppLabel(
            text=f"支出 {money(total_expense)} / 收入 {money(total_income)}",
            font_size=sp(13), color=TEXT_MUTED, halign="right"))
        self.column.add_widget(summary)

        for txn in rows:
            cat = self.categories.get_category(txn.category_id)
            color = EXPENSE if txn.type == TransactionType.EXPENSE else INCOME
            sign = "-" if txn.type == TransactionType.EXPENSE else "+"
            row = ListRow(
                title=txn.description or (cat.name if cat else "未分类"),
                subtitle=f"{txn.date:%Y-%m-%d %H:%M} · {self.account_name(txn.account_id)}"
                         f" · {cat.name if cat else '未分类'}",
                value=f"{sign}{money(txn.amount)}", value_color=rgba(color),
                badge_text=(cat.name[:1] if cat else "?"),
                badge_color=cat.color if cat else "#9CA3AF",
            )
            row.bind(on_touch_down=lambda w, t, x=txn: self._maybe_delete(w, t, x))
            self.column.add_widget(row)

    def _maybe_delete(self, widget, touch, txn):
        if not widget.collide_point(*touch.pos):
            return False
        if touch.is_double_tap:
            self.transactions.delete_transaction(txn.id)
            toast("已删除该笔交易")
            Clock.schedule_once(lambda *_: self.refresh(), 0.05)
            return True
        return False


# -------------------------------------------------------------- 攒钱 ---
class SavingsScreen(BaseScreen):
    name = "savings"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_header(HeaderBar(
            "攒钱计划", on_back=lambda: self.go("home"),
            action_text="新建", on_action=lambda: self.go("add_savings")))

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.column.clear_widgets()
        plans = self.savings.get_all_plans()
        if not plans:
            self.column.add_widget(EmptyHint("还没有攒钱计划"))
            return

        total_saved = sum(p.current_amount for p in plans)
        total_target = sum(p.target_amount for p in plans)
        head = RoundedBox(orientation="horizontal", size_hint_y=None,
                          height=dp(54), padding=dp(12))
        head.add_widget(AppLabel(text=f"共 {len(plans)} 个计划",
                                 font_size=sp(13), color=TEXT_MUTED))
        head.add_widget(AppLabel(
            text=f"{money(total_saved)} / {money(total_target)}",
            font_size=sp(12), color=TEXT_MUTED, halign="right",
            size_hint_x=None, width=dp(200)))
        self.column.add_widget(head)

        for plan in plans:
            self.column.add_widget(ProgressCard(
                name=f"{plan.name}（{plan.status.label}）",
                current=plan.current_amount,
                target=plan.target_amount,
                color=INCOME if plan.status == SavingsPlanStatus.ACTIVE else "#9CA3AF",
                on_add=lambda p=plan: self._deposit(p),
            ))

    def _deposit(self, plan):
        def submit(text):
            try:
                amount = float(text)
            except ValueError:
                toast("请输入正确金额")
                return
            if amount <= 0:
                toast("金额必须大于 0")
                return
            self.savings.add_savings(plan.id, amount)
            toast(f"已向「{plan.name}」存入 {money(amount)}")
            self.refresh()

        text_prompt("存入攒钱计划", f"存入金额（当前 {money(plan.current_amount)}）",
                    submit, hint="0.00")


class AddSavingsScreen(BaseScreen):
    name = "add_savings"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_header(
            HeaderBar("新建攒钱计划", on_back=lambda: self.go("savings")))

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

        self.name_field = Field("计划名称", hint="例如：买手机、旅行基金")
        self.column.add_widget(self.name_field)

        self.target_field = Field("目标金额", hint="10000", input_filter="float")
        self.column.add_widget(self.target_field)

        self.current_field = Field("已存金额（可选）", hint="0", input_filter="float")
        self.column.add_widget(self.current_field)

        self.date_field = Field("目标日期（可选）", hint="YYYY-MM-DD")
        self.column.add_widget(self.date_field)

        self.account = Choice("关联账户（自动转入）",
                              ["不关联"] + self.account_values())
        self.column.add_widget(self.account)

        self.auto_field = Field("每期自动存入（可选）", hint="0", input_filter="float")
        self.column.add_widget(self.auto_field)

        self.freq = Choice("自动存入频率", [f.label for f in TaskFrequency]
                           if False else ["每月", "每周", "每天"])
        self.column.add_widget(self.freq)

        self.column.add_widget(primary_button("创建计划", on_press=self.save))

    def on_pre_enter(self, *args):
        self.account.spinner.values = ["不关联"] + self.account_values()
        self.name_field.text = ""
        self.target_field.text = ""
        self.current_field.text = ""
        self.date_field.text = ""
        self.auto_field.text = ""

    def save(self):
        name = self.name_field.text
        if not name:
            toast("请输入计划名称")
            return
        try:
            target = float(self.target_field.text)
        except ValueError:
            toast("请输入目标金额")
            return
        if target <= 0:
            toast("目标金额必须大于 0")
            return

        try:
            current = float(self.current_field.text) if self.current_field.text else 0.0
            auto = float(self.auto_field.text) if self.auto_field.text else 0.0
        except ValueError:
            toast("金额格式不正确")
            return

        target_date = None
        if self.date_field.text:
            try:
                target_date = datetime.strptime(self.date_field.text, "%Y-%m-%d").date()
            except ValueError:
                toast("日期格式应为 YYYY-MM-DD")
                return

        account_id = None
        if self.account.text and self.account.text != "不关联":
            account_id = self.resolve_account(self.account.text)

        freq_map = {"每月": "monthly", "每周": "weekly", "每天": "daily"}

        plan = self.savings.create_plan(
            name=name,
            target_amount=target,
            target_date=target_date,
            account_id=account_id,
            auto_transfer_amount=auto,
            auto_transfer_frequency=freq_map.get(self.freq.text, "monthly"),
        )
        if current > 0:
            self.savings.add_savings(plan.id, current)

        toast("计划已创建")
        self.go("savings")


# ---------------------------------------------------------- 定时任务 ---
class ScheduledScreen(BaseScreen):
    name = "scheduled"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_header(HeaderBar(
            "定时记账", on_back=lambda: self.go("home"),
            action_text="新建", on_action=lambda: self.go("add_task")))

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.column.clear_widgets()
        tasks = self.tasks.get_all_tasks()
        if not tasks:
            self.column.add_widget(EmptyHint(
                "还没有定时任务\n例如：每月 1 号自动记一笔房租"))
            return

        for task in tasks:
            cat = self.categories.get_category(task.category_id)
            color = EXPENSE if task.type == TransactionType.EXPENSE else INCOME
            sign = "-" if task.type == TransactionType.EXPENSE else "+"
            row = ListRow(
                title=f"{task.name}（{task.frequency.label} {task.execute_time:%H:%M}）",
                subtitle=f"{cat.name if cat else '未分类'} · "
                         f"{self.account_name(task.account_id)} · "
                         f"{'启用' if task.is_active else '已停用'}",
                value=f"{sign}{money(task.amount)}", value_color=rgba(color),
                badge_text="定", badge_color="#6B7280",
            )
            actions = BoxLayout(orientation="horizontal", spacing=dp(8),
                                size_hint_y=None, height=dp(38))
            toggle = AppButton(
                text="停用" if task.is_active else "启用",
                bg_color="#E5E7EB", color=TEXT, height=dp(36), font_size=sp(13))
            toggle.bind(on_press=lambda b, t=task: self._toggle(t))
            delete = AppButton(text="删除", bg_color="#FEE2E2", color=EXPENSE,
                               height=dp(36), font_size=sp(13))
            delete.bind(on_press=lambda b, t=task: self._delete(t))
            actions.add_widget(toggle)
            actions.add_widget(delete)

            wrapper = RoundedBox(orientation="vertical", size_hint_y=None,
                                 height=dp(112), padding=dp(8), spacing=dp(6))
            wrapper.add_widget(row)
            wrapper.add_widget(actions)
            self.column.add_widget(wrapper)

    def _toggle(self, task):
        self.tasks.toggle_task(task.id)
        self.refresh()

    def _delete(self, task):
        self.tasks.delete_task(task.id)
        toast("已删除定时任务")
        self.refresh()


class AddScheduledScreen(BaseScreen):
    name = "add_task"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_header(
            HeaderBar("新建定时任务", on_back=lambda: self.go("scheduled")))

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

        self.name_field = Field("任务名称", hint="例如：每月房租")
        self.column.add_widget(self.name_field)

        self.amount_field = Field("金额", hint="3000", input_filter="float")
        self.column.add_widget(self.amount_field)

        self.type_choice = Choice("类型", ["支出", "收入"])
        self.column.add_widget(self.type_choice)

        self.category = Choice("分类", self.category_values(TransactionType.EXPENSE))
        self.column.add_widget(self.category)

        self.account = Choice("账户", self.account_values() or ["请先添加账户"])
        self.column.add_widget(self.account)

        self.frequency = Choice("频率", ["每天", "每周", "每月", "每年", "一次性"])
        self.column.add_widget(self.frequency)

        self.time_field = Field("执行时间", hint="09:00", text="09:00")
        self.column.add_widget(self.time_field)

        self.column.add_widget(primary_button("创建任务", on_press=self.save))

    def on_pre_enter(self, *args):
        accounts = self.account_values()
        self.account.spinner.values = accounts or ["请先添加账户"]
        if accounts:
            default = self.accounts.get_default_account()
            self.account.text = default.name if default else accounts[0]
        self._refresh_categories()

        self.name_field.text = ""
        self.amount_field.text = ""
        self.time_field.text = "09:00"

    def _refresh_categories(self):
        txn_type = (TransactionType.EXPENSE if self.type_choice.text == "支出"
                    else TransactionType.INCOME)
        values = self.category_values(txn_type)
        self.category.spinner.values = values
        if values:
            self.category.text = values[0]
        return txn_type

    def save(self):
        name = self.name_field.text
        if not name:
            toast("请输入任务名称")
            return
        try:
            amount = float(self.amount_field.text)
        except ValueError:
            toast("请输入正确金额")
            return
        if amount <= 0:
            toast("金额必须大于 0")
            return

        txn_type = (TransactionType.EXPENSE if self.type_choice.text == "支出"
                    else TransactionType.INCOME)
        category_id = self.resolve_category(self.category.text, txn_type)
        account_id = self.resolve_account(self.account.text)
        if not category_id or not account_id:
            toast("请选择分类和账户")
            return

        freq_map = {
            "每天": TaskFrequency.DAILY,
            "每周": TaskFrequency.WEEKLY,
            "每月": TaskFrequency.MONTHLY,
            "每年": TaskFrequency.YEARLY,
            "一次性": TaskFrequency.ONCE,
        }
        try:
            hh, mm = self.time_field.text.split(":")
            exec_time = time(int(hh), int(mm))
        except Exception:
            toast("时间格式应为 HH:MM")
            return

        self.tasks.create_task(
            name=name, amount=amount, type_=txn_type,
            category_id=category_id, account_id=account_id,
            frequency=freq_map.get(self.frequency.text, TaskFrequency.MONTHLY),
            execute_time=exec_time,
        )
        toast("定时任务已创建")
        self.go("scheduled")


# -------------------------------------------------------------- 设置 ---
class SettingsScreen(BaseScreen):
    name = "settings"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_header(
            HeaderBar("设置", on_back=lambda: self.go("home")))

        self.scroll, self.column = scroll_column()
        self.content.add_widget(self.scroll)

    def on_pre_enter(self, *args):
        self.refresh()

    def refresh(self):
        self.column.clear_widgets()

        # accounts
        self.column.add_widget(AppLabel(text="账户", bold=True, font_size=sp(15),
                                        size_hint_y=None, height=dp(26)))
        accounts = self.accounts.get_all_accounts()
        if not accounts:
            self.column.add_widget(EmptyHint("还没有账户，先添加一个"))
        for acc in accounts:
            self.column.add_widget(ListRow(
                title=acc.name + ("（默认）" if acc.is_default else ""),
                subtitle=f"余额 {money(acc.balance)}",
                badge_text=acc.name[:1], badge_color=acc.color,
            ))
        add_acc = AppButton(text="＋ 添加账户", bg_color=PRIMARY)
        add_acc.bind(on_press=lambda *_: self._add_account())
        self.column.add_widget(add_acc)

        # categories
        self.column.add_widget(AppLabel(text="分类", bold=True, font_size=sp(15),
                                        size_hint_y=None, height=dp(26)))
        for txn_type, label in [(TransactionType.EXPENSE, "支出"),
                                (TransactionType.INCOME, "收入")]:
            cats = self.categories.get_categories_by_type(txn_type)
            self.column.add_widget(AppLabel(
                text=f"{label}分类（{len(cats)}）", font_size=sp(13),
                color=TEXT_MUTED, size_hint_y=None, height=dp(22)))
            for start in range(0, len(cats), 4):
                flow = BoxLayout(orientation="horizontal", spacing=dp(6),
                                 size_hint_y=None, height=dp(40))
                for cat in cats[start:start + 4]:
                    chip = RoundedBox(bg_color=cat.color, radius=dp(8),
                                      size_hint=(None, None), size=(dp(70), dp(34)),
                                      padding=[dp(2), 0])
                    chip.add_widget(AppLabel(text=cat.name, font_size=sp(11),
                                             color="#FFFFFF", halign="center"))
                    flow.add_widget(chip)
                flow.add_widget(BoxLayout())
                self.column.add_widget(flow)

        # scheduled tasks entry
        self.column.add_widget(AppLabel(text="自动化", bold=True, font_size=sp(15),
                                        size_hint_y=None, height=dp(26)))
        task_btn = AppButton(text="定时记账任务", bg_color="#E5E7EB", color=TEXT)
        task_btn.bind(on_press=lambda *_: self.go("scheduled"))
        self.column.add_widget(task_btn)

        # automatic capture: two channels
        self.column.add_widget(AppLabel(text="自动记账授权", bold=True,
                                        font_size=sp(15), size_hint_y=None,
                                        height=dp(26)))

        notif_box = RoundedBox(orientation="vertical", size_hint_y=None,
                               height=dp(104), padding=dp(12), spacing=dp(4))
        notif_box.add_widget(AppLabel(text="通知监听（推荐，微信/支付宝）",
                                      bold=True, font_size=sp(14)))
        notif_box.add_widget(AppLabel(text=self._notification_status(),
                                      font_size=sp(12), color=TEXT_MUTED))
        notif_btn = AppButton(text="打开通知使用权设置", bg_color=PRIMARY,
                              height=dp(38), font_size=sp(13))
        notif_btn.bind(on_press=lambda *_: self._open_notification())
        notif_box.add_widget(notif_btn)
        self.column.add_widget(notif_box)

        acc_box = RoundedBox(orientation="vertical", size_hint_y=None,
                             height=dp(104), padding=dp(12), spacing=dp(4))
        acc_box.add_widget(AppLabel(text="无障碍读屏（补充商户/分类）",
                                    bold=True, font_size=sp(14)))
        acc_box.add_widget(AppLabel(text=self._accessibility_status(),
                                    font_size=sp(12), color=TEXT_MUTED))
        open_btn = AppButton(text="打开无障碍设置", bg_color=PRIMARY, height=dp(38),
                             font_size=sp(13))
        open_btn.bind(on_press=lambda *_: self._open_accessibility())
        acc_box.add_widget(open_btn)
        self.column.add_widget(acc_box)

        # data
        self.column.add_widget(AppLabel(text="数据备份", bold=True,
                                        font_size=sp(15), size_hint_y=None,
                                        height=dp(26)))

        backup_box = RoundedBox(orientation="vertical", size_hint_y=None,
                                height=dp(258), padding=dp(14), spacing=dp(6))
        backup_box.add_widget(AppLabel(text="备份文件夹", bold=True,
                                       font_size=sp(14)))

        directory = self._backup_dir()
        backup_box.add_widget(AppLabel(text=self._short_path(directory),
                                       font_size=sp(12),
                                       color=TEXT_MUTED, size_hint_y=None,
                                       height=dp(34)))

        last = self._backup_config().get("last_backup") or "从未备份"
        backup_box.add_widget(AppLabel(text=f"上次备份：{self._pretty_time(last)}",
                                       font_size=sp(12), color=TEXT_MUTED,
                                       size_hint_y=None, height=dp(20)))

        actions_row = BoxLayout(orientation="horizontal", spacing=dp(8),
                                size_hint_y=None, height=dp(40))
        change_btn = AppButton(text="更改目录", bg_color="#E5E7EB", color=TEXT,
                               height=dp(38), font_size=sp(13))
        change_btn.bind(on_press=lambda *_: self._change_backup_dir())
        backup_btn = AppButton(text="立即备份", height=dp(38), font_size=sp(13))
        backup_btn.bind(on_press=lambda *_: self._backup_now())
        actions_row.add_widget(change_btn)
        actions_row.add_widget(backup_btn)
        backup_box.add_widget(actions_row)

        restore_btn = AppButton(text="从备份恢复", bg_color="#E5E7EB", color=TEXT,
                                height=dp(38), font_size=sp(13))
        restore_btn.bind(on_press=lambda *_: self._restore_backup())
        backup_box.add_widget(restore_btn)

        auto_on = bool(self._backup_config().get("auto", True))
        auto_btn = AppButton(
            text=f"自动备份：{'开（每 24 小时）' if auto_on else '关'}",
            bg_color=PRIMARY if auto_on else "#E5E7EB",
            color="#FFFFFF" if auto_on else TEXT,
            height=dp(38), font_size=sp(13))
        auto_btn.bind(on_press=lambda *_: self._toggle_auto_backup())
        backup_box.add_widget(auto_btn)
        self.column.add_widget(backup_box)

        export_btn = AppButton(text="导出交易记录（CSV）", bg_color="#E5E7EB", color=TEXT)
        export_btn.bind(on_press=lambda *_: self._export())
        self.column.add_widget(export_btn)

        info = RoundedBox(orientation="vertical", size_hint_y=None,
                          height=dp(76), padding=dp(12), spacing=dp(4))
        info.add_widget(AppLabel(text="离线可用", bold=True, font_size=sp(13)))
        info.add_widget(AppLabel(
            text="所有数据保存在本机 SQLite，无需联网即可记账、统计和运行定时任务。",
            font_size=sp(12), color=TEXT_MUTED))
        self.column.add_widget(info)

    # ---------------------------------------------------------- backups
    def _data_dir(self):
        from kivy.app import App

        app = App.get_running_app()
        return getattr(app, "data_dir", None) or app.user_data_dir

    def _db_path(self):
        return self.db.db_path

    def _backup_config(self):
        from core import backup

        return backup.load_config(self._data_dir())

    def _backup_dir(self):
        from core import backup

        return backup.resolved_dir(self._data_dir())

    @staticmethod
    def _short_path(path, limit=44):
        """Middle-truncate long paths so the card stays readable."""
        if not path:
            return ""
        if len(path) <= limit:
            return path
        head = path[:16]
        tail = path[-(limit - 17):]
        return f"{head}…{tail}"

    @staticmethod
    def _pretty_time(value):
        if not value:
            return "从未备份"
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return str(value)

    def _change_backup_dir(self):
        current = self._backup_dir()

        def submit(text):
            text = (text or "").strip()
            if not text:
                return
            try:
                os.makedirs(text, exist_ok=True)
            except Exception as exc:
                toast(f"这个路径不可用：{exc}")
                return
            from core import backup

            config = backup.load_config(self._data_dir())
            config["directory"] = text
            backup.save_config(self._data_dir(), config)
            toast("备份目录已更新")
            self.refresh()

        from .widgets import Field
        from kivy.uix.boxlayout import BoxLayout as _Box
        from kivy.uix.popup import Popup
        from core import backup as backup_mod

        content = _Box(orientation="vertical", padding=dp(16), spacing=dp(10))
        field = Field("备份文件夹路径", hint="例如 D:\\备份  或 /sdcard/Download",
                      text=current)
        content.add_widget(field)
        content.add_widget(AppLabel(
            text="默认建议：" + backup_mod.default_backup_dir(self._data_dir()),
            font_size=sp(11), color=TEXT_MUTED, size_hint_y=None, height=dp(30)))

        popup = Popup(title="更改备份目录", size_hint=(0.92, 0.5),
                      content=content, auto_dismiss=True)
        row = _Box(orientation="horizontal", spacing=dp(10),
                   size_hint_y=None, height=dp(44))
        cancel = AppButton(text="取消", bg_color="#E5E7EB", color=TEXT)
        cancel.bind(on_press=lambda *_: popup.dismiss())
        ok = AppButton(text="保存")
        ok.bind(on_press=lambda *_: (popup.dismiss(), submit(field.text)))
        row.add_widget(cancel)
        row.add_widget(ok)
        content.add_widget(row)
        popup.open()

    def _backup_now(self):
        from core import backup

        try:
            path = backup.backup_now(
                self._db_path(), self._data_dir(),
                include_csv=bool(self._backup_config().get("include_csv", True)))
        except Exception as exc:
            toast(f"备份失败：{exc}")
            return
        size_kb = os.path.getsize(path) / 1024 if os.path.exists(path) else 0
        toast(f"已备份（{size_kb:.0f} KB）\n{path}")
        self.refresh()

    def _restore_backup(self):
        from core import backup
        from kivy.uix.popup import Popup
        from kivy.uix.scrollview import ScrollView

        directory = self._backup_dir()
        items = backup.list_backups(directory)
        if not items:
            toast(f"这个文件夹里没有备份：\n{directory}")
            return

        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        content.add_widget(AppLabel(
            text=f"共 {len(items)} 个备份，点选一个恢复（当前数据会先自动留底）",
            font_size=sp(12), color=TEXT_MUTED, size_hint_y=None, height=dp(32)))

        scroll = ScrollView(do_scroll_x=False)
        listing = BoxLayout(orientation="vertical", size_hint_y=None,
                            spacing=dp(6))
        listing.bind(minimum_height=listing.setter("height"))

        popup = Popup(title="从备份恢复", size_hint=(0.94, 0.72),
                      content=content, auto_dismiss=True)

        def do_restore(path, when):
            popup.dismiss()
            ok, message = backup.restore(self._db_path(), path,
                                         self._data_dir())
            if not ok:
                toast(f"恢复失败：{message}")
                return
            toast(f"已恢复到 {when} 的数据")
            self.refresh()

        for item in items:
            when = item["mtime"].strftime("%Y-%m-%d %H:%M")
            size_kb = item["size"] / 1024
            row = AppButton(
                text=f"{when}   （{size_kb:.0f} KB）",
                bg_color="#EEF1F6", color=TEXT, height=dp(42),
                font_size=sp(13))
            row.bind(on_press=lambda b, p=item["path"], w=when: do_restore(p, w))
            listing.add_widget(row)

        scroll.add_widget(listing)
        content.add_widget(scroll)

        close = AppButton(text="关闭", bg_color="#E5E7EB", color=TEXT)
        close.bind(on_press=lambda *_: popup.dismiss())
        content.add_widget(close)
        popup.open()

    def _notification_status(self):
        try:
            from android_bridge import IS_ANDROID, check_notification_permission
        except Exception:
            return "当前为桌面环境，通知监听仅在 Android 上生效"

        if not IS_ANDROID:
            return "当前为桌面环境，通知监听仅在 Android 上生效"
        return ("已开启：可从支付通知里读到金额"
                if check_notification_permission() else
                "未开启：在系统设置里允许本应用读取通知")

    def _open_notification(self):
        try:
            from android_bridge import open_notification_settings
            open_notification_settings()
        except Exception:
            toast("该功能仅在 Android 设备上可用")

    def _accessibility_status(self):
        try:
            from android_bridge import IS_ANDROID, check_accessibility_permission
        except Exception:
            return "当前为桌面环境，无障碍自动识别仅在 Android 上生效"

        if not IS_ANDROID:
            return "当前为桌面环境，无障碍自动识别仅在 Android 上生效"
        return ("已开启：可自动识别支付页面"
                if check_accessibility_permission() else
                "未开启：需在系统设置中授权本应用的无障碍服务")

    def _open_accessibility(self):
        try:
            from android_bridge import open_accessibility_settings
            open_accessibility_settings()
        except Exception:
            toast("该功能仅在 Android 设备上可用")

    def _add_account(self):
        title = "添加账户"
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
        name_field = Field("账户名称", hint="支付宝 / 微信 / 银行卡")
        balance_field = Field("初始余额", hint="0", input_filter="float")
        content.add_widget(name_field)
        content.add_widget(balance_field)

        from kivy.uix.popup import Popup

        popup = Popup(title=title, size_hint=(0.9, 0.55), content=content,
                      auto_dismiss=True)

        def submit():
            name = name_field.text
            if not name:
                toast("请输入账户名称")
                return
            try:
                balance = float(balance_field.text) if balance_field.text else 0.0
            except ValueError:
                toast("余额格式不正确")
                return
            is_first = len(self.accounts.get_all_accounts()) == 0
            self.accounts.create_account(name=name, balance=balance,
                                         is_default=is_first)
            popup.dismiss()
            toast("账户已添加")
            self.refresh()

        row = BoxLayout(orientation="horizontal", spacing=dp(10),
                        size_hint_y=None, height=dp(44))
        cancel = AppButton(text="取消", bg_color="#E5E7EB", color=TEXT)
        cancel.bind(on_press=lambda *_: popup.dismiss())
        ok = AppButton(text="保存")
        ok.bind(on_press=lambda *_: submit())
        row.add_widget(cancel)
        row.add_widget(ok)
        content.add_widget(row)
        popup.open()

    def _export(self):
        try:
            from kivy.app import App

            rows = self.transactions.get_transactions(limit=100000)
            app = App.get_running_app()
            data_dir = getattr(app, "data_dir", None) or app.user_data_dir
            target_dir = os.path.join(data_dir, "exports")
            os.makedirs(target_dir, exist_ok=True)
            path = os.path.join(target_dir,
                                f"transactions_{datetime.now():%Y%m%d_%H%M%S}.csv")
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(["日期", "类型", "金额", "分类", "账户", "备注", "来源"])
                for txn in rows:
                    writer.writerow([
                        txn.date.strftime("%Y-%m-%d %H:%M"),
                        "支出" if txn.type == TransactionType.EXPENSE else "收入",
                        f"{txn.amount:.2f}",
                        self.category_name(txn.category_id),
                        self.account_name(txn.account_id),
                        txn.description,
                        txn.source,
                    ])
            toast(f"已导出 {len(rows)} 条记录到\n{path}")
        except Exception as exc:
            toast(f"导出失败：{exc}")
