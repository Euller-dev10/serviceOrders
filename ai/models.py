from django.conf import settings
from django.db import models

from ai.fields import VectorField
from core.models import TimeStampedModel, TenantScopedModel

DOC_TYPE_CHOICES = [
    ('MANUAL', 'Manual'),
    ('NORM', 'Norma'),
    ('TEMPLATE', 'Modelo'),
    ('POLICY', 'Política'),
]

ROLE_CHOICES = [
    ('user', 'user'),
    ('assistant', 'assistant'),
    ('system', 'system'),
    ('tool', 'tool'),
]


class AIConfig(TimeStampedModel):
    """Configuração de IA por tenant; tenant nulo = global no BD."""

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ai_configs',
    )
    provider = models.CharField(
        'Provedor', max_length=30, default='mock'
    )
    model_name = models.CharField('Modelo', max_length=80, blank=True)
    embedding_model = models.CharField('Modelo de embedding', max_length=80, blank=True)
    is_active = models.BooleanField('Ativa', default=True)

    class Meta:
        verbose_name = 'Configuração de IA'
        verbose_name_plural = 'Configurações de IA'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant'],
                condition=models.Q(tenant__isnull=False),
                name='uniq_aiconfig_per_tenant',
            ),
        ]

    def __str__(self):
        scope = self.tenant.name if self.tenant else 'Global'
        return f'{scope}: {self.provider}/{self.model_name or "default"}'


class ChatSession(TenantScopedModel):
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='ai_sessions',
    )
    title = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    model_provider = models.CharField(max_length=30, blank=True)
    model_name = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title or f'Sessão #{self.pk}'


class ChatMessage(TenantScopedModel):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='user')
    content = models.TextField()
    tool_calls = models.JSONField(null=True, blank=True)
    token_prompt = models.PositiveIntegerField(default=0)
    token_completion = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.role}: {self.content[:50]}'


class SourceDocument(TenantScopedModel):
    title = models.CharField(max_length=200)
    content = models.TextField()
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES, default='MANUAL')
    file = models.FileField(upload_to='ai/sources/', blank=True)
    chunk = models.TextField(blank=True)
    embedding = VectorField(dim=settings.AI_EMBEDDING_DIM)
    content_hash = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Documento fonte'
        verbose_name_plural = 'Documentos fonte'
        constraints = [
            models.UniqueConstraint(
                fields=['tenant', 'content_hash'],
                name='uniq_source_hash_per_tenant',
            ),
        ]

    def __str__(self):
        return self.title


class TokenUsage(TenantScopedModel):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='token_usages',
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='token_usages',
    )
    provider = models.CharField(max_length=30)
    model_name = models.CharField(max_length=80)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    cached_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=12, decimal_places=6, default=0)

    def __str__(self):
        return f'{self.provider}/{self.model_name} {self.prompt_tokens}+{self.completion_tokens}'


class SemanticCache(TenantScopedModel):
    question_normalized = models.CharField(max_length=500)
    question_embedding = VectorField(dim=settings.AI_EMBEDDING_DIM)
    answer = models.TextField()
    model_name = models.CharField(max_length=80)
    hit_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.question_normalized[:80]
