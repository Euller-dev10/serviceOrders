from django.urls import path

from ai.views import (
    AIConfigUpdateView,
    ChatDetailView,
    ChatIndexView,
    ChatMessageSendView,
    ChatSessionCreateView,
    ChatStreamView,
    SourceDocumentCreateView,
    SourceDocumentDeleteView,
    SourceDocumentListView,
)

urlpatterns = [
    path('ia/', ChatIndexView.as_view(), name='chat_index'),
    path('ia/sessao/nova/', ChatSessionCreateView.as_view(), name='chat_session_create'),
    path('ia/sessao/<int:pk>/', ChatDetailView.as_view(), name='chat_detail'),
    path('ia/sessao/<int:pk>/mensagem/', ChatMessageSendView.as_view(), name='chat_message_send'),
    path('ia/fontes/', SourceDocumentListView.as_view(), name='source_list'),
    path('ia/fontes/nova/', SourceDocumentCreateView.as_view(), name='source_create'),
    path('ia/fontes/<int:pk>/excluir/', SourceDocumentDeleteView.as_view(), name='source_delete'),
    path('ia/config/', AIConfigUpdateView.as_view(), name='ai_config'),
    path('api/ia/sessao/<int:pk>/eventos/', ChatStreamView.as_view(), name='chat_stream'),
]
