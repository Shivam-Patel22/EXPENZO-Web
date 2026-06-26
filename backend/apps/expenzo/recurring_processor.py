import calendar
from datetime import datetime
from django.db import transaction
from django.utils import timezone as django_timezone
from .models import PersonalExpense, RecurringIncome, RecurringExpense

def process_recurring_finance(user):
    try:
        now = django_timezone.now()
        curr_year = now.year
        curr_month = now.month
        curr_day = now.day

        active_incomes = RecurringIncome.objects.filter(user=user, is_active=True)
        active_expenses = RecurringExpense.objects.filter(user=user, is_active=True)

        for item_list, is_income in [(active_incomes, True), (active_expenses, False)]:
            for item in item_list:
                # If never processed, start from its creation date. If processed, start from next month.
                if item.last_processed_year is None or item.last_processed_month is None:
                    start_year = item.created_at.year
                    start_month = item.created_at.month
                else:
                    start_year = item.last_processed_year
                    start_month = item.last_processed_month + 1
                    if start_month > 12:
                        start_month = 1
                        start_year += 1

                y = start_year
                m = start_month

                with transaction.atomic():
                    while y < curr_year or (y == curr_year and m <= curr_month):
                        last_day = calendar.monthrange(y, m)[1]
                        exec_day = min(item.execution_day, last_day)
                        
                        # If we are in the current month, only process if today >= exec_day
                        if y == curr_year and m == curr_month and curr_day < exec_day:
                            break
                        
                        process_date = django_timezone.make_aware(datetime(y, m, exec_day, 0, 0, 0))
                        
                        PersonalExpense.objects.create(
                            user=user, 
                            amount=item.amount, 
                            category="Income" if is_income else "Others",
                            payment_method=item.payment_method, 
                            account=item.account,
                            description=f"Fixed {'Income' if is_income else 'Expense'}: {item.name}",
                            date=process_date, 
                            month=m, 
                            year=y, 
                            is_recurring=True
                        )
                        
                        item.last_processed_year = y
                        item.last_processed_month = m
                        item.save()

                        m += 1
                        if m > 12:
                            m = 1
                            y += 1
    except Exception as e:
        print("Error processing recurring monthly finance:", e)

def recalculate_current_month(user):
    try:
        now = django_timezone.now()
        curr_year = now.year
        curr_month = now.month

        with transaction.atomic():
            # Delete current month's recurring transactions
            PersonalExpense.objects.filter(
                user=user,
                month=curr_month,
                year=curr_year,
                is_recurring=True
            ).delete()

            # Roll back last_processed to previous month so they re-trigger if applicable
            for ItemModel in [RecurringIncome, RecurringExpense]:
                items = ItemModel.objects.filter(
                    user=user, 
                    is_active=True,
                    last_processed_year=curr_year,
                    last_processed_month=curr_month
                )
                for item in items:
                    if curr_month == 1:
                        item.last_processed_month = 12
                        item.last_processed_year = curr_year - 1
                    else:
                        item.last_processed_month = curr_month - 1
                    item.save()

        # Re-process
        process_recurring_finance(user)
    except Exception as e:
        print("Error recalculating current month's recurring items:", e)
