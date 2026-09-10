from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import AuditLog
from .ledger import verify_audit_chain, ensure_genesis_block

def ledger_explorer_view(request):
    """
    Public / Electoral Commission Blockchain-Style Audit Ledger Explorer.
    Displays hash-chained blocks and allows real-time mathematical validation.
    """
    ensure_genesis_block()
    
    event_filter = request.GET.get('event_type', '')
    entries_qs = AuditLog.objects.order_by('-id')

    if event_filter:
        entries_qs = entries_qs.filter(event_type=event_filter)

    paginator = Paginator(entries_qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Run quick chain verification
    chain_health = verify_audit_chain()

    return render(request, 'audit/ledger_explorer.html', {
        'page_obj': page_obj,
        'chain_health': chain_health,
        'total_blocks': AuditLog.objects.count(),
        'event_filter': event_filter,
        'event_choices': AuditLog.EVENT_CHOICES
    })

def verify_chain_api(request):
    """AJAX API endpoint returning real-time cryptographic audit chain integrity status."""
    result = verify_audit_chain()
    return JsonResponse(result)
