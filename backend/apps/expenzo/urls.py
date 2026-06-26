from django.urls import path
from django.contrib.auth import views as auth_views
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
    path('activate/<uidb64>/<token>/', views.activate_account, name='activate_account'),
    
    # Password Reset
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    
    # API endpoints
    path('api/expenses/add/', views.add_expense_api, name='api_add_expense'),
    path('api/expenses/edit/<int:expense_id>/', views.edit_expense_api, name='api_edit_expense'),
    path('api/profile/change-password/', views.api_change_password, name='api_change_password'),
    path('api/profile/delete-account/', views.api_delete_account, name='api_delete_account'),
    path('api/expenses/delete/<int:expense_id>/', views.delete_expense_api, name='api_delete_expense'),
    path('api/recurring/delete/<int:item_id>/<str:item_type>/', views.delete_recurring_api, name='api_delete_recurring'),
    path('api/recurring/edit/<int:item_id>/<str:item_type>/', views.edit_recurring_api, name='api_edit_recurring'),
    path('api/groups/<int:group_id>/expense/add/', views.add_group_expense_api, name='api_add_group_expense'),
    path('api/groups/<int:group_id>/expense/edit/<int:expense_id>/', views.edit_group_expense_api, name='api_edit_group_expense'),
    path('api/groups/<int:group_id>/expense/delete/<int:expense_id>/', views.delete_group_expense_api, name='api_delete_group_expense'),
    path('api/groups/<int:group_id>/settlement/add/', views.add_settlement_api, name='api_add_settlement'),
    path('api/groups/<int:group_id>/delete/', views.delete_group_api, name='api_delete_group'),
    path('api/groups/<int:group_id>/edit/', views.edit_group_api, name='api_edit_group'),
    path('api/groups/<int:group_id>/member/<int:member_id>/remove/', views.api_remove_member, name='api_remove_member'),
    path('api/groups/<int:group_id>/leave/', views.api_leave_group, name='api_leave_group'),
    path('api/savings/save/', views.save_savings_goal_api, name='api_save_savings_goal'),
]
