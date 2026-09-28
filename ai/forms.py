from django import forms

from ai.models import AIConfig, SourceDocument

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB corpus
ALLOWED_EXTENSIONS = ('.txt', '.md', '.pdf')


class SourceDocumentForm(forms.ModelForm):
    class Meta:
        model = SourceDocument
        fields = ('title', 'doc_type', 'file', 'content')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Título do documento'}),
            'doc_type': forms.Select(attrs={'class': 'form-select'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Cole o texto do manual/norma (opcional se houver arquivo)'}),
        }

    def clean(self):
        cleaned = super().clean()
        file = cleaned.get('file')
        content = (cleaned.get('content') or '').strip()
        if not file and not content:
            raise forms.ValidationError('Envie um arquivo (.txt/.md) ou cole o conteúdo do documento.')
        if file:
            name = (file.name or '').lower()
            if not name.endswith(ALLOWED_EXTENSIONS):
                raise forms.ValidationError('Formato aceito: .txt, .md ou .pdf (texto extraído).')
            if file.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError('Arquivo maior que 10 MB.')
        return cleaned


class AIConfigForm(forms.ModelForm):
    class Meta:
        model = AIConfig
        fields = ('provider', 'model_name', 'embedding_model', 'is_active')
        widgets = {
            'provider': forms.Select(
                choices=[
                    ('mock', 'Mock (testes)'),
                    ('openai', 'OpenAI'),
                    ('opencode', 'OpenCode Zen'),
                    ('anthropic', 'Anthropic'),
                ],
                attrs={'class': 'form-select'},
            ),
            'model_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex.: gpt-4o-mini'}),
            'embedding_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex.: text-embedding-3-small'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
