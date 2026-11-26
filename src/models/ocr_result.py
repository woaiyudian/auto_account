"""
OCR Result and Pending Confirmation models
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import uuid
from .enums import TransactionType, ConfirmationStatus


@dataclass
class OCRResult:
    """Result from OCR screen capture"""
    raw_text: str
    parsed_amount: Optional[float] = None
    parsed_type: Optional[TransactionType] = None
    parsed_category: Optional[str] = None  # Category name or ID
    parsed_merchant: Optional[str] = None
    parsed_date: Optional[datetime] = None
    confidence: float = 0.0  # 0-1 overall confidence
    source_app: str = ""  # e.g., "alipay", "wechat", "bank"
    screen_coords: dict = field(default_factory=dict)  # x, y, width, height
    captured_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "parsed_amount": self.parsed_amount,
            "parsed_type": self.parsed_type.value if self.parsed_type else None,
            "parsed_category": self.parsed_category,
            "parsed_merchant": self.parsed_merchant,
            "parsed_date": self.parsed_date.isoformat() if self.parsed_date else None,
            "confidence": self.confidence,
            "source_app": self.source_app,
            "screen_coords": self.screen_coords,
            "captured_at": self.captured_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OCRResult":
        return cls(
            raw_text=data["raw_text"],
            parsed_amount=data.get("parsed_amount"),
            parsed_type=TransactionType(data["parsed_type"]) if data.get("parsed_type") else None,
            parsed_category=data.get("parsed_category"),
            parsed_merchant=data.get("parsed_merchant"),
            parsed_date=datetime.fromisoformat(data["parsed_date"]) if data.get("parsed_date") else None,
            confidence=data.get("confidence", 0.0),
            source_app=data.get("source_app", ""),
            screen_coords=data.get("screen_coords", {}),
            captured_at=datetime.fromisoformat(data["captured_at"]) if "captured_at" in data else datetime.now(),
        )

    def is_valid_for_confirmation(self) -> bool:
        """Check if OCR result has enough info to show confirmation dialog"""
        return (
            self.parsed_amount is not None
            and self.parsed_amount > 0
            and self.parsed_type is not None
            and self.confidence >= 0.5
        )


@dataclass
class PendingConfirmation:
    """A transaction waiting for user confirmation"""
    ocr_result: OCRResult
    suggested_account_id: str
    suggested_category_id: Optional[str] = None
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # Auto-expire after some time

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ocr_result": self.ocr_result.to_dict(),
            "suggested_account_id": self.suggested_account_id,
            "suggested_category_id": self.suggested_category_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "confirmed_at": self.confirmed_at.isoformat() if self.confirmed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PendingConfirmation":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            ocr_result=OCRResult.from_dict(data["ocr_result"]),
            suggested_account_id=data["suggested_account_id"],
            suggested_category_id=data.get("suggested_category_id"),
            status=ConfirmationStatus(data.get("status", "pending")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            confirmed_at=datetime.fromisoformat(data["confirmed_at"]) if data.get("confirmed_at") else None,
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
        )

    def confirm(self, account_id: Optional[str] = None, category_id: Optional[str] = None) -> None:
        """Confirm the pending transaction"""
        self.status = ConfirmationStatus.CONFIRMED
        self.confirmed_at = datetime.now()
        if account_id:
            self.suggested_account_id = account_id
        if category_id:
            self.suggested_category_id = category_id

    def reject(self) -> None:
        """Reject the pending transaction"""
        self.status = ConfirmationStatus.REJECTED
        self.confirmed_at = datetime.now()

    def expire(self) -> None:
        """Mark as expired"""
        self.status = ConfirmationStatus.EXPIRED