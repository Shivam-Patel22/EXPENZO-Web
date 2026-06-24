from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone as django_timezone
from datetime import datetime, timedelta
import json

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.core.mail import send_mail
from django.urls import reverse
from django.core.cache import cache

from .models import (
    UserProfile, PersonalExpense, RecurringIncome, RecurringExpense,
    MonthlyRecurringProcessing, Group, GroupMember, GroupExpense,
    GroupExpenseSplit, Settlement, GroupExpensePayment
)
from .recurring_processor import process_recurring_finance, recalculate_current_month
from .charts import (
    generate_savings_gauge_chart, generate_spending_pie_chart,
    generate_group_net_standing_chart
)
from .decorators import rate_limit

# Helper function to get get_object_or_404 substitute for clean usage
def get_object_or_none(model, **kwargs):
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        return None

@rate_limit(limit=60, window=60)
@login_required
def dashboard_view(request):
    user = request.user
    
    # Process recurring items dynamically
    process_recurring_finance(user)
    
    now = django_timezone.now()
    selected_year = now.year
    selected_month_num = now.month
    
    # Get filters
    filter_type = strip_tags(request.GET.get('filter', 'all'))
    search_query = strip_tags(request.GET.get('search', '').strip())[:100]
    
    # Fetch all personal expenses
    expenses = PersonalExpense.objects.filter(user=user).order_by('-date')
    
    # Apply search filter
    if search_query:
        expenses = expenses.filter(description__icontains=search_query)
        
    # Apply date filter for recent transactions
    filtered_expenses = expenses
    
    if filter_type == 'daily':
        filtered_expenses = expenses.filter(date__date=now.date())
    elif filter_type == 'weekly':
        seven_days_ago = now.date() - timedelta(days=7)
        filtered_expenses = expenses.filter(date__date__gte=seven_days_ago, date__date__lte=now.date())
    elif filter_type == 'monthly':
        filtered_expenses = expenses.filter(date__year=now.year, date__month=now.month)
        
    recent_transactions = filtered_expenses[:20]
    
    # Compute active month stats
    monthly_expenses = PersonalExpense.objects.filter(user=user, date__year=selected_year, date__month=selected_month_num)
    
    # Cumulative balance calculation (carrying over balances from previous months)
    # Get last day of selected month
    if selected_month_num == 12:
        end_of_selected_month = django_timezone.make_aware(datetime(selected_year + 1, 1, 1, 23, 59, 59)) - timedelta(seconds=1)
    else:
        end_of_selected_month = django_timezone.make_aware(datetime(selected_year, selected_month_num + 1, 1, 23, 59, 59)) - timedelta(seconds=1)
        
    all_past_and_current_expenses = PersonalExpense.objects.filter(user=user, date__lte=end_of_selected_month)
    
    cumulative_income = sum(exp.amount for exp in all_past_and_current_expenses if exp.category == "Income")
    cumulative_spend = sum(exp.amount for exp in all_past_and_current_expenses if exp.category != "Income")
    monthly_balance = cumulative_income - cumulative_spend
    
    # Calculate Pie Chart category breakdown
    category_sums = {}
    current_month_spends = monthly_expenses.exclude(category="Income")
    total_spend = sum(exp.amount for exp in current_month_spends)
    
    for exp in current_month_spends:
        category_sums[exp.category] = category_sums.get(exp.category, 0) + exp.amount
        
    category_breakdown = []
    pie_categories = []
    pie_values = []
    
    # Premium color matching
    COLORS = ["#818cf8", "#34d399", "#fb7185", "#fbbf24", "#a78bfa", "#22d3ee", "#f472b6", "#a7f3d0", "#c084fc", "#94a3b8"]
    
    for idx, (name, value) in enumerate(category_sums.items()):
        percentage = round((value / total_spend) * 100) if total_spend > 0 else 0
        category_breakdown.append({
            'name': name,
            'value': value,
            'percentage': percentage,
            'color': COLORS[idx % len(COLORS)]
        })
        pie_categories.append(name)
        pie_values.append(value)
        
    # Generate charts
    pie_chart_base64 = generate_spending_pie_chart(pie_categories, pie_values)
    
    profile = user.profile
    savings_target = profile.savings_target
    savings_current = profile.savings_current
    savings_percent = min(100, round((savings_current / savings_target) * 100)) if savings_target > 0 else 0
    
    gauge_chart_base64 = generate_savings_gauge_chart(savings_percent)
    active_month_label = now.strftime("%B %Y")
    
    context = {
        'recent_transactions': recent_transactions,
        'monthly_balance': monthly_balance,
        'savings_target': savings_target,
        'savings_current': savings_current,
        'savings_percent': savings_percent,
        'active_month_label': active_month_label,
        'category_breakdown': category_breakdown,
        'pie_chart': pie_chart_base64,
        'gauge_chart': gauge_chart_base64,
        'filter_type': filter_type,
        'search_query': search_query
    }
    return render(request, 'dashboard.html', context)

@rate_limit(limit=60, window=60)
@login_required
def history_view(request):
    user = request.user
    
    # Get filters
    search_query = strip_tags(request.GET.get('search', '').strip())[:100]
    category_filter = strip_tags(request.GET.get('category', 'All').strip())[:50]
    payment_filter = strip_tags(request.GET.get('paymentMethod', 'All').strip())[:50]
    
    expenses = PersonalExpense.objects.filter(user=user).order_by('-date')
    
    if search_query:
        expenses = expenses.filter(description__icontains=search_query)
    if category_filter != 'All':
        expenses = expenses.filter(category=category_filter)
    if payment_filter != 'All':
        expenses = expenses.filter(payment_method=payment_filter)
        
    # Distinct categories and payment methods for dropdown filters
    categories = ["Income", "Food", "Travel", "Shopping", "Entertainment", "Rent", "Utilities", "Health", "Education", "Investment", "Others"]
    payment_methods = ["Cash", "UPI", "Credit Card", "Debit Card", "Net Banking"]
    
    # Group expenses by year and month
    from collections import defaultdict
    grouped_data = defaultdict(list)
    for exp in expenses:
        key = exp.date.strftime("%Y-%m")
        grouped_data[key].append(exp)

    grouped_months = []
    # Color mapping for UI
    CATEGORY_COLORS = {
        "Food": "#34d399",
        "Travel": "#fb7185",
        "Shopping": "#fbbf24",
        "Entertainment": "#a78bfa",
        "Rent": "#22d3ee",
        "Utilities": "#f472b6",
        "Health": "#a7f3d0",
        "Education": "#c084fc",
        "Investment": "#818cf8",
        "Others": "#94a3b8"
    }

    for key in sorted(grouped_data.keys(), reverse=True):
        exps = grouped_data[key]
        year, month = map(int, key.split('-'))
        label = datetime(year, month, 1).strftime("%B %Y")
        
        total_spend = sum(e.amount for e in exps if e.category != "Income")
        
        # Calculate category breakdown
        category_sums = {}
        for e in exps:
            if e.category != "Income":
                category_sums[e.category] = category_sums.get(e.category, 0) + e.amount
                
        breakdown = []
        for cat_name, cat_val in category_sums.items():
            breakdown.append({
                'name': cat_name,
                'amount': cat_val,
                'color': CATEGORY_COLORS.get(cat_name, '#94a3b8')
            })
            
        grouped_months.append({
            'key': key,
            'label': label,
            'expenses': exps,
            'total_spend': total_spend,
            'category_breakdown': breakdown
        })
        
    context = {
        'grouped_months': grouped_months,
        'categories': categories,
        'payment_methods': payment_methods,
        'search_query': search_query,
        'selected_category': category_filter,
        'selected_payment': payment_filter
    }
    return render(request, 'history.html', context)

@rate_limit(limit=60, window=60)
@login_required
def recurring_view(request):
    user = request.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            new_type = strip_tags(request.POST.get('type', ''))
            name = strip_tags(request.POST.get('name', ''))[:100]
            try:
                amount = float(request.POST.get('amount', 0))
            except (ValueError, TypeError):
                amount = 0.0
            if amount > 0:
                if new_type == 'income':
                    RecurringIncome.objects.create(user=user, name=name, amount=amount)
                elif new_type == 'expense':
                    RecurringExpense.objects.create(user=user, name=name, amount=amount)
            recalculate_current_month(user)
        elif action == 'recalculate':
            recalculate_current_month(user)
        return redirect('recurring')
        
    incomes = RecurringIncome.objects.filter(user=user).order_by('-created_at')
    expenses = RecurringExpense.objects.filter(user=user).order_by('-created_at')
    
    context = {
        'recurring_incomes': incomes,
        'recurring_expenses': expenses
    }
    return render(request, 'recurring.html', context)

@rate_limit(limit=60, window=60)
@login_required
def groups_view(request):
    user = request.user
    
    if request.method == 'POST':
        name = strip_tags(request.POST.get('name', ''))[:100]
        description = strip_tags(request.POST.get('description', ''))[:500]
        icon = strip_tags(request.POST.get('icon', 'users'))[:50]
        
        if not name:
            return redirect('groups')
            
        # Create group and add creator as member
        group = Group.objects.create(name=name, description=description, icon=icon, created_by=user)
        GroupMember.objects.create(group=group, user=user, role='ADMIN')
        return redirect('group_detail', group_id=group.id)
        
    memberships = GroupMember.objects.filter(user=user).select_related('group')
    groups = [m.group for m in memberships]
    
    context = {
        'groups': groups
    }
    return render(request, 'groups.html', context)

@rate_limit(limit=60, window=60)
@login_required
def group_detail_view(request, group_id):
    user = request.user
    group = get_object_or_404(Group, id=group_id)
    
    # Verify membership and get role
    membership = GroupMember.objects.filter(group=group, user=user).first()
    if not membership:
        return render(request, '403.html', status=403)
    user_role = membership.role
        
    # Handle adding new member
    if request.method == 'POST' and 'new_member_email' in request.POST:
        if user_role != 'ADMIN':
            context = {'group': group, 'error': "Only Admins can add members."}
            return render(request, 'group_detail.html', context)
            
        email = strip_tags(request.POST.get('new_member_email', '')).strip()[:200]
        to_add = get_object_or_none(User, email=email)
        if to_add:
            GroupMember.objects.get_or_create(group=group, user=to_add)
        else:
            context = {'group': group, 'error': f"User with email '{email}' not found."}
            # reload data for rendering
            return render(request, 'group_detail.html', context)
        return redirect('group_detail', group_id=group.id)
        
    memberships = GroupMember.objects.filter(group=group).select_related('user', 'user__profile')
    members = [m.user for m in memberships]
    
    expenses = GroupExpense.objects.filter(group=group).select_related('paid_by').prefetch_related('payments__user', 'splits__user').order_by('-date')
    settlements = Settlement.objects.filter(group=group).select_related('from_user', 'to_user').order_by('-date')
    
    # Compute Net Balances
    net_balances = {m.id: 0.0 for m in members}
    
    for exp in expenses:
        payments = exp.payments.all()
        if payments.exists():
            for pmt in payments:
                if pmt.user_id in net_balances:
                    net_balances[pmt.user_id] += pmt.amount
        elif exp.paid_by_id:
            # Fallback for old data
            if exp.paid_by_id in net_balances:
                net_balances[exp.paid_by_id] += exp.amount
                
        for split in exp.splits.all():
            if split.user_id in net_balances:
                net_balances[split.user_id] -= split.amount
                
    for setl in settlements:
        if setl.from_user_id in net_balances:
            net_balances[setl.from_user_id] += setl.amount
        if setl.to_user_id in net_balances:
            net_balances[setl.to_user_id] -= setl.amount
            
    balances_list = []
    for m in members:
        net_val = round(net_balances[m.id], 2)
        balances_list.append({
            'userId': m.id,
            'name': m.first_name if m.first_name else m.username,
            'email': m.email,
            'net': net_val,
            'abs_net': abs(net_val)
        })
        
    # Debt Simplification Greedy Algorithm
    debtors = [b for b in balances_list if b['net'] < -0.01]
    creditors = [b for b in balances_list if b['net'] > 0.01]
    
    debtors.sort(key=lambda x: x['net']) # largest debt first
    creditors.sort(key=lambda x: x['net'], reverse=True) # largest credit first
    
    simplified_debts = []
    d_idx = 0
    c_idx = 0
    
    # Deep copy lists for greedy processing
    debtors_cp = [dict(d) for d in debtors]
    creditors_cp = [dict(c) for c in creditors]
    
    while d_idx < len(debtors_cp) and c_idx < len(creditors_cp):
        debtor = debtors_cp[d_idx]
        creditor = creditors_cp[c_idx]
        
        debt_amount = abs(debtor['net'])
        credit_amount = creditor['net']
        
        settled_amount = min(debt_amount, credit_amount)
        
        simplified_debts.append({
            'fromUserId': debtor['userId'],
            'fromUserName': debtor['name'],
            'toUserId': creditor['userId'],
            'toUserName': creditor['name'],
            'amount': round(settled_amount, 2)
        })
        
        debtor['net'] += settled_amount
        creditor['net'] -= settled_amount
        
        if abs(debtor['net']) < 0.01:
            d_idx += 1
        if abs(creditor['net']) < 0.01:
            c_idx += 1
            
    # Compute Analytics
    total_spend = sum(exp.amount for exp in expenses)
    contributions = {m.id: 0.0 for m in members}
    for exp in expenses:
        payments = exp.payments.all()
        if payments.exists():
            for pmt in payments:
                if pmt.user_id in contributions:
                    contributions[pmt.user_id] += pmt.amount
        else:
            if exp.paid_by_id in contributions:
                contributions[exp.paid_by_id] += exp.amount
        
    sorted_contribs = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
    highest_contrib_name = "N/A"
    if sorted_contribs and sorted_contribs[0][1] > 0:
        contrib_user = get_object_or_none(User, id=sorted_contribs[0][0])
        if contrib_user:
            highest_contrib_name = f"{contrib_user.first_name if contrib_user.first_name else contrib_user.username} (₹{round(sorted_contribs[0][1], 2)})"
            
    sorted_debtors = sorted(balances_list, key=lambda x: x['net'])
    highest_debtor_name = "None"
    if sorted_debtors and sorted_debtors[0]['net'] < -0.01:
        highest_debtor_name = f"{sorted_debtors[0]['name']} (owes ₹{abs(sorted_debtors[0]['net'])})"
        
    # Category parsing from descriptions
    category_spend = {}
    for exp in expenses:
        desc = exp.description.lower()
        category = "Others"
        if any(w in desc for w in ["food", "grocery", "dinner", "lunch", "restaurant", "cafe"]):
            category = "Food"
        elif any(w in desc for w in ["travel", "cab", "trip", "fuel", "car", "flight"]):
            category = "Travel"
        elif any(w in desc for w in ["rent", "flat", "room"]):
            category = "Rent"
        elif any(w in desc for w in ["electricity", "bill", "water", "utility"]):
            category = "Utilities"
        elif any(w in desc for w in ["movie", "concert", "show", "party", "entertainment"]):
            category = "Entertainment"
        elif any(w in desc for w in ["shop", "clothes", "shoes", "mall"]):
            category = "Shopping"
            
        category_spend[category] = category_spend.get(category, 0) + exp.amount
        
    category_breakdown = []
    pie_categories = []
    pie_values = []
    for name, val in category_spend.items():
        percentage = round((val / total_spend) * 100, 1) if total_spend > 0 else 0
        category_breakdown.append({
            'name': name,
            'value': round(val, 2),
            'percentage': percentage
        })
        pie_categories.append(name)
        pie_values.append(val)
        
    # Generate Analytics Charts using Matplotlib/Seaborn
    category_pie_chart = generate_spending_pie_chart(pie_categories, pie_values)
    
    standing_names = [b['name'] for b in balances_list]
    standing_nets = [b['net'] for b in balances_list]
    net_standing_chart = generate_group_net_standing_chart(standing_names, standing_nets)
    
    total_settled = sum(setl.amount for setl in settlements)
    settlement_ratio = round(total_settled / total_spend, 2) if total_spend > 0 else 0.0
    
    active_tab = strip_tags(request.GET.get('tab', 'ledger'))[:50] # ledger, balances, analytics
    
    extended_members = []
    for m in memberships:
        net_val = round(net_balances[m.user.id], 2)
        profile_pic = None
        if hasattr(m.user, 'profile'):
            profile_pic = m.user.profile.avatar
        extended_members.append({
            'id': m.user.id,
            'name': m.user.first_name if m.user.first_name else m.user.username,
            'email': m.user.email,
            'role': m.role,
            'joined_at': m.joined_at,
            'net': net_val,
            'abs_net': abs(net_val),
            'profile_pic': profile_pic
        })
        
    # --- Expense History Logic ---
    history_expenses = expenses
    search_query = strip_tags(request.GET.get('search', '').strip())[:100]
    category_filter = strip_tags(request.GET.get('category', 'All'))[:50]

    if search_query:
        history_expenses = history_expenses.filter(description__icontains=search_query)
    if category_filter != 'All':
        history_expenses = history_expenses.filter(category=category_filter)

    categories = ["Income", "Food", "Travel", "Shopping", "Entertainment", "Rent", "Utilities", "Health", "Education", "Investment", "Others"]

    from collections import defaultdict
    from datetime import datetime
    grouped_data = defaultdict(list)
    for exp in history_expenses:
        key = exp.date.strftime("%Y-%m")
        grouped_data[key].append(exp)

    grouped_months = []
    CATEGORY_COLORS = {
        "Food": "#34d399", "Travel": "#fb7185", "Shopping": "#fbbf24",
        "Entertainment": "#a78bfa", "Rent": "#22d3ee", "Utilities": "#f472b6",
        "Health": "#a7f3d0", "Education": "#c084fc", "Investment": "#818cf8",
        "Others": "#94a3b8"
    }

    for key in sorted(grouped_data.keys(), reverse=True):
        exps = grouped_data[key]
        year, month = map(int, key.split('-'))
        label = datetime(year, month, 1).strftime("%B %Y")
        
        total_month_spend = sum(e.amount for e in exps if e.category != "Income")
        
        category_sums = {}
        for e in exps:
            if e.category != "Income":
                category_sums[e.category] = category_sums.get(e.category, 0) + e.amount
                
        breakdown = []
        for cat_name, cat_val in category_sums.items():
            breakdown.append({
                'name': cat_name,
                'amount': cat_val,
                'color': CATEGORY_COLORS.get(cat_name, '#94a3b8')
            })
            
        grouped_months.append({
            'key': key,
            'label': label,
            'expenses': exps,
            'total_spend': total_month_spend,
            'category_breakdown': breakdown
        })
        
    context = {
        'group': group,
        'user_role': user_role,
        'members': members,
        'extended_members': extended_members,
        'expenses': expenses,
        'settlements': settlements,
        'balances': balances_list,
        'debts': simplified_debts,
        'total_spend': total_spend,
        'highest_contributor': highest_contrib_name,
        'highest_debtor': highest_debtor_name,
        'category_breakdown': category_breakdown,
        'category_pie_chart': category_pie_chart,
        'net_standing_chart': net_standing_chart,
        'total_settled': total_settled,
        'settlement_ratio': settlement_ratio,
        'active_tab': active_tab,
        'grouped_months': grouped_months,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_filter,
    }
    return render(request, 'group_detail.html', context)

@rate_limit(limit=60, window=60)
@login_required
def profile_view(request):
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        profile.phone = strip_tags(request.POST.get('phone', ''))[:20]
        profile.bio = strip_tags(request.POST.get('bio', ''))[:500]
        profile.country = strip_tags(request.POST.get('country', 'India'))[:100]
        profile.save()
        
        user.first_name = strip_tags(request.POST.get('name', user.first_name))[:150]
        user.save()
        return redirect('profile')
        
    context = {
        'profile': profile
    }
    return render(request, 'profile.html', context)

@rate_limit(limit=30, window=60)
@login_required
def add_expense_api(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            try:
                amount = float(body.get('amount'))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
                
            if amount <= 0:
                return JsonResponse({'error': 'Amount must be greater than zero.'}, status=400)
            category = strip_tags(body.get('category', ''))[:50]
            payment_method = strip_tags(body.get('paymentMethod', ''))[:50]
            description = strip_tags(body.get('description', ''))[:250]
            date_str = strip_tags(body.get('date', ''))[:20]
            
            txn_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            txn_date = django_timezone.make_aware(txn_date)
            
            # Check month restriction
            now = django_timezone.now()
            if txn_date.month != now.month or txn_date.year != now.year:
                return JsonResponse({'error': 'You can only add transactions for the current month.'}, status=400)
                
            expense = PersonalExpense.objects.create(
                user=request.user,
                amount=amount,
                category=category,
                payment_method=payment_method,
                description=description,
                date=txn_date,
                month=txn_date.month,
                year=txn_date.year
            )
            return JsonResponse({'id': expense.id, 'status': 'success'}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def edit_expense_api(request, expense_id):
    if request.method == 'POST' or request.method == 'PUT':
        try:
            expense = get_object_or_404(PersonalExpense, id=expense_id, user=request.user)
            body = json.loads(request.body)
            try:
                amount = float(body.get('amount'))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
                
            if amount <= 0:
                return JsonResponse({'error': 'Amount must be greater than zero.'}, status=400)
            category = strip_tags(body.get('category', ''))[:50]
            payment_method = strip_tags(body.get('paymentMethod', ''))[:50]
            description = strip_tags(body.get('description', ''))[:250]
            date_str = strip_tags(body.get('date', ''))[:20]
            
            txn_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            txn_date = django_timezone.make_aware(txn_date)
            
            expense.amount = amount
            expense.category = category
            expense.payment_method = payment_method
            expense.description = description
            expense.date = txn_date
            expense.save()
            
            recalculate_current_month(request.user)
            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST or PUT required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def delete_expense_api(request, expense_id):
    if request.method == 'POST' or request.method == 'DELETE':
        expense = get_object_or_404(PersonalExpense, id=expense_id, user=request.user)
        expense.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'POST or DELETE required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def delete_recurring_api(request, item_id, item_type):
    if request.method == 'POST' or request.method == 'DELETE':
        if item_type == 'income':
            item = get_object_or_404(RecurringIncome, id=item_id, user=request.user)
        elif item_type == 'expense':
            item = get_object_or_404(RecurringExpense, id=item_id, user=request.user)
        else:
            return JsonResponse({'error': 'Invalid type'}, status=400)
            
        item.delete()
        recalculate_current_month(request.user)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'POST or DELETE required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def edit_recurring_api(request, item_id, item_type):
    if request.method == 'POST' or request.method == 'PUT':
        try:
            body = json.loads(request.body)
            name = strip_tags(body.get('name', ''))[:100]
            try:
                amount = float(body.get('amount'))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
            
            if item_type == 'income':
                item = get_object_or_404(RecurringIncome, id=item_id, user=request.user)
            elif item_type == 'expense':
                item = get_object_or_404(RecurringExpense, id=item_id, user=request.user)
            else:
                return JsonResponse({'error': 'Invalid type'}, status=400)
                
            item.name = name
            item.amount = amount
            item.save()
            
            recalculate_current_month(request.user)
            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def add_group_expense_api(request, group_id):
    if request.method == 'POST':
        try:
            group = get_object_or_404(Group, id=group_id)
            if not GroupMember.objects.filter(group=group, user=request.user).exists():
                return JsonResponse({'error': 'Unauthorized: You are not a member of this group'}, status=403)
            body = json.loads(request.body)
            
            try:
                amount = float(body.get('amount'))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
                
            description = strip_tags(body.get('description', ''))[:250]
            payers = body.get('payers', []) # list of {userId, amount}
            payment_method = strip_tags(body.get('paymentMethod', 'UPI'))[:50]
            split_type = strip_tags(body.get('splitType', 'EQUAL'))[:50]
            splits_data = body.get('splits', []) # list of {userId, amount}
            date_str = strip_tags(body.get('date', ''))[:20]
            
            if amount <= 0:
                return JsonResponse({'error': 'Amount must be greater than zero.'}, status=400)
            if not payers:
                return JsonResponse({'error': 'At least one payer is required.'}, status=400)
            if not splits_data:
                return JsonResponse({'error': 'At least one person must be involved in the split to avoid division by zero.'}, status=400)
                
            # IDOR check: Verify all participants are in the group
            participant_ids = set([p['userId'] for p in payers] + [s['userId'] for s in splits_data])
            valid_member_ids = set(GroupMember.objects.filter(group=group).values_list('user_id', flat=True))
            for uid in participant_ids:
                if uid not in valid_member_ids:
                    return JsonResponse({'error': 'One or more users involved in this transaction are not members of the group.'}, status=400)
                    
            total_paid = sum(float(p['amount']) for p in payers)
            if abs(total_paid - amount) > 0.01:
                return JsonResponse({'error': f'Sum of payments ({total_paid}) must equal total amount ({amount}).'}, status=400)
            
            txn_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            txn_date = django_timezone.make_aware(txn_date)
            
            first_payer = get_object_or_404(User, id=payers[0]['userId'])
            
            desc_lower = description.lower()
            guessed_category = "Others"
            if any(w in desc_lower for w in ["food", "grocery", "dinner", "lunch", "restaurant", "cafe"]):
                guessed_category = "Food"
            elif any(w in desc_lower for w in ["travel", "cab", "trip", "fuel", "car", "flight"]):
                guessed_category = "Travel"
            elif any(w in desc_lower for w in ["rent", "flat", "room"]):
                guessed_category = "Rent"
            elif any(w in desc_lower for w in ["electricity", "bill", "water", "utility"]):
                guessed_category = "Utilities"
            elif any(w in desc_lower for w in ["movie", "concert", "show", "party", "entertainment"]):
                guessed_category = "Entertainment"
            elif any(w in desc_lower for w in ["shop", "clothes", "shoes", "mall"]):
                guessed_category = "Shopping"
                
            # Create group expense
            group_expense = GroupExpense.objects.create(
                group=group,
                paid_by=first_payer, # fallback for older records
                amount=amount,
                description=description,
                category=guessed_category,
                date=txn_date
            )
            
            # Create GroupExpensePayment records
            for p in payers:
                u = get_object_or_404(User, id=p['userId'])
                GroupExpensePayment.objects.create(
                    group_expense=group_expense,
                    user=u,
                    amount=float(p['amount'])
                )
            
            # Create splits
            if split_type == 'EQUAL':
                # splits_data is list of {userId}
                share = amount / len(splits_data)
                for s in splits_data:
                    u = get_object_or_404(User, id=s['userId'])
                    GroupExpenseSplit.objects.create(
                        group_expense=group_expense,
                        user=u,
                        amount=share
                    )
            elif split_type == 'EXACT':
                for s in splits_data:
                    u = get_object_or_404(User, id=s['userId'])
                    GroupExpenseSplit.objects.create(
                        group_expense=group_expense,
                        user=u,
                        amount=float(s['amount'])
                    )
            elif split_type == 'PERCENTAGE':
                for s in splits_data:
                    u = get_object_or_404(User, id=s['userId'])
                    share = (float(s['percentage']) / 100) * amount
                    GroupExpenseSplit.objects.create(
                        group_expense=group_expense,
                        user=u,
                        amount=share
                    )
                    
            return JsonResponse({'status': 'success'}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def edit_group_expense_api(request, group_id, expense_id):
    if request.method == 'POST' or request.method == 'PUT':
        try:
            group = get_object_or_404(Group, id=group_id)
            if not GroupMember.objects.filter(group=group, user=request.user).exists():
                return JsonResponse({'error': 'Unauthorized: You are not a member of this group'}, status=403)
            group_expense = get_object_or_404(GroupExpense, id=expense_id, group=group)
            body = json.loads(request.body)
            
            try:
                amount = float(body.get('amount'))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
                
            description = strip_tags(body.get('description', ''))[:250]
            payers = body.get('payers', [])
            split_type = strip_tags(body.get('splitType', 'EQUAL'))[:50]
            splits_data = body.get('splits', [])
            date_str = strip_tags(body.get('date', ''))[:20]
            
            if amount <= 0:
                return JsonResponse({'error': 'Amount must be greater than zero.'}, status=400)
            if not payers:
                return JsonResponse({'error': 'At least one payer is required.'}, status=400)
            if not splits_data:
                return JsonResponse({'error': 'At least one person must be involved in the split to avoid division by zero.'}, status=400)
                
            # IDOR check: Verify all participants are in the group
            participant_ids = set([p['userId'] for p in payers] + [s['userId'] for s in splits_data])
            valid_member_ids = set(GroupMember.objects.filter(group=group).values_list('user_id', flat=True))
            for uid in participant_ids:
                if uid not in valid_member_ids:
                    return JsonResponse({'error': 'One or more users involved in this transaction are not members of the group.'}, status=400)
                    
            total_paid = sum(float(p['amount']) for p in payers)
            if abs(total_paid - amount) > 0.01:
                return JsonResponse({'error': f'Sum of payments ({total_paid}) must equal total amount ({amount}).'}, status=400)
            
            txn_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            txn_date = django_timezone.make_aware(txn_date)
            
            first_payer = get_object_or_404(User, id=payers[0]['userId'])
            
            # Update expense object
            group_expense.amount = amount
            group_expense.description = description
            group_expense.date = txn_date
            group_expense.paid_by = first_payer
            group_expense.save()
            
            # Clear old payments and splits
            group_expense.payments.all().delete()
            group_expense.splits.all().delete()
            
            # Create new GroupExpensePayment records
            for p in payers:
                u = get_object_or_404(User, id=p['userId'])
                GroupExpensePayment.objects.create(
                    group_expense=group_expense,
                    user=u,
                    amount=float(p['amount'])
                )
            
            # Create new splits
            if split_type == 'EQUAL':
                share = amount / len(splits_data)
                for s in splits_data:
                    u = get_object_or_404(User, id=s['userId'])
                    GroupExpenseSplit.objects.create(group_expense=group_expense, user=u, amount=share)
            elif split_type == 'EXACT':
                for s in splits_data:
                    u = get_object_or_404(User, id=s['userId'])
                    GroupExpenseSplit.objects.create(group_expense=group_expense, user=u, amount=float(s['amount']))
            elif split_type == 'PERCENTAGE':
                for s in splits_data:
                    u = get_object_or_404(User, id=s['userId'])
                    share = (float(s['percentage']) / 100) * amount
                    GroupExpenseSplit.objects.create(group_expense=group_expense, user=u, amount=share)
                    
            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST or PUT required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def add_settlement_api(request, group_id):
    if request.method == 'POST':
        try:
            group = get_object_or_404(Group, id=group_id)
            if not GroupMember.objects.filter(group=group, user=request.user).exists():
                return JsonResponse({'error': 'Unauthorized: You are not a member of this group'}, status=403)
            body = json.loads(request.body)
            
            from_user_id = body.get('fromUserId')
            to_user_id = body.get('toUserId')
            try:
                amount = float(body.get('amount'))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid amount.'}, status=400)
            if amount <= 0:
                return JsonResponse({'error': 'Settlement amount must be greater than zero.'}, status=400)
            
            # IDOR check: Verify both users are members of the group
            valid_member_ids = set(GroupMember.objects.filter(group=group).values_list('user_id', flat=True))
            if from_user_id not in valid_member_ids or to_user_id not in valid_member_ids:
                return JsonResponse({'error': 'One or both users are not members of the group.'}, status=400)
                
            from_user = get_object_or_404(User, id=from_user_id)
            to_user = get_object_or_404(User, id=to_user_id)
            
            Settlement.objects.create(
                group=group,
                from_user=from_user,
                to_user=to_user,
                amount=amount,
                is_settled=True
            )
            return JsonResponse({'status': 'success'}, status=201)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def save_savings_goal_api(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            try:
                target = float(body.get('target', 0))
                current = float(body.get('current', 0))
            except (ValueError, TypeError):
                return JsonResponse({'error': 'Invalid float value.'}, status=400)
            
            profile = request.user.profile
            profile.savings_target = target
            profile.savings_current = current
            profile.save()
            
            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@rate_limit(limit=3, window=600)
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        name = strip_tags(request.POST.get('name', ''))[:100]
        email = strip_tags(request.POST.get('email', '')).strip()[:200]
        password = request.POST.get('password')
        confirm_pass = request.POST.get('confirm_password')
        
        if password != confirm_pass:
            return render(request, 'register.html', {'error': 'Passwords do not match'})
            
        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            return render(request, 'register.html', {'error': 'User with this email already exists'})
            
        # Enforce password policies
        try:
            validate_password(password)
        except ValidationError as e:
            return render(request, 'register.html', {'error': '\n'.join(e.messages)})
            
        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = name
        user.is_active = False # Require email activation
        user.save()
        
        # Send activation email
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        activation_link = request.build_absolute_uri(
            reverse('activate_account', kwargs={'uidb64': uid, 'token': token})
        )
        
        try:
            send_mail(
                'Activate your Expenzo Account',
                f'Hi {name},\n\nPlease click the link below to activate your account:\n{activation_link}',
                'noreply@expenzo.local',
                [email],
                fail_silently=False,
            )
            return render(request, 'login.html', {'message': 'Registration successful! Please check your console/terminal to activate your account.'})
        except Exception as e:
            # Fallback if email sending fails completely
            user.is_active = True
            user.save()
            login(request, user)
            return redirect('dashboard')
            
    return render(request, 'register.html')

def activate_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return redirect('dashboard')
    else:
        return render(request, 'login.html', {'error': 'Activation link is invalid or has expired.'})

@rate_limit(limit=10, window=60)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        email = strip_tags(request.POST.get('email', '')).strip()[:200]
        password = request.POST.get('password')
        
        # Rate Limiting Logic (Lockout 15 minutes after 5 failed attempts)
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        cache_key = f"login_attempts_{ip}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            return render(request, 'login.html', {'error': 'Too many failed login attempts. Please try again in 15 minutes.'})
            
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if not user.is_active:
                return render(request, 'login.html', {'error': 'Account is not activated. Please check your email / console for the link.'})
            cache.delete(cache_key) # Reset attempts on success
            login(request, user)
            return redirect('dashboard')
        else:
            cache.set(cache_key, attempts + 1, timeout=900) # 15 minutes lock
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@rate_limit(limit=30, window=60)
@login_required
def delete_group_expense_api(request, group_id, expense_id):
    if request.method == 'POST' or request.method == 'DELETE':
        group = get_object_or_404(Group, id=group_id)
        is_member = GroupMember.objects.filter(group=group, user=request.user).exists()
        if not is_member:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        expense = get_object_or_404(GroupExpense, id=expense_id, group=group)
        expense.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'POST or DELETE required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def delete_group_api(request, group_id):
    if request.method == 'POST' or request.method == 'DELETE':
        group = get_object_or_404(Group, id=group_id)
        membership = GroupMember.objects.filter(group=group, user=request.user).first()
        if not membership or membership.role != 'ADMIN':
            return JsonResponse({'error': 'Only Group Admins can delete this group.'}, status=403)
        group.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'POST or DELETE required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def edit_group_api(request, group_id):
    if request.method == 'POST':
        try:
            group = get_object_or_404(Group, id=group_id)
            membership = GroupMember.objects.filter(group=group, user=request.user).first()
            if not membership or membership.role != 'ADMIN':
                return JsonResponse({'error': 'Only Group Admins can edit group details.'}, status=403)
            body = json.loads(request.body)
            name = strip_tags(body.get('name', '')).strip()[:100]
            description = strip_tags(body.get('description', '')).strip()[:500]
            if not name:
                return JsonResponse({'error': 'Group name is required'}, status=400)
            group.name = name
            group.description = description
            group.save()
            return JsonResponse({'status': 'success'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

def get_user_group_balance(group, user_id):
    expenses = GroupExpense.objects.filter(group=group).prefetch_related('payments', 'splits')
    settlements = Settlement.objects.filter(group=group)
    net = 0.0
    
    for exp in expenses:
        for pmt in exp.payments.all():
            if pmt.user_id == user_id:
                net += pmt.amount
        if not exp.payments.exists() and exp.paid_by_id == user_id:
            net += exp.amount
            
        for split in exp.splits.all():
            if split.user_id == user_id:
                net -= split.amount
                
    for setl in settlements:
        if setl.from_user_id == user_id:
            net += setl.amount
        if setl.to_user_id == user_id:
            net -= setl.amount
            
    return round(net, 2)

@rate_limit(limit=30, window=60)
@login_required
def api_remove_member(request, group_id, member_id):
    if request.method == 'POST':
        group = get_object_or_404(Group, id=group_id)
        admin_membership = GroupMember.objects.filter(group=group, user=request.user).first()
        if not admin_membership or admin_membership.role != 'ADMIN':
            return JsonResponse({'error': 'Only Admins can remove members.'}, status=403)
            
        target_membership = get_object_or_404(GroupMember, group=group, user_id=member_id)
        
        balance = get_user_group_balance(group, member_id)
        if abs(balance) > 0.01:
            return JsonResponse({'error': f'This member cannot be removed until all balances are settled. Current balance: ₹{balance}'}, status=400)
            
        target_membership.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'POST required'}, status=405)

@rate_limit(limit=30, window=60)
@login_required
def api_leave_group(request, group_id):
    if request.method == 'POST':
        group = get_object_or_404(Group, id=group_id)
        membership = get_object_or_404(GroupMember, group=group, user=request.user)
        
        balance = get_user_group_balance(group, request.user.id)
        if abs(balance) > 0.01:
            return JsonResponse({'error': f'Please settle all balances before leaving the group. Current balance: ₹{balance}'}, status=400)
            
        membership.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'POST required'}, status=405)
