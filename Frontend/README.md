# Frontend — Liga Indonesia Search

Halaman web untuk `SearchEngine/search_engine.py` (BM25). Kode backend tidak diubah;
`api.py` hanya membungkusnya jadi endpoint HTTP.

## Menjalankan
Dari folder utama repository (bukan dari dalam `Frontend/`):

```bash
pip install -r Frontend/requirements.txt
python Frontend/api.py
```

Buka http://127.0.0.1:8000 (server butuh beberapa detik untuk membuat indeks saat pertama menyala).

## Struktur
```
Frontend/
├── api.py            # FastAPI: /api/meta, /api/search, dan melayani halaman
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```

## Endpoint
| Method | Path | Keterangan |
|---|---|---|
| GET | `/api/meta` | Daftar media, penulis, tahun, dan jumlah dokumen (untuk dropdown) |
| GET | `/api/search?q=...&top_k=10` | Hasil pencarian. `q` memakai sintaks backend; query tidak valid -> 400 + pesan |

Form di halaman menyusun `q` otomatis: kata biasa -> judul, `"kata"` -> isi, `@"penulis"`, `#"media"`, `%tahun`.
