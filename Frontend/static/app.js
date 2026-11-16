"use strict";

const $ = (id) => document.getElementById(id);
const el = {
  form: $("form"), q: $("q"), sub: $("sub"), status: $("status"),
  results: $("results"), intro: $("intro"), empty: $("empty"), error: $("error"),
};

/* Ikon garis per jenis berita, di pojok kanan atas kartu */
const BALL = '<circle cx="12" cy="12" r="9"/><polygon points="12,8 15.6,10.6 14.2,14.8 9.8,14.8 8.4,10.6"/><path d="M12 8V3M15.6 10.6l5-1.6M14.2 14.8l3 4M9.8 14.8l-3 4M8.4 10.6l-5-1.6"/>';
const ICONS = {
  transfer: '<path d="M4 8h14l-3.5-3.5M20 16H6l3.5 3.5"/>',
  pelatih: '<rect x="6" y="4" width="12" height="17" rx="1"/><path d="M9.5 2.5h5v3h-5zM9 11h6M9 15h6"/>',
  jadwal: '<rect x="3.5" y="5" width="17" height="15" rx="1"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  laga: BALL,
  bisnis: '<path d="M8.5 3L3 6l2 4 3-1v12h8V9l3 1 2-4-5.5-3c-.7 1.6-2 2.2-3.5 2.2S9.2 4.6 8.5 3z"/>',
  stadion: '<ellipse cx="12" cy="12" rx="9.5" ry="6.5"/><ellipse cx="12" cy="12" rx="5" ry="3"/>',
  umum: BALL,
};

function buildQuery() { return el.q.value.trim(); }

/* Kata yang disorot = kata biasa & isi tanda petik di query (tanpa @ # %) */
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
    const theme = r.theme || { club: null, cat: "umum" };
    const classes = ["card", `cat-${theme.cat}`, theme.club ? `club-${theme.club}` : ""].join(" ");
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
      <li class="${classes}">
        <svg class="mark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[theme.cat] || ICONS.umum}</svg>
        <div class="rank" aria-hidden="true">${i + 1}</div>
        <div class="body">
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
async function runSearch() {
  const query = buildQuery();
  setError("");
  if (!query) {
    el.results.innerHTML = "";
    el.empty.hidden = true;
    el.intro.hidden = false;
    el.status.textContent = "";
    return;
  }
  el.intro.hidden = true;

  if (controller) controller.abort();
  controller = new AbortController();
  el.status.textContent = "Mencari…";
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`, { signal: controller.signal });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Terjadi kesalahan di server.");
    el.empty.hidden = data.count > 0;
    renderResults(data, highlightTerms());
    el.status.textContent = data.count
      ? `Ditemukan ${data.count} artikel dalam ${data.took_ms.toLocaleString("id-ID")} ms`
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

async function init() {
  try {
    const meta = await (await fetch("/api/meta")).json();
    el.sub.textContent = `${meta.doc_count} artikel dari ${meta.media.join(", ")}.`;
  } catch {
    setError("Server tidak bisa dihubungi. Jalankan python Frontend/api.py lalu muat ulang halaman ini.");
    el.sub.textContent = "";
  }
}

el.form.addEventListener("submit", (e) => { e.preventDefault(); runSearch(); });
init();
