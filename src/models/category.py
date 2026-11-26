"""
Category model
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid
from .enums import TransactionType


@dataclass
class Category:
    """Represents a transaction category"""
    name: str
    type: TransactionType
    icon: str = "category"
    color: str = "#9E9E9E"
    parent_id: Optional[str] = None
    sort_order: int = 0
    is_system: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "icon": self.icon,
            "color": self.color,
            "parent_id": self.parent_id,
            "sort_order": self.sort_order,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Category":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            type=TransactionType(data["type"]),
            icon=data.get("icon", "category"),
            color=data.get("color", "#9E9E9E"),
            parent_id=data.get("parent_id"),
            sort_order=data.get("sort_order", 0),
            is_system=data.get("is_system", False),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
        )


# Default system categories
DEFAULT_EXPENSE_CATEGORIES = [
    Category(name="餐饮", type=TransactionType.EXPENSE, icon="restaurant", color="#FF5722", is_system=True, sort_order=1),
    Category(name="交通", type=TransactionType.EXPENSE, icon="directions_bus", color="#2196F3", is_system=True, sort_order=2),
    Category(name="购物", type=TransactionType.EXPENSE, icon="shopping_cart", color="#E91E63", is_system=True, sort_order=3),
    Category(name="娱乐", type=TransactionType.EXPENSE, icon="sports_esports", color="#9C27B0", is_system=True, sort_order=4),
    Category(name="医疗", type=TransactionType.EXPENSE, icon="local_hospital", color="#F44336", is_system=True, sort_order=5),
    Category(name="教育", type=TransactionType.EXPENSE, icon="school", color="#3F51B5", is_system=True, sort_order=6),
    Category(name="居住", type=TransactionType.EXPENSE, icon="home", color="#795548", is_system=True, sort_order=7),
    Category(name="通讯", type=TransactionType.EXPENSE, icon="phone", color="#00BCD4", is_system=True, sort_order=8),
    Category(name="其他支出", type=TransactionType.EXPENSE, icon="more_horiz", color="#9E9E9E", is_system=True, sort_order=99),
]

DEFAULT_INCOME_CATEGORIES = [
    Category(name="工资", type=TransactionType.INCOME, icon="work", color="#4CAF50", is_system=True, sort_order=1),
    Category(name="奖金", type=TransactionType.INCOME, icon="card_giftcard", color="#8BC34A", is_system=True, sort_order=2),
    Category(name="投资收益", type=TransactionType.INCOME, icon="trending_up", color="#009688", is_system=True, sort_order=3),
    Category(name="兼职", type=TransactionType.INCOME, icon="build", color="#FF9800", is_system=True, sort_order=4),
    Category(name="其他收入", type=TransactionType.INCOME, icon="more_horiz", color="#9E9E9E", is_system=True, sort_order=99),
]

DEFAULT_CATEGORIES = DEFAULT_EXPENSE_CATEGORIES + DEFAULT_INCOME_CATEGORIES