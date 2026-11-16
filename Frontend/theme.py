"""Menentukan tema background kartu hasil dari isi berita.

Setiap artikel diberi dua label sederhana berdasarkan kata kunci di judul dan isi:
  - club: klub yang paling banyak dibahas (menentukan warna kartu), atau None
  - cat : jenis berita (menentukan ikon dan warna kalau tidak ada klub)

Sengaja berbasis aturan kata kunci, bukan model, supaya mudah dijelaskan dan diubah.
Hanya klub yang warnanya sudah pasti yang dipetakan ke warna khusus.
"""
from __future__ import annotations

import re

# kata kunci klub -> nama kelas CSS (lihat style.css)
CLUBS: dict[str, list[str]] = {
    "persija": ["persija"],
    "persib": ["persib"],
    "persebaya": ["persebaya"],
    "arema": ["arema"],
    "persik": ["persik kediri", "persik"],
    "persipura": ["persipura"],
    "madura": ["madura united"],
    "semen-padang": ["semen padang"],
    # Klub di bawah ini ikut dideteksi supaya berita klub lain tidak salah diberi warna klub di atas,
    # tapi belum punya warna khusus: kartunya memakai warna jenis berita.
    "bali-united": ["bali united"],
    "borneo": ["borneo"],
    "dewa-united": ["dewa united"],
    "bhayangkara": ["bhayangkara"],
    "persijap": ["persijap"],
    "persiba": ["persiba"],
    "psis": ["psis"],
    "psm": ["psm"],
    "psim": ["psim"],
    "psms": ["psms"],
    "deltras": ["deltras"],
    "malut-united": ["malut united", "java united"],
    "kalteng": ["adhyaksa", "isenmulang", "kalteng"],
}

# jenis berita; urutan = prioritas kalau skor sama
CATEGORIES: dict[str, list[str]] = {
    "bisnis": ["sponsor", "adidas", "apparel", "aparel", "jersey", "berganti nama", "ganti nama",
               "kerja sama", "merchandise", "logo", "nama baru"],
    "transfer": ["datangkan", "mendatangkan", "daratkan", "perkenalkan", "rekrut", "direkrut", "gabung", "kontrak",
                 "perpanjang", "pemain baru", "dipinjamkan", "pinjaman", "bomber", "transfer"],
    "pelatih": ["pelatih", "shin tae", "latihan", "asisten", "coach"],
    "jadwal": ["jadwal", "bergulir", "kompetisi", "format", "championship", "semifinal",
               "piala presiden", "league cup", "regulasi"],
    "laga": ["gol", "menang", "kalah", "imbang", "skor", "penalti", "derby", "laga", "pertandingan"],
    "stadion": ["stadion", "suporter", "bobotoh", "jakmania", "aremania", "kandang"],
}
DEFAULT_CATEGORY = "umum"


def _count(text: str, keywords: list[str], whole_word: bool = False) -> int:
    """Hitung kemunculan kata kunci. whole_word=True mencegah 'persib' cocok dengan 'persiba'."""
    end = r"\b" if whole_word else ""
    return sum(len(re.findall(r"\b" + re.escape(k) + end, text)) for k in keywords)


def classify(title: str, body: str) -> dict[str, str | None]:
    t, b = str(title).casefold(), str(body).casefold()

    # Klub: dipilih kalau disebut di judul. Kalau tidak ada di judul, harus disebut
    # >= 5 kali di isi dan minimal 2x lebih sering dari klub lain (artinya memang fokus berita).
    title_hits = {n: _count(t, w, True) for n, w in CLUBS.items()}
    body_hits = {n: _count(b, w, True) for n, w in CLUBS.items()}
    club = None
    if any(title_hits.values()):
        club = max(CLUBS, key=lambda n: (title_hits[n], body_hits[n]))
    else:
        ranked = sorted(CLUBS, key=lambda n: -body_hits[n])
        top, second = ranked[0], ranked[1]
        if body_hits[top] >= 5 and body_hits[top] >= 2 * body_hits[second]:
            club = top

    # Jenis berita: judul bernilai 4x; kemunculan di isi dihitung maksimal 3 supaya
    # judul tetap menentukan. Minimal skor 4, kalau tidak -> "umum".
    cat, cat_score = DEFAULT_CATEGORY, 0
    for name, words in CATEGORIES.items():
        score = 4 * _count(t, words) + min(_count(b[:1500], words), 3)
        if score > cat_score:
            cat, cat_score = name, score
    if cat_score < 4:
        cat = DEFAULT_CATEGORY

    return {"club": club, "cat": cat}
