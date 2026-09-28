from __future__ import annotations

import hashlib
import html
import re


def content_hash(text: str) -> str:
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def chunk_text(text: str, *, size: int = 1200, overlap: int = 150) -> list[str]:
    """Chunking simples por parágrafos/tamanho com sobreposição."""
    text = (text or '').strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]

    chunks: list[str] = []
    paragraphs = re.split(r'\n\s*\n', text)
    current = ''
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 <= size:
            current = f'{current}\n\n{para}' if current else para
        else:
            if current:
                chunks.append(current)
            # se parágrafo maior que size, quebra em fatias
            while len(para) > size:
                chunks.append(para[:size])
                para = para[max(0, size - overlap):]
            current = para
    if current:
        chunks.append(current)
    return chunks


def safe_markdown(text: str) -> str:
    """Markdown mínimo seguro: escapa HTML e permite apenas subset básico."""
    escaped = html.escape(text or '', quote=False)

    # code inline
    escaped = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', escaped)
    # bold
    escaped = re.sub(r'\*\*([^*\n]+)\*\*', r'<strong>\1</strong>', escaped)
    # italic
    escaped = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', escaped)
    # headings
    escaped = re.sub(r'^### (.+)$', r'<h4>\1</h4>', escaped, flags=re.M)
    escaped = re.sub(r'^## (.+)$', r'<h3>\1</h3>', escaped, flags=re.M)
    escaped = re.sub(r'^# (.+)$', r'<h2>\1</h2>', escaped, flags=re.M)
    # lists
    escaped = re.sub(r'^[-*] (.+)$', r'<li>\1</li>', escaped, flags=re.M)
    # links (http/https only)
    escaped = re.sub(
        r'\[([^\]]+)\]\((https?://[^)\s]+)\)',
        r'<a href="\2" rel="noopener noreferrer nofollow" target="_blank">\1</a>',
        escaped,
    )
    # line breaks → paragraphs simples
    escaped = escaped.replace('\n\n', '</p><p>')
    escaped = escaped.replace('\n', '<br>')
    return f'<p>{escaped}</p>'


def extract_citations(text: str) -> list[str]:
    """Extrai citações [[fonte: título]] da resposta."""
    return re.findall(r'\[\[fonte:\s*([^\]]+)\]\]', text or '')
