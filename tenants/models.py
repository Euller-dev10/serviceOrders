from django.db import models

from core.models import TimeStampedModel


class Tenant(TimeStampedModel):
    STATUS_TRIAL = 'TRIAL'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_SUSPENDED = 'SUSPENDED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_CHOICES = [
        (STATUS_TRIAL, 'Trial'),
        (STATUS_ACTIVE, 'Ativo'),
        (STATUS_SUSPENDED, 'Suspenso'),
        (STATUS_CANCELED, 'Cancelado'),
    ]

    name = models.CharField('Nome / razão social', max_length=150)
    legal_name = models.CharField('Razão social', max_length=150, blank=True)
    document = models.CharField('CNPJ', max_length=18, unique=True, db_index=True)
    state_registration = models.CharField('Insc. Estadual', max_length=20, blank=True)
    zip_code = models.CharField('CEP', max_length=10, blank=True)
    street = models.CharField('Rua', max_length=150, blank=True)
    neighborhood = models.CharField('Bairro', max_length=100, blank=True)
    city = models.CharField('Cidade', max_length=100, blank=True)
    state = models.CharField('UF', max_length=2, blank=True)
    phone = models.CharField('Telefone', max_length=20, blank=True)
    email = models.EmailField('Email de contato', blank=True)
    logo = models.ImageField('Logo', upload_to='tenants/logos/', blank=True, null=True)
    ipem_register = models.CharField('Nº registro IPEM/PR', max_length=50, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL
    )
    timezone = models.CharField(max_length=50, default='America/Sao_Paulo')

    class Meta:
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'

    def __str__(self):
        return self.name


class Plan(models.Model):
    code = models.SlugField('Código', unique=True)
    name = models.CharField('Nome', max_length=80)
    price_monthly_cents = models.PositiveIntegerField('Preço mensal (centavos)', default=0)
    max_technicians = models.PositiveIntegerField(
        'Máx. técnicos', null=True, blank=True, help_text='Vazio = ilimitado'
    )
    max_service_orders_per_month = models.PositiveIntegerField(
        'Máx. O.S./mês', null=True, blank=True, help_text='Vazio = ilimitado'
    )
    max_ai_credits_per_month = models.PositiveIntegerField(
        'Máx. créditos IA/mês', null=True, blank=True, help_text='Vazio = ilimitado'
    )
    ai_enabled = models.BooleanField('IA habilitada', default=True)
    required_signature = models.BooleanField('Assinatura obrigatória', default=False)
    is_active = models.BooleanField('Ativo', default=True)

    def __str__(self):
        return self.name


class Subscription(models.Model):
    STATUS_PAST_DUE = 'PAST_DUE'
    STATUS_TRIALING = 'TRIALING'
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_CHOICES = [
        (STATUS_PAST_DUE, 'Em atraso'),
        (STATUS_TRIALING, 'Em trial'),
        (STATUS_ACTIVE, 'Ativa'),
    ]

    tenant = models.OneToOneField(
        Tenant, on_delete=models.CASCADE, related_name='subscription'
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIALING)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    seats_used = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.tenant} → {self.plan} ({self.status})'
