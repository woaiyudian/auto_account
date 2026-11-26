"""
Database layer for Auto Account App
SQLite-based with async support for future migration
"""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime, date, time
from typing import List, Optional, Dict, Any
from pathlib import Path

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
    DEFAULT_CATEGORIES,
)


class Database:
    """Main database handler"""

    def __init__(self, db_path: str = "auto_account.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema"""
        with self.transaction() as conn:
            # Accounts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    balance REAL DEFAULT 0.0,
                    icon TEXT DEFAULT 'wallet',
                    color TEXT DEFAULT '#2196F3',
                    is_default INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Categories table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    icon TEXT DEFAULT 'category',
                    color TEXT DEFAULT '#9E9E9E',
                    parent_id TEXT,
                    sort_order INTEGER DEFAULT 0,
                    is_system INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (parent_id) REFERENCES categories(id)
                )
            """)

            # Transactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source TEXT DEFAULT 'manual',
                    ocr_raw_text TEXT DEFAULT '',
                    confidence REAL DEFAULT 1.0,
                    FOREIGN KEY (account_id) REFERENCES accounts(id),
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
            """)

            # Savings plans table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS savings_plans (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    target_amount REAL NOT NULL,
                    current_amount REAL DEFAULT 0.0,
                    start_date TEXT NOT NULL,
                    target_date TEXT,
                    account_id TEXT,
                    auto_transfer_amount REAL DEFAULT 0.0,
                    auto_transfer_frequency TEXT DEFAULT 'monthly',
                    status TEXT DEFAULT 'active',
                    icon TEXT DEFAULT 'savings',
                    color TEXT DEFAULT '#4CAF50',
                    description TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (account_id) REFERENCES accounts(id)
                )
            """)

            # Scheduled tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL,
                    category_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    execute_time TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    description TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    last_executed TEXT,
                    next_execution TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (category_id) REFERENCES categories(id),
                    FOREIGN KEY (account_id) REFERENCES accounts(id)
                )
            """)

            # Pending confirmations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pending_confirmations (
                    id TEXT PRIMARY KEY,
                    ocr_raw_text TEXT NOT NULL,
                    ocr_parsed_amount REAL,
                    ocr_parsed_type TEXT,
                    ocr_parsed_category TEXT,
                    ocr_parsed_merchant TEXT,
                    ocr_parsed_date TEXT,
                    ocr_confidence REAL DEFAULT 0.0,
                    ocr_source_app TEXT DEFAULT '',
                    ocr_screen_coords TEXT DEFAULT '{}',
                    ocr_captured_at TEXT NOT NULL,
                    suggested_account_id TEXT NOT NULL,
                    suggested_category_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    confirmed_at TEXT,
                    expires_at TEXT
                )
            """)

            # Settings table (key-value)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_active ON scheduled_tasks(is_active)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_confirmations(status)")

            # Insert default categories if not exist
            self._init_default_categories(conn)

    def _init_default_categories(self, conn: sqlite3.Connection) -> None:
        """Insert default system categories"""
        for cat in DEFAULT_CATEGORIES:
            existing = conn.execute("SELECT id FROM categories WHERE id = ?", (cat.id,)).fetchone()
            if not existing:
                conn.execute("""
                    INSERT INTO categories (id, name, type, icon, color, parent_id, sort_order, is_system, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cat.id, cat.name, cat.type.value, cat.icon, cat.color,
                    cat.parent_id, cat.sort_order, int(cat.is_system), cat.created_at.isoformat()
                ))

    # ==================== Account Operations ====================

    def create_account(self, account: Account) -> Account:
        with self.transaction() as conn:
            # If this is default, unset other defaults
            if account.is_default:
                conn.execute("UPDATE accounts SET is_default = 0 WHERE is_default = 1")
            
            conn.execute("""
                INSERT INTO accounts (id, name, balance, icon, color, is_default, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account.id, account.name, account.balance, account.icon,
                account.color, int(account.is_default),
                account.created_at.isoformat(), account.updated_at.isoformat()
            ))
        return account

    def get_account(self, account_id: str) -> Optional[Account]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
            if row:
                return self._row_to_account(row)
        return None

    def get_all_accounts(self) -> List[Account]:
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM accounts ORDER BY is_default DESC, created_at").fetchall()
            return [self._row_to_account(row) for row in rows]

    def get_default_account(self) -> Optional[Account]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM accounts WHERE is_default = 1 LIMIT 1").fetchone()
            if row:
                return self._row_to_account(row)
            # Fallback to first account
            row = conn.execute("SELECT * FROM accounts LIMIT 1").fetchone()
            if row:
                return self._row_to_account(row)
        return None

    def update_account(self, account: Account) -> Account:
        account.updated_at = datetime.now()
        with self.transaction() as conn:
            if account.is_default:
                conn.execute("UPDATE accounts SET is_default = 0 WHERE is_default = 1 AND id != ?", (account.id,))
            conn.execute("""
                UPDATE accounts SET name=?, balance=?, icon=?, color=?, is_default=?, updated_at=?
                WHERE id=?
            """, (
                account.name, account.balance, account.icon, account.color,
                int(account.is_default), account.updated_at.isoformat(), account.id
            ))
        return account

    def delete_account(self, account_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
            return cursor.rowcount > 0

    def _row_to_account(self, row: sqlite3.Row) -> Account:
        return Account(
            id=row["id"],
            name=row["name"],
            balance=row["balance"],
            icon=row["icon"],
            color=row["color"],
            is_default=bool(row["is_default"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ==================== Category Operations ====================

    def create_category(self, category: Category) -> Category:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO categories (id, name, type, icon, color, parent_id, sort_order, is_system, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                category.id, category.name, category.type.value, category.icon,
                category.color, category.parent_id, category.sort_order,
                int(category.is_system), category.created_at.isoformat()
            ))
        return category

    def get_category(self, category_id: str) -> Optional[Category]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
            if row:
                return self._row_to_category(row)
        return None

    def get_categories_by_type(self, type_: TransactionType) -> List[Category]:
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM categories WHERE type = ? ORDER BY sort_order, name",
                (type_.value,)
            ).fetchall()
            return [self._row_to_category(row) for row in rows]

    def get_all_categories(self) -> List[Category]:
        with self.transaction() as conn:
            rows = conn.execute("SELECT * FROM categories ORDER BY type, sort_order, name").fetchall()
            return [self._row_to_category(row) for row in rows]

    def update_category(self, category: Category) -> Category:
        with self.transaction() as conn:
            conn.execute("""
                UPDATE categories SET name=?, icon=?, color=?, parent_id=?, sort_order=?
                WHERE id=?
            """, (
                category.name, category.icon, category.color,
                category.parent_id, category.sort_order, category.id
            ))
        return category

    def delete_category(self, category_id: str) -> bool:
        with self.transaction() as conn:
            # Don't delete system categories
            row = conn.execute("SELECT is_system FROM categories WHERE id = ?", (category_id,)).fetchone()
            if row and row["is_system"]:
                return False
            cursor = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            return cursor.rowcount > 0

    def _row_to_category(self, row: sqlite3.Row) -> Category:
        return Category(
            id=row["id"],
            name=row["name"],
            type=TransactionType(row["type"]),
            icon=row["icon"],
            color=row["color"],
            parent_id=row["parent_id"],
            sort_order=row["sort_order"],
            is_system=bool(row["is_system"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # ==================== Transaction Operations ====================

    def create_transaction(self, transaction: Transaction) -> Transaction:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO transactions (id, account_id, amount, type, category_id, date, description,
                    created_at, updated_at, source, ocr_raw_text, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                transaction.id, transaction.account_id, transaction.amount,
                transaction.type.value, transaction.category_id,
                transaction.date.isoformat(), transaction.description,
                transaction.created_at.isoformat(), transaction.updated_at.isoformat(),
                transaction.source, transaction.ocr_raw_text, transaction.confidence
            ))
            # Update account balance
            self._update_account_balance(conn, transaction.account_id, transaction.signed_amount)
        return transaction

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            if row:
                return self._row_to_transaction(row)
        return None

    def get_transactions(
        self,
        account_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        type_: Optional[TransactionType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Transaction]:
        with self.transaction() as conn:
            query = "SELECT * FROM transactions WHERE 1=1"
            params = []
            if account_id:
                query += " AND account_id = ?"
                params.append(account_id)
            if category_id:
                query += " AND category_id = ?"
                params.append(category_id)
            if start_date:
                query += " AND date >= ?"
                params.append(start_date.isoformat())
            if end_date:
                query += " AND date <= ?"
                params.append(end_date.isoformat())
            if type_:
                query += " AND type = ?"
                params.append(type_.value)
            query += " ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_transaction(row) for row in rows]

    def update_transaction(self, transaction: Transaction) -> Transaction:
        transaction.updated_at = datetime.now()
        with self.transaction() as conn:
            # Get old transaction for balance adjustment
            old = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction.id,)).fetchone()
            if old:
                old_amount = old["amount"] * (1 if old["type"] == "income" else -1)
                new_amount = transaction.signed_amount
                diff = new_amount - old_amount
                if diff != 0:
                    self._update_account_balance(conn, transaction.account_id, diff)
            
            conn.execute("""
                UPDATE transactions SET account_id=?, amount=?, type=?, category_id=?, date=?, 
                    description=?, updated_at=?, source=?, ocr_raw_text=?, confidence=?
                WHERE id=?
            """, (
                transaction.account_id, transaction.amount, transaction.type.value,
                transaction.category_id, transaction.date.isoformat(),
                transaction.description, transaction.updated_at.isoformat(),
                transaction.source, transaction.ocr_raw_text, transaction.confidence,
                transaction.id
            ))
        return transaction

    def delete_transaction(self, transaction_id: str) -> bool:
        with self.transaction() as conn:
            row = conn.execute("SELECT account_id, amount, type FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            if row:
                amount = row["amount"] * (1 if row["type"] == "income" else -1)
                self._update_account_balance(conn, row["account_id"], -amount)
            cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
            return cursor.rowcount > 0

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        return Transaction(
            id=row["id"],
            account_id=row["account_id"],
            amount=row["amount"],
            type=TransactionType(row["type"]),
            category_id=row["category_id"],
            date=datetime.fromisoformat(row["date"]),
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            source=row["source"],
            ocr_raw_text=row["ocr_raw_text"],
            confidence=row["confidence"],
        )

    def _update_account_balance(self, conn: sqlite3.Connection, account_id: str, delta: float) -> None:
        conn.execute("UPDATE accounts SET balance = balance + ?, updated_at = ? WHERE id = ?",
                     (delta, datetime.now().isoformat(), account_id))

    # ==================== Statistics ====================

    def get_balance_summary(self) -> Dict[str, Any]:
        """Get total balance across all accounts"""
        with self.transaction() as conn:
            row = conn.execute("SELECT SUM(balance) as total FROM accounts").fetchone()
            total = row["total"] if row["total"] else 0.0
            
            # Monthly income/expense
            now = datetime.now()
            month_start = date(now.year, now.month, 1)
            if now.month == 12:
                month_end = date(now.year + 1, 1, 1)
            else:
                month_end = date(now.year, now.month + 1, 1)
            
            income_row = conn.execute("""
                SELECT SUM(amount) as total FROM transactions 
                WHERE type = 'income' AND date >= ? AND date < ?
            """, (month_start.isoformat(), month_end.isoformat())).fetchone()
            expense_row = conn.execute("""
                SELECT SUM(amount) as total FROM transactions 
                WHERE type = 'expense' AND date >= ? AND date < ?
            """, (month_start.isoformat(), month_end.isoformat())).fetchone()
            
            return {
                "total_balance": total,
                "monthly_income": income_row["total"] if income_row["total"] else 0.0,
                "monthly_expense": expense_row["total"] if expense_row["total"] else 0.0,
            }

    def get_category_stats(
        self,
        type_: TransactionType,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get spending/earning by category"""
        with self.transaction() as conn:
            rows = conn.execute("""
                SELECT c.name, c.icon, c.color, SUM(t.amount) as total, COUNT(*) as count
                FROM transactions t
                JOIN categories c ON t.category_id = c.id
                WHERE t.type = ? AND t.date >= ? AND t.date <= ?
                GROUP BY c.id
                ORDER BY total DESC
            """, (type_.value, start_date.isoformat(), end_date.isoformat())).fetchall()
            return [dict(row) for row in rows]

    # ==================== Savings Plan Operations ====================

    def create_savings_plan(self, plan: SavingsPlan) -> SavingsPlan:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO savings_plans (id, name, target_amount, current_amount, start_date, target_date,
                    account_id, auto_transfer_amount, auto_transfer_frequency, status, icon, color, description,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan.id, plan.name, plan.target_amount, plan.current_amount,
                plan.start_date.isoformat(), plan.target_date.isoformat() if plan.target_date else None,
                plan.account_id, plan.auto_transfer_amount, plan.auto_transfer_frequency,
                plan.status.value, plan.icon, plan.color, plan.description,
                plan.created_at.isoformat(), plan.updated_at.isoformat()
            ))
        return plan

    def get_savings_plan(self, plan_id: str) -> Optional[SavingsPlan]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM savings_plans WHERE id = ?", (plan_id,)).fetchone()
            if row:
                return self._row_to_savings_plan(row)
        return None

    def get_all_savings_plans(self, status: Optional[SavingsPlanStatus] = None) -> List[SavingsPlan]:
        with self.transaction() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM savings_plans WHERE status = ? ORDER BY created_at DESC",
                    (status.value,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM savings_plans ORDER BY created_at DESC").fetchall()
            return [self._row_to_savings_plan(row) for row in rows]

    def update_savings_plan(self, plan: SavingsPlan) -> SavingsPlan:
        plan.updated_at = datetime.now()
        with self.transaction() as conn:
            conn.execute("""
                UPDATE savings_plans SET name=?, target_amount=?, current_amount=?, target_date=?,
                    account_id=?, auto_transfer_amount=?, auto_transfer_frequency=?, status=?,
                    icon=?, color=?, description=?, updated_at=?
                WHERE id=?
            """, (
                plan.name, plan.target_amount, plan.current_amount,
                plan.target_date.isoformat() if plan.target_date else None,
                plan.account_id, plan.auto_transfer_amount, plan.auto_transfer_frequency,
                plan.status.value, plan.icon, plan.color, plan.description,
                plan.updated_at.isoformat(), plan.id
            ))
        return plan

    def delete_savings_plan(self, plan_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM savings_plans WHERE id = ?", (plan_id,))
            return cursor.rowcount > 0

    def _row_to_savings_plan(self, row: sqlite3.Row) -> SavingsPlan:
        return SavingsPlan(
            id=row["id"],
            name=row["name"],
            target_amount=row["target_amount"],
            current_amount=row["current_amount"],
            start_date=date.fromisoformat(row["start_date"]),
            target_date=date.fromisoformat(row["target_date"]) if row["target_date"] else None,
            account_id=row["account_id"],
            auto_transfer_amount=row["auto_transfer_amount"],
            auto_transfer_frequency=row["auto_transfer_frequency"],
            status=SavingsPlanStatus(row["status"]),
            icon=row["icon"],
            color=row["color"],
            description=row["description"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ==================== Scheduled Task Operations ====================

    def create_scheduled_task(self, task: ScheduledTask) -> ScheduledTask:
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO scheduled_tasks (id, name, amount, type, category_id, account_id,
                    frequency, execute_time, start_date, end_date, description, is_active,
                    last_executed, next_execution, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.id, task.name, task.amount, task.type.value, task.category_id, task.account_id,
                task.frequency.value, task.execute_time.isoformat(),
                task.start_date.isoformat(), task.end_date.isoformat() if task.end_date else None,
                task.description, int(task.is_active),
                task.last_executed.isoformat() if task.last_executed else None,
                task.next_execution.isoformat() if task.next_execution else None,
                task.created_at.isoformat(), task.updated_at.isoformat()
            ))
        return task

    def get_scheduled_task(self, task_id: str) -> Optional[ScheduledTask]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)).fetchone()
            if row:
                return self._row_to_scheduled_task(row)
        return None

    def get_all_scheduled_tasks(self, active_only: bool = False) -> List[ScheduledTask]:
        with self.transaction() as conn:
            if active_only:
                rows = conn.execute(
                    "SELECT * FROM scheduled_tasks WHERE is_active = 1 ORDER BY next_execution"
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC").fetchall()
            return [self._row_to_scheduled_task(row) for row in rows]

    def get_due_scheduled_tasks(self, now: datetime) -> List[ScheduledTask]:
        """Get tasks that should execute now"""
        with self.transaction() as conn:
            rows = conn.execute("""
                SELECT * FROM scheduled_tasks 
                WHERE is_active = 1 
                AND start_date <= ?
                AND (end_date IS NULL OR end_date >= ?)
            """, (now.date().isoformat(), now.date().isoformat())).fetchall()
            tasks = [self._row_to_scheduled_task(row) for row in rows]
            return [t for t in tasks if t.should_execute(now)]

    def update_scheduled_task(self, task: ScheduledTask) -> ScheduledTask:
        task.updated_at = datetime.now()
        with self.transaction() as conn:
            conn.execute("""
                UPDATE scheduled_tasks SET name=?, amount=?, type=?, category_id=?, account_id=?,
                    frequency=?, execute_time=?, start_date=?, end_date=?, description=?,
                    is_active=?, last_executed=?, next_execution=?, updated_at=?
                WHERE id=?
            """, (
                task.name, task.amount, task.type.value, task.category_id, task.account_id,
                task.frequency.value, task.execute_time.isoformat(),
                task.start_date.isoformat(), task.end_date.isoformat() if task.end_date else None,
                task.description, int(task.is_active),
                task.last_executed.isoformat() if task.last_executed else None,
                task.next_execution.isoformat() if task.next_execution else None,
                task.updated_at.isoformat(), task.id
            ))
        return task

    def delete_scheduled_task(self, task_id: str) -> bool:
        with self.transaction() as conn:
            cursor = conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0

    def _row_to_scheduled_task(self, row: sqlite3.Row) -> ScheduledTask:
        return ScheduledTask(
            id=row["id"],
            name=row["name"],
            amount=row["amount"],
            type=TransactionType(row["type"]),
            category_id=row["category_id"],
            account_id=row["account_id"],
            frequency=TaskFrequency(row["frequency"]),
            execute_time=time.fromisoformat(row["execute_time"]),
            start_date=date.fromisoformat(row["start_date"]),
            end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
            description=row["description"],
            is_active=bool(row["is_active"]),
            last_executed=datetime.fromisoformat(row["last_executed"]) if row["last_executed"] else None,
            next_execution=datetime.fromisoformat(row["next_execution"]) if row["next_execution"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ==================== Pending Confirmation Operations ====================

    def create_pending_confirmation(self, pending: PendingConfirmation) -> PendingConfirmation:
        with self.transaction() as conn:
            ocr = pending.ocr_result
            conn.execute("""
                INSERT INTO pending_confirmations (id, ocr_raw_text, ocr_parsed_amount, ocr_parsed_type,
                    ocr_parsed_category, ocr_parsed_merchant, ocr_parsed_date, ocr_confidence,
                    ocr_source_app, ocr_screen_coords, ocr_captured_at,
                    suggested_account_id, suggested_category_id, status, created_at, confirmed_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pending.id, ocr.raw_text, ocr.parsed_amount,
                ocr.parsed_type.value if ocr.parsed_type else None,
                ocr.parsed_category, ocr.parsed_merchant,
                ocr.parsed_date.isoformat() if ocr.parsed_date else None,
                ocr.confidence, ocr.source_app, json.dumps(ocr.screen_coords),
                ocr.captured_at.isoformat(),
                pending.suggested_account_id, pending.suggested_category_id,
                pending.status.value, pending.created_at.isoformat(),
                pending.confirmed_at.isoformat() if pending.confirmed_at else None,
                pending.expires_at.isoformat() if pending.expires_at else None
            ))
        return pending

    def get_pending_confirmation(self, pending_id: str) -> Optional[PendingConfirmation]:
        with self.transaction() as conn:
            row = conn.execute("SELECT * FROM pending_confirmations WHERE id = ?", (pending_id,)).fetchone()
            if row:
                return self._row_to_pending_confirmation(row)
        return None

    def get_pending_confirmations(self, status: Optional[ConfirmationStatus] = None) -> List[PendingConfirmation]:
        with self.transaction() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM pending_confirmations WHERE status = ? ORDER BY created_at DESC",
                    (status.value,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM pending_confirmations ORDER BY created_at DESC").fetchall()
            return [self._row_to_pending_confirmation(row) for row in rows]

    def update_pending_confirmation(self, pending: PendingConfirmation) -> PendingConfirmation:
        with self.transaction() as conn:
            conn.execute("""
                UPDATE pending_confirmations SET suggested_account_id=?, suggested_category_id=?,
                    status=?, confirmed_at=?, expires_at=?
                WHERE id=?
            """, (
                pending.suggested_account_id, pending.suggested_category_id,
                pending.status.value,
                pending.confirmed_at.isoformat() if pending.confirmed_at else None,
                pending.expires_at.isoformat() if pending.expires_at else None,
                pending.id
            ))
        return pending

    def _row_to_pending_confirmation(self, row: sqlite3.Row) -> PendingConfirmation:
        ocr = OCRResult(
            raw_text=row["ocr_raw_text"],
            parsed_amount=row["ocr_parsed_amount"],
            parsed_type=TransactionType(row["ocr_parsed_type"]) if row["ocr_parsed_type"] else None,
            parsed_category=row["ocr_parsed_category"],
            parsed_merchant=row["ocr_parsed_merchant"],
            parsed_date=datetime.fromisoformat(row["ocr_parsed_date"]) if row["ocr_parsed_date"] else None,
            confidence=row["ocr_confidence"],
            source_app=row["ocr_source_app"],
            screen_coords=json.loads(row["ocr_screen_coords"]) if row["ocr_screen_coords"] else {},
            captured_at=datetime.fromisoformat(row["ocr_captured_at"]),
        )
        return PendingConfirmation(
            id=row["id"],
            ocr_result=ocr,
            suggested_account_id=row["suggested_account_id"],
            suggested_category_id=row["suggested_category_id"],
            status=ConfirmationStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            confirmed_at=datetime.fromisoformat(row["confirmed_at"]) if row["confirmed_at"] else None,
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        )

    # ==================== Settings ====================

    def get_setting(self, key: str, default: str = "") -> str:
        with self.transaction() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            """, (key, value))


# Global database instance
_db_instance: Optional[Database] = None


def get_database(db_path: str = "auto_account.db") -> Database:
    """Get global database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(db_path)
    return _db_instance


def init_database(db_path: str = "auto_account.db") -> Database:
    """Initialize global database instance"""
    global _db_instance
    _db_instance = Database(db_path)
    return _db_instance