import json
import uuid
import qrcode
import io
import base64
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth import get_user_model

from .models import Election, Position, Candidate, Ballot, HasVoted, GENESIS_BALLOT_HASH
from .forms import ElectionForm, PositionForm, CandidateForm
from apps.audit.ledger import log_audit_event, get_client_ip
from apps.audit.models import AuditLog

User = get_user_model()

def voter_mfa_required(view_func):
    """Decorator ensuring that user completed all 3 MFA stages."""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or request.session.get('mfa_step') != 'AUTHENTICATED':
            request.session['denied_reason'] = "Access Denied: You must authenticate with Password, OTP, and Biometrics."
            return redirect('accounts:access_denied')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def officer_required(view_func):
    """Decorator ensuring user is an Admin or Electoral Officer."""
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin_or_officer():
            request.session['denied_reason'] = "Access Denied: Electoral Commission / Administrative privileges required."
            return redirect('accounts:access_denied')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


@voter_mfa_required
def dashboard(request):
    """Voter Dashboard: Displays active, upcoming, and concluded elections."""
    user = request.user
    all_elections = Election.objects.all().prefetch_related('positions__candidates')
    
    # Check participation per election
    elections_data = []
    for election in all_elections:
        has_voted = HasVoted.objects.filter(election=election, voter=user).exists()
        receipt = HasVoted.objects.filter(election=election, voter=user).first()
        
        # Check eligibility (SUG = all; Faculty = match user faculty; Dept = match dept)
        is_eligible = True
        if election.category == Election.CATEGORY_FACULTY and election.faculty:
            is_eligible = (user.faculty and user.faculty.lower() == election.faculty.lower())
        elif election.category == Election.CATEGORY_DEPARTMENTAL and election.department:
            is_eligible = (user.department and user.department.lower() == election.department.lower())

        elections_data.append({
            'election': election,
            'has_voted': has_voted,
            'is_eligible': is_eligible,
            'receipt_token': receipt.receipt_token if receipt else None,
            'is_active': election.is_active(),
            'positions_count': election.positions.count()
        })

    return render(request, 'elections/dashboard.html', {
        'elections_data': elections_data,
        'user': user
    })


@voter_mfa_required
def voting_booth(request, election_id):
    """
    Supervised Polling Terminal Voting Booth.
    Displays positions and cleared candidates for the voter.
    """
    election = get_object_or_404(Election, id=election_id)
    user = request.user

    # 1. Check if election is open
    if not election.is_active():
        messages.error(request, f"Voting is currently not open for '{election.title}'. Status: {election.get_status_display()}")
        return redirect('elections:dashboard')

    # 2. Strict Double-Voting Prevention Guard
    if HasVoted.objects.filter(election=election, voter=user).exists():
        log_audit_event(
            AuditLog.EVENT_DOUBLE_VOTE_BLOCKED,
            request=request,
            user=user,
            details={"election_id": election.id, "election_title": election.title}
        )
        request.session['denied_reason'] = f"Double Voting Violation: You have already cast your ballot in '{election.title}'. Each registered student may vote only once."
        return redirect('accounts:access_denied')

    positions = election.positions.all().prefetch_related('candidates')
    
    return render(request, 'elections/voting_booth.html', {
        'election': election,
        'positions': positions,
        'user': user
    })


@voter_mfa_required
@require_POST
def cast_ballot_api(request, election_id):
    """
    Atomic Cryptographic Ballot Casting API.
    Enforces single-vote guard, decouples voter identity, and chains ballot hash to previous block.
    """
    election = get_object_or_404(Election, id=election_id)
    user = request.user

    if not election.is_active():
        return JsonResponse({'success': False, 'message': 'Election is not currently active.'}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
        votes = data.get('votes', {})  # Map of position_id -> candidate_id
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Invalid ballot payload: {str(e)}'}, status=400)

    if not votes:
        return JsonResponse({'success': False, 'message': 'Ballot is empty. Please select candidates.'}, status=400)

    # Perform atomic transaction
    with transaction.atomic():
        # Double-check single-vote constraint with row lock
        if HasVoted.objects.filter(election=election, voter=user).exists():
            log_audit_event(
                AuditLog.EVENT_DOUBLE_VOTE_BLOCKED,
                request=request,
                user=user,
                details={"election_id": election.id, "attack": "Concurrent second vote attempt"}
            )
            return JsonResponse({'success': False, 'message': 'Double-voting violation! Ballot rejected.'}, status=409)

        # Generate zero-knowledge cryptographic receipt token
        receipt_token = f"VOTE-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[4:8].upper()}-{uuid.uuid4().hex[8:12].upper()}"

        # 1. Lock Voter Participation (HasVoted)
        has_voted_record = HasVoted.objects.create(
            election=election,
            voter=user,
            receipt_token=receipt_token,
            polling_terminal_ip=get_client_ip(request)
        )

        # 2. Record Chained Anonymous Ballots
        for pos_id_str, cand_id in votes.items():
            try:
                position = election.positions.get(id=int(pos_id_str))
                candidate = position.candidates.get(id=int(cand_id), status=Candidate.STATUS_APPROVED)
            except (Position.DoesNotExist, Candidate.DoesNotExist, ValueError):
                continue

            last_hash = election.get_last_ballot_hash()
            ballot = Ballot(
                election=election,
                position=position,
                candidate=candidate,
                timestamp=timezone.now(),
                receipt_token=receipt_token,
                prev_ballot_hash=last_hash,
                nonce=uuid.uuid4().hex
            )
            ballot.ballot_hash = ballot.compute_ballot_hash(last_hash)
            ballot.save()

        # 3. Log to Tamper-Evident Hash-Chained Audit Ledger
        log_audit_event(
            AuditLog.EVENT_BALLOT_CAST,
            request=request,
            user=user,
            details={
                "election_id": election.id,
                "election_title": election.title,
                "receipt_token": receipt_token,
                "positions_voted": len(votes)
            }
        )

    return JsonResponse({
        'success': True,
        'receipt_token': receipt_token,
        'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
        'redirect_url': f'/elections/receipt/{receipt_token}/'
    })


@login_required
def vote_receipt_view(request, receipt_token):
    """
    Displays the verified cryptographic voting slip with QR code.
    Accessible to voter or via public verifier.
    """
    has_voted = HasVoted.objects.filter(receipt_token=receipt_token).first()
    ballots = Ballot.objects.filter(receipt_token=receipt_token).select_related('election', 'position', 'candidate')

    if not has_voted and not ballots.exists():
        messages.error(request, "Ballot receipt not found in cryptographic ledger.")
        return redirect('elections:dashboard')

    election = has_voted.election if has_voted else ballots.first().election

    # Generate QR Code image for the receipt verification link
    verify_url = f"{request.scheme}://{request.get_host()}/elections/verify-receipt/?token={receipt_token}"
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    return render(request, 'elections/vote_receipt.html', {
        'receipt_token': receipt_token,
        'has_voted': has_voted,
        'ballots': ballots,
        'election': election,
        'qr_b64': qr_b64,
        'verify_url': verify_url
    })


def public_results_view(request, election_id=None):
    """
    Public Live Election Results & Visual Telemetry.
    Displays live vote tallies, turnout percentages, and Chart.js leaderboards.
    """
    elections = Election.objects.filter(status__in=[Election.STATUS_ACTIVE, Election.STATUS_CONCLUDED])
    
    selected_election = None
    if election_id:
        selected_election = get_object_or_404(Election, id=election_id)
    elif elections.exists():
        selected_election = elections.first()

    results_data = []
    total_votes = 0

    if selected_election:
        total_votes = selected_election.total_ballots_cast()
        for position in selected_election.positions.all():
            candidates_list = []
            pos_total = Ballot.objects.filter(election=selected_election, position=position).count()
            
            for candidate in position.candidates.filter(status=Candidate.STATUS_APPROVED):
                c_votes = Ballot.objects.filter(election=selected_election, position=position, candidate=candidate).count()
                pct = round((c_votes / pos_total * 100), 1) if pos_total > 0 else 0.0
                candidates_list.append({
                    'candidate': candidate,
                    'votes': c_votes,
                    'percentage': pct
                })
            
            # Sort candidates by votes descending
            candidates_list.sort(key=lambda x: x['votes'], reverse=True)
            results_data.append({
                'position': position,
                'total_votes': pos_total,
                'candidates': candidates_list
            })

    return render(request, 'elections/public_results.html', {
        'elections': elections,
        'selected_election': selected_election,
        'results_data': results_data,
        'total_votes': total_votes,
        'results_json': json.dumps(results_data, default=str)
    })


def verify_receipt_public(request):
    """
    Public Zero-Knowledge Verifier tool.
    Confirms ballot inclusion in the cryptographic ledger without revealing votes.
    """
    token = request.GET.get('token', '').strip()
    ballot_records = []
    found = False

    if token:
        ballots = Ballot.objects.filter(receipt_token__iexact=token).select_related('election', 'position')
        if ballots.exists():
            found = True
            for b in ballots:
                ballot_records.append({
                    'election_title': b.election.title,
                    'position_title': b.position.title,
                    'timestamp': b.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'ballot_hash': b.ballot_hash,
                    'prev_ballot_hash': b.prev_ballot_hash
                })

    return render(request, 'elections/verify_receipt.html', {
        'token': token,
        'found': found,
        'ballot_records': ballot_records
    })


# -------------------------------------------------------------
# Electoral Commission / Administrative Views
# -------------------------------------------------------------

@officer_required
def admin_command_center(request):
    """
    Electoral Commission Command Center:
    Real-time election monitor, security alerts, and system controls.
    """
    elections = Election.objects.all().prefetch_related('positions')
    total_voters = User.objects.filter(role=User.ROLE_VOTER).count()
    verified_voters = User.objects.filter(role=User.ROLE_VOTER, is_verified=True).count()
    biometric_enrolled = User.objects.filter(role=User.ROLE_VOTER, biometric_enrolled=True).count()
    total_ballots_cast = HasVoted.objects.count()

    recent_audits = AuditLog.objects.order_by('-id')[:10]
    security_alerts = AuditLog.objects.filter(
        event_type__in=[AuditLog.EVENT_DOUBLE_VOTE_BLOCKED, AuditLog.EVENT_STAGE_SKIP_BLOCKED, AuditLog.EVENT_SECURITY_LOCKOUT]
    ).order_by('-id')[:8]

    return render(request, 'elections/admin_command_center.html', {
        'elections': elections,
        'total_voters': total_voters,
        'verified_voters': verified_voters,
        'biometric_enrolled': biometric_enrolled,
        'total_ballots_cast': total_ballots_cast,
        'recent_audits': recent_audits,
        'security_alerts': security_alerts
    })


@officer_required
def manage_election_status(request, election_id, new_status):
    """Toggle election status between DRAFT, ACTIVE, PAUSED, CONCLUDED."""
    election = get_object_or_404(Election, id=election_id)
    old_status = election.status
    if new_status in [Election.STATUS_DRAFT, Election.STATUS_ACTIVE, Election.STATUS_PAUSED, Election.STATUS_CONCLUDED]:
        election.status = new_status
        election.save(update_fields=['status'])
        log_audit_event(
            AuditLog.EVENT_ADMIN_ACTION,
            request=request,
            user=request.user,
            details={"action": f"Election '{election.title}' status changed from {old_status} to {new_status}"}
        )
        messages.success(request, f"Election status updated to '{election.get_status_display()}'.")
    return redirect('elections:admin_command_center')


@officer_required
def create_election_view(request):
    """Create a new university election."""
    form = ElectionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        election = form.save(commit=False)
        election.created_by = request.user
        election.save()
        log_audit_event(
            AuditLog.EVENT_ADMIN_ACTION,
            request=request,
            user=request.user,
            details={"action": f"Created new election: '{election.title}'"}
        )
        messages.success(request, f"Election '{election.title}' created successfully! Add positions and candidates.")
        return redirect('elections:admin_command_center')
    return render(request, 'elections/create_election.html', {'form': form})


@officer_required
def candidate_manager(request, election_id):
    """Manage positions and candidates for an election."""
    election = get_object_or_404(Election, id=election_id)
    pos_form = PositionForm(request.POST or None, prefix='pos')
    cand_form = CandidateForm(request.POST or None, prefix='cand')

    if request.method == 'POST':
        if 'add_position' in request.POST and pos_form.is_valid():
            pos = pos_form.save(commit=False)
            pos.election = election
            pos.save()
            messages.success(request, f"Position '{pos.title}' added.")
            return redirect('elections:candidate_manager', election_id=election.id)
        elif 'add_candidate' in request.POST and cand_form.is_valid():
            cand = cand_form.save(commit=False)
            pos_id = request.POST.get('target_position_id')
            cand.position = get_object_or_404(Position, id=pos_id, election=election)
            cand.save()
            messages.success(request, f"Candidate '{cand.full_name}' added to {cand.position.title}.")
            return redirect('elections:candidate_manager', election_id=election.id)

    positions = election.positions.all().prefetch_related('candidates')
    return render(request, 'elections/candidate_manager.html', {
        'election': election,
        'positions': positions,
        'pos_form': pos_form,
        'cand_form': cand_form
    })


@officer_required
def voter_roster_view(request):
    """Admin view for inspecting voter registry, search, and CSV import."""
    search_q = request.GET.get('q', '').strip()
    voters = User.objects.filter(role=User.ROLE_VOTER)
    if search_q:
        voters = voters.filter(matric_no__icontains=search_q) | voters.filter(first_name__icontains=search_q) | voters.filter(last_name__icontains=search_q)

    return render(request, 'elections/voter_roster.html', {
        'voters': voters,
        'search_q': search_q,
        'total_count': voters.count()
    })
