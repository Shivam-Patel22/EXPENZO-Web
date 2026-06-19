from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('history/', views.history_view, name='history'),
    path('recurring/', views.recurring_view, name='recurring'),
    path('groups/', views.groups_view, name='groups'),
    path('groups/<int:group_id>/', views.group_detail_view, name='group_detail'),
    path('profile/', views.profile_view, name='profile'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    
    # API endpoints
    path('api/expenses/add/', views.add_expense_api, name='api_add_expense'),
    path('api/expenses/delete/<int:expense_id>/', views.delete_expense_api, name='api_delete_expense'),
    path('api/recurring/delete/<int:item_id>/<str:item_type>/', views.delete_recurring_api, name='api_delete_recurring'),
    path('api/recurring/edit/<int:item_id>/<str:item_type>/', views.edit_recurring_api, name='api_edit_recurring'),
    path('api/groups/<int:group_id>/expense/add/', views.add_group_expense_api, name='api_add_group_expense'),
    path('api/groups/<int:group_id>/expense/delete/<int:expense_id>/', views.delete_group_expense_api, name='api_delete_group_expense'),
    path('api/groups/<int:group_id>/settlement/add/', views.add_settlement_api, name='api_add_settlement'),
    path('api/groups/<int:group_id>/delete/', views.delete_group_api, name='api_delete_group'),
    path('api/groups/<int:group_id>/edit/', views.edit_group_api, name='api_edit_group'),
    path('api/groups/<int:group_id>/member/<int:member_id>/remove/', views.api_remove_member, name='api_remove_member'),
    path('api/groups/<int:group_id>/leave/', views.api_leave_group, name='api_leave_group'),
    path('api/savings/save/', views.save_savings_goal_api, name='api_save_savings_goal'),
]
