from django.contrib import admin
from .models import Election, Position, Candidate, Ballot, HasVoted

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'start_time', 'end_time', 'created_at')
    list_filter = ('category', 'status', 'faculty', 'department')
    search_fields = ('title', 'description')

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ('title', 'election', 'order_num', 'max_choices')
    list_filter = ('election',)
    search_fields = ('title',)

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'nickname', 'position', 'matric_no', 'cgpa_cleared', 'status')
    list_filter = ('status', 'cgpa_cleared', 'position__election')
    search_fields = ('full_name', 'nickname', 'matric_no')

@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    list_display = ('id', 'election', 'position', 'candidate', 'timestamp', 'receipt_token', 'ballot_hash')
    list_filter = ('election', 'position')
    search_fields = ('receipt_token', 'ballot_hash')
    readonly_fields = ('election', 'position', 'candidate', 'timestamp', 'receipt_token', 'prev_ballot_hash', 'ballot_hash', 'nonce')

@admin.register(HasVoted)
class HasVotedAdmin(admin.ModelAdmin):
    list_display = ('voter', 'election', 'receipt_token', 'timestamp', 'polling_terminal_ip')
    list_filter = ('election',)
    search_fields = ('voter__matric_no', 'receipt_token')
    readonly_fields = ('voter', 'election', 'receipt_token', 'timestamp', 'polling_terminal_ip')
