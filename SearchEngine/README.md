# BM25 Search Engine — Liga Indonesia

Modul ini menggunakan **hasil preprocessing yang sudah ada** dan tidak menjalankan ulang pipeline preprocessing pada isi artikel.

## Struktur di repository

```text
Search-Engine-TemuKem-UAS/
├── Corpus/
│   └── Original/
├── Preprocessing/
│   └── hasil_preprocessing_project.csv
└── SearchEngine/
    ├── __init__.py
    ├── search_engine.py
    ├── requirements.txt
    └── tests/
        └── test_search_engine.py
```

## Persiapan

Jalankan dari folder utama repository:

```bash
pip install -r SearchEngine/requirements.txt
```

Pastikan file berikut tersedia:

```text
Preprocessing/hasil_preprocessing_project.csv
```

Kolom yang dibutuhkan: `doc_id`, `title`, `media`, `date`, `author`, dan `text_final`. Kolom `text_final` sudah berupa token yang telah melalui preprocessing dan stemming, sehingga tidak boleh diproses ulang.

## Menjalankan search engine

Dari folder utama repository:

```bash
python SearchEngine/search_engine.py
```

Atau tentukan lokasi CSV secara manual:

```bash
python SearchEngine/search_engine.py --data Preprocessing/hasil_preprocessing_project.csv --top-k 10
```

## Sintaks

| Sintaks | Kegunaan | Contoh |
|---|---|---|
| `kata` | Mencari pada judul artikel | `Persija Jakarta` |
| `"kata"` | Mencari pada isi artikel | `"transfer pemain"` |
| `@penulis` | Filter penulis | `@Sandy` |
| `@"Nama Lengkap"` | Filter nama penulis yang memiliki spasi | `@"Sandy Firdaus"` |
| `%YYYY` | Filter tahun publikasi | `%2026` |
| `#media` | Filter media | `#Kompas` |
| `#"Nama Media"` | Filter media yang memiliki spasi | `#"IDN Times"` |

Contoh kombinasi:

```text
Persija "transfer pemain" @"Sandy Firdaus" %2026 #Kompas
```

Kata tanpa tanda petik mencari hasil `title`, sedangkan kata/frasa dalam tanda petik mencari hasil `text_final`. Tanda petik menentukan field pencarian, bukan exact phrase matching: kata-kata di dalam tanda petik tetap diberi skor BM25 sebagai kumpulan term.

Filter dari kategori berbeda digabung dengan logika AND (author AND year AND media). Beberapa nilai dalam kategori filter yang sama digabung dengan OR. Jika query berisi kata judul sekaligus kata isi artikel, dokumen harus mendapatkan skor positif pada kedua field. Jika query hanya berisi filter metadata, hasil diurutkan berdasarkan tanggal terbaru karena tidak ada skor relevansi kata kunci.

Jika dua field pencarian digunakan sekaligus, skor BM25 masing-masing field dinormalisasi terhadap skor tertinggi pada kandidat yang lolos filter, lalu dirata-ratakan. Ini menghindari perbandingan langsung antara skor judul dan isi artikel yang skala nilainya dapat berbeda.

## Pengujian

Dari folder utama repository:

```bash
pip install pytest
python -m pytest SearchEngine/tests -v
```

## Parameter BM25

Implementasi menggunakan Okapi BM25 dengan parameter awal `k1=1.5` dan `b=0.75`. Parameter dapat diubah melalui konstruktor `NewsSearchEngine` jika kelompok ingin melakukan eksperimen.