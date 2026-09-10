from django.urls import path
from . import views

app_name = 'elections'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('booth/<int:election_id>/', views.voting_booth, name='voting_booth'),
    path('api/cast-ballot/<int:election_id>/', views.cast_ballot_api, name='cast_ballot_api'),
    path('receipt/<str:receipt_token>/', views.vote_receipt_view, name='vote_receipt'),
    path('results/', views.public_results_view, name='public_results'),
    path('results/<int:election_id>/', views.public_results_view, name='public_results_election'),
    path('verify-receipt/', views.verify_receipt_public, name='verify_receipt'),
    
    # Admin / Electoral Officer
    path('admin/command-center/', views.admin_command_center, name='admin_command_center'),
    path('admin/election/create/', views.create_election_view, name='create_election'),
    path('admin/election/<int:election_id>/status/<str:new_status>/', views.manage_election_status, name='manage_election_status'),
    path('admin/election/<int:election_id>/candidates/', views.candidate_manager, name='candidate_manager'),
    path('admin/voter-roster/', views.voter_roster_view, name='voter_roster'),
]
