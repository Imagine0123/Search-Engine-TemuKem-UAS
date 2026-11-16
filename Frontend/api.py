"""API tipis untuk frontend. Membungkus NewsSearchEngine tanpa mengubah kode backend.

Jalankan dari folder utama repository:
    python Frontend/api.py
lalu buka http://127.0.0.1:8000
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
for path in (REPO_ROOT, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from SearchEngine.search_engine import NewsSearchEngine
from theme import classify

STATIC_DIR = HERE / "static"

app = FastAPI(title="Liga Indonesia Search")

# Indeks dibuat sekali saat server menyala (stemming judul butuh beberapa detik).
engine = NewsSearchEngine()

# Tema background kartu per dokumen, dihitung sekali dari judul dan isi artikel.
THEMES = {
    row.doc_id: classify(row.title, row.raw_text)
    for row in engine.df.itertuples()
}


@app.get("/api/meta")
def meta() -> dict:
    return {
        "doc_count": int(len(engine.df)),
        "media": sorted({m.strip() for m in engine.df["media"] if m.strip()}),
    }


@app.get("/api/search")
def search(q: str = Query(..., description="Query dengan sintaks backend"), top_k: int = Query(100, ge=1, le=100)) -> dict:
    started = time.perf_counter()
    try:
        results = engine.search(q, top_k=top_k)
    except ValueError as exc:  # query tidak valid -> pesan dari backend dikirim apa adanya
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    for item in results:
        item["theme"] = THEMES.get(item["doc_id"], {"club": None, "cat": "umum"})
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
