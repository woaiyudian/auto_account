"""
Transaction model
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid
from .enums import TransactionType


@dataclass
class Transaction:
    """Represents a single financial transaction"""
    account_id: str
    amount: float
    type: TransactionType
    category_id: str
    date: datetime
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    # For auto-captured transactions
    source: str = "manual"  # manual, auto, scheduled
    ocr_raw_text: str = ""
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "amount": self.amount,
            "type": self.type.value,
            "category_id": self.category_id,
            "date": self.date.isoformat(),
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "source": self.source,
            "ocr_raw_text": self.ocr_raw_text,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            account_id=data["account_id"],
            amount=data["amount"],
            type=TransactionType(data["type"]),
            category_id=data["category_id"],
            date=datetime.fromisoformat(data["date"]),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
            source=data.get("source", "manual"),
            ocr_raw_text=data.get("ocr_raw_text", ""),
            confidence=data.get("confidence", 1.0),
        )

    @property
    def signed_amount(self) -> float:
        """Amount with sign based on transaction type"""
        return self.amount * self.type.sign

    def __repr__(self) -> str:
        sign = "-" if self.type == TransactionType.EXPENSE else "+"
        return f"Transaction({sign}{self.amount:.2f}, {self.category_id}, {self.date.strftime('%Y-%m-%d')})"