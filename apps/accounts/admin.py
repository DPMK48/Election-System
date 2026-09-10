from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('matric_no', 'first_name', 'last_name', 'role', 'faculty', 'department', 'level', 'totp_enabled', 'biometric_enrolled', 'is_locked')
    list_filter = ('role', 'faculty', 'department', 'level', 'is_locked', 'totp_enabled', 'biometric_enrolled')
    search_fields = ('matric_no', 'first_name', 'last_name', 'email')
    ordering = ('matric_no',)
    fieldsets = (
        (None, {'fields': ('matric_no', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'faculty', 'department', 'level')}),
        ('Role & Electoral Permissions', {'fields': ('role', 'is_verified', 'is_active', 'is_staff', 'is_superuser')}),
        ('Multi-Factor Authentication (MFA)', {'fields': ('totp_secret', 'totp_enabled', 'biometric_enrolled', 'failed_login_attempts', 'is_locked')}),
    )
