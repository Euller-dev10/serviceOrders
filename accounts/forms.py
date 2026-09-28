from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

User = get_user_model()


class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(
            attrs={'autofocus': True, 'placeholder': 'seu@email.com', 'class': 'form-control'}
        ),
    )
    password = forms.CharField(
        label='Senha',
        strip=False,
        widget=forms.PasswordInput(
            attrs={'placeholder': '••••••••', 'class': 'form-control'}
        ),
    )

    error_messages = {
        'invalid_login': 'Email ou senha inválidos.',
        'inactive': 'Esta conta está inativa.',
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        email = self.cleaned_data.get('email')
        password = self.cleaned_data.get('password')
        if email and password:
            from django.contrib.auth import authenticate

            self.user = authenticate(self.request, username=email, password=password)
            if self.user is None:
                raise forms.ValidationError(
                    self.error_messages['invalid_login'], code='invalid_login'
                )
            if not self.user.is_active:
                raise forms.ValidationError(
                    self.error_messages['inactive'], code='inactive'
                )
        return self.cleaned_data

    def get_user(self):
        return self.user


class EmailUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email',)
        widgets = {
            'email': forms.EmailInput(attrs={'placeholder': 'seu@email.com'}),
        }


class UserInviteForm(forms.ModelForm):
    """ADMIN convida usuários do tenant (email + role); senha definida no aceite."""

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class UserEditForm(forms.ModelForm):
    """Edição de usuário do tenant (nome, role, telefone, ativo)."""

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'phone', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class InviteAcceptForm(forms.Form):
    password1 = forms.CharField(
        label='Nova senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    password2 = forms.CharField(
        label='Confirmar senha',
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError('As senhas não coincidem.')
        if password1:
            import re

            if len(password1) < 8:
                raise forms.ValidationError('A senha deve ter pelo menos 8 caracteres.')
            if not re.search(r'[A-Za-z]', password1) or not re.search(r'\d', password1):
                raise forms.ValidationError('A senha deve conter letras e números.')
        return cleaned
