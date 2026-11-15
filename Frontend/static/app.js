"use strict";

const $ = (id) => document.getElementById(id);
const el = {
  form: $("form"), q: $("q"), scope: $("scope"), hint: $("hint"),
  media: $("media"), author: $("author"), year: $("year"), topk: $("topk"),
  reset: $("reset"), status: $("status"), qout: $("qout"),
  results: $("results"), empty: $("empty"), error: $("error"), sub: $("sub"),
  examples: $("examples"),
};

const HINTS = {
  title: "Mencari kata di judul artikel.",
  content: "Mencari kata di isi artikel.",
  both: "Artikel harus cocok di judul dan di isi.",
};

/* Menyusun string query sesuai sintaks backend:
   kata biasa -> judul, "kata" -> isi, @penulis, #media, %tahun */
function buildQuery() {
  const text = el.q.value.trim();
  const parts = [];
  if (text) {
    if (/["@#%]/.test(text)) {
      parts.push(text); // sintaks diketik langsung
    } else if (el.scope.value === "title") {
      parts.push(text);
    } else if (el.scope.value === "content") {
      parts.push(`"${text}"`);
    } else {
      parts.push(text, `"${text}"`);
    }
  }
  if (el.author.value) parts.push(`@"${el.author.value}"`);
  if (el.media.value) parts.push(`#"${el.media.value}"`);
  if (el.year.value) parts.push(`%${el.year.value}`);
  return parts.join(" ");
}

function highlightTerms() {
  const raw = el.q.value.replace(/@"[^"]*"|@\S+|#"[^"]*"|#\S+|%\S+/g, " ").replace(/"/g, " ");
  return [...new Set(raw.split(/\s+/).filter((w) => w.length >= 3))];
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* Escape per potongan supaya "amp" tidak merusak entitas HTML */
function highlight(text, terms) {
  if (!terms.length) return escapeHtml(text);
  const pattern = new RegExp(terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|"), "gi");
  let out = "", last = 0, m;
  while ((m = pattern.exec(text)) !== null) {
    out += escapeHtml(text.slice(last, m.index)) + "<mark>" + escapeHtml(m[0]) + "</mark>";
    last = m.index + m[0].length;
    if (m[0].length === 0) pattern.lastIndex++;
  }
  return out + escapeHtml(text.slice(last));
}

const dateFmt = new Intl.DateTimeFormat("id-ID", { day: "numeric", month: "long", year: "numeric" });
function formatDate(iso) {
  const d = new Date(iso + "T00:00:00");
  return isNaN(d) ? iso : dateFmt.format(d);
}

const FIELD_LABEL = { title: "cocok di judul", content: "cocok di isi" };

function renderResults(data, terms) {
  el.results.innerHTML = data.results.map((r, i) => {
    const filterOnly = r.score === null;
    const gauge = filterOnly
      ? `<span class="latest">Urut terbaru</span>`
      : `<span class="gauge" title="Skor BM25 ternormalisasi"><i><b style="width:${Math.round(r.score * 100)}%"></b></i>Skor ${r.score.toFixed(3)}</span>`;
    const fields = (r.matched_fields || []).map((f) => `<span class="chip">${FIELD_LABEL[f] || f}</span>`).join("");
    const title = highlight(r.title, terms);
    const link = r.url
      ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener noreferrer">${title}</a>`
      : title;
    return `
      <li class="card">
        <div class="rank" aria-hidden="true">${i + 1}</div>
        <div>
          <div class="byline">
            <span class="media-tag">${escapeHtml(r.media)}</span>
            <span>${escapeHtml(formatDate(r.date))}</span>
            <span>${r.author ? escapeHtml(r.author) : "Penulis tidak tersedia"}</span>
          </div>
          <h2>${link}</h2>
          ${r.snippet ? `<p class="snippet">${highlight(r.snippet, terms)}</p>` : ""}
          <div class="foot-row">${gauge}${fields}<span>${escapeHtml(r.doc_id)}</span></div>
        </div>
      </li>`;
  }).join("");
}

function setError(msg) {
  el.error.hidden = !msg;
  el.error.textContent = msg || "";
}

let controller = null;
async function runSearch({ latest = false } = {}) {
  const query = buildQuery();
  el.qout.textContent = query || "–";
  [el.media, el.author, el.year].forEach((s) => s.classList.toggle("active", !!s.value));
  setError("");
  if (!query) {
    el.results.innerHTML = "";
    el.empty.hidden = true;
    el.status.textContent = "Ketik kata kunci atau pilih filter untuk mulai.";
    return;
  }

  if (controller) controller.abort();
  controller = new AbortController();
  el.status.textContent = "Mencari…";
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}&top_k=${el.topk.value}`, { signal: controller.signal });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Terjadi kesalahan di server.");
    el.empty.hidden = data.count > 0;
    renderResults(data, highlightTerms());
    const ms = data.took_ms.toLocaleString("id-ID");
    el.status.textContent = data.count
      ? `${latest ? "Artikel terbaru: " : "Ditemukan "}${data.count} artikel dalam ${ms} ms`
      : "";
  } catch (err) {
    if (err.name === "AbortError") return;
    el.results.innerHTML = "";
    el.empty.hidden = true;
    el.status.textContent = "";
    setError(err instanceof TypeError
      ? "Server tidak bisa dihubungi. Pastikan api.py masih berjalan."
      : err.message);
  }
}

function fillSelect(select, values) {
  values.forEach((v) => select.append(new Option(v, v)));
}

function updateHint() { el.hint.textContent = HINTS[el.scope.value]; }

function resetFilters() {
  [el.media, el.author, el.year].forEach((s) => (s.value = ""));
}

async function init() {
  updateHint();
  try {
    const meta = await (await fetch("/api/meta")).json();
    fillSelect(el.media, meta.media);
    fillSelect(el.author, meta.authors);
    fillSelect(el.year, meta.years);
    el.sub.textContent = `${meta.doc_count} artikel dari ${meta.media.join(", ")}.`;
    // Tampilan awal: artikel terbaru di tahun terbaru
    if (meta.years.length) {
      el.year.value = meta.years[0];
      await runSearch({ latest: true });
      el.year.value = "";
      [el.media, el.author, el.year].forEach((s) => s.classList.remove("active"));
    }
  } catch {
    setError("Server tidak bisa dihubungi. Jalankan python Frontend/api.py lalu muat ulang halaman ini.");
    el.sub.textContent = "";
  }
}

el.form.addEventListener("submit", (e) => { e.preventDefault(); runSearch(); });
[el.media, el.author, el.year, el.topk, el.scope].forEach((s) =>
  s.addEventListener("change", () => { updateHint(); runSearch(); }));
el.reset.addEventListener("click", () => { resetFilters(); runSearch(); });
el.examples.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-q]");
  if (!b) return;
  el.q.value = b.dataset.q;
  el.scope.value = b.dataset.scope || "title";
  resetFilters();
  if (b.dataset.media) el.media.value = b.dataset.media;
  updateHint();
  runSearch();
});

init();
