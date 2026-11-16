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

## Pencarian
Satu kotak pencarian, semua fitur lewat sintaks query backend:
`Persija` (judul), `"transfer pemain"` (isi), `@"Nama Penulis"`, `%2026`, `#Kompas`.
Teks di kotak dikirim apa adanya ke `NewsSearchEngine.search()`.

## Struktur
```
Frontend/
├── api.py            # FastAPI: /api/meta, /api/search, dan melayani halaman
├── theme.py          # aturan kata kunci: klub + jenis berita -> tema kartu
├── requirements.txt
└── static/
    ├── index.html
    ├── style.css     # warna klub (.club-*) dan jenis berita (.cat-*)
    └── app.js
```

## Endpoint
| Method | Path | Keterangan |
|---|---|---|
| GET | `/api/meta` | Jumlah dokumen dan daftar media |
| GET | `/api/search?q=...` | Hasil pencarian (maks. 100). Query tidak valid -> 400 + pesan dari backend. Tiap hasil punya tambahan `theme: {club, cat}` |

## Warna kartu
`theme.py` membaca judul + isi artikel dan memberi label `theme: {club, cat}` ke tiap hasil:
- **club**: klub yang disebut di judul (atau dominan di isi) menentukan warna kartu.
  Warna khusus baru ada untuk Persija, Persib, Persebaya, Arema, Persik, Persipura, Madura United, Semen Padang;
  klub lain terdeteksi tapi memakai warna jenis berita.
- **cat**: jenis berita (transfer, pelatih, jadwal, laga, bisnis, stadion, umum) menentukan ikon dan warna cadangan.

Mau tambah klub: tambah kata kunci di `CLUBS` (theme.py) dan satu baris `.club-nama` di `static/style.css`.
