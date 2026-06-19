from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=50, null=True, blank=True)
    country = models.CharField(max_length=100, default="India")
    savings_target = models.FloatField(default=0.0)
    savings_current = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.user.username}'s Profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class PersonalExpense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='personal_expenses')
    amount = models.FloatField()
    category = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    date = models.DateTimeField()
    month = models.IntegerField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category}: {self.description} ({self.amount})"

class RecurringIncome(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_incomes')
    name = models.CharField(max_length=255)
    amount = models.FloatField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Recurring Income: {self.name} ({self.amount})"

class RecurringExpense(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_expenses')
    name = models.CharField(max_length=255)
    amount = models.FloatField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Recurring Expense: {self.name} ({self.amount})"

class MonthlyRecurringProcessing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_processings')
    month = models.IntegerField()
    year = models.IntegerField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'month', 'year')

    def __str__(self):
        return f"Recurring Processed: {self.month}/{self.year} for {self.user.username}"

class Group(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    icon = models.CharField(max_length=50, null=True, blank=True, default="users")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class GroupMember(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('MEMBER', 'Member')
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"

class GroupExpense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='expenses')
    paid_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paid_group_expenses', null=True, blank=True)
    amount = models.FloatField()
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.description} ({self.amount}) in {self.group.name}"

class GroupExpensePayment(models.Model):
    group_expense = models.ForeignKey(GroupExpense, on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expense_payments')
    amount = models.FloatField()

    def __str__(self):
        return f"{self.user.username} paid {self.amount} for {self.group_expense.description}"


class GroupExpenseSplit(models.Model):
    group_expense = models.ForeignKey(GroupExpense, on_delete=models.CASCADE, related_name='splits')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='splits')
    amount = models.FloatField()
    is_settled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} owes {self.amount} for {self.group_expense.description}"

class Settlement(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='settlements')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_settlements')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_settlements')
    amount = models.FloatField()
    is_settled = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Settlement {self.from_user.username} -> {self.to_user.username} ({self.amount})"
