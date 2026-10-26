// app.js — hash router + pages for the Vocabulary Notebook UI.
//   #/login       log in            #/register    create an account
//   #/            list (topics, search, filter by part of speech, sort, edit, delete)
//   #/admin-login sign-in form for admin accounts only (checked by the server)
//   #/progress    the logged-in user's own progress
//   #/admin       admins only: manage words (?tab=learners: learners' progress)
//   #/admin/new   admins only: add a word     #/admin/edit/{id}   edit a word
//   #/review      typed review by topic or random, English <-> Vietnamese; logs results
// Everything goes through the JSON API under /api (app/auth.py, app/routes.py).
// The session is an HttpOnly cookie the browser sends by itself; this file never sees it.
"use strict";

const view = document.getElementById("view");
let me = undefined; // undefined = not checked yet, null = logged out
const PAGE_SIZE = 30;
const POS_LABELS = {
  noun: "Nouns", verb: "Verbs", adjective: "Adjectives", adverb: "Adverbs",
  preposition: "Prepositions", conjunction: "Conjunctions", pronoun: "Pronouns", phrase: "Phrases",
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
      ? "Invalid data: " + body.detail.map((d) => d.msg).join("; ")
      : body.detail || `Error ${res.status}`;
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
  if (!("speechSynthesis" in window)) return toast("Your browser cannot play pronunciation");
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
  for (const link of document.querySelectorAll("[data-admin-only]")) link.hidden = !isAdmin();
}

const isAdmin = () => me?.role === "admin";

document.querySelector("[data-logout]").addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {
    // Already logged out on the server: nothing else to do.
  }
  setUser(null);
  toast("Logged out");
  location.hash = "#/login";
});

const AUTH_TEXT = {
  login: {
    title: "Welcome back",
    subtitle: "Log in to keep practicing your vocabulary.",
    submit: "Log in",
    switch: ["Don't have an account? ", "#/register", "Sign up"],
  },
  register: {
    title: "Create an account",
    subtitle: "Start practicing 300+ common words, sorted by topic.",
    submit: "Create account",
    switch: ["Already have an account? ", "#/login", "Log in"],
  },
  "admin-login": {
    title: "Admin sign in",
    subtitle: "Only admin accounts can sign in here. Admin accounts cannot be created by signing up.",
    submit: "Sign in as admin",
    switch: ["", "#/login", "← Back to learner sign in"],
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
  const isAdminLogin = mode === "admin-login";
  $(root, "data-auth-tabs").hidden = isAdminLogin;
  $(root, "data-admin-link").hidden = isAdminLogin;
  $(root, "data-auth-tabs").closest(".auth-card").classList.toggle("admin-mode", isAdminLogin);
  $(root, "data-name-field").hidden = !isRegister;
  form.display_name.required = isRegister;
  form.password.autocomplete = isRegister ? "new-password" : "current-password";
  form.password.placeholder = isRegister ? "At least 8 characters" : "Your password";
  (isRegister ? form.display_name : form.email).focus();

  const toggle = $(root, "data-toggle-password");
  toggle.addEventListener("click", () => {
    const show = form.password.type === "password";
    form.password.type = show ? "text" : "password";
    toggle.textContent = show ? "Hide" : "Show";
  });

  function check() {
    if (isRegister && !form.display_name.value.trim()) return "Please enter a display name.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.value.trim())) return "Please enter a valid email.";
    if (isRegister && form.password.value.length < 8) return "Password must be at least 8 characters.";
    if (!form.password.value) return "Please enter your password.";
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
    if (isAdminLogin) body.admin = true; // the server refuses non-admin accounts
    submit.disabled = true;
    try {
      const endpoint = isRegister ? "/auth/register" : "/auth/login";
      const user = await api(endpoint, { method: "POST", body: JSON.stringify(body) });
      setUser(user);
      toast(isRegister ? `Hi ${user.display_name}! Your account is ready.` : `Welcome back, ${user.display_name}!`);
      location.hash = isAdminLogin ? "#/admin" : "#/";
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
  posSelect.append(el("option", { value: "", textContent: "All parts of speech" }),
    ...Object.keys(POS_LABELS).filter((p) => posCounts[p])
      .map((p) => el("option", { value: p, textContent: `${POS_LABELS[p]} (${posCounts[p]})` })));

  function renderTiles() {
    const byTopic = {};
    for (const w of words) byTopic[w.topic_id ?? ""] = (byTopic[w.topic_id ?? ""] || 0) + 1;
    const defs = [{ slug: "", icon: "📚", name: "All", n: words.length }]
      .concat(topics.map((t) => ({ slug: t.slug, icon: t.icon, name: t.name, n: byTopic[t.id] || 0 })));
    if (byTopic[""]) defs.push({ slug: "none", icon: "🗂️", name: "Uncategorized", n: byTopic[""] });
    tiles.replaceChildren(...defs.map((d) => {
      const tile = el("button", { type: "button", className: "topic-tile" },
        el("span", { className: "icon", textContent: d.icon }),
        el("span", { className: "name", textContent: d.name }),
        el("span", { className: "n", textContent: `${d.n} ${d.n === 1 ? "word" : "words"}` }));
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
      reviewTopic.textContent = `Practice ${topic.icon} ${topic.name} →`;
    }
    const items = filtered();
    count.textContent = state.q || state.pos || state.topic
      ? `${items.length} of ${words.length} words match`
      : `${words.length} words in the bank`;
    if (items.length === 0) {
      list.replaceChildren(el("li", {
        className: "card empty",
        textContent: words.length ? "No words match." : "No words yet. An admin will add them soon.",
      }));
    } else {
      list.replaceChildren(...items.slice(0, state.shown).map((w) => wordItem(w)));
    }
    more.hidden = items.length <= state.shown;
    more.textContent = `Show more (${items.length - state.shown})`;
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
    ["Total words", words.length],
    ["New this week", words.filter((w) => new Date(w.created_at) > weekAgo).length],
    ["With an example", words.filter((w) => w.example).length],
    ["Topics in use", new Set(words.map((w) => w.topic_id).filter((id) => id != null)).size],
  ];
  box.replaceChildren(...stats.map(([label, value]) => el("div", { className: "card stat" },
    el("div", { className: "label", textContent: label }),
    el("div", { className: "value", textContent: value.toLocaleString("en-US") }))));
}

// Learners read words here; changing them happens on the admin page.
function wordItem(w) {
  const li = el("li", { className: "card word-item" });
  const sound = iconButton("speak", "Listen");
  sound.addEventListener("click", () => speak(w.word));
  const actions = el("div", { className: "actions" }, sound);
  if (isAdmin()) {
    const edit = iconButton("edit", "Edit in admin");
    edit.href = `#/admin/edit/${w.id}`;
    actions.append(edit);
  }

  li.append(
    el("div", { className: "word-head" },
      el("span", { className: "w", textContent: w.word }),
      posBadge(w.part_of_speech),
      actions),
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
  $(root, "data-title").textContent = id ? "Edit word" : "Add a new word";
  try {
    await loadTopics();
  } catch (err) {
    return showError(view, err);
  }
  topicOptions(form.topic_id);
  form.topic_id.prepend(el("option", { value: "", textContent: "— Uncategorized —" }));
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
      toast(id ? "Changes saved" : `Added "${data.word}"`);
      location.hash = "#/admin";
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
  "en-vi": { label: "What does this word mean in Vietnamese?", placeholder: "Type the Vietnamese meaning..." },
  "vi-en": { label: "Which English word means:", placeholder: "Type the English word..." },
};
const VERDICTS = {
  correct: ["ok", "✓ Correct!"],
  accent: ["ok", "✓ Correct! Remember to type the Vietnamese accents."],
  close: ["ok", "≈ Almost, just a small typo. Counted as correct."],
  // vi-en: a typo in the English word is shown but does not count.
  closeMiss: ["warn", "≈ Almost, but the spelling is wrong, so it does not count."],
  wrong: ["bad", "✗ Not quite."],
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
  topicOptions(topicSelect, { allLabel: `🎲 Random – all topics (${words.length})`, counts });
  const topic = topicBySlug(topicSlug);
  if (!topic || !counts[topic.id]) topicSlug = "";
  topicSelect.value = topicSlug;
  if (topicSlug) words = words.filter((w) => w.topic_id === topic.id);
  shuffle(words);
  if (words.length === 0) {
    card.innerHTML = '<p class="empty">No words to practice yet.</p>';
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
      `Card ${i + 1} of ${words.length} · Correct ${score.remembered} · Wrong ${score.forgot}`;
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
      : `Starts with: “${w.meaning_vi.split(/[,;]/)[0].trim().split(" ")[0]} …”`;
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
      `Correct ${score.remembered} · Wrong ${score.forgot} out of ${words.length} cards`;
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
    v.textContent = "✓ Counted as correct.";
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

// ---------- Tiến độ ----------
async function progressPage() {
  const root = mount("tpl-progress");
  let p;
  try {
    p = await api("/me/progress");
  } catch (err) {
    return showError(view.querySelector("section"), err);
  }
  const accuracy = p.answered ? Math.round((p.correct / p.answered) * 100) + "%" : "—";
  $(root, "data-progress-stats").replaceChildren(...[
    ["Answers", p.answered.toLocaleString("en-US"), "checked in Practice"],
    ["Accuracy", accuracy, `${p.correct} right`],
    ["Words practiced", p.practiced, `of ${p.total_words}`],
    ["Words mastered", p.mastered, "last answer right"],
  ].map(([label, value, sub]) => el("div", { className: "card stat" },
    el("div", { className: "label", textContent: label }),
    el("div", { className: "value", textContent: value }),
    el("div", { className: "sub", textContent: sub }))));

  // Last 7 days: one bar per day, the green part is the correct answers.
  const max = Math.max(1, ...p.last_7_days.map((d) => d.answered));
  $(root, "data-week").replaceChildren(...p.last_7_days.map((d) => {
    const date = new Date(d.day + "T00:00:00");
    const bar = el("div", { className: "bar", title: `${d.correct} right of ${d.answered}` },
      el("div", { className: "bar-ok" }));
    bar.style.height = `${(d.answered / max) * 100}%`;
    bar.firstChild.style.height = d.answered ? `${(d.correct / d.answered) * 100}%` : "0";
    return el("div", { className: "day" },
      el("span", { className: "n", textContent: d.answered || "" }),
      el("div", { className: "bar-box" }, bar),
      el("span", { className: "label", textContent: date.toLocaleDateString("en-US", { weekday: "short" }) }));
  }));

  const toReview = $(root, "data-to-review");
  toReview.replaceChildren(...(p.to_review.length
    ? p.to_review.map((w) => el("li", {},
      el("strong", { textContent: w.word }), el("span", { textContent: ` — ${w.meaning_vi}` }),
      el("span", { className: "muted forgot", textContent: `forgot ${w.forgot}×` })))
    : [el("li", { className: "muted", textContent: p.answered ? "Nothing to fix. Nice work!" : "Practice a few words first." })]));

  $(root, "data-topic-progress").replaceChildren(...p.topics.filter((t) => t.total).map((t) => {
    const bar = el("div", { className: "track" },
      el("div", { className: "seen" }), el("div", { className: "ok" }));
    bar.children[0].style.width = `${(t.practiced / t.total) * 100}%`;
    bar.children[1].style.width = `${(t.mastered / t.total) * 100}%`;
    const row = el("a", { className: "topic-row", href: `#/review?topic=${t.slug}`, title: `Practice ${t.name}` },
      el("span", { className: "name", textContent: `${t.icon} ${t.name}` }),
      bar,
      el("span", { className: "muted nums", textContent: `${t.mastered} / ${t.total}` }));
    return row;
  }));
}

// ---------- Admin ----------
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString("en-GB") : "—");

async function adminPage(params) {
  const root = mount("tpl-admin");
  const tab = params.get("tab") === "learners" ? "learners" : "words";
  for (const t of root.querySelectorAll("[data-admin-tab]")) t.classList.toggle("active", t.dataset.adminTab === tab);
  $(root, "data-admin-words").hidden = tab !== "words";
  $(root, "data-admin-learners").hidden = tab !== "learners";

  let words, users;
  try {
    [words, users] = await Promise.all([api("/words"), api("/admin/users"), loadTopics()]);
  } catch (err) {
    return showError(view.querySelector("section"), err);
  }
  const learners = users.filter((u) => u.role === "learner");
  const practiced = users.reduce((n, u) => n + u.review_count, 0);
  $(root, "data-admin-stats").replaceChildren(...[
    ["Words", words.length],
    ["Topics", topicsCache.length],
    ["Learners", learners.length],
    ["Answers logged", practiced],
  ].map(([label, value]) => el("div", { className: "card stat" },
    el("div", { className: "label", textContent: label }),
    el("div", { className: "value", textContent: value.toLocaleString("en-US") }))));

  if (tab === "learners") return renderLearners($(root, "data-learner-rows"), users);

  const form = $(root, "data-search");
  const topicSelect = $(root, "data-admin-topic");
  const rows = $(root, "data-rows");
  const count = $(root, "data-count");
  const more = $(root, "data-more");
  const state = { q: "", topic: "", shown: 50 };
  const counts = {};
  for (const w of words) counts[w.topic_id] = (counts[w.topic_id] || 0) + 1;
  topicOptions(topicSelect, { allLabel: `All topics (${words.length})`, counts });
  if (counts.null || counts.undefined) {
    topicSelect.append(el("option", { value: "none", textContent: `🗂️ Uncategorized (${(counts.null || 0) + (counts.undefined || 0)})` }));
  }

  function render() {
    const q = state.q.toLowerCase();
    const topic = topicBySlug(state.topic);
    const items = words.filter((w) =>
      (!state.topic || (state.topic === "none" ? w.topic_id == null : w.topic_id === topic?.id)) &&
      (!q || w.word.toLowerCase().includes(q) || w.meaning_vi.toLowerCase().includes(q)));
    count.textContent = `${items.length} of ${words.length} words`;
    rows.replaceChildren(...items.slice(0, state.shown).map((w) => adminRow(w, () => {
      words = words.filter((x) => x.id !== w.id);
      render();
    })));
    if (!items.length) {
      rows.append(el("tr", {}, el("td", { colSpan: 5, className: "empty", textContent: "No words match." })));
    }
    more.hidden = items.length <= state.shown;
    more.textContent = `Show more (${items.length - state.shown})`;
  }

  let typing;
  form.q.addEventListener("input", () => {
    clearTimeout(typing);
    typing = setTimeout(() => { state.q = form.q.value.trim(); state.shown = 50; render(); }, 150);
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  topicSelect.addEventListener("change", () => { state.topic = topicSelect.value; state.shown = 50; render(); });
  more.addEventListener("click", () => { state.shown += 50; render(); });
  render();
}

function adminRow(w, onDeleted) {
  const topic = topicById(w.topic_id);
  const edit = iconButton("edit", "Edit");
  edit.href = `#/admin/edit/${w.id}`;
  const del = iconButton("trash", "Delete", "danger");
  del.addEventListener("click", async () => {
    if (!confirm(`Delete "${w.word}" for every learner? Their practice history for it is deleted too.`)) return;
    try {
      await api(`/words/${w.id}`, { method: "DELETE" });
      toast(`Deleted "${w.word}"`);
      onDeleted();
    } catch (err) {
      toast(err.message);
    }
  });
  return el("tr", {},
    el("td", {}, el("strong", { textContent: w.word }), " ", posBadge(w.part_of_speech)),
    el("td", { textContent: w.meaning_vi }),
    el("td", { className: "nowrap", textContent: topic ? `${topic.icon} ${topic.name}` : "—" }),
    el("td", { className: "muted hide-sm ex", textContent: w.example || "" }),
    el("td", { className: "row-actions" }, edit, del));
}

function renderLearners(tbody, users) {
  if (!users.length) {
    tbody.replaceChildren(el("tr", {}, el("td", { colSpan: 7, className: "empty", textContent: "No accounts yet." })));
    return;
  }
  tbody.replaceChildren(...users.map((u) => {
    const accuracy = u.review_count ? Math.round((u.remembered_count / u.review_count) * 100) + "%" : "—";
    return el("tr", {},
      el("td", {}, el("strong", { textContent: u.display_name })),
      el("td", { textContent: u.email }),
      el("td", {}, el("span", { className: `badge ${u.role === "admin" ? "verb" : ""}`, textContent: u.role })),
      el("td", { textContent: u.review_count.toLocaleString("en-US") }),
      el("td", { textContent: accuracy }),
      el("td", { className: "hide-sm", textContent: fmtDate(u.last_review_at) }),
      el("td", { className: "hide-sm", textContent: fmtDate(u.created_at) }));
  }));
}

// ---------- Router ----------
const PUBLIC_PAGES = ["/login", "/register", "/admin-login"];

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

  // Admin pages: learners are sent back to their word list.
  if (path.startsWith("/admin") && !isAdmin()) {
    toast("Only admins can open that page");
    location.hash = "#/";
    return;
  }

  let page = "list";
  const edit = path.match(/^\/admin\/edit\/(\d+)$/);
  if (path === "/admin") { page = "admin"; adminPage(params); }
  else if (path === "/admin/new") { page = "admin"; formPage(null); }
  else if (edit) { page = "admin"; formPage(Number(edit[1])); }
  else if (path === "/progress") { page = "progress"; progressPage(); }
  else if (path === "/review") { page = "review"; reviewPage(params.get("topic")); }
  else listPage(params);
  for (const a of document.querySelectorAll("[data-nav]")) {
    a.classList.toggle("active", a.dataset.nav === page);
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
