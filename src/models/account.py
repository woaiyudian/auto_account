"""
Account model
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class Account:
    """Represents a financial account (wallet, bank card, Alipay, WeChat Pay, etc.)"""
    name: str
    balance: float = 0.0
    icon: str = "wallet"  # Icon identifier
    color: str = "#2196F3"  # Hex color
    is_default: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "balance": self.balance,
            "icon": self.icon,
            "color": self.color,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Account":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            balance=data.get("balance", 0.0),
            icon=data.get("icon", "wallet"),
            color=data.get("color", "#2196F3"),
            is_default=data.get("is_default", False),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )

    def update_balance(self, amount: float) -> None:
        """Update account balance"""
        self.balance += amount
        self.updated_at = datetime.now()