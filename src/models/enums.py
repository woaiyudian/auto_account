"""
Enumeration types for the Auto Account App
"""
from enum import Enum


class TransactionType(Enum):
    """Transaction type: expense or income"""
    EXPENSE = "expense"
    INCOME = "income"

    @property
    def label(self) -> str:
        return "支出" if self == TransactionType.EXPENSE else "收入"

    @property
    def sign(self) -> int:
        return -1 if self == TransactionType.EXPENSE else 1


class TaskFrequency(Enum):
    """Frequency for scheduled tasks"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    ONCE = "once"

    @property
    def label(self) -> str:
        labels = {
            TaskFrequency.DAILY: "每天",
            TaskFrequency.WEEKLY: "每周",
            TaskFrequency.MONTHLY: "每月",
            TaskFrequency.YEARLY: "每年",
            TaskFrequency.ONCE: "一次性",
        }
        return labels[self]


class SavingsPlanStatus(Enum):
    """Status of a savings plan"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    @property
    def label(self) -> str:
        labels = {
            SavingsPlanStatus.ACTIVE: "进行中",
            SavingsPlanStatus.PAUSED: "已暂停",
            SavingsPlanStatus.COMPLETED: "已完成",
            SavingsPlanStatus.CANCELLED: "已取消",
        }
        return labels[self]


class ConfirmationStatus(Enum):
    """Status of a pending confirmation"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    EXPIRED = "expired"

    @property
    def label(self) -> str:
        labels = {
            ConfirmationStatus.PENDING: "待确认",
            ConfirmationStatus.CONFIRMED: "已确认",
            ConfirmationStatus.REJECTED: "已拒绝",
            ConfirmationStatus.EXPIRED: "已过期",
        }
        return labels[self]