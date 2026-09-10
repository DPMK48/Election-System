from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('ledger/', views.ledger_explorer_view, name='ledger_explorer'),
    path('api/verify-chain/', views.verify_chain_api, name='verify_chain_api'),
]
