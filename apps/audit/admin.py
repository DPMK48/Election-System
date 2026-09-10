from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'timestamp', 'event_type', 'matric_no', 'ip_address', 'current_hash')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('matric_no', 'current_hash', 'prev_hash', 'details')
    readonly_fields = ('id', 'timestamp', 'event_type', 'user_id', 'matric_no', 'ip_address', 'details', 'prev_hash', 'current_hash')
