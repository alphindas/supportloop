"""Split articles into chunks along their markdown headings."""

import hashlib
import re
from dataclasses import dataclass

from app.rag.kb import Article


@dataclass(frozen=True)
class Chunk:
    """A searchable piece of one article."""

    chunk_id: str
    article_id: str
    category: str
    heading: str
    text: str  # includes the article title and heading, so the chunk makes sense on its own


def slugify(heading: str) -> str:
    """Turn a heading into a lowercase, dash-separated ID."""
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-") or "section"


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split on '## ' headings. Text before the first heading is called 'Overview'."""
    sections: list[tuple[str, list[str]]] = [("Overview", [])]
    for line in body.splitlines():
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        else:
            sections[-1][1].append(line)
    joined = [(heading, "\n".join(lines).strip()) for heading, lines in sections]
    return [(heading, text) for heading, text in joined if text]


def split_long_text(text: str, max_words: int) -> list[str]:
    """Group paragraphs into pieces of at most max_words.

    A single paragraph longer than the limit is kept whole, so sentences and lists
    are never cut in half.
    """
    pieces: list[str] = []
    current: list[str] = []
    count = 0
    for paragraph in re.split(r"\n\s*\n", text):
        words = len(paragraph.split())
        if current and count + words > max_words:
            pieces.append("\n\n".join(current))
            current, count = [], 0
        current.append(paragraph)
        count += words
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def chunk_article(article: Article, max_words: int) -> list[Chunk]:
    """Chunk one article.

    IDs look like 'article-id#heading-slug'. They depend on the heading, not on the
    position, so editing or adding one section does not rename the others.
    """
    chunks: list[Chunk] = []
    seen: dict[str, int] = {}
    for heading, section in split_sections(article.body):
        for piece in split_long_text(section, max_words):
            base = f"{article.id}#{slugify(heading)}"
            seen[base] = seen.get(base, 0) + 1
            chunk_id = base if seen[base] == 1 else f"{base}-{seen[base]}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    article_id=article.id,
                    category=article.category,
                    heading=heading,
                    text=f"{article.title}\n{heading}\n{piece}",
                )
            )
    return chunks


def chunk_articles(articles: list[Article], max_words: int) -> list[Chunk]:
    """Chunk every article."""
    return [chunk for article in articles for chunk in chunk_article(article, max_words)]


def corpus_fingerprint(chunks: list[Chunk]) -> str:
    """Short hash of all chunk IDs and texts. It changes whenever the content changes."""
    digest = hashlib.sha256()
    for chunk in sorted(chunks, key=lambda c: c.chunk_id):
        digest.update(f"{chunk.chunk_id}\x00{chunk.text}\x00".encode())
    return digest.hexdigest()[:16]
