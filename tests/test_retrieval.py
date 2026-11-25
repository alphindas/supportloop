"""RRF maths and the retrieval pipeline, using fake models."""

from pathlib import Path

import pytest

from app.rag.chunking import Chunk
from app.rag.fusion import reciprocal_rank_fusion
from app.rag.models import FakeEmbedder, FakeReranker
from app.rag.retriever import HybridRetriever, RetrievalConfig, build_index

CONFIG = RetrievalConfig(bm25_top_k=5, dense_top_k=5, rrf_k=60, rerank_candidates=5)


def chunk(article_id: str, text: str) -> Chunk:
    return Chunk(f"{article_id}#overview", article_id, "cards", "Overview", text)


CHUNKS = [
    chunk("pin", "How to change your card PIN in the app"),
    chunk("fees", "Transfer fees for international SWIFT payments"),
    chunk("topup", "Top up your account by bank transfer or card"),
]


def test_rrf_rewards_items_ranked_well_in_both_lists() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "a"]], k=60)
    assert [item for item, _ in fused] == ["b", "a", "c"]
    assert fused[0][1] == pytest.approx(1 / 62 + 1 / 61)


def test_rrf_handles_items_missing_from_one_list() -> None:
    assert dict(reciprocal_rank_fusion([["a"], []], k=1)) == {"a": 0.5}


@pytest.mark.parametrize("reranker", [FakeReranker(), None])
def test_pipeline_finds_the_right_chunk(tmp_path: Path, reranker: FakeReranker | None) -> None:
    build_index(CHUNKS, FakeEmbedder(), tmp_path)
    retriever = HybridRetriever(CHUNKS, FakeEmbedder(), reranker, tmp_path, CONFIG)
    results = retriever.retrieve("change my PIN", top_k=2)
    assert results[0].chunk.article_id == "pin"
    assert results[0].bm25_rank == 1
    assert len(results) == 2


def test_dense_mode_does_not_use_bm25(tmp_path: Path) -> None:
    build_index(CHUNKS, FakeEmbedder(), tmp_path)
    dense = RetrievalConfig(5, 5, 60, 5, mode="dense")
    retriever = HybridRetriever(CHUNKS, FakeEmbedder(), FakeReranker(), tmp_path, dense)
    results = retriever.retrieve("change my PIN", top_k=3)
    assert results[0].chunk.article_id == "pin"
    assert all(r.bm25_rank is None and r.dense_rank is not None for r in results)
    assert retriever._bm25 is None


def test_stale_index_is_rejected(tmp_path: Path) -> None:
    build_index(CHUNKS, FakeEmbedder(), tmp_path)
    changed = [*CHUNKS, chunk("new", "A new article")]
    with pytest.raises(RuntimeError, match="make ingest"):
        HybridRetriever(changed, FakeEmbedder(), None, tmp_path, CONFIG)


def test_reingest_removes_deleted_chunks(tmp_path: Path) -> None:
    build_index(CHUNKS, FakeEmbedder(), tmp_path)
    build_index(CHUNKS[:2], FakeEmbedder(), tmp_path)
    retriever = HybridRetriever(CHUNKS[:2], FakeEmbedder(), None, tmp_path, CONFIG)
    found = retriever.retrieve("top up by bank transfer", top_k=5)
    assert "topup" not in {r.chunk.article_id for r in found}
