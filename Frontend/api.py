"""API tipis untuk frontend. Membungkus NewsSearchEngine tanpa mengubah kode backend.

Jalankan dari folder utama repository:
    python Frontend/api.py
lalu buka http://127.0.0.1:8000
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from SearchEngine.search_engine import NewsSearchEngine

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Liga Indonesia Search")

# Indeks dibuat sekali saat server menyala (stemming judul butuh beberapa detik).
engine = NewsSearchEngine()


def _build_meta() -> dict:
    df = engine.df
    years = sorted({str(d.year) for d in engine._parsed_dates if d == d}, reverse=True)
    return {
        "doc_count": int(len(df)),
        "media": sorted({m.strip() for m in df["media"] if m.strip()}),
        # strip(): beberapa nama penulis di CSV berakhiran "\r\n"
        "authors": sorted({a.strip() for a in df["author"] if a.strip()}),
        "years": years,
    }


META = _build_meta()


@app.get("/api/meta")
def meta() -> dict:
    return META


@app.get("/api/search")
def search(q: str = Query(..., description="Query dengan sintaks backend"), top_k: int = Query(10, ge=1, le=100)) -> dict:
    started = time.perf_counter()
    try:
        results = engine.search(q, top_k=top_k)
    except ValueError as exc:  # query tidak valid -> pesan dari backend dikirim apa adanya
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "query": q,
        "count": len(results),
        "took_ms": round((time.perf_counter() - started) * 1000, 1),
        "results": results,
    }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
