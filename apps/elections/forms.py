from django import forms
from .models import Election, Position, Candidate

class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ['title', 'description', 'category', 'faculty', 'department', 'target_level', 'status', 'start_time', 'end_time']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026/2027 SUG General Elections'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'faculty': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional: Faculty name'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional: Department name'}),
            'target_level': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional level filter'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

class PositionForm(forms.ModelForm):
    class Meta:
        model = Position
        fields = ['title', 'order_num', 'max_choices', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. President, Vice President'}),
            'order_num': forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
            'max_choices': forms.NumberInput(attrs={'class': 'form-control', 'value': 1}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['full_name', 'nickname', 'matric_no', 'photo_url', 'manifesto', 'cgpa_cleared', 'status']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'nickname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. "Apex Innovator"'}),
            'matric_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Candidate Matric No'}),
            'photo_url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '/static/img/candidate_avatar.svg'}),
            'manifesto': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'cgpa_cleared': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
