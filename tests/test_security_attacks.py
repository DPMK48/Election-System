import json
from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.elections.models import Election, Position, Candidate, HasVoted, Ballot
from apps.audit.models import AuditLog

class SecurityAttacksTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="20/54321U/1",
            matric_no="20/54321U/1",
            password="VoterPass123!",
            first_name="Chukwuma",
            last_name="Okonkwo"
        )

        now = timezone.now()
        self.election = Election.objects.create(
            title="SUG Election",
            status=Election.STATUS_ACTIVE,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=1)
        )
        self.position = Position.objects.create(
            election=self.election,
            title="President",
            order_num=1
        )
        self.candidate = Candidate.objects.create(
            position=self.position,
            full_name="David Obinna Eze",
            status=Candidate.STATUS_APPROVED
        )

    def test_stage_skip_to_step2_blocked(self):
        """Attempting to access Step 2 without completing Step 1 is blocked."""
        response = self.client.get(reverse('accounts:login_step2_otp'))
        self.assertRedirects(response, reverse('accounts:access_denied'))
        
        # Verify security alert logged to audit trail
        alert_exists = AuditLog.objects.filter(event_type=AuditLog.EVENT_STAGE_SKIP_BLOCKED).exists()
        self.assertTrue(alert_exists)

    def test_stage_skip_to_step3_blocked(self):
        """Attempting to access Step 3 without completing Step 2 is blocked."""
        response = self.client.get(reverse('accounts:login_step3_biometric'))
        self.assertRedirects(response, reverse('accounts:access_denied'))

    def test_unauthenticated_ballot_cast_blocked(self):
        """Attempting to cast ballot without 3-factor authentication is blocked."""
        response = self.client.post(
            reverse('elections:cast_ballot_api', args=[self.election.id]),
            data=json.dumps({'votes': {str(self.position.id): self.candidate.id}}),
            content_type='application/json'
        )
        # Should redirect to access denied due to voter_mfa_required decorator
        self.assertEqual(response.status_code, 302)

    def test_double_voting_prevention(self):
        """A voter cannot cast more than one ballot in the same election."""
        # 1. Simulate fully authenticated session
        session = self.client.session
        session['mfa_user_id'] = self.user.id
        session['mfa_matric_no'] = self.user.matric_no
        session['mfa_step'] = 'AUTHENTICATED'
        session.save()
        self.client.force_login(self.user)

        # 2. First ballot submission (Should Succeed)
        res1 = self.client.post(
            reverse('elections:cast_ballot_api', args=[self.election.id]),
            data=json.dumps({'votes': {str(self.position.id): self.candidate.id}}),
            content_type='application/json'
        )
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.json()['success'])
        self.assertEqual(HasVoted.objects.filter(election=self.election, voter=self.user).count(), 1)

        # 3. Second ballot submission (Must Fail with HTTP 409 Conflict)
        res2 = self.client.post(
            reverse('elections:cast_ballot_api', args=[self.election.id]),
            data=json.dumps({'votes': {str(self.position.id): self.candidate.id}}),
            content_type='application/json'
        )
        self.assertEqual(res2.status_code, 409)
        self.assertFalse(res2.json()['success'])

        # Verify double vote block logged in audit trail
        double_vote_logged = AuditLog.objects.filter(event_type=AuditLog.EVENT_DOUBLE_VOTE_BLOCKED).exists()
        self.assertTrue(double_vote_logged)
