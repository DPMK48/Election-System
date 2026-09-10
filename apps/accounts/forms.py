from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()

class PasswordAuthForm(forms.Form):
    matric_no = forms.CharField(
        max_length=50,
        label="Registration Number / Staff ID",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. 20/54321U/1',
            'autofocus': True,
            'autocomplete': 'username',
            'id': 'id_matric_no'
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password',
            'autocomplete': 'current-password',
            'id': 'id_password'
        })
    )

class OTPAuthForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        label="6-Digit OTP Code",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center',
            'placeholder': '123456',
            'maxlength': '6',
            'autofocus': True,
            'autocomplete': 'one-time-code',
            'id': 'id_otp_code',
            'style': 'font-size: 1.75rem; letter-spacing: 0.4rem; font-weight: 700;'
        })
    )

class VoterRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Minimum 6 characters', 'id': 'id_reg_password'})
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Re-enter password', 'id': 'id_reg_confirm_password'})
    )

    class Meta:
        model = User
        fields = ['matric_no', 'first_name', 'last_name', 'email', 'faculty', 'department', 'level', 'phone_number']
        widgets = {
            'matric_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 20/54321U/1'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Surname'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'student@atbu.edu.ng'}),
            'faculty': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Science'}),
            'department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Computer Science'}),
            'level': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '100, 200, 300, 400, 500'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 08012345678'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if password and confirm and password != confirm:
            self.add_error('confirm_password', 'Passwords do not match.')
        return cleaned_data
