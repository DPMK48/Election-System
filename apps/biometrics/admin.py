from django.contrib import admin
from .models import FingerprintTemplate

@admin.register(FingerprintTemplate)
class FingerprintTemplateAdmin(admin.ModelAdmin):
    list_display = ('user', 'finger_index', 'minutiae_count', 'is_active', 'enrolled_at')
    list_filter = ('finger_index', 'is_active', 'enrolled_at')
    search_fields = ('user__matric_no', 'user__first_name', 'user__last_name')
    readonly_fields = ('encrypted_template', 'nonce', 'tag', 'minutiae_count', 'enrolled_at')
