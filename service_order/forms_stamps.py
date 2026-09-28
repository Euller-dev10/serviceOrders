from django import forms
import re

from service_order.models import Stamp, StampDelivery


class StampCreateForm(forms.Form):
    numbers = forms.CharField(
        label='Números dos selos',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 8,
            'placeholder': 'S-000123\nS-000124\nS-000125',
        }),
        help_text='Informe um número por linha ou separe os números por vírgula ou ponto e vírgula.',
    )
    # Aceita o campo antigo para não quebrar integrações e formulários já enviados.
    number = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant

    def clean(self):
        cleaned_data = super().clean()
        raw = cleaned_data.get('numbers') or cleaned_data.get('number') or ''
        numbers = [number.strip() for number in re.split(r'[\n,;]+', raw) if number.strip()]
        if not numbers:
            self.add_error('numbers', 'Informe pelo menos um número de selo.')
            return cleaned_data
        if len(numbers) != len(set(numbers)):
            self.add_error('numbers', 'Não repita números no mesmo lote.')
        if self.tenant:
            existing = set(Stamp.objects.filter(tenant=self.tenant, number__in=numbers).values_list('number', flat=True))
            if existing:
                self.add_error('numbers', f'Número(s) já cadastrado(s): {", ".join(sorted(existing))}.')
        cleaned_data['numbers_list'] = numbers
        return cleaned_data


class StampDeliveryForm(forms.ModelForm):
    class Meta:
        model = StampDelivery
        fields = ('number', 'user')

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        qs = Stamp.objects.filter(status='AVAILABLE')
        if tenant is not None:
            qs = qs.filter(tenant=tenant)
        self.fields['number'].queryset = qs
        self.fields['number'].empty_label = 'Selecione um selo disponível...'

        user_qs = self.fields['user'].queryset.filter(is_superuser=False)
        if tenant is not None:
            user_qs = user_qs.filter(tenant=tenant)
        self.fields['user'].queryset = user_qs
        self.fields['user'].empty_label = 'Selecione o técnico...'


class StampBulkDeliveryForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=StampDeliveryForm.base_fields['user'].queryset,
        label='Técnico',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    stamps = forms.ModelMultipleChoiceField(
        queryset=Stamp.objects.none(),
        label='Selos disponíveis',
        widget=forms.CheckboxSelectMultiple,
        required=True,
        help_text='Marque os selos que serão entregues ao técnico.',
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        users = self.fields['user'].queryset.filter(is_superuser=False)
        if tenant is not None:
            users = users.filter(tenant=tenant, is_active=True)
            self.fields['stamps'].queryset = Stamp.objects.filter(
                tenant=tenant, status='AVAILABLE'
            ).order_by('number')
        self.fields['user'].queryset = users
