// app.js — hash router + pages for the Vocabulary Notebook UI.
//   #/login       log in            #/register    create an account
//   #/            list (topics, search, filter by part of speech, sort, edit, delete)
//   #/new         add a word
//   #/edit/{id}   edit a word
//   #/review      typed review by topic or random, English <-> Vietnamese; logs results
// Everything goes through the JSON API under /api (app/auth.py, app/routes.py).
// The session is an HttpOnly cookie the browser sends by itself; this file never sees it.
"use strict";

const view = document.getElementById("view");
let me = undefined; // undefined = not checked yet, null = logged out
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
  if (res.status === 401 && !path.startsWith("/auth/")) {
    // Session expired or logged out in another tab: back to the login page.
    setUser(null);
    location.hash = "#/login";
  }
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

// ---------- Tài khoản ----------
function setUser(user) {
  me = user;
  document.querySelector("[data-nav-links]").hidden = !user;
  document.querySelector("[data-user]").hidden = !user;
  if (user) {
    document.querySelector("[data-user-name]").textContent = user.display_name;
    document.querySelector("[data-avatar]").textContent = user.display_name.trim()[0].toUpperCase();
  }
}

document.querySelector("[data-logout]").addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {
    // Already logged out on the server: nothing else to do.
  }
  setUser(null);
  toast("Đã đăng xuất");
  location.hash = "#/login";
});

const AUTH_TEXT = {
  login: {
    title: "Chào mừng trở lại",
    subtitle: "Đăng nhập để tiếp tục ôn từ vựng.",
    submit: "Đăng nhập",
    switch: ['Chưa có tài khoản? ', "#/register", "Đăng ký ngay"],
  },
  register: {
    title: "Tạo tài khoản",
    subtitle: "Sổ của bạn có sẵn hơn 200 từ thông dụng để bắt đầu.",
    submit: "Tạo tài khoản",
    switch: ["Đã có tài khoản? ", "#/login", "Đăng nhập"],
  },
};

function authPage(mode) {
  const root = mount("tpl-auth");
  const text = AUTH_TEXT[mode];
  const form = $(root, "data-auth-form");
  const error = $(root, "data-error");
  const submit = $(root, "data-submit");
  $(root, "data-auth-title").textContent = text.title;
  $(root, "data-auth-subtitle").textContent = text.subtitle;
  submit.textContent = text.submit;
  $(root, "data-switch").append(text.switch[0], el("a", { href: text.switch[1], textContent: text.switch[2] }));
  for (const tab of root.querySelectorAll("[data-tab]")) {
    tab.classList.toggle("active", tab.dataset.tab === mode);
  }
  const isRegister = mode === "register";
  $(root, "data-name-field").hidden = !isRegister;
  form.display_name.required = isRegister;
  form.password.autocomplete = isRegister ? "new-password" : "current-password";
  form.password.placeholder = isRegister ? "Ít nhất 8 ký tự" : "Mật khẩu của bạn";
  (isRegister ? form.display_name : form.email).focus();

  const toggle = $(root, "data-toggle-password");
  toggle.addEventListener("click", () => {
    const show = form.password.type === "password";
    form.password.type = show ? "text" : "password";
    toggle.textContent = show ? "Ẩn" : "Hiện";
  });

  function check() {
    if (isRegister && !form.display_name.value.trim()) return "Vui lòng nhập tên hiển thị.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.value.trim())) return "Email không hợp lệ.";
    if (isRegister && form.password.value.length < 8) return "Mật khẩu cần ít nhất 8 ký tự.";
    if (!form.password.value) return "Vui lòng nhập mật khẩu.";
    return "";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const problem = check();
    error.textContent = problem;
    error.hidden = !problem;
    if (problem) return;

    const body = { email: form.email.value.trim(), password: form.password.value };
    if (isRegister) body.display_name = form.display_name.value.trim();
    submit.disabled = true;
    try {
      const user = await api(`/auth/${mode}`, { method: "POST", body: JSON.stringify(body) });
      setUser(user);
      toast(isRegister ? `Chào ${user.display_name}! Tài khoản đã được tạo.` : `Chào mừng trở lại, ${user.display_name}!`);
      location.hash = "#/";
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
}

// ---------- Chủ đề ----------
// The topic list is the same for everyone and rarely changes: fetched once per visit.
let topicsCache = null;
async function loadTopics() {
  if (!topicsCache) topicsCache = await api("/topics");
  return topicsCache;
}
const topicBySlug = (slug) => topicsCache?.find((t) => t.slug === slug);
const topicById = (id) => topicsCache?.find((t) => t.id === id);

// Fills a <select> with the topics. With allLabel the values are slugs (review page),
// otherwise topic ids (word form). With counts, empty topics are disabled.
function topicOptions(select, { allLabel, counts } = {}) {
  const opts = [];
  if (allLabel) opts.push(el("option", { value: "", textContent: allLabel }));
  for (const t of topicsCache) {
    const n = counts ? counts[t.id] || 0 : null;
    const opt = el("option", {
      value: allLabel ? t.slug : t.id,
      textContent: `${t.icon} ${t.name}` + (counts ? ` (${n})` : ""),
    });
    if (counts && !n) opt.disabled = true;
    opts.push(opt);
  }
  select.replaceChildren(...opts);
}

// ---------- Danh sách ----------
async function listPage(params) {
  const root = mount("tpl-list");
  const form = $(root, "data-search");
  const list = $(root, "data-words");
  const count = $(root, "data-count");
  const more = $(root, "data-more");
  const sort = $(root, "data-sort");
  const posSelect = $(root, "data-pos");
  const tiles = $(root, "data-topics");
  const reviewTopic = $(root, "data-review-topic");
  form.q.value = params.get("q") || "";
  list.replaceChildren(...Array.from({ length: 6 }, () => el("li", { className: "card skeleton" })));

  let words, topics;
  try {
    [words, topics] = await Promise.all([api("/words"), loadTopics()]);
  } catch (err) {
    return showError(list, err);
  }
  renderStats($(root, "data-stats"), words);

  const state = {
    q: form.q.value, topic: params.get("topic") || "", pos: "", sort: "new", shown: PAGE_SIZE,
  };

  // Part of speech: only the ones present in the notebook.
  const posCounts = {};
  for (const w of words) posCounts[w.part_of_speech] = (posCounts[w.part_of_speech] || 0) + 1;
  posSelect.append(el("option", { value: "", textContent: "Mọi loại từ" }),
    ...Object.keys(POS_LABELS).filter((p) => posCounts[p])
      .map((p) => el("option", { value: p, textContent: `${POS_LABELS[p]} (${posCounts[p]})` })));

  function renderTiles() {
    const byTopic = {};
    for (const w of words) byTopic[w.topic_id ?? ""] = (byTopic[w.topic_id ?? ""] || 0) + 1;
    const defs = [{ slug: "", icon: "📚", name: "Tất cả", n: words.length }]
      .concat(topics.map((t) => ({ slug: t.slug, icon: t.icon, name: t.name, n: byTopic[t.id] || 0 })));
    if (byTopic[""]) defs.push({ slug: "none", icon: "🗂️", name: "Chưa phân loại", n: byTopic[""] });
    tiles.replaceChildren(...defs.map((d) => {
      const tile = el("button", { type: "button", className: "topic-tile" },
        el("span", { className: "icon", textContent: d.icon }),
        el("span", { className: "name", textContent: d.name }),
        el("span", { className: "n", textContent: `${d.n} từ` }));
      tile.classList.toggle("active", d.slug === state.topic);
      tile.setAttribute("aria-pressed", d.slug === state.topic);
      tile.addEventListener("click", () => {
        state.topic = d.slug;
        state.shown = PAGE_SIZE;
        syncUrl();
        render();
      });
      return tile;
    }));
  }

  function inTopic(w) {
    if (!state.topic) return true;
    if (state.topic === "none") return w.topic_id == null;
    return topicBySlug(state.topic)?.id === w.topic_id;
  }

  function filtered() {
    const q = state.q.toLowerCase();
    const out = words.filter((w) => inTopic(w) &&
      (!state.pos || w.part_of_speech === state.pos) &&
      (!q || w.word.toLowerCase().includes(q) || w.meaning_vi.toLowerCase().includes(q)));
    if (state.sort === "az") out.sort((a, b) => a.word.localeCompare(b.word));
    if (state.sort === "za") out.sort((a, b) => b.word.localeCompare(a.word));
    return out;
  }

  function render() {
    renderTiles();
    const topic = topicBySlug(state.topic);
    reviewTopic.hidden = !topic;
    if (topic) {
      reviewTopic.href = `#/review?topic=${topic.slug}`;
      reviewTopic.textContent = `Ôn chủ đề ${topic.icon} ${topic.name} →`;
    }
    const items = filtered();
    count.textContent = state.q || state.pos || state.topic
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

  // Search text and topic are kept in the URL without re-running the router.
  function syncUrl() {
    const qs = new URLSearchParams();
    if (state.q) qs.set("q", state.q);
    if (state.topic) qs.set("topic", state.topic);
    const query = qs.toString();
    history.replaceState(null, "", "#/" + (query ? "?" + query : ""));
  }

  let typing;
  form.q.addEventListener("input", () => {
    clearTimeout(typing);
    typing = setTimeout(() => {
      state.q = form.q.value.trim();
      state.shown = PAGE_SIZE;
      syncUrl();
      render();
    }, 150);
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  sort.addEventListener("change", () => { state.sort = sort.value; render(); });
  posSelect.addEventListener("change", () => {
    state.pos = posSelect.value;
    state.shown = PAGE_SIZE;
    render();
  });
  more.addEventListener("click", () => { state.shown += PAGE_SIZE; render(); });
  render();
}

function renderStats(box, words) {
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000;
  const stats = [
    ["Tổng số từ", words.length],
    ["Thêm trong 7 ngày", words.filter((w) => new Date(w.created_at) > weekAgo).length],
    ["Có câu ví dụ", words.filter((w) => w.example).length],
    ["Chủ đề đang học", new Set(words.map((w) => w.topic_id).filter((id) => id != null)).size],
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
  const topic = topicById(w.topic_id);
  if (topic) {
    li.append(el("a", {
      className: "topic-tag", href: `#/?topic=${topic.slug}`, textContent: `${topic.icon} ${topic.name}`,
    }));
  }
  return li;
}

// ---------- Thêm / Sửa ----------
async function formPage(id) {
  const root = mount("tpl-form");
  const form = $(root, "data-form");
  const error = $(root, "data-error");
  $(root, "data-title").textContent = id ? "Sửa từ" : "Thêm từ mới";
  try {
    await loadTopics();
  } catch (err) {
    return showError(view, err);
  }
  topicOptions(form.topic_id);
  form.topic_id.prepend(el("option", { value: "", textContent: "— Chưa phân loại —" }));
  form.topic_id.value = "";

  if (id) {
    try {
      const w = await api(`/words/${id}`);
      for (const k of ["word", "meaning_vi", "part_of_speech", "example", "usage_note", "topic_id"]) {
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
    if (data.topic_id) data.topic_id = Number(data.topic_id);
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

// Deck size and direction are remembered in this browser (best effort).
function pref(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}
function savePref(key, value) {
  try { localStorage.setItem(key, value); } catch { /* private mode: keep it for this visit */ }
}

const MODES = {
  "en-vi": { label: "Nghĩa tiếng Việt của từ này là gì?", placeholder: "Gõ nghĩa tiếng Việt..." },
  "vi-en": { label: "Từ tiếng Anh nào có nghĩa là:", placeholder: "Type the English word..." },
};
const VERDICTS = {
  correct: ["ok", "✓ Chính xác!"],
  accent: ["ok", "✓ Đúng rồi! Nhớ gõ dấu cho chuẩn nhé."],
  close: ["ok", "≈ Gần đúng, chỉ sai chính tả một chút."],
  // vi-en: a typo in the English word is shown but does not count.
  closeMiss: ["warn", "≈ Gần đúng, nhưng sai chính tả nên chưa tính điểm."],
  wrong: ["bad", "✗ Chưa đúng."],
};

async function reviewPage(topicFromUrl) {
  const root = mount("tpl-review");
  const card = $(root, "data-card");
  const size = $(root, "data-size");
  const form = $(root, "data-answer-form");
  const input = $(root, "data-input");
  const feedback = $(root, "data-feedback");
  const before = $(root, "data-before");
  const hint = $(root, "data-hint");
  const override = $(root, "data-override");
  const bar = $(root, "data-bar");
  let mode = pref("review-mode", "en-vi");

  const topicSelect = $(root, "data-review-topic-select");
  // A topic in the URL (from the list page) wins over the remembered one.
  let topicSlug = topicFromUrl ?? pref("review-topic", "");
  size.value = pref("review-size", "20");
  size.addEventListener("change", () => { savePref("review-size", size.value); reviewPage(topicSlug); });
  topicSelect.addEventListener("change", () => {
    savePref("review-topic", topicSelect.value);
    location.hash = topicSelect.value ? `#/review?topic=${topicSelect.value}` : "#/review";
  });
  for (const btn of root.querySelectorAll("[data-mode]")) {
    btn.classList.toggle("active", btn.dataset.mode === mode);
    btn.setAttribute("aria-checked", btn.dataset.mode === mode);
    btn.addEventListener("click", () => {
      if (btn.dataset.mode === mode) return;
      savePref("review-mode", btn.dataset.mode);
      reviewPage(topicSlug); // a new round in the other direction
    });
  }

  let words;
  try {
    [words] = await Promise.all([api("/words"), loadTopics()]);
  } catch (err) {
    return showError(card, err);
  }
  // "Ngẫu nhiên" = every word; otherwise only the chosen topic (empty topics are disabled).
  const counts = {};
  for (const w of words) counts[w.topic_id] = (counts[w.topic_id] || 0) + 1;
  topicOptions(topicSelect, { allLabel: `🎲 Ngẫu nhiên – tất cả chủ đề (${words.length})`, counts });
  const topic = topicBySlug(topicSlug);
  if (!topic || !counts[topic.id]) topicSlug = "";
  topicSelect.value = topicSlug;
  if (topicSlug) words = words.filter((w) => w.topic_id === topic.id);
  shuffle(words);
  if (words.length === 0) {
    card.innerHTML = '<p class="empty">Chưa có từ nào để ôn. <a href="#/new">Thêm từ</a></p>';
    return;
  }
  if (Number(size.value) > 0) words = words.slice(0, Number(size.value));

  let i = 0;
  let result = null; // "remembered" / "forgot" once the current card is answered
  let busy = false;
  const score = { remembered: 0, forgot: 0 };
  const missed = [];

  function render() {
    const w = words[i];
    result = null;
    bar.style.width = `${(i / words.length) * 100}%`;
    $(root, "data-progress").textContent =
      `Thẻ ${i + 1} / ${words.length} · Đúng ${score.remembered} · Sai ${score.forgot}`;
    const pos = $(root, "data-pos");
    pos.className = `badge ${w.part_of_speech || ""}`;
    pos.textContent = w.part_of_speech || "";
    $(root, "data-prompt-label").textContent = MODES[mode].label;
    $(root, "data-prompt").textContent = mode === "en-vi" ? w.word : w.meaning_vi;
    // In vi-en the sound would give the answer away, so it waits until after checking.
    $(root, "data-speak").hidden = mode === "vi-en";
    input.value = "";
    input.disabled = false;
    input.placeholder = MODES[mode].placeholder;
    input.lang = mode === "en-vi" ? "vi" : "en";
    input.className = "";
    $(root, "data-check").disabled = false;
    hint.hidden = true;
    before.hidden = false;
    feedback.hidden = true;
    input.focus();
  }

  function showHint() {
    const w = words[i];
    // vi-en: first letter + blanks; en-vi: first word of the meaning.
    hint.textContent = mode === "vi-en"
      ? w.word.replace(/[a-z]/gi, (c, k) => (k === 0 ? c : "_")).split("").join(" ")
      : `Bắt đầu bằng: “${w.meaning_vi.split(/[,;]/)[0].trim().split(" ")[0]} …”`;
    hint.hidden = false;
    input.focus();
  }

  function showFeedback(verdict, expected) {
    const w = words[i];
    const [tone, text] = VERDICTS[verdict];
    const v = $(root, "data-verdict");
    v.className = `verdict ${tone}`;
    v.textContent = text;
    $(root, "data-expected").textContent = expected;
    $(root, "data-example").textContent = w.example || "";
    $(root, "data-note").textContent = w.usage_note || "";
    feedback.className = `feedback ${tone}`;
    input.className = tone;
    input.disabled = true;
    $(root, "data-check").disabled = true;
    before.hidden = true;
    feedback.hidden = false;
    override.hidden = result !== "forgot" || !input.value.trim();
    $(root, "data-speak").hidden = false;
    $(root, "data-next").focus();
  }

  async function checkAnswer() {
    if (busy || result) return;
    const answer = input.value.trim();
    if (!answer) return skip();
    busy = true;
    try {
      const r = await api(`/words/${words[i].id}/check`, {
        method: "POST",
        body: JSON.stringify({ direction: mode, answer }),
      });
      result = r.correct ? "remembered" : "forgot";
      showFeedback(r.verdict === "close" && !r.correct ? "closeMiss" : r.verdict, r.expected);
    } catch (err) {
      toast(err.message);
    } finally {
      busy = false;
    }
  }

  function skip() {
    if (result) return;
    result = "forgot";
    showFeedback("wrong", mode === "en-vi" ? words[i].meaning_vi : words[i].word);
  }

  async function next() {
    if (busy || !result) return;
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
    if (result === "forgot") missed.push(words[i]);
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
    $(root, "data-summary").textContent =
      `Đúng ${score.remembered} · Sai ${score.forgot} trên tổng ${words.length} thẻ`;
    if (missed.length) {
      $(root, "data-missed").replaceChildren(...missed.map((w) => el("li", {},
        el("strong", { textContent: w.word }), ` — ${w.meaning_vi}`)));
      $(root, "data-missed-box").hidden = false;
    }
    $(root, "data-done").hidden = false;
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); checkAnswer(); });
  $(root, "data-hint-btn").addEventListener("click", showHint);
  $(root, "data-skip").addEventListener("click", skip);
  $(root, "data-next").addEventListener("click", next);
  $(root, "data-speak").addEventListener("click", () => speak(words[i].word));
  override.addEventListener("click", () => {
    result = "remembered";
    override.hidden = true;
    const v = $(root, "data-verdict");
    v.className = "verdict ok";
    v.textContent = "✓ Đã tính là đúng.";
    feedback.className = "feedback ok";
    input.className = "ok";
    $(root, "data-next").focus();
  });
  $(root, "data-again").addEventListener("click", () => reviewPage(topicSlug));

  // Enter on the "Tiếp tục" button already clicks it; this covers focus elsewhere.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || card.hidden || !result || e.target.closest("button")) return;
    e.preventDefault();
    next();
  }, { signal: pageSignal() });

  render();
}

// ---------- Router ----------
const PUBLIC_PAGES = ["/login", "/register"];

async function route() {
  const [path, qs] = location.hash.replace(/^#/, "").split("?");
  const params = new URLSearchParams(qs);

  if (me === undefined) {
    try {
      setUser(await api("/auth/me"));
    } catch {
      setUser(null);
    }
  }
  // Logged out: only the login / register pages. Logged in: never those two.
  if (!me && !PUBLIC_PAGES.includes(path)) { location.hash = "#/login"; return; }
  if (me && PUBLIC_PAGES.includes(path)) { location.hash = "#/"; return; }
  if (PUBLIC_PAGES.includes(path)) { authPage(path.slice(1)); window.scrollTo(0, 0); return; }

  let page = "list";
  const edit = path.match(/^\/edit\/(\d+)$/);
  if (path === "/new") { page = "new"; formPage(null); }
  else if (edit) { page = "edit"; formPage(Number(edit[1])); }
  else if (path === "/review") { page = "review"; reviewPage(params.get("topic")); }
  else listPage(params);
  for (const a of document.querySelectorAll("[data-nav]")) {
    a.classList.toggle("active", a.dataset.nav === page);
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
