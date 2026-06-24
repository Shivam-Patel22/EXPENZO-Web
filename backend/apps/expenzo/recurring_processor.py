from datetime import datetime, timezone
from django.db import transaction, IntegrityError
from django.utils import timezone as django_timezone
from .models import PersonalExpense, RecurringIncome, RecurringExpense, MonthlyRecurringProcessing

def process_recurring_finance(user):
    try:
        now = django_timezone.now()
        curr_year = now.year
        curr_month = now.month

        # Get earliest transaction to determine start date, or default to current month
        earliest_tx = PersonalExpense.objects.filter(user=user).order_by('date').first()

        if earliest_tx:
            start_year = earliest_tx.year if earliest_tx.year is not None else earliest_tx.date.year
            start_month = earliest_tx.month if earliest_tx.month is not None else earliest_tx.date.month
        else:
            start_year = curr_year
            start_month = curr_month

        y = start_year
        m = start_month

        # Loop through each month up to the current calendar month
        while y < curr_year or (y == curr_year and m <= curr_month):
            already_processed = MonthlyRecurringProcessing.objects.filter(
                user=user, month=m, year=y
            ).exists()

            if not already_processed:
                try:
                    with transaction.atomic():
                        # Create processing record FIRST to act as a database lock
                        # If a concurrent request is processing this month, this will throw IntegrityError
                        MonthlyRecurringProcessing.objects.create(
                            user=user,
                            month=m,
                            year=y
                        )
                        
                        # Fetch active recurring items
                        active_incomes = RecurringIncome.objects.filter(user=user, is_active=True)
                        active_expenses = RecurringExpense.objects.filter(user=user, is_active=True)

                        # First day of that month in UTC/aware datetime
                        process_date = django_timezone.make_aware(datetime(y, m, 1, 0, 0, 0))

                        # Insert income entries
                        for inc in active_incomes:
                            PersonalExpense.objects.create(
                                user=user, amount=inc.amount, category="Income",
                                payment_method="Net Banking", description=f"Fixed Income: {inc.name}",
                                date=process_date, month=m, year=y, is_recurring=True
                            )

                        # Insert expense entries
                        for exp in active_expenses:
                            PersonalExpense.objects.create(
                                user=user, amount=exp.amount, category="Others",
                                payment_method="Cash", description=f"Fixed Expense: {exp.name}",
                                date=process_date, month=m, year=y, is_recurring=True
                            )
                except IntegrityError:
                    # A concurrent process already created the MonthlyRecurringProcessing record
                    pass

            # Advance one month
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

            # Delete current month's processing record
            MonthlyRecurringProcessing.objects.filter(
                user=user,
                month=curr_month,
                year=curr_year
            ).delete()

        # Re-process
        process_recurring_finance(user)
    except Exception as e:
        print("Error recalculating current month's recurring items:", e)
