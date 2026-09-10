import json
import logging
from django.db import transaction, connection
from django.utils import timezone
from .models import AuditLog

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64

def sync_audit_sequence():
    """Synchronize the PostgreSQL sequence for AuditLog with max(id) to avoid duplicate key errors."""
    try:
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence('audit_auditlog', 'id'), coalesce(max(id), 1), max(id) IS NOT NULL) FROM audit_auditlog;"
                )
    except Exception as e:
        logger.warning(f"Could not sync PostgreSQL audit sequence: {e}")

def get_client_ip(request):
    """Extract real client IP address from request."""
    if not request:
        return '127.0.0.1'
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')

def ensure_genesis_block():
    """Ensure the immutable genesis block exists at Block #1."""
    genesis = AuditLog.objects.order_by('id').first()
    if not genesis:
        entry = AuditLog(
            timestamp=timezone.now(),
            event_type=AuditLog.EVENT_SYSTEM_INIT,
            user_id=None,
            matric_no="SYSTEM",
            ip_address="127.0.0.1",
            details=json.dumps({"info": "ATBU E-Voting Genesis Block Initialized"}),
            prev_hash=GENESIS_HASH,
        )
        entry.current_hash = entry.compute_hash(GENESIS_HASH)
        entry.save()
        sync_audit_sequence()
        logger.info(f"Genesis Block initialized with hash: {entry.current_hash}")
        return entry
    return genesis

@transaction.atomic
def log_audit_event(event_type, request=None, user=None, matric_no=None, details=None):
    """
    Atomically appends a new hash-chained audit block to the ledger.
    Guarantees thread-safe sequential chaining.
    """
    ensure_genesis_block()
    
    # Lock the latest entry to prevent race condition branching in concurrent environments
    last_entry = AuditLog.objects.select_for_update().order_by('-id').first()
    prev_hash = last_entry.current_hash if last_entry else GENESIS_HASH

    user_id = user.id if user and hasattr(user, 'id') else None
    user_matric = matric_no or (user.matric_no if user and hasattr(user, 'matric_no') else None)
    ip_addr = get_client_ip(request)

    details_str = ""
    if isinstance(details, (dict, list)):
        details_str = json.dumps(details, default=str)
    elif details is not None:
        details_str = str(details)

    entry = AuditLog(
        timestamp=timezone.now(),
        event_type=event_type,
        user_id=user_id,
        matric_no=user_matric,
        ip_address=ip_addr,
        details=details_str,
        prev_hash=prev_hash
    )
    entry.current_hash = entry.compute_hash(prev_hash)
    entry.save()
    return entry

def verify_audit_chain():
    """
    Validates the entire audit log chain from Genesis Block to current head.
    Returns:
        dict: {
            'is_valid': bool,
            'total_blocks': int,
            'tampered_block_id': int or None,
            'error_message': str or None
        }
    """
    ensure_genesis_block()
    entries = AuditLog.objects.order_by('id').all()
    total = len(entries)

    if total == 0:
        return {'is_valid': True, 'total_blocks': 0, 'tampered_block_id': None, 'error_message': None}

    expected_prev_hash = GENESIS_HASH

    for idx, entry in enumerate(entries):
        # 1. Verify prev_hash matches the previous block's current_hash
        if entry.prev_hash != expected_prev_hash:
            return {
                'is_valid': False,
                'total_blocks': total,
                'tampered_block_id': entry.id,
                'error_message': f"Broken link at Block #{entry.id}: prev_hash ({entry.prev_hash[:12]}...) != expected ({expected_prev_hash[:12]}...)"
            }

        # 2. Recalculate block hash from content and compare
        recomputed = entry.compute_hash(entry.prev_hash)
        if recomputed != entry.current_hash:
            return {
                'is_valid': False,
                'total_blocks': total,
                'tampered_block_id': entry.id,
                'error_message': f"Tampered content at Block #{entry.id}: computed hash ({recomputed[:12]}...) != stored current_hash ({entry.current_hash[:12]}...)"
            }

        expected_prev_hash = entry.current_hash

    return {
        'is_valid': True,
        'total_blocks': total,
        'tampered_block_id': None,
        'error_message': None,
        'latest_hash': expected_prev_hash
    }
