"""
Core business logic services for Auto Account App
"""
import re
import uuid
from datetime import datetime, date, time, timedelta
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

from core.database import Database, get_database
from models import (
    Account,
    Transaction,
    TransactionType,
    Category,
    SavingsPlan,
    SavingsPlanStatus,
    ScheduledTask,
    TaskFrequency,
    OCRResult,
    PendingConfirmation,
    ConfirmationStatus,
    DEFAULT_EXPENSE_CATEGORIES,
    DEFAULT_INCOME_CATEGORIES,
)


class AccountService:
    """Service for account management"""

    def __init__(self, db: Database = None):
        self.db = db or get_database()

    def create_account(self, name: str, balance: float = 0.0, icon: str = "wallet",
                       color: str = "#2196F3", is_default: bool = False) -> Account:
        account = Account(
            name=name,
            balance=balance,
            icon=icon,
            color=color,
            is_default=is_default
        )
        return self.db.create_account(account)

    def get_account(self, account_id: str) -> Optional[Account]:
        return self.db.get_account(account_id)

    def get_all_accounts(self) -> List[Account]:
        return self.db.get_all_accounts()

    def get_default_account(self) -> Optional[Account]:
        return self.db.get_default_account()

    def update_account(self, account: Account) -> Account:
        return self.db.update_account(account)

    def delete_account(self, account_id: str) -> bool:
        return self.db.delete_account(account_id)

    def set_default_account(self, account_id: str) -> Optional[Account]:
        accounts = self.get_all_accounts()
        for acc in accounts:
            acc.is_default = (acc.id == account_id)
            self.db.update_account(acc)
        return self.get_account(account_id)

    def adjust_balance(self, account_id: str, delta: float) -> Optional[Account]:
        account = self.get_account(account_id)
        if account:
            account.update_balance(delta)
            return self.update_account(account)
        return None


class CategoryService:
    """Service for category management"""

    def __init__(self, db: Database = None):
        self.db = db or get_database()

    def create_category(self, name: str, type_: TransactionType, icon: str = "category",
                        color: str = "#9E9E9E", parent_id: str = None, sort_order: int = 0) -> Category:
        category = Category(
            name=name,
            type=type_,
            icon=icon,
            color=color,
            parent_id=parent_id,
            sort_order=sort_order
        )
        return self.db.create_category(category)

    def get_category(self, category_id: str) -> Optional[Category]:
        return self.db.get_category(category_id)

    def get_categories_by_type(self, type_: TransactionType) -> List[Category]:
        return self.db.get_categories_by_type(type_)

    def get_all_categories(self) -> List[Category]:
        return self.db.get_all_categories()

    def update_category(self, category: Category) -> Category:
        return self.db.update_category(category)

    def delete_category(self, category_id: str) -> bool:
        return self.db.delete_category(category_id)

    def find_category_by_name(self, name: str, type_: TransactionType) -> Optional[Category]:
        """Find category by name (fuzzy match)"""
        categories = self.get_categories_by_type(type_)
        name_lower = name.lower()
        for cat in categories:
            if cat.name.lower() == name_lower or name_lower in cat.name.lower():
                return cat
        return None


class TransactionService:
    """Service for transaction management"""

    def __init__(self, db: Database = None):
        self.db = db or get_database()

    def create_transaction(self, account_id: str, amount: float, type_: TransactionType,
                           category_id: str, date_: datetime, description: str = "",
                           source: str = "manual", ocr_raw_text: str = "", confidence: float = 1.0) -> Transaction:
        transaction = Transaction(
            account_id=account_id,
            amount=amount,
            type=type_,
            category_id=category_id,
            date=date_,
            description=description,
            source=source,
            ocr_raw_text=ocr_raw_text,
            confidence=confidence
        )
        return self.db.create_transaction(transaction)

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        return self.db.get_transaction(transaction_id)

    def get_transactions(self, **filters) -> List[Transaction]:
        return self.db.get_transactions(**filters)

    def get_recent_transactions(self, limit: int = 20) -> List[Transaction]:
        return self.db.get_transactions(limit=limit)

    def update_transaction(self, transaction: Transaction) -> Transaction:
        return self.db.update_transaction(transaction)

    def delete_transaction(self, transaction_id: str) -> bool:
        return self.db.delete_transaction(transaction_id)

    def get_monthly_summary(self, year: int, month: int) -> Dict[str, Any]:
        """Get income/expense summary for a month"""
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        
        transactions = self.db.get_transactions(start_date=start, end_date=end)
        
        income = sum(t.amount for t in transactions if t.type == TransactionType.INCOME)
        expense = sum(t.amount for t in transactions if t.type == TransactionType.EXPENSE)
        
        return {
            "income": income,
            "expense": expense,
            "net": income - expense,
            "transaction_count": len(transactions),
        }

    def get_category_stats(self, type_: TransactionType, start_date: date, end_date: date) -> List[Dict]:
        return self.db.get_category_stats(type_, start_date, end_date)

    def get_balance_summary(self) -> Dict[str, Any]:
        return self.db.get_balance_summary()


class SavingsPlanService:
    """Service for savings plan management"""

    def __init__(self, db: Database = None, account_service: AccountService = None):
        self.db = db or get_database()
        self.account_service = account_service or AccountService(db)

    def create_plan(self, name: str, target_amount: float, target_date: date = None,
                    account_id: str = None, auto_transfer_amount: float = 0.0,
                    auto_transfer_frequency: str = "monthly", icon: str = "savings",
                    color: str = "#4CAF50", description: str = "") -> SavingsPlan:
        plan = SavingsPlan(
            name=name,
            target_amount=target_amount,
            target_date=target_date,
            account_id=account_id,
            auto_transfer_amount=auto_transfer_amount,
            auto_transfer_frequency=auto_transfer_frequency,
            icon=icon,
            color=color,
            description=description
        )
        return self.db.create_savings_plan(plan)

    def get_plan(self, plan_id: str) -> Optional[SavingsPlan]:
        return self.db.get_savings_plan(plan_id)

    def get_all_plans(self, status: SavingsPlanStatus = None) -> List[SavingsPlan]:
        return self.db.get_all_savings_plans(status)

    def get_active_plans(self) -> List[SavingsPlan]:
        return self.get_all_plans(SavingsPlanStatus.ACTIVE)

    def update_plan(self, plan: SavingsPlan) -> SavingsPlan:
        return self.db.update_savings_plan(plan)

    def delete_plan(self, plan_id: str) -> bool:
        return self.db.delete_savings_plan(plan_id)

    def add_savings(self, plan_id: str, amount: float) -> Optional[SavingsPlan]:
        plan = self.get_plan(plan_id)
        if plan:
            plan.add_savings(amount)
            return self.update_plan(plan)
        return None

    def withdraw_savings(self, plan_id: str, amount: float) -> Optional[SavingsPlan]:
        plan = self.get_plan(plan_id)
        if plan:
            plan.withdraw(amount)
            return self.update_plan(plan)
        return None

    def process_auto_transfers(self) -> List[Tuple[SavingsPlan, Transaction]]:
        """Process automatic transfers for savings plans"""
        results = []
        plans = self.get_active_plans()
        for plan in plans:
            if plan.auto_transfer_amount > 0 and plan.account_id:
                # Check if it's time to transfer (simplified - daily check)
                # In production, you'd check based on frequency and last transfer date
                account = self.account_service.get_account(plan.account_id)
                if account and account.balance >= plan.auto_transfer_amount:
                    # Create transaction
                    txn_service = TransactionService(self.db)
                    category = self._get_or_create_savings_category()
                    txn = txn_service.create_transaction(
                        account_id=plan.account_id,
                        amount=plan.auto_transfer_amount,
                        type_=TransactionType.EXPENSE,
                        category_id=category.id,
                        date_=datetime.now(),
                        description=f"自动存入：{plan.name}",
                        source="auto_savings"
                    )
                    plan.add_savings(plan.auto_transfer_amount)
                    self.update_plan(plan)
                    results.append((plan, txn))
        return results

    def _get_or_create_savings_category(self) -> Category:
        cat_service = CategoryService(self.db)
        cat = cat_service.find_category_by_name("储蓄", TransactionType.EXPENSE)
        if not cat:
            cat = cat_service.create_category("储蓄", TransactionType.EXPENSE, "savings", "#4CAF50")
        return cat


class ScheduledTaskService:
    """Service for scheduled task management"""

    def __init__(self, db: Database = None, transaction_service: TransactionService = None):
        self.db = db or get_database()
        self.transaction_service = transaction_service or TransactionService(db)

    def create_task(self, name: str, amount: float, type_: TransactionType,
                    category_id: str, account_id: str, frequency: TaskFrequency,
                    execute_time: time, start_date: date = None, end_date: date = None,
                    description: str = "") -> ScheduledTask:
        if start_date is None:
            start_date = date.today()
        
        task = ScheduledTask(
            name=name,
            amount=amount,
            type=type_,
            category_id=category_id,
            account_id=account_id,
            frequency=frequency,
            execute_time=execute_time,
            start_date=start_date,
            end_date=end_date,
            description=description
        )
        return self.db.create_scheduled_task(task)

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        return self.db.get_scheduled_task(task_id)

    def get_all_tasks(self, active_only: bool = False) -> List[ScheduledTask]:
        return self.db.get_all_scheduled_tasks(active_only)

    def update_task(self, task: ScheduledTask) -> ScheduledTask:
        return self.db.update_scheduled_task(task)

    def delete_task(self, task_id: str) -> bool:
        return self.db.delete_scheduled_task(task_id)

    def toggle_task(self, task_id: str) -> Optional[ScheduledTask]:
        task = self.get_task(task_id)
        if task:
            task.is_active = not task.is_active
            return self.update_task(task)
        return None

    def process_due_tasks(self, now: datetime = None) -> List[Tuple[ScheduledTask, Transaction]]:
        """Process all due scheduled tasks"""
        if now is None:
            now = datetime.now()
        
        due_tasks = self.db.get_due_scheduled_tasks(now)
        results = []
        
        for task in due_tasks:
            try:
                txn = self.transaction_service.create_transaction(
                    account_id=task.account_id,
                    amount=task.amount,
                    type_=task.type,
                    category_id=task.category_id,
                    date_=now,
                    description=f"定时任务：{task.name}",
                    source="scheduled"
                )
                task.mark_executed(now)
                self.update_task(task)
                results.append((task, txn))
            except Exception as e:
                print(f"Failed to execute scheduled task {task.id}: {e}")
        
        return results


class OCRService:
    """Service for OCR processing and transaction extraction"""

    # Common patterns for Chinese payment apps
    AMOUNT_PATTERNS = [
        r'[¥￥]\s*(\d+(?:\.\d{1,2})?)',
        r'(\d+(?:\.\d{1,2})?)\s*[元￥¥]',
        r'金额[：:]\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)',
        r'支付[：:]\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)',
        r'收款[：:]\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)',
        r'转账[：:]\s*[¥￥]?\s*(\d+(?:\.\d{1,2})?)',
    ]
    
    EXPENSE_KEYWORDS = ['支付', '付款', '消费', '扣款', '转出', '发红包', '充值', '缴费']
    INCOME_KEYWORDS = ['收款', '转入', '收到', '红包收入', '退款', '工资', '到账']
    
    CATEGORY_KEYWORDS = {
        '餐饮': ['餐', '饭', '吃', '外卖', '美团', '饿了么', '肯德基', '麦当劳', '星巴克', '咖啡', '奶茶'],
        '交通': ['打车', '滴滴', '高德', '地铁', '公交', '火车', '飞机', '机票', '打车', '共享单车', '加油'],
        '购物': ['淘宝', '京东', '拼多多', '购物', '超市', '便利店', '商场', '天猫', '唯品会'],
        '娱乐': ['电影', '游戏', '网易云', 'QQ音乐', '爱奇艺', '腾讯视频', 'B站', '哔哩哔哩', '会员'],
        '医疗': ['医院', '药店', '挂号', '体检', '买药', '药房', '诊所'],
        '教育': ['培训', '课程', '书籍', '教材', '学费', '考试', '证书'],
        '居住': ['房租', '水费', '电费', '燃气费', '物业费', '宽带', '网费', '房贷'],
        '通讯': ['话费', '流量', '宽带', '移动', '联通', '电信', '充值'],
    }

    def __init__(self, db: Database = None, category_service: CategoryService = None,
                 account_service: AccountService = None):
        self.db = db or get_database()
        self.category_service = category_service or CategoryService(db)
        self.account_service = account_service or AccountService(db)

    def parse_screen_text(self, text: str, source_app: str = "") -> OCRResult:
        """Parse OCR text and extract transaction info"""
        result = OCRResult(
            raw_text=text,
            source_app=source_app.lower(),
            captured_at=datetime.now()
        )
        
        # Extract amount
        result.parsed_amount = self._extract_amount(text)
        
        # Determine transaction type
        result.parsed_type = self._determine_type(text, source_app)
        
        # Extract merchant/description
        result.parsed_merchant = self._extract_merchant(text, source_app)
        
        # Determine category
        result.parsed_category = self._determine_category(text, result.parsed_type)
        
        # Calculate confidence
        result.confidence = self._calculate_confidence(result)
        
        return result

    def _extract_amount(self, text: str) -> Optional[float]:
        for pattern in self.AMOUNT_PATTERNS:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        return None

    def _determine_type(self, text: str, source_app: str) -> Optional[TransactionType]:
        text_lower = text.lower()
        
        # App-specific heuristics
        if source_app in ['alipay', 'wechat']:
            if any(kw in text for kw in ['收款', '转入', '红包收入', '到账', '收到']):
                return TransactionType.INCOME
            if any(kw in text for kw in ['支付', '付款', '转账', '发红包', '充值', '缴费']):
                return TransactionType.EXPENSE
        
        # General keywords
        expense_score = sum(1 for kw in self.EXPENSE_KEYWORDS if kw in text)
        income_score = sum(1 for kw in self.INCOME_KEYWORDS if kw in text)
        
        if expense_score > income_score:
            return TransactionType.EXPENSE
        elif income_score > expense_score:
            return TransactionType.INCOME
        
        return None

    #: tokens that look like labels rather than merchant names
    _NOISE_TOKENS = {
        "支付", "付款", "收款", "转账", "消费", "扣款", "充值", "缴费",
        "成功", "完成", "订单", "订单号", "金额", "元", "余额", "详情", "账单",
        "支出", "收入", "来自", "给", "向", "共", "笔", "已", "成功支付",
    }

    _APP_NAMES = {
        "支付宝", "微信", "微信支付", "云闪付", "钉钉", "QQ", "手机银行",
        "中国银行", "工商银行", "招商银行", "建设银行", "农业银行", "交通银行",
    }

    def _looks_like_merchant(self, token: str) -> bool:
        if not token or token in self._NOISE_TOKENS:
            return False
        if re.search(r"\d", token) or token.endswith(("元", "¥", "￥")):
            return False
        if token in self.CATEGORY_KEYWORDS:
            return False
        return True

    def _extract_merchant(self, text: str, source_app: str) -> Optional[str]:
        # Try to find merchant name in common patterns
        patterns = [
            r'商户[：:]\s*([^\n\r]+)',
            r'收款方[：:]\s*([^\n\r]+)',
            r'付款方[：:]\s*([^\n\r]+)',
            r'对方[：:]\s*([^\n\r]+)',
            r'来自[：:]?\s*([^\s，,。]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip()
                if value:
                    return value

        # Heuristics based on the flat text layout of payment screens:
        # "支付宝 支付 38.50元 餐饮 肯德基 ..." -> merchant is the token right
        # after the category word (or the verb).
        parts = [p.strip("，,。:：") for p in text.split()]

        for i, token in enumerate(parts):
            if token in self.CATEGORY_KEYWORDS:
                for candidate in parts[i + 1:]:
                    if self._looks_like_merchant(candidate):
                        return candidate

        for i, token in enumerate(parts):
            if token in ("支付", "付款", "收款", "转账", "消费"):
                for candidate in parts[i + 1:]:
                    if self._looks_like_merchant(candidate):
                        return candidate

        # Generic heuristic: first meaningful token that is not a label/number
        for token in parts:
            if self._looks_like_merchant(token) and token not in self._APP_NAMES:
                return token

        return None

    def _determine_category(self, text: str, type_: Optional[TransactionType]) -> Optional[str]:
        if not type_:
            return None
        
        text_lower = text.lower()
        categories = self.category_service.get_categories_by_type(type_)
        
        # Check keyword mapping
        for cat_name, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                for cat in categories:
                    if cat.name == cat_name:
                        return cat.id
        
        # Fallback: try to match category name in text
        for cat in categories:
            if cat.name in text:
                return cat.id
        
        return None

    def _calculate_confidence(self, result: OCRResult) -> float:
        confidence = 0.0
        if result.parsed_amount:
            confidence += 0.4
        if result.parsed_type:
            confidence += 0.3
        if result.parsed_category:
            confidence += 0.2
        if result.parsed_merchant:
            confidence += 0.1
        return min(confidence, 1.0)

    def create_pending_confirmation(self, ocr_result: OCRResult, 
                                    suggested_account_id: str = None) -> PendingConfirmation:
        """Create a pending confirmation from OCR result"""
        if suggested_account_id is None:
            default_acc = self.account_service.get_default_account()
            suggested_account_id = default_acc.id if default_acc else ""
        
        suggested_category_id = None
        if ocr_result.parsed_category:
            suggested_category_id = ocr_result.parsed_category
        
        # Expire after 1 hour
        expires_at = datetime.now() + timedelta(hours=1)
        
        pending = PendingConfirmation(
            ocr_result=ocr_result,
            suggested_account_id=suggested_account_id,
            suggested_category_id=suggested_category_id,
            expires_at=expires_at
        )
        
        return self.db.create_pending_confirmation(pending)

    def process_confirmation(self, pending_id: str, account_id: str = None, 
                             category_id: str = None) -> Optional[Transaction]:
        """Process a confirmed pending transaction"""
        pending = self.db.get_pending_confirmation(pending_id)
        if not pending or pending.status != ConfirmationStatus.PENDING:
            return None
        
        ocr = pending.ocr_result
        
        # Use provided or suggested values
        final_account_id = account_id or pending.suggested_account_id
        final_category_id = category_id or pending.suggested_category_id
        
        if not final_account_id or not final_category_id or not ocr.parsed_amount or not ocr.parsed_type:
            return None
        
        # Create transaction
        txn_service = TransactionService(self.db)
        transaction = txn_service.create_transaction(
            account_id=final_account_id,
            amount=ocr.parsed_amount,
            type_=ocr.parsed_type,
            category_id=final_category_id,
            date_=ocr.parsed_date or datetime.now(),
            description=ocr.parsed_merchant or ocr.raw_text[:50],
            source="auto",
            ocr_raw_text=ocr.raw_text,
            confidence=ocr.confidence
        )
        
        # Update pending status
        pending.confirm(account_id=final_account_id, category_id=final_category_id)
        self.db.update_pending_confirmation(pending)
        
        return transaction

    def reject_confirmation(self, pending_id: str) -> bool:
        """Reject a pending confirmation"""
        pending = self.db.get_pending_confirmation(pending_id)
        if pending and pending.status == ConfirmationStatus.PENDING:
            pending.reject()
            self.db.update_pending_confirmation(pending)
            return True
        return False

    def cleanup_expired_confirmations(self) -> int:
        """Mark expired confirmations"""
        pendings = self.db.get_pending_confirmations(ConfirmationStatus.PENDING)
        count = 0
        now = datetime.now()
        for pending in pendings:
            if pending.expires_at and pending.expires_at < now:
                pending.expire()
                self.db.update_pending_confirmation(pending)
                count += 1
        return count


class StatisticsService:
    """Service for statistics and reports"""

    def __init__(self, db: Database = None):
        self.db = db or get_database()

    def get_overview(self) -> Dict[str, Any]:
        """Get financial overview"""
        return self.db.get_balance_summary()

    def get_monthly_report(self, year: int, month: int) -> Dict[str, Any]:
        """Get detailed monthly report"""
        start = date(year, month, 1)
        if month == 12:
            end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        
        txn_service = TransactionService(self.db)
        summary = txn_service.get_monthly_summary(year, month)
        
        expense_stats = txn_service.get_category_stats(TransactionType.EXPENSE, start, end)
        income_stats = txn_service.get_category_stats(TransactionType.INCOME, start, end)
        
        return {
            "period": f"{year}-{month:02d}",
            "summary": summary,
            "expense_by_category": expense_stats,
            "income_by_category": income_stats,
        }

    def get_yearly_report(self, year: int) -> Dict[str, Any]:
        """Get yearly report"""
        months = []
        total_income = 0
        total_expense = 0
        
        for month in range(1, 13):
            report = self.get_monthly_report(year, month)
            months.append(report)
            total_income += report["summary"]["income"]
            total_expense += report["summary"]["expense"]
        
        return {
            "year": year,
            "total_income": total_income,
            "total_expense": total_expense,
            "net": total_income - total_expense,
            "months": months,
        }

    def get_savings_progress(self) -> List[Dict[str, Any]]:
        """Get all savings plans progress"""
        plan_service = SavingsPlanService(self.db)
        plans = plan_service.get_all_plans()
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "target_amount": p.target_amount,
                "current_amount": p.current_amount,
                "progress": p.progress,
                "remaining": p.remaining_amount,
                "days_remaining": p.days_remaining,
                "status": p.status.value,
                "icon": p.icon,
                "color": p.color,
            }
            for p in plans
        ]