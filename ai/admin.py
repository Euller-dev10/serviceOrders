from django.contrib import admin
from django.db.models import Count, Sum
from django.utils import timezone

from ai.models import AIConfig, ChatMessage, ChatSession, SemanticCache, SourceDocument, TokenUsage


@admin.register(AIConfig)
class AIConfigAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'provider', 'model_name', 'embedding_model', 'is_active', 'updated_at')
    list_filter = ('provider', 'is_active')
    search_fields = ('model_name', 'embedding_model', 'tenant__name')
    autocomplete_fields = ('tenant',)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ('role', 'content', 'token_prompt', 'token_completion', 'latency_ms', 'created_at')


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'tenant', 'user', 'title', 'model_provider', 'model_name', 'is_active', 'updated_at')
    list_filter = ('is_active', 'model_provider')
    search_fields = ('title', 'user__email')
    inlines = [ChatMessageInline]


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'tenant', 'doc_type', 'is_active', 'created_at')
    list_filter = ('doc_type', 'is_active')
    search_fields = ('title', 'content')
    readonly_fields = ('content_hash', 'embedding')


@admin.register(TokenUsage)
class TokenUsageAdmin(admin.ModelAdmin):
    list_display = (
        'tenant',
        'user',
        'provider',
        'model_name',
        'prompt_tokens',
        'completion_tokens',
        'cached_tokens',
        'cost_usd',
        'created_at',
    )
    list_filter = ('provider', 'model_name', 'created_at')
    readonly_fields = (
        'tenant', 'user', 'provider', 'model_name',
        'prompt_tokens', 'completion_tokens', 'cached_tokens', 'cost_usd',
    )
    change_list_template = 'admin/ai/tokenusage/changelist.html'

    def changelist_view(self, request, extra_context=None):
        today = timezone.localdate()
        start = today - timezone.timedelta(days=30)
        qs = self.get_queryset(request).filter(created_at__date__gte=start)

        by_tenant = (
            qs.values('tenant__name')
            .annotate(
                total_prompt=Sum('prompt_tokens'),
                total_completion=Sum('completion_tokens'),
                total_cached=Sum('cached_tokens'),
                requests=Count('id'),
            )
            .order_by('-total_prompt')
        )
        by_day = (
            qs.extra(select={'day': 'date(created_at)'})
            .values('day')
            .annotate(
                total_prompt=Sum('prompt_tokens'),
                total_completion=Sum('completion_tokens'),
                requests=Count('id'),
            )
            .order_by('day')
        )
        extra_context = extra_context or {}
        extra_context.update({
            'tokens_by_tenant': by_tenant,
            'tokens_by_day': by_day,
            'metrics_title': 'Tokens por dia / tenant (últimos 30 dias)',
        })
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SemanticCache)
class SemanticCacheAdmin(admin.ModelAdmin):
    list_display = ('question_normalized', 'tenant', 'model_name', 'hit_count', 'expires_at')
    list_filter = ('model_name',)
    search_fields = ('question_normalized',)
