"""Pipeline de chunk + embed dos SourceDocument (Sprint 2.3)."""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from ai.markdown_utils import chunk_text, content_hash
from ai.models import SourceDocument
from ai.services import embed_text


class Command(BaseCommand):
    help = 'Gera chunks e embeddings dos documentos RAG (SourceDocument).'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', type=int, default=None, help='Filtrar por tenant_id')
        parser.add_argument('--reembed', action='store_true', help='Reembere mesmo com hash igual')

    def handle(self, *args, **options):
        tenant_id = options.get('tenant')
        reembed = options.get('reembed')
        qs = SourceDocument.objects.filter(is_active=True)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        processed = 0
        skipped = 0
        for doc in qs.iterator():
            text = (doc.content or '').strip()
            if doc.file and not text:
                # arquivos .txt/.md lidos como texto
                try:
                    if hasattr(doc.file, 'open'):
                        doc.file.open('rb')
                        raw = doc.file.read()
                        text = raw.decode('utf-8', errors='ignore')
                        doc.file.close()
                except Exception:
                    text = ''

            if not text:
                skipped += 1
                continue

            new_hash = content_hash(text)
            if not reembed and doc.content_hash == new_hash and doc.embedding:
                skipped += 1
                continue

            chunks = chunk_text(text)
            # MVP: 1 documento = 1 chunk principal (primeiro); campos chunk/embedding
            primary = chunks[0] if chunks else text
            doc.content = text
            doc.content_hash = new_hash
            doc.chunk = primary
            doc.embedding = embed_text(primary)
            doc.save(update_fields=['content', 'content_hash', 'chunk', 'embedding'])
            processed += 1
            self.stdout.write(f'  embed: {doc.title} ({len(primary)} chars)')

        self.stdout.write(self.style.SUCCESS(
            f'Concluído: {processed} processados, {skipped} ignorados.'
        ))
        if processed == 0 and skipped == 0:
            raise CommandError('Nenhum documento para processar.')
