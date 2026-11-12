"""Artikel search engine menggunakan BM25 untuk projek Mata Kuliaah Temu Kembali.

Req file: Preprocessing/hasil_preprocessing_project.csv
Req columns: doc_id, title, media, date, author, text_final

Query syntax:
    default              Cari judul artikel (BM25 bag-of-words)
    "dengan kutip"       Cari isi artikel (BM25 bag-of-words, not exact phrase)
    @penulis             Filter berdasarkan nama penulis (case-insensitive, partial match)
    %YYYY                Filter berdasarkan tahun publikasi (4 digit, misal %2026)
    #media               Filter berdasarkan nama media (case-insensitive, partial match)

Contoh query:
    Persija Jakarta
    "transfer pemain"
    @"Sandy Firdaus" %2026 #Kompas
    Persija "transfer pemain" @Sandy %2026 #IDN
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = PROJECT_ROOT / "Preprocessing" / "hasil_preprocessing_project.csv"
DEFAULT_RAW = PROJECT_ROOT / "Corpus" / "Original" / "Corpus_Liga Indonesia.xlsx"
REQUIRED_COLUMNS = {"doc_id", "title", "media", "date", "author", "text_final"}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
HEX_LIKE = re.compile(r"(?=.*\d)[a-f0-9]{8,}")
NEGATION_WORDS = {"tidak", "bukan", "jangan", "tanpa", "belum"}
EXTRA_STOPWORDS = {
    # Berdasarkan daftar stopword pada preprocessing, ditambah beberapa kata yang umum di berita olahraga.
    "kompas", "com", "antara", "idn", "times",
    "senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu",
    "januari", "februari", "maret", "april", "mei", "juni", "juli",
    "agustus", "september", "oktober", "november", "desember",
}


@dataclass
class ParsedQuery:
    """Menyimpan bagian-bagian query setelah dipisahkan oleh parser. 
    Kata biasa masuk ke pencarian judul, 
    kata di dalam tanda petik masuk kepencarian isi artikel, 
    sedangkan simbol khusus menjadi filter metadata."""

    title_terms: list[str]
    content_terms: list[str]
    authors: list[str]
    years: list[str]
    media: list[str]

    @property
    def has_filters(self) -> bool:
        return bool(self.authors or self.years or self.media)

    @property
    def has_terms(self) -> bool:
        return bool(self.title_terms or self.content_terms)


class IndonesianQueryPreprocessor:
    """Memproses query dan judul agar sesuai dengan hasil preprocessing corpus.
    Isi artikel sudah melalui preprocessing di notebook preprocessing. Disini,
    preprocessing yang sama diterapkan pada query baru dari pengguna dan pada
    judul artikel yang masih berupa teks asli. Dengan begitu, istilah yang
    dibandingkan BM25 berada dalam bentuk yang konsisten."""

    def __init__(self) -> None:
        try:
            from Sastrawi.Stemmer.StemmerFactory import StemmerFactory
            from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory
        except ImportError as exc:
            raise RuntimeError(
                "PySastrawi belum terpasang. Jalankan: pip install -r SearchEngine/requirements.txt"
            ) from exc

        self.stemmer = StemmerFactory().create_stemmer()
        stopwords = set(StopWordRemoverFactory().get_stop_words())
        # Berdasarkan Notebook: kata negasi tidak dihapus.
        stopwords.difference_update(NEGATION_WORDS)
        stopwords.update(EXTRA_STOPWORDS)
        self.stopwords = stopwords
        self._stem_cache: dict[str, str] = {}

    def __call__(self, text: str) -> list[str]:
        tokens = TOKEN_PATTERN.findall(str(text).casefold())
        # Berdasarkan Filtering() di Notebook: buang nomor, token yang mirip heksadesimal panjang, dan stopword. Ini akan membuang
        # token yang hanya berupa angka, misal tahun, dan token yang mirip heksadesimal panjang, misal kode tim sepak bola
        # yang tidak relevan untuk pencarian. Stopword dihapus agar tidak memengaruhi skor BM25.
        tokens = [
            token for token in tokens
            if not token.isdigit() and not HEX_LIKE.fullmatch(token)
        ]
        tokens = [token for token in tokens if token not in self.stopwords]

        result: list[str] = []
        for token in tokens:
            if token not in self._stem_cache:
                self._stem_cache[token] = self.stemmer.stem(token)
            stemmed = self._stem_cache[token]
            if stemmed:
                result.append(stemmed)
        return result


def parse_query(query: str) -> ParsedQuery:
    """Memisahkan kata pencarian dan filter metadata dari query pengguna.
    
    Kata yang tidak ada tanda petik digunakan untuk mencari judul. Kata
    yang diantara tanda petik digunakan untuk mencari isi artikel. Simbol @, %,
    dan # masing-masing dibaca sebagai filter penulis, tahun terbit, dan media.
    
    Jika satu jenis filter ditulis lebih dari sekali, nilainya digabung dengan
    logika OR. Filter dari jenis yang berbeda harus sama-sama terpenuhi (AND)."""

    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query tidak boleh kosong.")
    if query.count('"') % 2:
        raise ValueError('Tanda petik tidak berpasangan. Contoh: "transfer pemain"')

    parsed = ParsedQuery([], [], [], [], [])
    # Tokenisasi query: setiap token bisa berupa operator metadata, kata di dalam tanda petik, atau kata biasa.
    tokens = re.findall(r'@"[^"]+"|@\S+|#"[^"]+"|#\S+|%\S+|"[^"]+"|\S+', query)

    for token in tokens:
        if token.startswith("@"):
            value = token[1:]
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            value = value.strip()
            if not value:
                raise ValueError("Operator @ harus diikuti nama penulis.")
            parsed.authors.append(value)
        elif token.startswith("#"):
            value = token[1:]
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            value = value.strip()
            if not value:
                raise ValueError("Operator # harus diikuti nama media.")
            parsed.media.append(value)
        elif token.startswith("%"):
            year = token[1:]
            if not re.fullmatch(r"\d{4}", year):
                raise ValueError(f"Format tahun tidak valid: {token}. Gunakan %YYYY, misalnya %2026.")
            parsed.years.append(year)
        elif token.startswith('"') and token.endswith('"'):
            value = token[1:-1].strip()
            if not value:
                raise ValueError('Pencarian isi artikel di antara tanda petik tidak boleh kosong.')
            parsed.content_terms.extend(value.split())
        else:
            parsed.title_terms.append(token)

    if not (parsed.has_terms or parsed.has_filters):
        raise ValueError("Query tidak memiliki kata kunci atau filter yang dapat diproses.")
    return parsed


def _normalize_metadata(value: object) -> str:
    """Menyeragamkan metadata agar pencarian buta pada huruf besar atau tanda baca."""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def _parse_date(value: object) -> pd.Timestamp:
    """Membaca tanggal dalam format umum maupun angka serial dari Excel."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return pd.NaT
    text = str(value).strip()
    if not text:
        return pd.NaT
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        # Excel's 1900 date system, using the conventional 1899-12-30 origin.
        try:
            return pd.to_datetime(float(text), unit="D", origin="1899-12-30", errors="coerce")
        except (ValueError, OverflowError):
            return pd.NaT
    return pd.to_datetime(text, errors="coerce")


class BM25Index:
    """Membuat indeks BM25 tanpa bergantung pada library pencarian tambahan.
    
    Indeks menyimpan frekuensi setiap istilah di masing-masing dokumen, panjang
    dokumen, rata-rata panjang dokumen, dan nilai IDF. Data tersebut dipakai
    untuk menghitung skor relevansi dokumen terhadap query.
    
    Perhitungan menggunakan varian IDF positif Robertson/Sparck Jones:
        IDF(t) = log(1 + (N - df(t) + 0.5) / (df(t) + 0.5))
    
    Skor BM25 mempertimbangkan frekuensi istilah dan panjang dokumen:
        BM25(t,d) = IDF(t) * [tf * (k1 + 1)] /
                        [tf + k1 * (1 - b + b * |d| / avgdl)]
    
    Parameter k1 mengatur pengaruh frekuensi istilah, sedangkan b mengatur
    seberapa besar panjang dokumen memengaruhi skor."""

    def __init__(self, documents: Iterable[Iterable[str]], k1: float = 1.5, b: float = 0.75):
        if k1 <= 0:
            raise ValueError("Parameter k1 harus lebih besar dari 0.")
        if not 0 <= b <= 1:
            raise ValueError("Parameter b harus berada pada rentang 0 sampai 1.")

        self.documents = [list(doc) for doc in documents]
        self.k1 = float(k1)
        self.b = float(b)
        self.doc_length = [len(doc) for doc in self.documents]
        self.doc_count = len(self.documents)
        self.avg_length = (
            sum(self.doc_length) / self.doc_count if self.doc_count else 0.0
        )
        self.term_frequencies = [Counter(doc) for doc in self.documents]

        doc_frequency: Counter[str] = Counter()
        for doc in self.documents:
            doc_frequency.update(set(doc))

        self.idf = {
            term: math.log(1.0 + (self.doc_count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in doc_frequency.items()
        }

    def get_scores(self, query_tokens: Iterable[str]) -> list[float]:
        query_terms = set(query_tokens)
        scores = [0.0] * self.doc_count
        if not query_terms or not self.doc_count:
            return scores

        avgdl = self.avg_length or 1.0
        for doc_index, term_frequency in enumerate(self.term_frequencies):
            doc_length = self.doc_length[doc_index]
            length_norm = self.k1 * (1.0 - self.b + self.b * doc_length / avgdl)
            score = 0.0
            for term in query_terms:
                tf = term_frequency.get(term, 0)
                if tf == 0:
                    continue
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + length_norm
                score += self.idf.get(term, 0.0) * numerator / denominator
            scores[doc_index] = score
        return scores


class NewsSearchEngine:
    """Mengelola pencarian berita menggunakan BM25 dan filter metadata.
    
    Saat dibuat, kelas ini membaca corpus hasil preprocessing, menyiapkan
    indeks BM25 terpisah untuk judul dan isi artikel, serta menyimpan metadata
    yang diperlukan untuk filter penulis, tahun terbit, dan media."""

    def __init__(
        self,
        corpus_path: str | Path = DEFAULT_CORPUS,
        *,
        k1: float = 1.5,
        b: float = 0.75,
        query_preprocessor: Optional[Callable[[str], list[str]]] = None,
        original_corpus_path: str | Path = DEFAULT_RAW,
    ) -> None:
        self.corpus_path = Path(corpus_path)
        if not self.corpus_path.exists():
            raise FileNotFoundError(
                f"File corpus tidak ditemukan: {self.corpus_path}\n"
                "Pastikan hasil preprocessing berada di Preprocessing/hasil_preprocessing_project.csv."
            )

        self.df = pd.read_csv(self.corpus_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        missing = REQUIRED_COLUMNS - set(self.df.columns)
        if missing:
            raise ValueError(
                "Kolom wajib tidak ditemukan pada CSV preprocessing: " + ", ".join(sorted(missing))
            )
        self.df = self.df.fillna("").reset_index(drop=True)

        # Preprocessing tidak ada kolom URL dan raw_text.
        # Diambil dari file Excel asli jika tersedia, untuk menampilkan cuplikan dan URL di hasil pencarian.
        self.df["url"] = self.df["url"] if "url" in self.df.columns else ""
        self.df["raw_text"] = self.df["raw_text"] if "raw_text" in self.df.columns else ""
        original_path = Path(original_corpus_path)
        if original_path.exists() and (self.df["url"].eq("").any() or self.df["raw_text"].eq("").any()):
            try:
                original = pd.read_excel(
                    original_path,
                    sheet_name="Corpus_Gabungan",
                    usecols=lambda column: column in {"doc_id", "url", "text"},
                    dtype=str,
                ).fillna("")
                original = original.rename(columns={"text": "raw_text"})
                original = original.drop_duplicates(subset=["doc_id"], keep="first")
                for field in ("url", "raw_text"):
                    if field in original.columns:
                        lookup = original.set_index("doc_id")[field]
                        missing_values = self.df[field].eq("")
                        self.df.loc[missing_values, field] = self.df.loc[missing_values, "doc_id"].map(lookup).fillna("")
            except (ValueError, KeyError, ImportError) as exc:
                print(f"Peringatan: metadata URL/teks asli tidak dapat dimuat: {exc}", file=sys.stderr)

        self._parsed_dates = [_parse_date(value) for value in self.df["date"]]
        self.query_preprocessor = query_preprocessor or IndonesianQueryPreprocessor()

        # Mengambil isi artikel yang sudah diproses di notebook preprocessing.
        content_documents = [
            [token for token in str(value).split() if token]
            for value in self.df["text_final"]
        ]
        # Judul artikel diproses dengan preprocessing yang sama seperti query pengguna, agar tokenisasi, filtering, dan stemming konsisten.
        # Ini memungkinkan pencarian BM25 pada judul artikel menggunakan token yang sama dengan query pengguna.
        title_documents = [
            self.query_preprocessor(title)
            for title in self.df["title"]
        ]

        self.title_index = BM25Index(title_documents, k1=k1, b=b)
        self.content_index = BM25Index(content_documents, k1=k1, b=b)

    def _filter_candidates(self, parsed: ParsedQuery) -> list[int]:
        candidates = list(range(len(self.df)))

        if parsed.authors:
            author_values = [_normalize_metadata(value) for value in parsed.authors]
            candidates = [
                i for i in candidates
                if any(value in _normalize_metadata(self.df.at[i, "author"]) for value in author_values)
                and bool(str(self.df.at[i, "author"]).strip())
            ]

        if parsed.years:
            years = set(parsed.years)
            candidates = [
                i for i in candidates
                if not pd.isna(self._parsed_dates[i])
                and str(self._parsed_dates[i].year) in years
            ]

        if parsed.media:
            media_values = [_normalize_metadata(value) for value in parsed.media]
            candidates = [
                i for i in candidates
                if any(
                    value in _normalize_metadata(self.df.at[i, "media"])
                    or _normalize_metadata(self.df.at[i, "media"]) in value
                    for value in media_values
                )
            ]

        return candidates

    @staticmethod
    def _normalize_candidate_scores(scores: list[float], candidates: list[int]) -> dict[int, float]:
        if not candidates:
            return {}
        maximum = max(scores[i] for i in candidates)
        if maximum <= 0:
            return {i: 0.0 for i in candidates}
        return {i: scores[i] / maximum for i in candidates}

    @staticmethod
    def _make_snippet(raw_text: object, query_terms: list[str], max_length: int = 240) -> str:
        """Mengambil cuplikan singkat dari artikel untuk ditampilkan di hasil pencarian.
        Jika memungkinkan, cuplikan dimulai di sekitar kata yang dicari agar
        pengguna lebih mudah melihat bagian artikel yang berkaitan."""

        text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
        if not text:
            return ""
        lower_text = text.casefold()
        start = -1
        for term in query_terms:
            candidate = lower_text.find(term.casefold())
            if candidate >= 0:
                start = candidate
                break
        if start < 0:
            start = 0
        start = max(0, start - 70)
        excerpt = text[start:start + max_length].strip()
        if start > 0:
            excerpt = "…" + excerpt
        if start + max_length < len(text):
            excerpt += "…"
        return excerpt

    def search(self, query: str, top_k: int = 10) -> list[dict[str, object]]:
        """Mencari artikel dan mengembalikan hasil yang sudah diurutkan.
        
        Filter dari kategori berbeda harus terpenuhi semuanya: penulis AND tahun
        AND media. Jika ada beberapa nilai pada kategori filter yang sama, cukup
        salah satunya yang cocok (OR).
        
        Jika query berisi kata untuk judul sekaligus isi artikel, dokumen harus
        memperoleh skor BM25 positif pada kedua kolom tersebut. Skor dari tiap
        kolom dinormalisasi terlebih dahulu, kemudian dirata-ratakan untuk
        menentukan urutan hasil.
        
        Jika query hanya berisi filter metadata tanpa kata kunci, hasil diurutkan
        berdasarkan tanggal terbit terbaru karena tidak ada skor BM25 yang dapat
        digunakan sebagai dasar pemeringkatan."""

        if top_k < 1:
            raise ValueError("top_k harus minimal 1.")

        parsed = parse_query(query)
        candidates = self._filter_candidates(parsed)
        if not candidates:
            return []

        field_scores: list[dict[int, float]] = []
        matched_fields: list[str] = []

        if parsed.title_terms:
            tokens = self.query_preprocessor(" ".join(parsed.title_terms))
            if not tokens:
                raise ValueError("Kata kunci judul tidak menghasilkan token setelah preprocessing.")
            raw_scores = self.title_index.get_scores(tokens)
            field_scores.append({i: raw_scores[i] for i in candidates})
            matched_fields.append("title")

        if parsed.content_terms:
            tokens = self.query_preprocessor(" ".join(parsed.content_terms))
            if not tokens:
                raise ValueError("Kata kunci isi artikel tidak menghasilkan token setelah preprocessing.")
            raw_scores = self.content_index.get_scores(tokens)
            field_scores.append({i: raw_scores[i] for i in candidates})
            matched_fields.append("content")

        ranked: list[tuple[int, Optional[float]]] = []
        if field_scores:
            # Jika query berisi kata kunci untuk judul dan/atau isi artikel, 
            # dokumen harus memiliki skor BM25 positif pada semua kolom yang dicari.
            matching_candidates = [
                i for i in candidates
                if all(scores.get(i, 0.0) > 0 for scores in field_scores)
            ]
            if not matching_candidates:
                return []

            normalized_fields = [
                self._normalize_candidate_scores(
                    [scores.get(i, 0.0) for i in range(len(self.df))],
                    matching_candidates,
                )
                for scores in field_scores
            ]
            for i in matching_candidates:
                combined_score = sum(field[i] for field in normalized_fields) / len(normalized_fields)
                ranked.append((i, combined_score))
            ranked.sort(
                key=lambda item: (
                    -(item[1] or 0.0),
                    -(self._parsed_dates[item[0]].timestamp() if not pd.isna(self._parsed_dates[item[0]]) else 0),
                    str(self.df.at[item[0], "doc_id"]),
                )
            )
        else:
            # Jika query hanya berisi filter metadata tanpa kata kunci, 
            # urutkan hasil berdasarkan tanggal terbit.
            ranked = [(i, None) for i in candidates]
            ranked.sort(
                key=lambda item: (
                    -(self._parsed_dates[item[0]].timestamp() if not pd.isna(self._parsed_dates[item[0]]) else 0),
                    str(self.df.at[item[0], "doc_id"]),
                )
            )

        results: list[dict[str, object]] = []
        for index, score in ranked[:top_k]:
            row = self.df.iloc[index]
            parsed_date = self._parsed_dates[index]
            results.append({
                "doc_id": row["doc_id"],
                "title": row["title"],
                "author": row["author"],
                "date": "" if pd.isna(parsed_date) else parsed_date.strftime("%Y-%m-%d"),
                "media": row["media"],
                "url": row.get("url", ""),
                "snippet": self._make_snippet(row.get("raw_text", ""), parsed.content_terms or parsed.title_terms),
                "score": None if score is None else round(float(score), 6),
                "matched_fields": matched_fields.copy(),
            })
        return results


def _print_results(results: list[dict[str, object]]) -> None:
    if not results:
        print("Tidak ada artikel yang cocok dengan query.")
        return
    print(f"\nDitemukan {len(results)} artikel:\n")
    for number, item in enumerate(results, start=1):
        score = "Filter-only" if item["score"] is None else f"Skor: {item['score']:.4f}"
        print(f"{number}. {item['title']}")
        print(f"   {score} | {item['media']} | {item['date']}")
        print(f"   Penulis: {item['author'] or 'Tidak tersedia'}")
        print(f"   ID: {item['doc_id']}")
        if item["snippet"]:
            print(f"   Cuplikan: {item['snippet']}")
        if item["url"]:
            print(f"   URL: {item['url']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="BM25 Search Engine - Berita Liga Indonesia")
    parser.add_argument(
        "--data", type=Path, default=DEFAULT_CORPUS,
        help=f"Path CSV preprocessing (default: {DEFAULT_CORPUS})",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Jumlah hasil yang ditampilkan")
    args = parser.parse_args()

    try:
        engine = NewsSearchEngine(args.data)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Gagal memuat search engine: {exc}", file=sys.stderr)
        return 1

    print("BM25 Search Engine - Liga Indonesia")
    print(f"Corpus: {args.data} ({len(engine.df)} dokumen)")
    print('Ketik query. Gunakan @author, %tahun, #media, dan "kata" untuk isi artikel.')
    print("Contoh: Persija \"transfer pemain\" @Sandy %2026 #Kompas")
    print("Ketik :q untuk keluar.\n")

    while True:
        try:
            query = input("Search> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKeluar.")
            break
        if query.casefold() in {":q", ":quit", "exit", "quit"}:
            print("Keluar.")
            break
        if not query:
            continue
        try:
            _print_results(engine.search(query, top_k=args.top_k))
        except ValueError as exc:
            print(f"Query tidak valid: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())