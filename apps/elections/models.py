import hashlib
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

GENESIS_BALLOT_HASH = "0" * 64

class Election(models.Model):
    CATEGORY_SUG = 'SUG'
    CATEGORY_FACULTY = 'FACULTY'
    CATEGORY_DEPARTMENTAL = 'DEPARTMENTAL'

    CATEGORY_CHOICES = [
        (CATEGORY_SUG, 'Student Union Government (SUG) General Election'),
        (CATEGORY_FACULTY, 'Faculty Representative Election'),
        (CATEGORY_DEPARTMENTAL, 'Departmental Association Election'),
    ]

    STATUS_DRAFT = 'DRAFT'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAUSED = 'PAUSED'
    STATUS_CONCLUDED = 'CONCLUDED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft (Setup Stage)'),
        (STATUS_ACTIVE, 'Active (Voting Open)'),
        (STATUS_PAUSED, 'Paused (Temporary Hold)'),
        (STATUS_CONCLUDED, 'Concluded (Official Results Finalized)'),
    ]

    title = models.CharField(max_length=200, help_text="e.g. 2026/2027 SUG General Elections")
    description = models.TextField(blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_SUG)
    faculty = models.CharField(max_length=150, blank=True, null=True, help_text="Required if Faculty Election")
    department = models.CharField(max_length=150, blank=True, null=True, help_text="Required if Departmental Election")
    target_level = models.IntegerField(blank=True, null=True, help_text="Optional level restriction (e.g. 400)")
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_elections')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"

    def is_active(self):
        now = timezone.now()
        return self.status == self.STATUS_ACTIVE and self.start_time <= now <= self.end_time

    def total_ballots_cast(self):
        return self.hasvoted_set.count()

    def get_last_ballot_hash(self):
        """Returns the latest ballot hash in this election's cryptographic chain."""
        last_ballot = self.ballots.order_by('-id').first()
        return last_ballot.ballot_hash if last_ballot else GENESIS_BALLOT_HASH


class Position(models.Model):
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='positions')
    title = models.CharField(max_length=150, help_text="e.g. President, Vice President, Secretary General")
    order_num = models.IntegerField(default=1, help_text="Display order on ballot")
    max_choices = models.IntegerField(default=1, help_text="Maximum candidate choices allowed")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['election', 'order_num', 'id']

    def __str__(self):
        return f"{self.title} ({self.election.title})"


class Candidate(models.Model):
    STATUS_APPROVED = 'APPROVED'
    STATUS_PENDING = 'PENDING'
    STATUS_DISQUALIFIED = 'DISQUALIFIED'

    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Cleared & Approved'),
        (STATUS_PENDING, 'Pending Screening'),
        (STATUS_DISQUALIFIED, 'Disqualified'),
    ]

    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='candidates')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='candidacies')
    full_name = models.CharField(max_length=150)
    nickname = models.CharField(max_length=100, blank=True, null=True, help_text="Campaign Alias / Moniker")
    matric_no = models.CharField(max_length=50, blank=True, null=True)
    photo_url = models.CharField(max_length=300, blank=True, null=True, default='/static/img/default_avatar.svg')
    manifesto = models.TextField(help_text="Key campaign agenda and vision")
    cgpa_cleared = models.BooleanField(default=True, help_text="Academic clearance by Senate Committee")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_APPROVED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['position', 'full_name']

    def __str__(self):
        alias = f' "{self.nickname}"' if self.nickname else ''
        return f"{self.full_name}{alias} - {self.position.title}"

    def get_vote_count(self):
        return self.ballots.count()


class Ballot(models.Model):
    """
    Anonymous Cryptographic Ballot Record.
    Stores the vote choice in a chained hash sequence without storing voter identity.
    """
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='ballots')
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='ballots')
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='ballots')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    receipt_token = models.CharField(max_length=64, db_index=True, help_text="Zero-knowledge receipt token for public verifier")
    prev_ballot_hash = models.CharField(max_length=64, db_index=True)
    ballot_hash = models.CharField(max_length=64, unique=True, db_index=True)
    nonce = models.CharField(max_length=32, default=uuid.uuid4().hex)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"Ballot #{self.id} [{self.election.title}] -> {self.position.title}: {self.candidate.full_name}"

    def compute_ballot_hash(self, prev_hash):
        payload = f"{prev_hash}|{self.election_id}|{self.position_id}|{self.candidate_id}|{self.timestamp.isoformat()}|{self.receipt_token}|{self.nonce}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()


class HasVoted(models.Model):
    """
    Guarantees Single-Vote Enforcement.
    Stores voter participation per election to prevent double voting.
    """
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(default=timezone.now)
    receipt_token = models.CharField(max_length=64, unique=True, help_text="Receipt token issued to voter")
    polling_terminal_ip = models.CharField(max_length=45, default='127.0.0.1')

    class Meta:
        unique_together = ('election', 'voter')
        verbose_name = 'Voter Participation Record'
        verbose_name_plural = 'Voter Participation Records (HasVoted)'

    def __str__(self):
        return f"Voter {self.voter.matric_no} voted in {self.election.title} at {self.timestamp}"
