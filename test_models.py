#!/usr/bin/env python3
"""
Test script for data models
"""
import sys
sys.path.insert(0, r"D:\im\auto_account\src")

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

from datetime import datetime, date, time


def test_account():
    print("=== Testing Account ===")
    acc = Account(name="支付宝", balance=1000.0, icon="alipay", color="#1677FF", is_default=True)
    print(f"Created: {acc}")
    print(f"Dict: {acc.to_dict()}")
    
    # Test from_dict
    acc2 = Account.from_dict(acc.to_dict())
    print(f"Restored: {acc2.name}, balance={acc2.balance}")
    assert acc.id == acc2.id
    print("✓ Account test passed\n")


def test_transaction():
    print("=== Testing Transaction ===")
    cat = Category(name="餐饮", type=TransactionType.EXPENSE, icon="restaurant", color="#FF5722")
    txn = Transaction(
        account_id="acc1",
        amount=25.50,
        type=TransactionType.EXPENSE,
        category_id=cat.id,
        date=datetime.now(),
        description="午餐",
        source="manual"
    )
    print(f"Created: {txn}")
    print(f"Signed amount: {txn.signed_amount}")
    
    # Test from_dict
    txn2 = Transaction.from_dict(txn.to_dict())
    print(f"Restored: {txn2.amount}, type={txn2.type}")
    assert txn.id == txn2.id
    print("✓ Transaction test passed\n")


def test_category():
    print("=== Testing Category ===")
    print(f"Default categories count: {len(DEFAULT_CATEGORIES)}")
    expense_cats = [c for c in DEFAULT_CATEGORIES if c.type == TransactionType.EXPENSE]
    income_cats = [c for c in DEFAULT_CATEGORIES if c.type == TransactionType.INCOME]
    print(f"Expense categories: {len(expense_cats)}")
    print(f"Income categories: {len(income_cats)}")
    for c in expense_cats[:3]:
        print(f"  - {c.name} ({c.icon}) {c.color}")
    print("✓ Category test passed\n")


def test_savings_plan():
    print("=== Testing SavingsPlan ===")
    plan = SavingsPlan(
        name="买手机基金",
        target_amount=5000.0,
        current_amount=1200.0,
        target_date=date(2026, 12, 31),
        icon="phone_android",
        color="#2196F3",
        description="存钱买新手机"
    )
    print(f"Created: {plan.name}")
    print(f"Progress: {plan.progress:.1f}%")
    print(f"Remaining: {plan.remaining_amount:.2f}")
    print(f"Days remaining: {plan.days_remaining}")
    print(f"Is completed: {plan.is_completed}")
    
    plan.add_savings(1000)
    print(f"After adding 1000: progress={plan.progress:.1f}%, status={plan.status}")
    
    plan2 = SavingsPlan.from_dict(plan.to_dict())
    print(f"Restored: {plan2.name}, progress={plan2.progress:.1f}%")
    print("✓ SavingsPlan test passed\n")


def test_scheduled_task():
    print("=== Testing ScheduledTask ===")
    task = ScheduledTask(
        name="月租金",
        amount=3000.0,
        type=TransactionType.EXPENSE,
        category_id="cat_rent",
        account_id="acc_bank",
        frequency=TaskFrequency.MONTHLY,
        execute_time=time(9, 0),
        description="每月房租"
    )
    print(f"Created: {task.name}, freq={task.frequency.label}")
    
    now = datetime.now()
    print(f"Should execute now: {task.should_execute(now)}")
    
    task2 = ScheduledTask.from_dict(task.to_dict())
    print(f"Restored: {task2.name}, freq={task2.frequency}")
    print("✓ ScheduledTask test passed\n")


def test_ocr_confirmation():
    print("=== Testing OCR & Confirmation ===")
    ocr = OCRResult(
        raw_text="支付宝 收款 25.00元 餐饮 美团外卖",
        parsed_amount=25.0,
        parsed_type=TransactionType.EXPENSE,
        parsed_merchant="美团外卖",
        confidence=0.85,
        source_app="alipay"
    )
    print(f"OCR valid for confirmation: {ocr.is_valid_for_confirmation()}")
    print(f"Parsed: {ocr.parsed_amount} {ocr.parsed_type}")
    
    pending = PendingConfirmation(
        ocr_result=ocr,
        suggested_account_id="acc_alipay",
        suggested_category_id="cat_food"
    )
    print(f"Pending: {pending.id}, status={pending.status.label}")
    
    pending.confirm()
    print(f"After confirm: {pending.status.label}")
    
    pending2 = PendingConfirmation.from_dict(pending.to_dict())
    print(f"Restored: {pending2.id}, status={pending2.status.label}")
    print("✓ OCR & Confirmation test passed\n")


if __name__ == "__main__":
    print("Running model tests...\n")
    test_account()
    test_transaction()
    test_category()
    test_savings_plan()
    test_scheduled_task()
    test_ocr_confirmation()
    print("=== All tests passed! ===")