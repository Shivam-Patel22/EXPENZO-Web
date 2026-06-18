from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone as django_timezone
from datetime import datetime, timedelta
import json

from .models import (
    UserProfile, PersonalExpense, RecurringIncome, RecurringExpense,
    MonthlyRecurringProcessing, Group, GroupMember, GroupExpense,
    GroupExpenseSplit, Settlement
)
from .recurring_processor import process_recurring_finance, recalculate_current_month
from .charts import (
    generate_savings_gauge_chart, generate_spending_pie_chart,
    generate_group_net_standing_chart
)

# Helper function to get get_object_or_404 substitute for clean usage
def get_object_or_none(model, **kwargs):
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        return None

@login_required
def dashboard_view(request):
    user = request.user
    
    # Process recurring items dynamically
    process_recurring_finance(user)
    
    now = django_timezone.now()
    selected_year = now.year
    selected_month_num = now.month
    
    # Get filters
    filter_type = request.GET.get('filter', 'all') # all, daily, weekly, monthly
    search_query = request.GET.get('search', '').strip()
    
    # Fetch all personal expenses
    expenses = PersonalExpense.objects.filter(user=user).order_by('-date')
    
    # Apply search filter
    if search_query:
        expenses = expenses.filter(description__icontains=search_query)
        
    # Apply date filter for recent transactions
    filtered_expenses = expenses
    start_of_today = django_timezone.make_aware(datetime(now.year, now.month, now.day, 0, 0, 0))
    end_of_today = django_timezone.make_aware(datetime(now.year, now.month, now.day, 23, 59, 59))
    
    if filter_type == 'daily':
        filtered_expenses = expenses.filter(date__gte=start_of_today, date__lte=end_of_today)
    elif filter_type == 'weekly':
        seven_days_ago = start_of_today - timedelta(days=7)
        filtered_expenses = expenses.filter(date__gte=seven_days_ago, date__lte=end_of_today)
    elif filter_type == 'monthly':
        start_of_month = django_timezone.make_aware(datetime(now.year, now.month, 1, 0, 0, 0))
        # Last day of month
        if now.month == 12:
            end_of_month = django_timezone.make_aware(datetime(now.year + 1, 1, 1, 23, 59, 59)) - timedelta(days=1)
        else:
            end_of_month = django_timezone.make_aware(datetime(now.year, now.month + 1, 1, 23, 59, 59)) - timedelta(days=1)
        filtered_expenses = expenses.filter(date__gte=start_of_month, date__lte=end_of_month)
        
    recent_transactions = filtered_expenses[:5]
    
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

@login_required
def history_view(request):
    user = request.user
    
    # Get filters
    search_query = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', 'All').strip()
    payment_filter = request.GET.get('paymentMethod', 'All').strip()
    
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

@login_required
def recurring_view(request):
    user = request.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            new_type = request.POST.get('type')
            name = request.POST.get('name')
            amount = float(request.POST.get('amount', 0))
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

@login_required
def groups_view(request):
    user = request.user
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        
        # Create group and add creator as member
        group = Group.objects.create(name=name, description=description, created_by=user)
        GroupMember.objects.create(group=group, user=user)
        return redirect('group_detail', group_id=group.id)
        
    memberships = GroupMember.objects.filter(user=user)
    groups = [m.group for m in memberships]
    
    context = {
        'groups': groups
    }
    return render(request, 'groups.html', context)

@login_required
def group_detail_view(request, group_id):
    user = request.user
    group = get_object_or_404(Group, id=group_id)
    
    # Verify membership
    is_member = GroupMember.objects.filter(group=group, user=user).exists()
    if not is_member:
        return render(request, '403.html', status=403)
        
    # Handle adding new member
    if request.method == 'POST' and 'new_member_email' in request.POST:
        email = request.POST.get('new_member_email').strip()
        to_add = get_object_or_none(User, email=email)
        if to_add:
            GroupMember.objects.get_or_create(group=group, user=to_add)
        else:
            context = {'group': group, 'error': f"User with email '{email}' not found."}
            # reload data for rendering
            return render(request, 'group_detail.html', context)
        return redirect('group_detail', group_id=group.id)
        
    memberships = GroupMember.objects.filter(group=group)
    members = [m.user for m in memberships]
    
    expenses = GroupExpense.objects.filter(group=group).order_by('-date')
    settlements = Settlement.objects.filter(group=group).order_by('-date')
    
    # Compute Net Balances
    net_balances = {m.id: 0.0 for m in members}
    
    for exp in expenses:
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
        balances_list.append({
            'userId': m.id,
            'name': m.first_name if m.first_name else m.username,
            'email': m.email,
            'net': round(net_balances[m.id], 2)
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
    
    active_tab = request.GET.get('tab', 'ledger') # ledger, balances, analytics
    
    context = {
        'group': group,
        'members': members,
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
        'active_tab': active_tab
    }
    return render(request, 'group_detail.html', context)

@login_required
def profile_view(request):
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        profile.phone = request.POST.get('phone', '')
        profile.bio = request.POST.get('bio', '')
        profile.country = request.POST.get('country', 'India')
        profile.save()
        
        user.first_name = request.POST.get('name', user.first_name)
        user.save()
        return redirect('profile')
        
    context = {
        'profile': profile
    }
    return render(request, 'profile.html', context)

@csrf_exempt
@login_required
def add_expense_api(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            amount = float(body.get('amount'))
            category = body.get('category')
            payment_method = body.get('paymentMethod')
            description = body.get('description')
            date_str = body.get('date')
            
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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@csrf_exempt
@login_required
def delete_expense_api(request, expense_id):
    if request.method == 'POST' or request.method == 'DELETE':
        expense = get_object_or_404(PersonalExpense, id=expense_id, user=request.user)
        expense.delete()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'POST or DELETE required'}, status=405)

@csrf_exempt
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

@csrf_exempt
@login_required
def edit_recurring_api(request, item_id, item_type):
    if request.method == 'POST' or request.method == 'PUT':
        try:
            body = json.loads(request.body)
            name = body.get('name')
            amount = float(body.get('amount'))
            
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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@csrf_exempt
@login_required
def add_group_expense_api(request, group_id):
    if request.method == 'POST':
        try:
            group = get_object_or_404(Group, id=group_id)
            body = json.loads(request.body)
            
            amount = float(body.get('amount'))
            description = body.get('description')
            paid_by_id = body.get('paidBy')
            payment_method = body.get('paymentMethod', 'UPI')
            split_type = body.get('splitType', 'EQUAL')
            splits_data = body.get('splits', []) # list of {userId, amount}
            date_str = body.get('date')
            
            txn_date = datetime.strptime(date_str, "%Y-%m-%d") if date_str else datetime.now()
            txn_date = django_timezone.make_aware(txn_date)
            
            paid_by = get_object_or_404(User, id=paid_by_id)
            
            # Create group expense
            group_expense = GroupExpense.objects.create(
                group=group,
                paid_by=paid_by,
                amount=amount,
                description=description,
                category="Group Expense",
                date=txn_date
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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@csrf_exempt
@login_required
def add_settlement_api(request, group_id):
    if request.method == 'POST':
        try:
            group = get_object_or_404(Group, id=group_id)
            body = json.loads(request.body)
            
            from_user_id = body.get('fromUserId')
            to_user_id = body.get('toUserId')
            amount = float(body.get('amount'))
            
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
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

@csrf_exempt
@login_required
def save_savings_goal_api(request):
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            target = float(body.get('target', 0))
            current = float(body.get('current', 0))
            
            profile = request.user.profile
            profile.savings_target = target
            profile.savings_current = current
            profile.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'POST required'}, status=405)

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_pass = request.POST.get('confirm_password')
        
        if password != confirm_pass:
            return render(request, 'register.html', {'error': 'Passwords do not match'})
            
        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            return render(request, 'register.html', {'error': 'User with this email already exists'})
            
        user = User.objects.create_user(username=email, email=email, password=password)
        user.first_name = name
        user.save()
        
        login(request, user)
        return redirect('dashboard')
    return render(request, 'register.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'login.html', {'error': 'Invalid credentials'})
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    return redirect('login')
