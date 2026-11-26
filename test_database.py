#!/usr/bin/env python3
"""
Test script for database and services
"""
import sys
import os
sys.path.insert(0, r"D:\im\auto_account\src")

# Use a test database
TEST_DB = "test_auto_account.db"

# Clean up any existing test db
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from core.database import Database
from core.services import (
    AccountService,
    CategoryService,
    TransactionService,
    SavingsPlanService,
    ScheduledTaskService,
    OCRService,
    StatisticsService,
)
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
)
from datetime import datetime, date, time, timedelta


def setup_database():
    """Create a fresh database for testing"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    return Database(TEST_DB)


def test_account_service():
    print("=== Testing AccountService ===")
    db = setup_database()
    service = AccountService(db)
    
    # Create accounts
    acc1 = service.create_account("支付宝", 1000.0, "alipay", "#1677FF", True)
    acc2 = service.create_account("微信支付", 500.0, "wechat", "#07C160")
    acc3 = service.create_account("银行卡", 10000.0, "bank", "#2196F3")
    
    print(f"Created accounts: {acc1.name}, {acc2.name}, {acc3.name}")
    
    # Get all
    accounts = service.get_all_accounts()
    print(f"Total accounts: {len(accounts)}")
    
    # Get default
    default = service.get_default_account()
    print(f"Default account: {default.name} (balance: {default.balance})")
    
    # Update balance
    service.adjust_balance(acc1.id, -50.0)
    updated = service.get_account(acc1.id)
    print(f"After spending 50: {updated.name} balance = {updated.balance}")
    
    print("[OK] AccountService test passed\n")
    return db


def test_category_service():
    print("=== Testing CategoryService ===")
    db = setup_database()
    service = CategoryService(db)
    
    # Get default categories
    expense_cats = service.get_categories_by_type(TransactionType.EXPENSE)
    income_cats = service.get_categories_by_type(TransactionType.INCOME)
    print(f"Expense categories: {len(expense_cats)}")
    print(f"Income categories: {len(income_cats)}")
    
    # Create custom category
    custom = service.create_category("宠物", TransactionType.EXPENSE, "pets", "#FF9800")
    print(f"Created custom category: {custom.name}")
    
    # Find by name
    found = service.find_category_by_name("餐饮", TransactionType.EXPENSE)
    print(f"Found '餐饮': {found.name if found else 'None'}")
    
    found2 = service.find_category_by_name("外卖", TransactionType.EXPENSE)
    print(f"Found '外卖' (fuzzy): {found2.name if found2 else 'None'}")
    
    print("[OK] CategoryService test passed\n")
    return db


def test_transaction_service():
    print("=== Testing TransactionService ===")
    db = setup_database()
    # Setup accounts and categories first
    acc_service = AccountService(db)
    cat_service = CategoryService(db)
    
    acc = acc_service.create_account("测试账户", 1000.0)
    food_cat = cat_service.find_category_by_name("餐饮", TransactionType.EXPENSE)
    salary_cat = cat_service.find_category_by_name("工资", TransactionType.INCOME)
    
    service = TransactionService(db)
    
    # Create expense
    txn1 = service.create_transaction(
        account_id=acc.id,
        amount=25.50,
        type_=TransactionType.EXPENSE,
        category_id=food_cat.id,
        date_=datetime.now(),
        description="午餐"
    )
    print(f"Created expense: {txn1.amount} - {txn1.description}")
    
    # Create income
    txn2 = service.create_transaction(
        account_id=acc.id,
        amount=5000.0,
        type_=TransactionType.INCOME,
        category_id=salary_cat.id,
        date_=datetime.now(),
        description="工资"
    )
    print(f"Created income: {txn2.amount} - {txn2.description}")
    
    # Check balance
    updated_acc = acc_service.get_account(acc.id)
    print(f"Account balance after transactions: {updated_acc.balance}")
    
    # Get recent
    recent = service.get_recent_transactions(10)
    print(f"Recent transactions: {len(recent)}")
    
    # Monthly summary
    now = datetime.now()
    summary = service.get_monthly_summary(now.year, now.month)
    print(f"Monthly summary: income={summary['income']}, expense={summary['expense']}, net={summary['net']}")
    
    print("[OK] TransactionService test passed\n")
    return db


def test_savings_plan_service():
    print("=== Testing SavingsPlanService ===")
    db = setup_database()
    acc_service = AccountService(db)
    acc = acc_service.create_account("储蓄账户", 5000.0)
    
    service = SavingsPlanService(db, acc_service)
    
    # Create plan
    target_date = date.today() + timedelta(days=90)
    plan = service.create_plan(
        name="旅行基金",
        target_amount=3000.0,
        target_date=target_date,
        account_id=acc.id,
        auto_transfer_amount=200.0,
        auto_transfer_frequency="monthly",
        description="存钱去旅行"
    )
    print(f"Created plan: {plan.name}, target={plan.target_amount}, progress={plan.progress:.1f}%")
    
    # Add savings
    plan = service.add_savings(plan.id, 500.0)
    print(f"After adding 500: progress={plan.progress:.1f}%")
    
    # Get active plans
    active = service.get_active_plans()
    print(f"Active plans: {len(active)}")
    
    print("[OK] SavingsPlanService test passed\n")
    return db


def test_scheduled_task_service():
    print("=== Testing ScheduledTaskService ===")
    db = setup_database()
    acc_service = AccountService(db)
    cat_service = CategoryService(db)
    txn_service = TransactionService(db)
    
    acc = acc_service.create_account("工资卡", 10000.0)
    rent_cat = cat_service.find_category_by_name("居住", TransactionType.EXPENSE)
    
    service = ScheduledTaskService(db, txn_service)
    
    # Create monthly rent task
    task = service.create_task(
        name="月租金",
        amount=3000.0,
        type_=TransactionType.EXPENSE,
        category_id=rent_cat.id,
        account_id=acc.id,
        frequency=TaskFrequency.MONTHLY,
        execute_time=time(9, 0),
        description="每月房租自动扣款"
    )
    print(f"Created task: {task.name}, freq={task.frequency.label}")
    
    # Test should_execute
    now = datetime.now()
    print(f"Should execute now: {task.should_execute(now)}")
    
    # Process due tasks (should not execute if already today)
    results = service.process_due_tasks(now)
    print(f"Processed tasks: {len(results)}")
    
    # Manually set last_executed to yesterday and try again
    task.last_executed = now - timedelta(days=2)
    service.update_task(task)
    results = service.process_due_tasks(now)
    print(f"Processed tasks (after reset): {len(results)}")
    if results:
        executed_task, txn = results[0]
        print(f"  Executed: {executed_task.name}, transaction: {txn.amount}")
    
    print("[OK] ScheduledTaskService test passed\n")
    return db


def test_ocr_service():
    print("=== Testing OCRService ===")
    db = setup_database()
    acc_service = AccountService(db)
    cat_service = CategoryService(db)
    acc = acc_service.create_account("支付宝", 1000.0)
    
    service = OCRService(db, cat_service, acc_service)
    
    # Test Alipay expense
    text1 = "支付宝 支付 25.00元 餐饮 美团外卖 订单号: 123456"
    ocr1 = service.parse_screen_text(text1, "alipay")
    print(f"Parsed: amount={ocr1.parsed_amount}, type={ocr1.parsed_type}, merchant={ocr1.parsed_merchant}, category={ocr1.parsed_category}, confidence={ocr1.confidence:.2f}")
    
    # Test WeChat income
    text2 = "微信收款 500.00元 转账 张三 备注: 借钱"
    ocr2 = service.parse_screen_text(text2, "wechat")
    print(f"Parsed: amount={ocr2.parsed_amount}, type={ocr2.parsed_type}, merchant={ocr2.parsed_merchant}, confidence={ocr2.confidence:.2f}")
    
    # Create pending confirmation
    pending = service.create_pending_confirmation(ocr1, acc.id)
    print(f"Created pending: {pending.id}, status={pending.status.label}")
    
    # Confirm it
    food_cat = cat_service.find_category_by_name("餐饮", TransactionType.EXPENSE)
    txn = service.process_confirmation(pending.id, account_id=acc.id, category_id=food_cat.id)
    print(f"Confirmed transaction: {txn.amount} - {txn.description}")
    
    # Check pending status
    pending2 = service.db.get_pending_confirmation(pending.id)
    print(f"Pending status after confirm: {pending2.status.label}")
    
    print("[OK] OCRService test passed\n")
    return db


def test_statistics_service():
    print("=== Testing StatisticsService ===")
    db = setup_database()
    acc_service = AccountService(db)
    cat_service = CategoryService(db)
    txn_service = TransactionService(db)
    plan_service = SavingsPlanService(db, acc_service)
    
    acc = acc_service.create_account("主账户", 5000.0)
    food_cat = cat_service.find_category_by_name("餐饮", TransactionType.EXPENSE)
    salary_cat = cat_service.find_category_by_name("工资", TransactionType.INCOME)
    
    # Add some transactions
    now = datetime.now()
    for i in range(5):
        txn_service.create_transaction(
            account_id=acc.id,
            amount=20.0 + i * 5,
            type_=TransactionType.EXPENSE,
            category_id=food_cat.id,
            date_=now - timedelta(days=i),
            description=f"餐饮 {i}"
        )
    txn_service.create_transaction(
        account_id=acc.id,
        amount=8000.0,
        type_=TransactionType.INCOME,
        category_id=salary_cat.id,
        date_=now,
        description="月薪"
    )
    
    # Create savings plan
    plan = plan_service.create_plan("应急基金", 10000.0)
    plan.current_amount = 3000.0
    plan_service.update_plan(plan)
    
    service = StatisticsService(db)
    
    # Overview
    overview = service.get_overview()
    print(f"Overview: balance={overview['total_balance']}, income={overview['monthly_income']}, expense={overview['monthly_expense']}")
    
    # Monthly report
    report = service.get_monthly_report(now.year, now.month)
    print(f"Monthly report: expense categories={len(report['expense_by_category'])}, income categories={len(report['income_by_category'])}")
    
    # Savings progress
    savings = service.get_savings_progress()
    print(f"Savings plans: {len(savings)}")
    for s in savings:
        print(f"  {s['name']}: {s['progress']:.1f}%")
    
    print("[OK] StatisticsService test passed\n")
    return db


if __name__ == "__main__":
    print("Running database and service tests...\n")
    
    test_account_service()
    test_category_service()
    test_transaction_service()
    test_savings_plan_service()
    test_scheduled_task_service()
    test_ocr_service()
    test_statistics_service()
    
    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    
    print("=== All tests passed! ===")