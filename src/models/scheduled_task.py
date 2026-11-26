"""
Scheduled Task model
"""
from dataclasses import dataclass, field
from datetime import datetime, time, date
from typing import Optional
import uuid
from .enums import TaskFrequency, TransactionType


@dataclass
class ScheduledTask:
    """Represents a recurring transaction task"""
    name: str
    amount: float
    type: TransactionType
    category_id: str
    account_id: str
    frequency: TaskFrequency
    execute_time: time  # Time of day to execute
    start_date: date = field(default_factory=date.today)
    end_date: Optional[date] = None
    description: str = ""
    is_active: bool = True
    last_executed: Optional[datetime] = None
    next_execution: Optional[datetime] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "amount": self.amount,
            "type": self.type.value,
            "category_id": self.category_id,
            "account_id": self.account_id,
            "frequency": self.frequency.value,
            "execute_time": self.execute_time.isoformat(),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "description": self.description,
            "is_active": self.is_active,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "next_execution": self.next_execution.isoformat() if self.next_execution else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledTask":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            amount=data["amount"],
            type=TransactionType(data["type"]),
            category_id=data["category_id"],
            account_id=data["account_id"],
            frequency=TaskFrequency(data["frequency"]),
            execute_time=time.fromisoformat(data["execute_time"]),
            start_date=date.fromisoformat(data["start_date"]),
            end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            description=data.get("description", ""),
            is_active=data.get("is_active", True),
            last_executed=datetime.fromisoformat(data["last_executed"]) if data.get("last_executed") else None,
            next_execution=datetime.fromisoformat(data["next_execution"]) if data.get("next_execution") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )

    def should_execute(self, now: datetime) -> bool:
        """Check if task should execute at given time"""
        if not self.is_active:
            return False

        if now.date() < self.start_date:
            return False

        if self.end_date and now.date() > self.end_date:
            return False

        if now.time() < self.execute_time:
            return False

        if self.last_executed and self.last_executed.date() == now.date():
            return False  # Already executed today

        # Check frequency
        if self.frequency == TaskFrequency.DAILY:
            return True
        elif self.frequency == TaskFrequency.WEEKLY:
            return self.last_executed is None or (now.date() - self.last_executed.date()).days >= 7
        elif self.frequency == TaskFrequency.MONTHLY:
            if self.last_executed is None:
                return True
            return now.month != self.last_executed.month or now.year != self.last_executed.year
        elif self.frequency == TaskFrequency.YEARLY:
            if self.last_executed is None:
                return True
            return now.year != self.last_executed.year
        elif self.frequency == TaskFrequency.ONCE:
            return self.last_executed is None

        return False

    def mark_executed(self, execution_time: datetime) -> None:
        """Mark task as executed"""
        self.last_executed = execution_time
        self.updated_at = datetime.now()