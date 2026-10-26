// app.js — hash router + pages for the Vocabulary Notebook UI.
//   #/            list (search, filter by part of speech, sort, edit, delete)
//   #/new         add a word
//   #/edit/{id}   edit a word
//   #/review      flashcard review, logs remembered / forgot
// Everything goes through the JSON API under /api (app/routes.py).
"use strict";

const view = document.getElementById("view");
const PAGE_SIZE = 30;
const POS_LABELS = {
  noun: "Danh từ", verb: "Động từ", adjective: "Tính từ", adverb: "Trạng từ",
  preposition: "Giới từ", conjunction: "Liên từ", pronoun: "Đại từ", phrase: "Cụm từ",
};

async function api(path, options = {}) {
  const res = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    // FastAPI sends {detail: "..."} or, for 422, {detail: [{msg: ...}]}.
    const detail = Array.isArray(body.detail)
      ? "Dữ liệu không hợp lệ: " + body.detail.map((d) => d.msg).join("; ")
      : body.detail || `Lỗi ${res.status}`;
    throw new Error(detail);
  }
  return body;
}

// Listeners added through `pageSignal` are removed when the next page mounts.
let pageAbort = new AbortController();
const pageSignal = () => pageAbort.signal;

function mount(templateId) {
  pageAbort.abort();
  pageAbort = new AbortController();
  view.replaceChildren(document.getElementById(templateId).content.cloneNode(true));
  return view;
}

const $ = (root, attr) => root.querySelector(`[${attr}]`);
const el = (tag, props = {}, ...children) => {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
};

let toastTimer;
function toast(message) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (box.hidden = true), 2500);
}

function showError(root, err) {
  root.replaceChildren(el("p", { className: "card empty", textContent: err.message }));
}

function speak(text) {
  if (!("speechSynthesis" in window)) return toast("Trình duyệt không hỗ trợ phát âm");
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-US";
  u.rate = 0.9;
  speechSynthesis.speak(u);
}

const ICONS = {
  speak: '<path d="M11 5 6 9H3v6h3l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
  trash: '<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/>',
};
function iconButton(icon, label, extraClass = "") {
  const tag = icon === "edit" ? "a" : "button";
  const btn = el(tag, { className: `icon-btn ${extraClass}`, title: label });
  btn.setAttribute("aria-label", label);
  btn.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[icon]}</svg>`;
  return btn;
}

function posBadge(pos) {
  return el("span", { className: `badge ${pos || ""}`, textContent: pos || "" });
}

// ---------- Danh sách ----------
async function listPage(query = "") {
  const root = mount("tpl-list");
  const form = $(root, "data-search");
  const list = $(root, "data-words");
  const count = $(root, "data-count");
  const more = $(root, "data-more");
  const sort = $(root, "data-sort");
  const chips = $(root, "data-chips");
  form.q.value = query;
  list.replaceChildren(...Array.from({ length: 6 }, () => el("li", { className: "card skeleton" })));

  let words;
  try {
    words = await api("/words");
  } catch (err) {
    return showError(list, err);
  }
  renderStats($(root, "data-stats"), words);

  const state = { q: query, pos: "", sort: "new", shown: PAGE_SIZE };

  // One chip per part of speech present in the notebook.
  const counts = {};
  for (const w of words) counts[w.part_of_speech || ""] = (counts[w.part_of_speech || ""] || 0) + 1;
  const chipDefs = [["", "Tất cả", words.length]].concat(
    Object.keys(POS_LABELS).filter((p) => counts[p]).map((p) => [p, POS_LABELS[p], counts[p]]),
  );
  for (const [pos, label, n] of chipDefs) {
    const chip = el("button", { className: "chip", type: "button", textContent: label },
      el("span", { className: "n", textContent: n }));
    chip.dataset.pos = pos;
    chip.addEventListener("click", () => { state.pos = pos; state.shown = PAGE_SIZE; render(); });
    chips.append(chip);
  }

  function filtered() {
    const q = state.q.toLowerCase();
    const out = words.filter((w) =>
      (!state.pos || w.part_of_speech === state.pos) &&
      (!q || w.word.toLowerCase().includes(q) || w.meaning_vi.toLowerCase().includes(q)));
    if (state.sort === "az") out.sort((a, b) => a.word.localeCompare(b.word));
    if (state.sort === "za") out.sort((a, b) => b.word.localeCompare(a.word));
    return out;
  }

  function render() {
    for (const c of chips.children) c.classList.toggle("active", c.dataset.pos === state.pos);
    const items = filtered();
    count.textContent = state.q || state.pos
      ? `${items.length} / ${words.length} từ phù hợp`
      : `${words.length} từ trong sổ`;
    if (items.length === 0) {
      list.replaceChildren(el("li", {
        className: "card empty",
        textContent: words.length ? "Không tìm thấy từ nào phù hợp." : "Chưa có từ nào. Hãy thêm từ đầu tiên!",
      }));
    } else {
      list.replaceChildren(...items.slice(0, state.shown).map((w) => wordItem(w, () => {
        words = words.filter((x) => x.id !== w.id);
        renderStats($(root, "data-stats"), words);
        render();
      })));
    }
    more.hidden = items.length <= state.shown;
    more.textContent = `Xem thêm (${items.length - state.shown})`;
  }

  // Live search; the query is kept in the URL without re-running the router.
  let typing;
  form.q.addEventListener("input", () => {
    clearTimeout(typing);
    typing = setTimeout(() => {
      state.q = form.q.value.trim();
      state.shown = PAGE_SIZE;
      history.replaceState(null, "", state.q ? "#/?q=" + encodeURIComponent(state.q) : "#/");
      render();
    }, 150);
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  sort.addEventListener("change", () => { state.sort = sort.value; render(); });
  more.addEventListener("click", () => { state.shown += PAGE_SIZE; render(); });
  render();
}

function renderStats(box, words) {
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const stats = [
    ["Tổng số từ", words.length],
    ["Thêm trong 7 ngày", words.filter((w) => new Date(w.created_at) > weekAgo).length],
    ["Có câu ví dụ", words.filter((w) => w.example).length],
    ["Cụm từ & thành ngữ", words.filter((w) => w.part_of_speech === "phrase").length],
  ];
  box.replaceChildren(...stats.map(([label, value]) => el("div", { className: "card stat" },
    el("div", { className: "label", textContent: label }),
    el("div", { className: "value", textContent: value.toLocaleString("vi-VN") }))));
}

function wordItem(w, onDeleted) {
  const li = el("li", { className: "card word-item" });

  const sound = iconButton("speak", "Nghe phát âm");
  sound.addEventListener("click", () => speak(w.word));
  const edit = iconButton("edit", "Sửa");
  edit.href = `#/edit/${w.id}`;
  const del = iconButton("trash", "Xoá", "danger");
  del.addEventListener("click", async () => {
    if (!confirm(`Xoá từ "${w.word}"? Lịch sử ôn tập của từ này cũng bị xoá.`)) return;
    try {
      await api(`/words/${w.id}`, { method: "DELETE" });
      toast(`Đã xoá "${w.word}"`);
      onDeleted();
    } catch (err) {
      toast(err.message);
    }
  });

  li.append(
    el("div", { className: "word-head" },
      el("span", { className: "w", textContent: w.word }),
      posBadge(w.part_of_speech),
      el("div", { className: "actions" }, sound, edit, del)),
    el("div", { className: "meaning", textContent: w.meaning_vi }),
  );
  if (w.example) li.append(el("p", { className: "ex", textContent: w.example }));
  if (w.usage_note) li.append(el("p", { className: "note", textContent: w.usage_note }));
  return li;
}

// ---------- Thêm / Sửa ----------
async function formPage(id) {
  const root = mount("tpl-form");
  const form = $(root, "data-form");
  const error = $(root, "data-error");
  $(root, "data-title").textContent = id ? "Sửa từ" : "Thêm từ mới";

  if (id) {
    try {
      const w = await api(`/words/${id}`);
      for (const k of ["word", "meaning_vi", "part_of_speech", "example", "usage_note"]) {
        form[k].value = w[k] ?? "";
      }
    } catch (err) {
      return showError(view, err);
    }
  }
  form.word.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    error.hidden = true;
    const data = Object.fromEntries(new FormData(form));
    for (const k of Object.keys(data)) {
      data[k] = data[k].trim();
      if (data[k] === "") data[k] = null; // optional fields are stored as NULL
    }
    const submit = $(root, "data-submit");
    submit.disabled = true;
    try {
      await api(id ? `/words/${id}` : "/words", {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(data),
      });
      toast(id ? "Đã lưu thay đổi" : `Đã thêm "${data.word}"`);
      location.hash = "#/";
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
}

// ---------- Ôn tập ----------
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

let deckSize = "20"; // remembered between review rounds

async function reviewPage() {
  const root = mount("tpl-review");
  const card = $(root, "data-card");
  const size = $(root, "data-size");
  size.value = deckSize;
  size.addEventListener("change", () => { deckSize = size.value; reviewPage(); });

  let words;
  try {
    words = shuffle(await api("/words"));
  } catch (err) {
    return showError(card, err);
  }
  if (words.length === 0) {
    card.innerHTML = '<p class="empty">Chưa có từ nào để ôn. <a href="#/new">Thêm từ</a></p>';
    return;
  }
  if (Number(deckSize) > 0) words = words.slice(0, Number(deckSize));

  let i = 0;
  let busy = false;
  const score = { remembered: 0, forgot: 0 };
  const answer = $(root, "data-answer");
  const showBox = $(root, "data-actions-show");
  const gradeBox = $(root, "data-actions-grade");
  const bar = $(root, "data-bar");

  function render() {
    const w = words[i];
    bar.style.width = `${(i / words.length) * 100}%`;
    $(root, "data-progress").textContent =
      `Thẻ ${i + 1} / ${words.length} · Nhớ ${score.remembered} · Quên ${score.forgot}`;
    const pos = $(root, "data-pos");
    pos.className = `badge ${w.part_of_speech || ""}`;
    pos.textContent = w.part_of_speech || "";
    $(root, "data-word").textContent = w.word;
    $(root, "data-meaning").textContent = w.meaning_vi;
    $(root, "data-example").textContent = w.example || "";
    $(root, "data-note").textContent = w.usage_note || "";
    answer.hidden = true;
    showBox.hidden = false;
    gradeBox.hidden = true;
  }

  function reveal() {
    answer.hidden = false;
    showBox.hidden = true;
    gradeBox.hidden = false;
  }

  async function grade(result) {
    if (busy || gradeBox.hidden) return;
    busy = true;
    try {
      await api(`/words/${words[i].id}/reviews`, {
        method: "POST",
        body: JSON.stringify({ result }),
      });
    } catch (err) {
      toast(err.message);
      return;
    } finally {
      busy = false;
    }
    score[result]++;
    i++;
    if (i < words.length) return render();
    finish();
  }

  function finish() {
    bar.style.width = "100%";
    card.hidden = true;
    $(root, "data-progress").textContent = "";
    const percent = Math.round((score.remembered / words.length) * 100);
    $(root, "data-ring").style.setProperty("--p", percent);
    $(root, "data-percent").textContent = `${percent}%`;
    $(root, "data-done").hidden = false;
    $(root, "data-summary").textContent =
      `Nhớ ${score.remembered} · Quên ${score.forgot} trên tổng ${words.length} thẻ`;
  }

  $(root, "data-show").addEventListener("click", reveal);
  $(root, "data-speak").addEventListener("click", () => speak(words[i].word));
  for (const btn of root.querySelectorAll("[data-grade]")) {
    btn.addEventListener("click", () => grade(btn.dataset.grade));
  }
  $(root, "data-again").addEventListener("click", () => reviewPage());

  // Keyboard: Space / Enter shows the meaning, 1 = forgot, 2 = remembered.
  document.addEventListener("keydown", (e) => {
    if (card.hidden || e.target.matches("input, select, textarea")) return;
    if ((e.key === " " || e.key === "Enter") && !showBox.hidden) { e.preventDefault(); reveal(); }
    else if (e.key === "1") grade("forgot");
    else if (e.key === "2") grade("remembered");
  }, { signal: pageSignal() });

  render();
}

// ---------- Router ----------
function route() {
  const [path, qs] = location.hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(qs);
  let page = "list";
  const edit = path.match(/^\/edit\/(\d+)$/);
  if (path === "/new") { page = "new"; formPage(null); }
  else if (edit) { page = "edit"; formPage(Number(edit[1])); }
  else if (path === "/review") { page = "review"; reviewPage(); }
  else listPage(params.get("q") || "");
  for (const a of document.querySelectorAll("[data-nav]")) {
    a.classList.toggle("active", a.dataset.nav === page);
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
