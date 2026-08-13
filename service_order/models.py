from django.db import models
from django.conf import settings
from django.utils import timezone

class Client(models.Model):

    id = models.AutoField(primary_key=True)
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

    def __str__(self):
        return f'CNPJ - {self.document} - {self.name} - {self.city}'


class Unit(models.Model):

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=4, verbose_name="Unidade")


    def __str__(self):
        return self.name


class Scale(models.Model):
    
    id = models.AutoField(primary_key=True)
    brand = models.CharField(max_length=30, verbose_name="Marca")
    model = models.CharField(max_length=20, verbose_name="Modelo")
    serie = models.CharField(max_length=30, verbose_name="Número de Série")
    capacity = models.CharField(max_length=30, verbose_name="Capacidade")
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='unit_scale', verbose_name="Unidade")
    division = models.CharField(max_length=10, verbose_name='E(kg)')
    tag = models.CharField(max_length=20, verbose_name="TAG", blank=True, null=True)
    inv_inmetro = models.CharField(max_length=10, verbose_name='N° Inventário do Inmetro', blank=True, null=True)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='scale_client', verbose_name="Proprietário")

    def __str__(self):
        return f'{self.brand} - {self.model}'
    

class Stamp(models.Model):

    STATUS_CHOICES = [
        ('DISPONIVEL', 'PARA DISTRIBUIR'),
        ('DISTRIBUÍDO', 'COM O TÉCNICO'),
        ('DANIFICADO', 'Danificado / Cancelado'),
    ]

    number = models.CharField(max_length=20, verbose_name='Número de selo')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONIVEL')


    def __str__(self):
        return self.number


class StampDelivery(models.Model):

    STATUS_CHOICES = [
        ('DISPONIVEL', 'Com o Técnico (Disponível)'),
        ('UTILIZADO', 'Aplicado em Equipamento'),
        ('DANIFICADO', 'Danificado / Cancelado'),
    ]

    number = models.ForeignKey(Stamp, on_delete=models.PROTECT, related_name='stam_util', verbose_name='Número de selo')
    date = models.DateField(verbose_name='Data', auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_stamp', verbose_name='Técnico')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DISPONIVEL')

    def __str__(self):
        return f'{self.number}'
    
    def save(self, *args, **kwargs):
        # Captura o selo vinculado a esta distribuição
        selo = self.number

        # SE FOR UM REGISTRO NOVO (Criando a distribuição pela primeira vez)
        if not self.pk:
            if self.status == 'DISPONIVEL':
                selo.status = 'DISTRIBUÍDO'
            elif self.status == 'DANIFICADO':
                selo.status = 'DANIFICADO'
            selo.save()

        # SE FOR UMA ATUALIZAÇÃO (Ex: Técnico usou o selo no equipamento e mudou para UTILIZADO)
        else:
            # Buscamos como a distribuição estava antes de ser alterada
            antigo_status = StampDelivery.objects.get(pk=self.pk).status
            
            # Se mudou de DISPONIVEL para UTILIZADO ou DANIFICADO
            if antigo_status == 'DISPONIVEL' and self.status in ['UTILIZADO', 'DANIFICADO']:
                # Se foi danificado, atualiza o selo original. Se foi utilizado, 
                # ele pode continuar como 'DISTRIBUÍDO' (pois já saiu do estoque).
                if self.status == 'DANIFICADO':
                    selo.status = 'DANIFICADO'
                    selo.save()

        # Executa o salvamento padrão do Django para a distribuição
        super().save(*args, **kwargs)




class ServiceOrder(models.Model):

    id = models.AutoField(primary_key=True)
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
    stamp = models.OneToOneField(StampDelivery, on_delete=models.PROTECT, blank=True, null=True, verbose_name='stamp_service_order')
    host = models.BooleanField(verbose_name='Hospedagem', default=False)
    food = models.BooleanField(verbose_name='Alimentação', default=False)

    


    def __str__(self):
        return f'{self.id} - {self.client}'


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




class Company(models.Model):

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, verbose_name="Razão Social / Nome")
    document = models.CharField(max_length=30, verbose_name="CNPJ / CPF")
    state_registration = models.CharField(max_length=20, blank=True, null=True, verbose_name="Insc. Estadual")
    address = models.CharField(max_length=50, blank=True, null=True, verbose_name="Rua")
    district = models.CharField(max_length=50, blank=True, null=True, verbose_name="Bairro")
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Cidade")
    uf = models.CharField(max_length=5, blank=True, null=True, verbose_name='UF')
    cep = models.CharField(max_length=30, blank=True, null=True, verbose_name="CEP")
    contact = models.CharField (max_length=20, blank=True, null=True, verbose_name="Contato")
    email = models.CharField(max_length=100, blank=True, null=True, verbose_name="Email")
    logo = models.ImageField(upload_to='service_order/', blank=True, null=True)
    
    def __str__(self):
        return f'CNPJ - {self.name} - {self.document} - {self.city}'