"""
Savings Plan model
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
import uuid
from .enums import SavingsPlanStatus


@dataclass
class SavingsPlan:
    """Represents a savings goal/plan"""
    name: str
    target_amount: float
    current_amount: float = 0.0
    start_date: date = field(default_factory=date.today)
    target_date: Optional[date] = None
    account_id: Optional[str] = None  # Linked account for auto-transfer
    auto_transfer_amount: float = 0.0  # Amount to auto-transfer per period
    auto_transfer_frequency: str = "monthly"  # daily, weekly, monthly
    status: SavingsPlanStatus = SavingsPlanStatus.ACTIVE
    icon: str = "savings"
    color: str = "#4CAF50"
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "target_amount": self.target_amount,
            "current_amount": self.current_amount,
            "start_date": self.start_date.isoformat(),
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "account_id": self.account_id,
            "auto_transfer_amount": self.auto_transfer_amount,
            "auto_transfer_frequency": self.auto_transfer_frequency,
            "status": self.status.value,
            "icon": self.icon,
            "color": self.color,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SavingsPlan":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            target_amount=data["target_amount"],
            current_amount=data.get("current_amount", 0.0),
            start_date=date.fromisoformat(data["start_date"]) if "start_date" in data else date.today(),
            target_date=date.fromisoformat(data["target_date"]) if data.get("target_date") else None,
            account_id=data.get("account_id"),
            auto_transfer_amount=data.get("auto_transfer_amount", 0.0),
            auto_transfer_frequency=data.get("auto_transfer_frequency", "monthly"),
            status=SavingsPlanStatus(data.get("status", "active")),
            icon=data.get("icon", "savings"),
            color=data.get("color", "#4CAF50"),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )

    @property
    def progress(self) -> float:
        """Progress percentage (0-100)"""
        if self.target_amount <= 0:
            return 0.0
        return min(100.0, (self.current_amount / self.target_amount) * 100)

    @property
    def remaining_amount(self) -> float:
        """Remaining amount to reach target"""
        return max(0.0, self.target_amount - self.current_amount)

    @property
    def is_completed(self) -> bool:
        return self.current_amount >= self.target_amount

    @property
    def days_remaining(self) -> Optional[int]:
        """Days until target date"""
        if not self.target_date:
            return None
        delta = self.target_date - date.today()
        return delta.days

    def add_savings(self, amount: float) -> None:
        """Add savings to the plan"""
        self.current_amount += amount
        self.updated_at = datetime.now()
        if self.is_completed and self.status == SavingsPlanStatus.ACTIVE:
            self.status = SavingsPlanStatus.COMPLETED

    def withdraw(self, amount: float) -> None:
        """Withdraw from savings plan"""
        self.current_amount = max(0.0, self.current_amount - amount)
        self.updated_at = datetime.now()
        if self.status == SavingsPlanStatus.COMPLETED:
            self.status = SavingsPlanStatus.ACTIVE