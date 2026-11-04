// app.js — hash router + pages for the Vocabulary Notebook UI.
//   #/login       log in            #/register    create an account
//   #/            list (topics, search, filter by part of speech, sort, edit, delete)
//   #/admin-login sign-in form for admin accounts only (checked by the server)
//   #/progress    the logged-in user's own progress
//   #/admin       admins only: manage words (?tab=learners: learners' progress)
//   #/admin/new   admins only: add a word     #/admin/edit/{id}   edit a word
//   #/notebook    my own notebook (Vietnamese UI)
//   #/notebook/new  add a word to it          #/notebook/edit/{id}  edit one of my words
//   #/notebook/sentence  write a sentence with one of my words, the AI grades it (?word={id})
//   #/notebook/suggest   AI suggests new words by topic + level, tick them to add (?topic={id})
//   #/notebook/chat      chat in English with an AI tutor that uses my notebook words
//   #/review      typed review by topic or random, English <-> Vietnamese; logs results
//   #/quiz        server-graded quiz from the private notebook
//   #/srs         spaced repetition for words due today
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
  let res;
  try {
    res = await fetch("/api" + path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new Error("Could not connect to the server. Check your connection and try again.");
  }
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
  save: '<path d="M6 3h12v18l-6-4-6 4z"/><path d="M12 7v6M9 10h6"/>',
  saved: '<path d="M6 3h12v18l-6-4-6 4z" fill="currentColor"/>',
  write: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 20h6"/>',
};
function iconButton(icon, label, extraClass = "") {
  const tag = icon === "edit" || icon === "write" ? "a" : "button";
  const btn = el(tag, { className: `icon-btn ${extraClass}`, title: label });
  btn.setAttribute("aria-label", label);
  btn.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[icon]}</svg>`;
  return btn;
}

function posBadge(pos) {
  return el("span", { className: `badge ${pos || ""}`, textContent: pos || "" });
}

// ---------- Account ----------
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

// ---------- Topics ----------
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

// ---------- Word list ----------
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

  let words, topics, mine;
  try {
    [words, topics, mine] = await Promise.all([
      api("/words"), loadTopics(), api("/notebook/words").catch(() => []),
    ]);
  } catch (err) {
    return showError(list, err);
  }
  // Lower-cased words already in my notebook, to show them as saved.
  const saved = new Set(mine.map((w) => w.word.toLowerCase()));
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
      list.replaceChildren(...items.slice(0, state.shown).map((w) => wordItem(w, saved)));
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
// The bookmark button copies the word into my own notebook.
function wordItem(w, saved = new Set()) {
  const li = el("li", { className: "card word-item" });
  const sound = iconButton("speak", "Listen");
  sound.addEventListener("click", () => speak(w.word));
  const actions = el("div", { className: "actions" }, sound, saveButton(w, saved));
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
    el("div", { className: "meaning", textContent: w.meaning_vi, lang: "vi" }),
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

function saveButton(w, saved) {
  const isSaved = () => saved.has(w.word.toLowerCase());
  const btn = el("button", { className: "icon-btn save-btn" });
  const paint = () => {
    const label = isSaved() ? "Already in my notebook" : "Add to my notebook";
    btn.title = label;
    btn.setAttribute("aria-label", label);
    btn.classList.toggle("saved", isSaved());
    btn.innerHTML = `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[isSaved() ? "saved" : "save"]}</svg>`;
  };
  paint();
  btn.addEventListener("click", async () => {
    if (isSaved()) return toast(`"${w.word}" is already in your notebook`);
    btn.disabled = true;
    try {
      await api(`/notebook/from-bank/${w.id}`, { method: "POST" });
      saved.add(w.word.toLowerCase());
      paint();
      toast(`Added "${w.word}" to your notebook`);
    } catch (err) {
      toast(err.message);
    } finally {
      btn.disabled = false;
    }
  });
  return btn;
}

// ---------- My notebook ----------
async function notebookPage(params) {
  const root = mount("tpl-notebook");
  const form = $(root, "data-search");
  const list = $(root, "data-words");
  const count = $(root, "data-count");
  const more = $(root, "data-more");
  const sort = $(root, "data-sort");
  form.q.value = params.get("q") || "";
  list.replaceChildren(...Array.from({ length: 6 }, () => el("li", { className: "card skeleton" })));

  let words;
  try {
    [words] = await Promise.all([api("/notebook/words"), loadTopics()]);
  } catch (err) {
    return showError(list, err);
  }
  const state = { q: form.q.value.trim(), sort: pref("notebook-sort", "new"), shown: PAGE_SIZE };
  sort.value = state.sort;

  function render() {
    const q = state.q.toLowerCase();
    const items = words.filter((w) =>
      !q || w.word.toLowerCase().includes(q) || w.meaning_vi.toLowerCase().includes(q));
    if (state.sort === "az") items.sort((a, b) => a.word.localeCompare(b.word));
    if (state.sort === "za") items.sort((a, b) => b.word.localeCompare(a.word));
    count.textContent = q ? `${items.length} / ${words.length} matching words` : `${words.length} words in your notebook`;
    if (items.length === 0) {
      const empty = el("li", { className: "card empty" });
      if (words.length) empty.textContent = "No matching words.";
      else {
        empty.append("Your notebook is empty. ",
          el("a", { href: "#/notebook/new", textContent: "Add your first word" }),
          " or click 🔖 on a word in the ", el("a", { href: "#/", textContent: "shared bank" }), ".");
      }
      list.replaceChildren(empty);
    } else {
      list.replaceChildren(...items.slice(0, state.shown).map((w) => notebookItem(w, () => {
        words = words.filter((x) => x.id !== w.id);
        render();
      })));
    }
    more.hidden = items.length <= state.shown;
    more.textContent = `Show more (${items.length - state.shown})`;
  }

  let typing;
  form.q.addEventListener("input", () => {
    clearTimeout(typing);
    typing = setTimeout(() => {
      state.q = form.q.value.trim();
      state.shown = PAGE_SIZE;
      history.replaceState(null, "", "#/notebook" + (state.q ? "?q=" + encodeURIComponent(state.q) : ""));
      render();
    }, 150);
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  sort.addEventListener("change", () => { state.sort = sort.value; savePref("notebook-sort", sort.value); render(); });
  more.addEventListener("click", () => { state.shown += PAGE_SIZE; render(); });
  render();
}

const SOURCE_LABELS = { bank: "shared bank", ai: "AI suggestion" };

function chips(label, items, className = "") {
  if (!items?.length) return null;
  return el("p", { className: `chips ${className}` },
    el("span", { className: "chips-label", textContent: label }),
    ...items.map((t) => el("span", { className: "chip", textContent: t, lang: "en" })));
}

function notebookItem(w, onDeleted) {
  const li = el("li", { className: "card word-item" });
  const sound = iconButton("speak", "Listen");
  sound.addEventListener("click", () => speak(w.word));
  const write = iconButton("write", "Write a sentence with this word");
  write.href = `#/notebook/sentence?word=${w.id}`;
  const edit = iconButton("edit", "Edit");
  edit.href = `#/notebook/edit/${w.id}`;
  const del = iconButton("trash", "Remove from notebook", "danger");
  del.addEventListener("click", async () => {
    if (!confirm(`Remove "${w.word}" from your notebook?`)) return;
    try {
      await api(`/notebook/words/${w.id}`, { method: "DELETE" });
      toast(`Removed "${w.word}"`);
      onDeleted();
    } catch (err) {
      toast(err.message);
    }
  });

  const head = el("div", { className: "word-head nb" },
    el("span", { className: "w", textContent: w.word, lang: "en" }));
  if (w.ipa) head.append(el("span", { className: "ipa", textContent: w.ipa }));
  head.append(posBadge(w.part_of_speech), el("div", { className: "actions" }, sound, write, edit, del));
  li.append(head, el("div", { className: "meaning", textContent: w.meaning_vi, lang: "vi" }));
  if (w.definition_en) li.append(el("p", { className: "def", textContent: w.definition_en, lang: "en" }));
  if (w.examples.length) {
    li.append(el("ul", { className: "examples" }, ...w.examples.map((ex) => el("li", {},
      el("span", { className: "ex", textContent: ex.en, lang: "en" }),
      ex.vi ? el("span", { className: "ex-vi", textContent: ex.vi, lang: "vi" }) : ""))));
  }
  for (const node of [
    chips("Synonyms", w.synonyms),
    chips("Antonyms", w.antonyms, "anti"),
    chips("Collocations", w.collocations),
  ]) if (node) li.append(node);
  if (w.usage_note) li.append(el("p", { className: "note", textContent: w.usage_note }));
  const foot = el("div", { className: "word-foot" });
  const topic = topicById(w.topic_id);
  if (topic) foot.append(el("span", { className: "topic-tag", textContent: `${topic.icon} ${topic.name}` }));
  if (SOURCE_LABELS[w.source]) foot.append(el("span", { className: "source", textContent: SOURCE_LABELS[w.source] }));
  if (foot.childNodes.length) li.append(foot);
  return li;
}

const splitList = (text) => text.split(/[,;\n]/).map((t) => t.trim()).filter(Boolean);

async function notebookFormPage(id) {
  const root = mount("tpl-notebook-form");
  const form = $(root, "data-form");
  const error = $(root, "data-error");
  const submit = $(root, "data-submit");
  $(root, "data-title").textContent = id ? "Edit word" : "Add a word to your notebook";
  let aiStatus = null;
  try {
    [, aiStatus] = await Promise.all([loadTopics(), api("/ai/status").catch(() => null)]);
  } catch (err) {
    return showError(view, err);
  }
  const ai = setupAiFill(root, form, aiStatus, submit);
  topicOptions(form.topic_id);
  form.topic_id.prepend(el("option", { value: "", textContent: "— Uncategorized —" }));
  form.topic_id.value = "";
  form.part_of_speech.replaceChildren(el("option", { value: "", textContent: "— Select —" }),
    ...Object.keys(POS_LABELS).map((p) => el("option", { value: p, textContent: p })));

  if (id) {
    try {
      fillNotebookForm(form, await api(`/notebook/words/${id}`));
    } catch (err) {
      return showError(view, err);
    }
  }
  form.word.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    error.hidden = true;
    const data = readNotebookForm(form);
    const problem = !data.word ? "Please enter an English word." : !data.meaning_vi ? "Please enter the Vietnamese meaning." : "";
    if (problem) {
      error.textContent = problem;
      error.hidden = false;
      return;
    }
    if (!id && ai.filled()) data.source = "ai";
    submit.disabled = true;
    try {
      await api(id ? `/notebook/words/${id}` : "/notebook/words", {
        method: id ? "PATCH" : "POST",
        body: JSON.stringify(data),
      });
      toast(id ? "Changes saved" : `Added "${data.word}" to your notebook`);
      location.hash = "#/notebook";
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
}

// ---------- Fill a word with AI ----------
// The browser only calls our own /api/ai/lookup; the Gemini key stays on the server.
const AI_TIMEOUT_MS = 45000; // the server retries a busy AI a few times before answering

function setupAiFill(root, form, status, submit) {
  const button = $(root, "data-ai-fill");
  const panel = $(root, "data-ai-panel");
  const hint = $(root, "data-ai-hint");
  let filled = false;
  let controller = null;

  if (!status?.enabled) {
    button.disabled = true;
    button.title = "AI is not enabled on the server (GEMINI_API_KEY is missing)";
    hint.textContent = "AI is not enabled on the server. You can still enter the word manually.";
  }
  const quota = el("span");
  function showQuota(s) {
    quota.textContent = ` ${Math.max(0, s.limit_per_day - s.used_today)}/${s.limit_per_day} AI requests remaining today (looking up an existing word is free).`;
  }
  if (status?.enabled) {
    hint.append(quota);
    showQuota(status);
  }

  function show(kind, ...children) {
    panel.className = `ai-panel ${kind}`;
    panel.replaceChildren(...children);
    panel.hidden = false;
  }

  function hasContent() {
    return ["meaning_vi", "definition_en", "example_en_0", "ipa"].some((k) => form[k].value.trim());
  }

  async function run(word) {
    word = (word ?? form.word.value).trim();
    if (!word) {
      form.word.focus();
      return show("warn", el("span", { className: "grow", textContent: "Please enter an English word first." }));
    }
    if (hasContent() && !confirm("Overwrite the existing fields with AI suggestions?")) return;

    controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, AI_TIMEOUT_MS);
    const cancel = el("button", { type: "button", className: "btn small ghost", textContent: "Cancel" });
    cancel.addEventListener("click", () => controller.abort());
    show("", el("span", { className: "spinner", ariaHidden: "true" }),
      el("span", { className: "grow", textContent: `AI is looking up "${word}"… this usually takes a few seconds.` }), cancel);
    button.disabled = submit.disabled = true;
    root.querySelector("[data-form]").setAttribute("aria-busy", "true");
    try {
      const body = await api("/ai/lookup", {
        method: "POST", body: JSON.stringify({ word }), signal: controller.signal,
      });
      const r = body.result;
      if (!r.is_english_word) {
        const parts = [el("span", { className: "grow", textContent: `Could not find the English word "${word}".` })];
        if (r.suggestion) {
          const retry = el("button", { type: "button", className: "btn small", textContent: `Did you mean "${r.suggestion}"?` });
          retry.addEventListener("click", () => { form.word.value = r.suggestion; run(r.suggestion); });
          parts.push(retry);
        }
        return show("warn", ...parts);
      }
      fillNotebookForm(form, {
        word: r.word || word,
        meaning_vi: r.meaning_vi,
        ipa: r.ipa,
        part_of_speech: r.part_of_speech,
        definition_en: r.definition_en,
        usage_note: r.usage_note,
        examples: r.examples,
        synonyms: r.synonyms,
        antonyms: r.antonyms,
        collocations: r.collocations,
        ...(body.topic_id ? { topic_id: body.topic_id } : {}),
      });
      filled = true;
      for (const field of form.querySelectorAll("input, textarea, select")) {
        if (field.name !== "word" && field.value) field.classList.add("ai-filled");
      }
      show("", el("span", { className: "grow" },
        el("strong", { textContent: "✨ AI filled in the information. " }),
        "Review and edit it as needed before saving.",
        body.cached ? el("span", { className: "muted", textContent: " (from cache, no request used)" }) : ""));
      form.meaning_vi.focus();
    } catch (err) {
      if (err.name === "AbortError" && !timedOut) return show("warn", el("span", { className: "grow", textContent: "Cancelled." }));
      const message = timedOut ? "The AI took too long to respond. Please try again." : err.message;
      const again = el("button", { type: "button", className: "btn small", textContent: "Try again" });
      again.addEventListener("click", () => run());
      show("error", el("span", { className: "grow", textContent: message }), again);
    } finally {
      clearTimeout(timer);
      button.disabled = submit.disabled = false;
      root.querySelector("[data-form]").removeAttribute("aria-busy");
      api("/ai/status").then(showQuota).catch(() => {}); // the count may have changed
    }
  }

  button.addEventListener("click", () => run());
  // Fields the user changes after the AI filled them lose the highlight.
  form.addEventListener("input", (e) => e.target.classList.remove("ai-filled"));
  return { filled: () => filled };
}

// ---------- Conversation practice (chatbot using notebook words) ----------
// The conversation lives in this page only; each turn sends it to POST /api/ai/chat.
const CHAT_WORDS = 6;
const CHAT_HISTORY = 20; // the server accepts at most 20 messages

async function chatPage() {
  const root = mount("tpl-chat");
  const body = $(root, "data-chat-body");
  const chipsBox = $(root, "data-chat-words");
  const log = $(root, "data-chat-log");
  const form = $(root, "data-form");
  const send = $(root, "data-submit");
  const hint = $(root, "data-ai-hint");

  let words, status;
  try {
    [words, status] = await Promise.all([api("/notebook/words"), api("/ai/status").catch(() => null)]);
  } catch (err) {
    return showError(body, err);
  }
  if (!words.length) {
    return body.replaceChildren(el("p", { className: "card empty" }, "Your notebook is empty. ",
      el("a", { href: "#/notebook/new", textContent: "Add a word" }), " and come back to practice the conversation."));
  }
  const aiOn = Boolean(status?.enabled);
  if (!aiOn) {
    send.disabled = form.message.disabled = true;
    hint.textContent = "AI is not enabled on the server, so conversation practice is unavailable.";
  }

  let targets = [];
  let history = []; // [{role: "learner" | "tutor", text}]
  let busy = false;
  const used = new Set();

  function pickWords() {
    targets = shuffle([...words]).slice(0, CHAT_WORDS);
    used.clear();
    chipsBox.replaceChildren(...targets.map((w) => {
      const chip = el("span", { className: "chip", textContent: w.word, title: w.meaning_vi, lang: "en" });
      chip.dataset.word = w.word.toLowerCase();
      return chip;
    }));
  }
  function markUsed(list) {
    for (const word of list) used.add(word);
    for (const chip of chipsBox.children) chip.classList.toggle("used", used.has(chip.dataset.word));
    const n = targets.filter((w) => used.has(w.word.toLowerCase())).length;
    $(root, "data-chat-score").textContent = `Words used correctly: ${n}/${targets.length}`;
  }

  function bubble(role, text) {
    const b = el("div", { className: `bubble ${role}` }, el("p", { textContent: text, lang: role === "tutor" ? "en" : "" }));
    log.append(b);
    b.scrollIntoView({ behavior: "smooth", block: "end" });
    return b;
  }
  function tutorBubble(r) {
    const b = bubble("tutor", r.reply);
    const vi = el("p", { className: "vi", textContent: r.reply_vi, hidden: true, lang: "vi" });
    const toggle = el("button", { type: "button", className: "btn small ghost", textContent: "Translate" });
    toggle.addEventListener("click", () => { vi.hidden = !vi.hidden; toggle.textContent = vi.hidden ? "Translate" : "Hide translation"; });
    const sound = iconButton("speak", "Listen");
    sound.addEventListener("click", () => speak(r.reply));
    b.append(vi, el("div", { className: "bubble-tools" }, sound, toggle));
  }
  function correctionNote(learnerBubble, c) {
    learnerBubble.append(el("div", { className: "bubble-fix" },
      el("span", { textContent: "✏️ " }),
      el("s", { textContent: c.original, lang: "en" }), " → ",
      el("strong", { textContent: c.corrected, lang: "en" }),
      el("span", { className: "muted", textContent: ` · ${c.explanation_vi}`, lang: "vi" })));
  }

  async function turn(learnerBubble) {
    busy = true;
    send.disabled = true;
    const typing = el("div", { className: "bubble tutor typing" }, el("span", { className: "spinner", ariaHidden: "true" }), " Replying…");
    log.append(typing);
    typing.scrollIntoView({ behavior: "smooth", block: "end" });
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), AI_TIMEOUT_MS);
    try {
      const res = await api("/ai/chat", {
        method: "POST",
        body: JSON.stringify({ word_ids: targets.map((w) => w.id), messages: history.slice(-CHAT_HISTORY) }),
        signal: controller.signal,
      });
      typing.remove();
      const r = res.reply;
      if (learnerBubble && r.correction) correctionNote(learnerBubble, r.correction);
      markUsed(r.learner_used);
      history.push({ role: "tutor", text: r.reply });
      tutorBubble(r);
    } catch (err) {
      typing.remove();
      const message = err.name === "AbortError" ? "The AI took too long to respond. Please try again." : err.message;
      const again = el("button", { type: "button", className: "btn small", textContent: "Try again" });
      const box = el("div", { className: "ai-panel error" }, el("span", { className: "grow", textContent: message }), again);
      again.addEventListener("click", () => { box.remove(); turn(learnerBubble); });
      log.append(box);
    } finally {
      clearTimeout(timer);
      busy = false;
      send.disabled = !aiOn;
      form.message.focus();
      api("/ai/status").then((s) => {
        hint.textContent = `Each message uses 1 AI request. ${Math.max(0, s.limit_per_day - s.used_today)}/${s.limit_per_day} requests remaining today.`;
      }).catch(() => {});
    }
  }

  function restart() {
    pickWords();
    history = [];
    log.replaceChildren();
    markUsed([]);
    if (aiOn) turn(null);
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = form.message.value.trim();
    if (!text || busy || !aiOn) return;
    form.message.value = "";
    history.push({ role: "learner", text });
    turn(bubble("learner", text));
  });
  form.message.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); }
  });
  $(root, "data-new-words").addEventListener("click", () => {
    if (history.length > 1 && !confirm("Start a new conversation with a different set of words?")) return;
    restart();
  });
  restart();
}

// ---------- Suggest words by topic + level ----------
// POST /api/ai/suggest-words returns new words (not in my notebook yet); the ones the learner
// ticks are saved with the normal POST /api/notebook/words.
const LEVELS = {
  A1: "A1 — beginner", A2: "A2 — elementary", B1: "B1 — intermediate",
  B2: "B2 — upper-intermediate", C1: "C1 — advanced",
};

async function suggestPage(params) {
  const root = mount("tpl-suggest");
  const body = $(root, "data-suggest-body");
  const form = $(root, "data-form");
  const panel = $(root, "data-ai-panel");
  const hint = $(root, "data-ai-hint");
  const submit = $(root, "data-submit");
  const list = $(root, "data-suggestions");
  const actions = $(root, "data-suggest-actions");
  const addBtn = $(root, "data-add");
  const moreBtn = $(root, "data-more");

  let status;
  try {
    [, status] = await Promise.all([loadTopics(), api("/ai/status").catch(() => null)]);
  } catch (err) {
    return showError(body, err);
  }
  topicOptions(form.topic_id);
  form.topic_id.value = params.get("topic") || pref("suggest-topic", String(topicsCache[0]?.id ?? ""));
  if (!form.topic_id.value) form.topic_id.selectedIndex = 0;
  form.level.replaceChildren(...Object.entries(LEVELS).map(([v, t]) => el("option", { value: v, textContent: t })));
  form.level.value = pref("suggest-level", "B1");

  const quota = el("span");
  function showQuota(s) {
    quota.textContent = ` ${Math.max(0, s.limit_per_day - s.used_today)}/${s.limit_per_day} AI requests remaining today.`;
  }
  const aiOn = Boolean(status?.enabled);
  if (aiOn) {
    hint.append(quota);
    showQuota(status);
  } else {
    submit.disabled = true;
    submit.title = "AI is not enabled on the server (GEMINI_API_KEY is missing)";
    hint.textContent = "AI is not enabled on the server, so suggestions are unavailable.";
  }

  let shown = [];   // every word shown for the current topic + level ("Suggest more" skips them)
  let topicId = null;

  function show(kind, ...children) {
    panel.className = `ai-panel ${kind}`;
    panel.replaceChildren(...children);
    panel.hidden = false;
  }
  function selected() {
    return [...list.querySelectorAll("input[type=checkbox]:checked:not(:disabled)")];
  }
  function updateAdd() {
    const n = selected().length;
    addBtn.disabled = n === 0;
    addBtn.textContent = n ? `+ Add ${n} word${n === 1 ? "" : "s"} to notebook` : "Select words to add";
  }

  function item(w) {
    const box = el("input", { type: "checkbox" });
    box.word = w;
    box.addEventListener("change", updateAdd);
    const sound = iconButton("speak", "Listen");
    sound.addEventListener("click", (e) => { e.preventDefault(); speak(w.word); });
    const head = el("div", { className: "word-head nb" },
      el("span", { className: "w", textContent: w.word, lang: "en" }));
    if (w.ipa) head.append(el("span", { className: "ipa", textContent: w.ipa }));
    head.append(posBadge(w.part_of_speech), sound);
    const text = el("div", { className: "suggest-text" }, head,
      el("div", { className: "meaning", textContent: w.meaning_vi, lang: "vi" }));
    if (w.definition_en) text.append(el("p", { className: "def", textContent: w.definition_en, lang: "en" }));
    text.append(el("ul", { className: "examples" }, el("li", {},
      el("span", { className: "ex", textContent: w.example.en, lang: "en" }),
      el("span", { className: "ex-vi", textContent: w.example.vi, lang: "vi" }))));
    return el("li", { className: "card word-item suggest-item" }, el("label", {}, box, text));
  }

  async function run(more) {
    if (!aiOn) return;
    if (!more) {
      shown = [];
      list.replaceChildren();
      actions.hidden = true;
    }
    topicId = Number(form.topic_id.value);
    savePref("suggest-topic", form.topic_id.value);
    savePref("suggest-level", form.level.value);
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, AI_TIMEOUT_MS);
    const cancel = el("button", { type: "button", className: "btn small ghost", textContent: "Cancel" });
    cancel.addEventListener("click", () => controller.abort());
    show("", el("span", { className: "spinner", ariaHidden: "true" }),
      el("span", { className: "grow", textContent: "AI is selecting words… this usually takes a few seconds." }), cancel);
    submit.disabled = moreBtn.disabled = true;
    try {
      const res = await api("/ai/suggest-words", {
        method: "POST",
        body: JSON.stringify({ topic_id: topicId, level: form.level.value, exclude: shown }),
        signal: controller.signal,
      });
      shown.push(...res.words.map((w) => w.word));
      list.append(...res.words.map(item));
      if (!res.words.length) {
        show("warn", el("span", { className: "grow", textContent: "AI could not find more new words for this topic. Try another level." }));
      } else {
        panel.hidden = true;
      }
      actions.hidden = !list.children.length;
      updateAdd();
    } catch (err) {
      if (err.name === "AbortError" && !timedOut) return show("warn", el("span", { className: "grow", textContent: "Cancelled." }));
      const again = el("button", { type: "button", className: "btn small", textContent: "Try again" });
      again.addEventListener("click", () => run(more));
      const message = timedOut ? "The AI took too long to respond. Please try again." : err.message;
      show("error", el("span", { className: "grow", textContent: message }), again);
    } finally {
      clearTimeout(timer);
      submit.disabled = !aiOn;
      moreBtn.disabled = false;
      api("/ai/status").then(showQuota).catch(() => {}); // the count may have changed
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); run(false); });
  moreBtn.addEventListener("click", () => run(true));

  addBtn.addEventListener("click", async () => {
    const boxes = selected();
    addBtn.disabled = true;
    let added = 0;
    const failed = [];
    for (const box of boxes) {
      const w = box.word;
      try {
        await api("/notebook/words", {
          method: "POST",
          body: JSON.stringify({
            word: w.word, meaning_vi: w.meaning_vi, ipa: w.ipa || null,
            part_of_speech: w.part_of_speech, definition_en: w.definition_en || null,
            examples: [w.example], topic_id: topicId, source: "ai",
          }),
        });
        added++;
      } catch (err) {
        failed.push(`${w.word}: ${err.message}`);
        continue;
      }
      box.checked = true;
      box.disabled = true;
      box.closest("li").classList.add("added");
    }
    if (added) toast(`Added ${added} word${added === 1 ? "" : "s"} to your notebook`);
    if (failed.length) show("error", el("span", { className: "grow", textContent: failed.join(" · ") }));
    updateAdd();
  });
}

// ---------- Write a sentence (AI grades it) ----------
// POST /api/ai/check-sentence {word_id, sentence}: the server looks the word up in my notebook.
const SENTENCE_VERDICTS = {
  correct: { icon: "✅", label: "Correct sentence" },
  minor_issues: { icon: "🟡", label: "Almost correct, with minor issues" },
  incorrect: { icon: "❌", label: "Incorrect sentence" },
};
const ERROR_TYPES = {
  grammar: "Grammar", word_usage: "Word usage", spelling: "Spelling",
  word_choice: "Word choice", punctuation: "Punctuation", missing_word: "Missing word",
};

async function sentencePage(params) {
  const root = mount("tpl-sentence");
  const body = $(root, "data-sentence-body");
  const form = $(root, "data-form");
  const select = $(root, "data-word-select");
  const card = $(root, "data-word-card");
  const panel = $(root, "data-ai-panel");
  const hint = $(root, "data-ai-hint");
  const submit = $(root, "data-submit");
  const result = $(root, "data-result");

  let words, status;
  try {
    [words, status] = await Promise.all([api("/notebook/words"), api("/ai/status").catch(() => null)]);
  } catch (err) {
    return showError(body, err);
  }
  if (!words.length) {
    return body.replaceChildren(el("p", { className: "card empty" }, "Your notebook is empty. ",
      el("a", { href: "#/notebook/new", textContent: "Add a word" }), " and come back to write a sentence."));
  }

  const sorted = [...words].sort((a, b) => a.word.localeCompare(b.word));
  select.replaceChildren(...sorted.map((w) =>
    el("option", { value: w.id, textContent: `${w.word} — ${w.meaning_vi}` })));
  const wanted = words.find((w) => String(w.id) === params.get("word"));
  select.value = String((wanted || words[0]).id);

  const quota = el("span");
  function showQuota(s) {
    quota.textContent = ` ${Math.max(0, s.limit_per_day - s.used_today)}/${s.limit_per_day} AI requests remaining today (graded sentences are free).`;
  }
  const aiOn = Boolean(status?.enabled);
  if (aiOn) {
    hint.append(quota);
    showQuota(status);
  } else {
    submit.disabled = true;
    submit.title = "AI is not enabled on the server (GEMINI_API_KEY is missing)";
    hint.textContent = "AI is not enabled on the server, so sentences cannot be graded.";
  }

  const current = () => words.find((w) => String(w.id) === select.value);
  function showWord() {
    const w = current();
    const sound = iconButton("speak", "Listen");
    sound.addEventListener("click", () => speak(w.word));
    const head = el("div", { className: "word-head nb" }, el("span", { className: "w", textContent: w.word, lang: "en" }));
    if (w.ipa) head.append(el("span", { className: "ipa", textContent: w.ipa }));
    head.append(posBadge(w.part_of_speech), sound);
    card.replaceChildren(head, el("div", { className: "meaning", textContent: w.meaning_vi, lang: "vi" }));
    if (w.examples[0]) card.append(el("p", { className: "ex", textContent: `Example: ${w.examples[0].en}`, lang: "en" }));
    form.sentence.placeholder = `Write an English sentence using "${w.word}"…`;
    history.replaceState(null, "", `#/notebook/sentence?word=${w.id}`);
  }
  function reset() {
    result.hidden = panel.hidden = true;
    form.sentence.value = "";
    form.sentence.focus();
  }

  select.addEventListener("change", () => { showWord(); reset(); });
  $(root, "data-random").addEventListener("click", () => {
    const others = words.filter((w) => String(w.id) !== select.value);
    if (!others.length) return;
    select.value = String(others[Math.floor(Math.random() * others.length)].id);
    showWord();
    reset();
  });
  form.sentence.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); form.requestSubmit(); }
  });

  function show(kind, ...children) {
    panel.className = `ai-panel ${kind}`;
    panel.replaceChildren(...children);
    panel.hidden = false;
  }

  function line(label, text) {
    const sound = iconButton("speak", "Listen to this sentence");
    sound.addEventListener("click", () => speak(text));
    return el("div", { className: "sentence-line" },
      el("span", { className: "chips-label", textContent: label }),
      el("span", { className: "ex", textContent: text, lang: "en" }), sound);
  }

  function renderResult(r, cached) {
    const v = SENTENCE_VERDICTS[r.verdict];
    const nodes = [
      el("p", { className: `verdict ${r.verdict}`, textContent: `${v.icon} ${v.label}` }),
      el("p", { className: "sentence-feedback", textContent: r.feedback_vi }),
    ];
    if (!r.uses_word) {
      nodes.push(el("p", { className: "ai-panel warn",
        textContent: `Your sentence does not use "${current().word}". Rewrite it using this word.` }));
    }
    if (r.errors.length) {
      nodes.push(el("ul", { className: "sentence-errors" }, ...r.errors.map((e) => el("li", {},
        el("div", {},
          el("span", { className: "chip", textContent: ERROR_TYPES[e.type] || e.type }),
          e.excerpt ? el("q", { className: "excerpt", textContent: e.excerpt, lang: "en" }) : ""),
        el("span", { textContent: e.explanation_vi, lang: "vi" })))));
    }
    if (r.verdict !== "correct") nodes.push(line("Corrected sentence", r.corrected));
    if (r.better_version) nodes.push(line("Better wording", r.better_version));
    const again = el("button", { type: "button", className: "btn", textContent: "Write another sentence" });
    again.addEventListener("click", reset);
    nodes.push(el("div", { className: "row end" },
      cached ? el("span", { className: "muted small", textContent: "Result from cache; no request used." }) : "",
      again));
    result.replaceChildren(...nodes);
    result.hidden = false;
    result.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!aiOn) return;
    const sentence = form.sentence.value.trim();
    if (sentence.length < 3) {
      form.sentence.focus();
      return show("warn", el("span", { className: "grow", textContent: "Please write an English sentence." }));
    }
    const controller = new AbortController();
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, AI_TIMEOUT_MS);
    const cancel = el("button", { type: "button", className: "btn small ghost", textContent: "Cancel" });
    cancel.addEventListener("click", () => controller.abort());
    show("", el("span", { className: "spinner", ariaHidden: "true" }),
      el("span", { className: "grow", textContent: "AI is grading your sentence… this usually takes a few seconds." }), cancel);
    result.hidden = true;
    submit.disabled = select.disabled = true;
    form.setAttribute("aria-busy", "true");
    try {
      const res = await api("/ai/check-sentence", {
        method: "POST",
        body: JSON.stringify({ word_id: Number(select.value), sentence }),
        signal: controller.signal,
      });
      panel.hidden = true;
      renderResult(res.result, res.cached);
    } catch (err) {
      if (err.name === "AbortError" && !timedOut) return show("warn", el("span", { className: "grow", textContent: "Cancelled." }));
      const again = el("button", { type: "button", className: "btn small", textContent: "Try again" });
      again.addEventListener("click", () => form.requestSubmit());
      const message = timedOut ? "The AI took too long to respond. Please try again." : err.message;
      show("error", el("span", { className: "grow", textContent: message }), again);
    } finally {
      clearTimeout(timer);
      submit.disabled = select.disabled = false;
      form.removeAttribute("aria-busy");
      api("/ai/status").then(showQuota).catch(() => {}); // the count may have changed
    }
  });

  showWord();
  form.sentence.focus();
}

// The form <-> the JSON of one notebook word. Lists are typed comma-separated.
function fillNotebookForm(form, w) {
  for (const k of ["word", "meaning_vi", "ipa", "part_of_speech", "definition_en", "usage_note", "topic_id"]) {
    if (w[k] !== undefined) form[k].value = w[k] ?? "";
  }
  for (const k of ["synonyms", "antonyms", "collocations"]) {
    if (w[k] !== undefined) form[k].value = (w[k] || []).join(", ");
  }
  if (w.examples !== undefined) {
    for (let i = 0; i < 2; i++) {
      form[`example_en_${i}`].value = w.examples[i]?.en ?? "";
      form[`example_vi_${i}`].value = w.examples[i]?.vi ?? "";
    }
  }
}

function readNotebookForm(form) {
  const val = (name) => form[name].value.trim();
  const examples = [0, 1]
    .map((i) => ({ en: val(`example_en_${i}`), vi: val(`example_vi_${i}`) || null }))
    .filter((ex) => ex.en);
  return {
    word: val("word"),
    meaning_vi: val("meaning_vi"),
    ipa: val("ipa") || null,
    part_of_speech: val("part_of_speech") || null,
    definition_en: val("definition_en") || null,
    examples,
    synonyms: splitList(val("synonyms")),
    antonyms: splitList(val("antonyms")),
    collocations: splitList(val("collocations")),
    usage_note: val("usage_note") || null,
    topic_id: val("topic_id") ? Number(val("topic_id")) : null,
  };
}

// ---------- Add / Edit ----------
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

// ---------- Practice ----------
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
  // "Random" = every word; otherwise only the chosen topic (empty topics are disabled).
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

  // Enter on the "Continue" button already clicks it; this covers focus elsewhere.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || card.hidden || !result || e.target.closest("button")) return;
    e.preventDefault();
    next();
  }, { signal: pageSignal() });

  render();
}

// ---------- Notebook quiz ----------
async function quizPage() {
  const root = mount("tpl-quiz");
  const start = $(root, "data-quiz-start");
  const count = $(root, "data-quiz-count");
  const area = $(root, "data-quiz-area");
  let quiz;
  let busy = false;

  start.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (busy) return;
    busy = true;
    const button = start.querySelector("button");
    button.disabled = true;
    area.replaceChildren();
    try {
      quiz = await api("/quiz", {
        method: "POST",
        body: JSON.stringify({ count: Number(count.value) }),
      });
      renderQuiz();
    } catch (err) {
      area.replaceChildren(el("p", { className: "error", textContent: err.message }));
    } finally {
      busy = false;
      button.disabled = false;
    }
  });

  function renderQuiz() {
    const form = el("form", { className: "quiz-form card" });
    form.append(el("p", {
      className: "muted",
      textContent: `${quiz.questions.length} questions · Answers will be graded after submission.`,
    }));
    for (const question of quiz.questions) {
      const field = el("fieldset", { className: "quiz-question" });
      field.append(el("legend", {
        textContent: `${question.id}. ${question.prompt}`,
      }));
      if (question.choices) {
        for (const choice of question.choices) {
          const input = el("input", {
            type: "radio", name: `q-${question.id}`, value: choice, required: true,
          });
          field.append(el("label", { className: "quiz-option" }, input, ` ${choice}`));
        }
      } else {
        field.append(el("input", {
          type: "text", name: `q-${question.id}`, required: true, maxLength: 300,
          autocomplete: "off", placeholder: "Enter your answer...",
        }));
      }
      form.append(field);
    }
    form.append(el("button", { className: "btn primary", type: "submit", textContent: "Submit quiz" }));
    form.addEventListener("submit", submitQuiz);
    area.replaceChildren(form);
  }

  async function submitQuiz(event) {
    event.preventDefault();
    if (busy) return;
    busy = true;
    const form = event.currentTarget;
    const button = form.querySelector("button[type=submit]");
    button.disabled = true;
    const answers = quiz.questions.map((question) => {
      const selected = form.querySelector(`[name="q-${question.id}"]:checked`)
        || form.querySelector(`[name="q-${question.id}"]`);
      return { question_id: question.id, answer: selected.value.trim() };
    });
    try {
      const result = await api(`/quiz/${quiz.quiz_id}/submit`, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      const report = el("div", { className: "card quiz-results" });
      report.append(
        el("h2", { textContent: `Result: ${result.score}/${result.total}` }),
      );
      for (const question of result.questions) {
        report.append(el("article", {
          className: `quiz-result ${question.correct ? "ok" : "bad"}`,
        },
        el("strong", { textContent: `${question.id}. ${question.prompt}` }),
        el("p", { textContent: question.correct
          ? `Correct: ${question.expected}`
          : `Your answer: ${question.answer || "—"} · Correct answer: ${question.expected}` })));
      }
      report.append(el("button", {
        className: "btn primary", type: "button", textContent: "Start a new quiz",
      }));
      report.lastChild.addEventListener("click", () => start.requestSubmit());
      area.replaceChildren(report);
    } catch (err) {
      toast(err.message);
      button.disabled = false;
    } finally {
      busy = false;
    }
  }
}

// ---------- Spaced review ----------
async function srsPage() {
  const root = mount("tpl-srs");
  const card = $(root, "data-srs-card");
  const count = $(root, "data-srs-count");
  let cards;
  try {
    ({ cards } = await api("/srs/today"));
  } catch (err) {
    return showError(card, err);
  }
  let index = 0;

  function render() {
    count.textContent = `${Math.max(0, cards.length - index)} words to review`;
    if (index >= cards.length) {
      card.replaceChildren(el("div", { className: "card empty" },
        el("p", { textContent: "You have reviewed all words due today. Great job!" }),
        el("a", { className: "btn", href: "#/notebook", textContent: "Back to my notebook" })));
      return;
    }
    const word = cards[index];
    const panel = el("article", { className: "card srs-card" },
      el("p", { className: "muted", textContent: `Word ${index + 1}/${cards.length}` }),
      el("h2", { className: "flash-word", textContent: word.word }));
    if (word.part_of_speech) {
      panel.append(el("span", { className: "badge", textContent: word.part_of_speech }));
    }
    const reveal = el("button", {
      className: "btn primary", type: "button", textContent: "Show meaning",
    });
    const answer = el("div", { className: "srs-answer", hidden: true },
      el("h3", { textContent: word.meaning_vi, lang: "vi" }));
    if (word.definition_en) {
      answer.append(el("p", { className: "muted", textContent: word.definition_en }));
    }
    for (const example of word.examples || []) {
      answer.append(el("p", { className: "example", textContent: example.en }));
    }
    const feedback = el("p", { className: "muted", role: "status" });
    const ratings = el("div", { className: "srs-ratings", hidden: true });
    const labels = ["Forgot", "Very hard", "Hard", "Somewhat", "Remembered", "Easy"];
    labels.forEach((label, quality) => {
      const button = el("button", {
        className: "btn small", type: "button", textContent: `${label} (${quality})`,
      });
      button.addEventListener("click", () => rate(quality, button));
      ratings.append(button);
    });
    reveal.addEventListener("click", () => {
      answer.hidden = false;
      ratings.hidden = false;
      reveal.hidden = true;
    });
    panel.append(reveal, answer, ratings, feedback);
    card.replaceChildren(panel);

    async function rate(quality, button) {
      if (button.disabled) return;
      ratings.querySelectorAll("button").forEach((item) => { item.disabled = true; });
      try {
        const scheduled = await api(`/srs/words/${word.id}/review`, {
          method: "POST",
          body: JSON.stringify({ quality }),
        });
        const dueDate = new Date(`${scheduled.next_review}T00:00:00+07:00`);
        feedback.textContent =
          `Saved · level ${scheduled.level}/5 · review on ${dueDate.toLocaleDateString("en-US")}`;
        if (quality < 3) {
          feedback.textContent += " · Creating a memory tip...";
          try {
            const tip = await api(`/srs/words/${word.id}/mnemonic`, { method: "POST" });
            feedback.textContent += ` ${tip.mnemonic}`;
          } catch (err) {
            feedback.textContent = `Review schedule saved, but the memory tip could not be created: ${err.message}`;
          }
        }
        index++;
        const next = el("button", {
          className: "btn primary", type: "button", textContent: "Next word",
        });
        next.addEventListener("click", render);
        panel.append(next);
      } catch (err) {
        feedback.textContent = err.message;
        ratings.querySelectorAll("button").forEach((item) => { item.disabled = false; });
      }
    }
  }

  render();
}

// ---------- Progress ----------
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
  setupImport(root, () => adminPage(params));

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

// CSV import: the file is checked first (dry run, nothing saved), the admin reads the
// summary and the first rows, then confirms. A file with errors cannot be saved.
function setupImport(root, onImported) {
  const panel = $(root, "data-import");
  const file = $(root, "data-import-file");
  const update = $(root, "data-import-update");
  const result = $(root, "data-import-result");
  const save = $(root, "data-import-save");
  let text = "";

  $(root, "data-import-open").addEventListener("click", () => { panel.hidden = false; file.focus(); });
  $(root, "data-import-close").addEventListener("click", () => { panel.hidden = true; });

  async function preview() {
    if (!text) return;
    result.hidden = true;
    let r;
    try {
      r = await api("/admin/import", {
        method: "POST",
        body: JSON.stringify({ csv: text, update_existing: update.checked, dry_run: true }),
      });
    } catch (err) {
      return toast(err.message);
    }
    const existingWord = update.checked ? "will be updated" : "already in the bank, will be skipped";
    $(root, "data-import-summary").replaceChildren(
      el("strong", { textContent: `${r.total} valid rows` }),
      ` · ${r.new} new · ${r.existing} ${existingWord}`,
      r.errors.length ? el("span", { className: "bad", textContent: ` · ${r.errors.length} with errors` }) : "",
    );
    $(root, "data-import-errors").replaceChildren(...r.errors.slice(0, 20).map((e) =>
      el("li", {}, el("strong", { textContent: `Line ${e.line}: ` }), e.message)));
    $(root, "data-import-sample").replaceChildren(...r.sample.map((w) => {
      const topic = topicById(w.topic_id);
      return el("tr", {},
        el("td", {}, el("strong", { textContent: w.word }), " ", posBadge(w.part_of_speech)),
        el("td", { textContent: w.meaning_vi }),
        el("td", { className: "nowrap", textContent: topic ? `${topic.icon} ${topic.name}` : "—" }),
        el("td", { className: w.exists ? "muted" : "", textContent: w.exists ? (update.checked ? "Update" : "Skip") : "New" }));
    }));
    const count = r.new + (update.checked ? r.existing : 0);
    save.disabled = r.errors.length > 0 || count === 0;
    save.textContent = r.errors.length ? "Fix the errors in the file first"
      : count ? `Import ${count} word${count === 1 ? "" : "s"}` : "Nothing new to import";
    result.hidden = false;
  }

  file.addEventListener("change", async () => {
    text = file.files[0] ? await file.files[0].text() : "";
    preview();
  });
  update.addEventListener("change", preview);
  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      const r = await api("/admin/import", {
        method: "POST",
        body: JSON.stringify({ csv: text, update_existing: update.checked, dry_run: false }),
      });
      toast(`Imported: ${r.new} new` + (update.checked ? `, ${r.existing} updated` : ""));
      topicsCache = null; // word counts per topic changed
      onImported();
    } catch (err) {
      toast(err.message);
      save.disabled = false;
    }
  });
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
  const editMine = path.match(/^\/notebook\/edit\/(\d+)$/);
  if (path === "/admin") { page = "admin"; adminPage(params); }
  else if (path === "/admin/new") { page = "admin"; formPage(null); }
  else if (edit) { page = "admin"; formPage(Number(edit[1])); }
  else if (path === "/notebook") { page = "notebook"; notebookPage(params); }
  else if (path === "/notebook/new") { page = "notebook"; notebookFormPage(null); }
  else if (path === "/notebook/sentence") { page = "notebook"; sentencePage(params); }
  else if (path === "/notebook/suggest") { page = "notebook"; suggestPage(params); }
  else if (path === "/notebook/chat") { page = "notebook"; chatPage(); }
  else if (editMine) { page = "notebook"; notebookFormPage(Number(editMine[1])); }
  else if (path === "/progress") { page = "progress"; progressPage(); }
  else if (path === "/quiz") { page = "quiz"; quizPage(); }
  else if (path === "/srs") { page = "srs"; srsPage(); }
  else if (path === "/review") { page = "review"; reviewPage(params.get("topic")); }
  else listPage(params);
  for (const a of document.querySelectorAll("[data-nav]")) {
    a.classList.toggle("active", a.dataset.nav === page);
  }
  // On phones the menu scrolls sideways: keep the current page's link in view.
  const nav = document.querySelector("[data-nav-links]");
  const active = nav.querySelector("a.active");
  if (active && nav.scrollWidth > nav.clientWidth) {
    const left = active.offsetLeft - nav.offsetLeft; // both measured from the sticky topbar
    nav.scrollLeft = left - (nav.clientWidth - active.offsetWidth) / 2;
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", route);
route();
