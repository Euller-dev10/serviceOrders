from django.db import models
from django.conf import settings
from django.utils import timezone

from core.managers import TenantManager
from core.models import TimeStampedModel


class Client(TimeStampedModel):

    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='clients',
        db_index=True,
    )
    name = models.CharField(max_length=100, verbose_name="Razão Social / Nome")
    document = models.CharField(max_length=30, verbose_name="CNPJ / CPF")
    state_registration = models.CharField(max_length=20, blank=True, null=True, verbose_name="Insc. Estadual")
    address = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rua")
    district = models.CharField(max_length=50, blank=True, null=True, verbose_name="Bairro")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    uf = models.CharField(max_length=5, blank=True, null=True, verbose_name='UF')
    cep = models.CharField(max_length=30, blank=True, null=True, verbose_name="CEP")
    contact = models.CharField(max_length=20, blank=True, null=True, verbose_name="Contato")
    email = models.CharField(max_length=100, blank=True, null=True, verbose_name="Email")

    objects = models.Manager()
    scoped = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'document'], name='uniq_client_tenant_document'),
        ]

    def __str__(self):
        return f'CNPJ - {self.document} - {self.name} - {self.city}'


class Unit(TimeStampedModel):

    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='units',
        db_index=True,
    )
    name = models.CharField(max_length=4, verbose_name="Unidade")

    objects = models.Manager()
    scoped = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'name'], name='uniq_unit_tenant_name'),
        ]

    def __str__(self):
        return self.name


class Scale(TimeStampedModel):

    TYPE_ROAD = 'RODOVIARIA'
    TYPE_RAIL = 'FERROVIARIA'
    TYPE_ROAD_RAIL = 'RODOFERROVIARIA'
    TYPE_CHOICES = [
        (TYPE_ROAD, 'Rodoviária'),
        (TYPE_RAIL, 'Ferroviária'),
        (TYPE_ROAD_RAIL, 'Rodoferroviária'),
    ]

    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='scales',
        db_index=True,
    )
    brand = models.CharField(max_length=30, verbose_name="Marca")
    model = models.CharField(max_length=20, verbose_name="Modelo")
    serie = models.CharField(max_length=30, verbose_name="Número de Série")
    capacity = models.CharField(max_length=30, verbose_name="Capacidade")
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='unit_scale', verbose_name="Unidade")
    division = models.CharField(max_length=10, verbose_name='E(kg)')
    tag = models.CharField(max_length=20, verbose_name="TAG", blank=True, null=True)
    inv_inmetro = models.CharField(max_length=10, verbose_name='N° Inventário do Inmetro', blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='scale_client', verbose_name="Proprietário")
    portaria = models.CharField(max_length=30, verbose_name="Portaria/Ano", blank=True, null=True)
    scale_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        blank=True,
        null=True,
        default=None,
        verbose_name='Tipo de balança',
    )
    minimum_capacity_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Capacidade mínima (kg)',
        blank=True,
        null=True,
    )
    metrological_class = models.CharField(
        max_length=10,
        verbose_name='Classe metrológica',
        blank=True,
        null=True,
    )

    objects = models.Manager()
    scoped = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'client', 'serie'],
                name='uniq_scale_serial_per_client',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'client'], name='idx_scale_tenant_client'),
            models.Index(fields=['tenant', 'serie'], name='idx_scale_tenant_serie'),
        ]

    def __str__(self):
        return f'{self.brand} - {self.model}'
    

class Stamp(TimeStampedModel):

    STATUS_CHOICES = [
        ('AVAILABLE', 'Para distribuir'),
        ('DISTRIBUTED', 'Com o técnico'),
        ('DAMAGED', 'Danificado / Cancelado'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='stamps',
        db_index=True,
    )
    number = models.CharField(max_length=20, verbose_name='Número de selo')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')

    objects = models.Manager()
    scoped = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'number'], name='uniq_stamp_tenant_number'),
        ]

    def __str__(self):
        return self.number


class StampDelivery(TimeStampedModel):

    STATUS_CHOICES = [
        ('AVAILABLE', 'Com o técnico (disponível)'),
        ('USED', 'Aplicado em equipamento'),
        ('DAMAGED', 'Danificado / Cancelado'),
    ]

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='stamp_deliveries',
        db_index=True,
    )
    number = models.ForeignKey(Stamp, on_delete=models.PROTECT, related_name='stam_util', verbose_name='Número de selo')
    date = models.DateField(verbose_name='Data', auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_stamp', verbose_name='Técnico')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')

    objects = models.Manager()
    scoped = TenantManager()

    def __str__(self):
        return f'{self.number}'

    def save(self, *args, **kwargs):
        selo = self.number

        if not self.pk:
            if self.status == 'AVAILABLE':
                selo.status = 'DISTRIBUTED'
            elif self.status == 'DAMAGED':
                selo.status = 'DAMAGED'
            selo.save()
        else:
            antigo_status = StampDelivery.objects.get(pk=self.pk).status
            if antigo_status == 'AVAILABLE' and self.status in ['USED', 'DAMAGED']:
                if self.status == 'DAMAGED':
                    selo.status = 'DAMAGED'
                    selo.save()

        super().save(*args, **kwargs)




class ServiceOrder(TimeStampedModel):

    STATUS_DRAFT = 'DRAFT'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Rascunho'),
        (STATUS_COMPLETED, 'Concluída'),
        (STATUS_CANCELED, 'Cancelada'),
    ]

    id = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='service_orders',
        db_index=True,
        null=True,
        blank=True,
    )
    number = models.PositiveIntegerField(
        'Número sequencial',
        null=True,
        blank=True,
        db_index=True,
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='client_os', verbose_name="Cliente")
    scale = models.ForeignKey(Scale, on_delete=models.CASCADE, related_name='scale_os', verbose_name="Balança")

    service1 = models.BooleanField(verbose_name='Manutenção corretiva', default=False)
    service2 = models.BooleanField(verbose_name='Manutenção preventiva', default=False)
    service3 = models.BooleanField(verbose_name='Certificação com pesos padrão', default=False)
    service4 = models.BooleanField(verbose_name='Ajustes com pesos padrão', default=False)
    service5 = models.BooleanField(verbose_name='Certificado de conformidade', default=False)
    service6 = models.BooleanField(verbose_name='Reparo em plataforma/estrutura metálica', default=False)
    service7 = models.BooleanField(verbose_name='Reparo em dispositivo eletroeletrônico', default=False)
    service8 = models.BooleanField(verbose_name='Reparo em comunicação / equipamentos externos', default=False)
    observation = models.CharField(max_length=500, verbose_name='Observações', blank=True, null=True)
    verified = models.BooleanField(verbose_name='Equipamento Verificado pelo INMETRO esse ano ?', default=False)
    date = models.DateTimeField(verbose_name='Data do Serviço', default=timezone.now)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='os_user', blank=True, null=True)
    new_instalation = models.BooleanField(verbose_name='Instalação nova', default=False)
    signature = models.TextField(verbose_name='Assinatura do cliente', blank=True, null=True)
    client_signer_name = models.CharField(
        max_length=120,
        verbose_name='Nome do responsável que assinou',
        blank=True,
    )
    stamp = models.OneToOneField(StampDelivery, on_delete=models.PROTECT, blank=True, null=True, verbose_name='stamp_service_order')
    stamp_retired = models.CharField(max_length=15, verbose_name="Número de Selo Retirado", blank=True, null=True)
    host = models.BooleanField(verbose_name='Hospedagem', default=False)
    food = models.BooleanField(verbose_name='Alimentação', default=False)
    status = models.CharField(
        'Status',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_COMPLETED,
        db_index=True,
    )

    objects = models.Manager()
    scoped = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'number'],
                name='uniq_os_number_per_tenant',
                condition=models.Q(number__isnull=False),
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', '-date'], name='idx_os_tenant_date'),
            models.Index(fields=['tenant', 'user'], name='idx_os_tenant_user'),
            models.Index(fields=['tenant', 'client'], name='idx_os_tenant_client'),
        ]

    def __str__(self):
        return f'{self.id} - {self.client}'

    @property
    def display_number(self):
        if self.number is None:
            return str(self.id)
        return str(self.number).zfill(5)


class TechnicalReport(TimeStampedModel):
    STATUS_DRAFT = 'DRAFT'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_CANCELED = 'CANCELED'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Rascunho'),
        (STATUS_COMPLETED, 'Concluído'),
        (STATUS_CANCELED, 'Cancelado'),
    ]
    SERVICE_REPAIR = 'REPARO'
    SERVICE_REFURBISHMENT = 'REFORMA'
    SERVICE_NEW = 'INSTRUMENTO_NOVO'
    SERVICE_CHOICES = [
        (SERVICE_REPAIR, 'Conserto'),
        (SERVICE_REFURBISHMENT, 'Reforma'),
        (SERVICE_NEW, 'Instrumento novo'),
    ]

    service_order = models.OneToOneField(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name='technical_report',
        verbose_name='Ordem de serviço',
    )
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='technical_reports',
        db_index=True,
    )
    number = models.PositiveIntegerField(null=True, blank=True, verbose_name='Número do relatório')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    owner_code = models.CharField(max_length=40, blank=True, verbose_name='Cód. proprietário')
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES, blank=True, verbose_name='Serviço executado')
    standard_weight_certificate = models.CharField(max_length=80, blank=True, verbose_name='Certificado do peso padrão')
    truck_plate_snapshot = models.CharField(max_length=20, blank=True, verbose_name='Placa do caminhão')
    technician_name = models.CharField(max_length=120, blank=True, verbose_name='Técnico')
    completed_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_reason = models.TextField(blank=True, verbose_name='Motivo do cancelamento')
    observation = models.TextField(blank=True, verbose_name='Observações do relatório')

    # Regulatory snapshots preserve the printed document after later catalog edits.
    scale_type_snapshot = models.CharField(max_length=20, blank=True)
    minimum_capacity_snapshot_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    metrological_class_snapshot = models.CharField(max_length=10, blank=True)
    capacity_snapshot = models.CharField(max_length=30, blank=True)
    division_snapshot = models.CharField(max_length=10, blank=True)
    stamp_applied_snapshot = models.CharField(max_length=20, blank=True)
    stamp_retired_snapshot = models.CharField(max_length=20, blank=True)
    eccentricity_applied_load_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Carga aplicada no ensaio de excentricidade (kg)',
    )

    objects = models.Manager()
    scoped = TenantManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'service_order'], name='uniq_report_tenant_service_order'),
            models.UniqueConstraint(
                fields=['tenant', 'number'],
                condition=models.Q(number__isnull=False),
                name='uniq_report_number_per_tenant',
            ),
        ]
        indexes = [
            models.Index(fields=['tenant', 'status'], name='idx_report_tenant_status'),
        ]

    def __str__(self):
        return f'Relatório técnico da O.S. {self.service_order.display_number}'

    @property
    def display_number(self):
        if self.number:
            return str(self.number).zfill(5)
        return str(self.pk).zfill(5) if self.pk else ''


class FidelityTest(models.Model):
    report = models.ForeignKey(TechnicalReport, on_delete=models.CASCADE, related_name='fidelity_tests')
    sequence = models.PositiveSmallIntegerField()
    load_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    indication_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    error_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    ema_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ['sequence']
        constraints = [models.UniqueConstraint(fields=['report', 'sequence'], name='uniq_fidelity_report_sequence')]


class EccentricityTest(models.Model):
    report = models.ForeignKey(TechnicalReport, on_delete=models.CASCADE, related_name='eccentricity_tests')
    sequence = models.PositiveSmallIntegerField()
    load_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    indication_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    error_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    ema_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ['sequence']
        constraints = [models.UniqueConstraint(fields=['report', 'sequence'], name='uniq_eccentricity_report_sequence')]


class WeighingTest(models.Model):
    report = models.ForeignKey(TechnicalReport, on_delete=models.CASCADE, related_name='weighing_tests')
    sequence = models.PositiveSmallIntegerField()
    load_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    indication_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    error_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    ema_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ['sequence']
        constraints = [models.UniqueConstraint(fields=['report', 'sequence'], name='uniq_weighing_report_sequence')]


class Part(models.Model):
    
    code = models.IntegerField(verbose_name='Código', blank=True, null=True)
    amount = models.IntegerField(verbose_name='Quantidade', blank=True, null=True)
    description = models.CharField(max_length=500, verbose_name='Descrição', blank=True, null=True)
    serie = models.CharField(max_length=20, verbose_name='Série', blank=True, null=True)
    base = models.BooleanField(verbose_name='Base de troca', default=False)
    service_order = models.ForeignKey(ServiceOrder, on_delete=models.CASCADE, blank=True, null=True, related_name='service_order_part', verbose_name='Ordem de Serviço')


class TimeService(models.Model):

    day = models.DateField(verbose_name='Dia', default=timezone.now, blank=True, null=True,)
    start = models.TimeField(verbose_name='Início', blank=True, null=True)
    stop = models.TimeField(verbose_name='Parada', blank=True, null=True,)
    total_hours = models.TimeField(verbose_name='Total de Horas', blank=True, null=True,)
    car = models.CharField(max_length=20, verbose_name='Carro', blank=True, null=True)
    truck = models.CharField(max_length=20, verbose_name='Caminhão', blank=True, null=True)
    service_order = models.ForeignKey(ServiceOrder, on_delete=models.PROTECT, blank=True, null=True, related_name='time_service')
