import re

import pandas as pd
import pytest

from SearchEngine.search_engine import BM25Index, NewsSearchEngine, parse_query


def simple_preprocessor(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text).casefold())


def test_parse_mixed_query():
    parsed = parse_query('Persija "transfer pemain" @"Sandy Firdaus" %2026 #Kompas')
    assert parsed.title_terms == ["Persija"]
    assert parsed.content_terms == ["transfer", "pemain"]
    assert parsed.authors == ["Sandy Firdaus"]
    assert parsed.years == ["2026"]
    assert parsed.media == ["Kompas"]


def test_invalid_year_is_rejected():
    with pytest.raises(ValueError, match="Format tahun tidak valid"):
        parse_query("Persija %abc")


def test_unmatched_quote_is_rejected():
    with pytest.raises(ValueError, match="tidak berpasangan"):
        parse_query('"transfer pemain')


def test_empty_author_filter_is_rejected():
    with pytest.raises(ValueError, match="nama penulis"):
        parse_query('@""')


def test_bm25_prefers_more_relevant_document():
    index = BM25Index([
        ["persija", "jakarta", "juara"],
        ["persija", "transfer", "pemain", "persija", "transfer"],
        ["persib", "bandung"],
    ])
    scores = index.get_scores(["persija", "transfer"])
    assert scores[1] > scores[0] > scores[2]


def test_search_combines_title_content_and_metadata(tmp_path):
    corpus = pd.DataFrame([
        {
            "doc_id": "KMP001", "title": "Persija Jakarta Umumkan Pemain Baru",
            "media": "Kompas", "date": "2026-08-15", "author": "Sandy Firdaus",
            "text_final": "transfer pemain persija jakarta skuad baru",
        },
        {
            "doc_id": "ANT001", "title": "Persib Rekrut Pemain Baru",
            "media": "ANTARA", "date": "2026-08-16", "author": "Budi Santoso",
            "text_final": "transfer pemain persib bandung skuad",
        },
        {
            "doc_id": "IDN001", "title": "Persija Menang Pertandingan",
            "media": "IDN Times", "date": "2025-08-17", "author": "Sandy Firdaus",
            "text_final": "persija menang pertandingan liga",
        },
    ])
    path = tmp_path / "processed.csv"
    corpus.to_csv(path, index=False)

    engine = NewsSearchEngine(path, query_preprocessor=simple_preprocessor)
    results = engine.search('Persija "transfer pemain" @"Sandy Firdaus" %2026 #Kompas')

    assert len(results) == 1
    assert results[0]["doc_id"] == "KMP001"
    assert results[0]["matched_fields"] == ["title", "content"]
    assert results[0]["score"] is not None


def test_filter_only_query_returns_matching_documents(tmp_path):
    corpus = pd.DataFrame([
        {"doc_id": "KMP001", "title": "A", "media": "Kompas", "date": "2026-08-15", "author": "Sandy", "text_final": "alpha beta"},
        {"doc_id": "ANT001", "title": "B", "media": "ANTARA", "date": "2026-08-16", "author": "Budi", "text_final": "beta gamma"},
    ])
    path = tmp_path / "processed.csv"
    corpus.to_csv(path, index=False)

    engine = NewsSearchEngine(path, query_preprocessor=simple_preprocessor)
    results = engine.search("%2026 #Kompas")

    assert [item["doc_id"] for item in results] == ["KMP001"]
    assert results[0]["score"] is None


def test_author_partial_match_is_case_insensitive(tmp_path):
    corpus = pd.DataFrame([
        {"doc_id": "KMP001", "title": "A", "media": "Kompas", "date": "2026-08-15", "author": "Sandy Firdaus", "text_final": "alpha beta"},
        {"doc_id": "ANT001", "title": "B", "media": "ANTARA", "date": "2026-08-16", "author": "Budi Santoso", "text_final": "beta gamma"},
    ])
    path = tmp_path / "processed.csv"
    corpus.to_csv(path, index=False)

    engine = NewsSearchEngine(path, query_preprocessor=simple_preprocessor)
    results = engine.search("@sAnDy")
    assert [item["doc_id"] for item in results] == ["KMP001"]

def test_title_query_requires_all_terms_in_the_same_title(tmp_path):
    corpus = pd.DataFrame([
        {
            "doc_id": "DOC001", "title": "Persija Raih Kemenangan",
            "media": "Kompas", "date": "2026-08-15", "author": "Author A",
            "text_final": "berita sepak bola",
        },
        {
            "doc_id": "DOC002", "title": "Persib Rekrut Pemain Baru",
            "media": "ANTARA", "date": "2026-08-16", "author": "Author B",
            "text_final": "berita sepak bola",
        },
        {
            "doc_id": "DOC003", "title": "Persija dan Persib Bertanding",
            "media": "Kompas", "date": "2026-08-17", "author": "Author C",
            "text_final": "berita sepak bola",
        },
    ])
    path = tmp_path / "processed.csv"
    corpus.to_csv(path, index=False)

    engine = NewsSearchEngine(path, query_preprocessor=simple_preprocessor)
    results = engine.search("Persija Persib")

    assert [item["doc_id"] for item in results] == ["DOC003"]


def test_content_query_requires_all_terms_in_the_same_article(tmp_path):
    corpus = pd.DataFrame([
        {
            "doc_id": "DOC001", "title": "Berita Sepak Bola A",
            "media": "Kompas", "date": "2026-08-15", "author": "Author A",
            "text_final": "persija menang pertandingan",
        },
        {
            "doc_id": "DOC002", "title": "Berita Sepak Bola B",
            "media": "ANTARA", "date": "2026-08-16", "author": "Author B",
            "text_final": "persib menang pertandingan",
        },
        {
            "doc_id": "DOC003", "title": "Berita Sepak Bola C",
            "media": "Kompas", "date": "2026-08-17", "author": "Author C",
            "text_final": "persija dan persib bertemu",
        },
    ])
    path = tmp_path / "processed.csv"
    corpus.to_csv(path, index=False)

    engine = NewsSearchEngine(path, query_preprocessor=simple_preprocessor)
    results = engine.search('"persija persib"')

    assert [item["doc_id"] for item in results] == ["DOC003"]