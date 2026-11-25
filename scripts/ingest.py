"""Chunk the knowledge base, embed it and build the search index."""

import time

from app.config import get_settings
from app.rag.chunking import chunk_articles, corpus_fingerprint
from app.rag.kb import load_articles
from app.rag.models import build_embedder
from app.rag.retriever import build_index


def main() -> None:
    """Build the index with the embedding model from settings."""
    settings = get_settings()
    articles = load_articles(settings.resolve(settings.kb_dir))
    chunks = chunk_articles(articles, settings.chunk_max_words)
    started = time.perf_counter()
    embedder = build_embedder(settings.embedding_model, settings.retrieval_device)
    build_index(chunks, embedder, settings.resolve(settings.index_dir))
    embedder.release()
    print(
        f"Indexed {len(articles)} articles as {len(chunks)} chunks with {settings.embedding_model} "
        f"in {time.perf_counter() - started:.1f}s (fingerprint {corpus_fingerprint(chunks)})"
    )


if __name__ == "__main__":
    main()
