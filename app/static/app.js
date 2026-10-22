// app.js — hash router + pages for the Vocabulary Notebook UI.
//   #/            list (search, edit, delete)
//   #/new         add a word
//   #/edit/{id}   edit a word
//   #/review      flashcard review, logs remembered / forgot
// Everything goes through the JSON API under /api (app/routes.py).
"use strict";

const view = document.getElementById("view");

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

function mount(templateId) {
  view.replaceChildren(document.getElementById(templateId).content.cloneNode(true));
  return view;
}

const $ = (root, attr) => root.querySelector(`[${attr}]`);

let toastTimer;
function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 2500);
}

function showError(root, err) {
  root.replaceChildren(Object.assign(document.createElement("p"), {
    className: "card empty", textContent: err.message,
  }));
}

// ---------- Danh sách ----------
async function listPage(query = "") {
  const root = mount("tpl-list");
  const form = $(root, "data-search");
  const list = $(root, "data-words");
  const count = $(root, "data-count");
  form.q.value = query;
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = form.q.value.trim();
    location.hash = q ? "#/?q=" + encodeURIComponent(q) : "#/";
  });

  let words;
  try {
    words = await api("/words" + (query ? "?q=" + encodeURIComponent(query) : ""));
  } catch (err) {
    return showError(list, err);
  }
  count.textContent = query ? `${words.length} kết quả cho "${query}"` : `${words.length} từ`;
  if (words.length === 0) {
    list.innerHTML = `<li class="card empty">${query ? "Không tìm thấy từ nào." : "Chưa có từ nào. Hãy thêm từ đầu tiên!"}</li>`;
    return;
  }
  for (const w of words) list.append(wordItem(w));
}

function wordItem(w) {
  const li = document.createElement("li");
  li.className = "card word-item";
  const info = document.createElement("div");
  const head = document.createElement("div");
  head.append(
    Object.assign(document.createElement("span"), { className: "w", textContent: w.word }),
    Object.assign(document.createElement("span"), { className: "pos", textContent: w.part_of_speech || "" }),
  );
  info.append(head, Object.assign(document.createElement("div"), { textContent: w.meaning_vi }));
  if (w.example) {
    info.append(Object.assign(document.createElement("p"), { className: "ex", textContent: w.example }));
  }

  const actions = document.createElement("div");
  actions.className = "actions";
  const edit = Object.assign(document.createElement("a"), {
    className: "btn small", href: `#/edit/${w.id}`, textContent: "Sửa",
  });
  const del = Object.assign(document.createElement("button"), {
    className: "btn small danger", textContent: "Xoá",
  });
  del.addEventListener("click", async () => {
    if (!confirm(`Xoá từ "${w.word}"? Lịch sử ôn tập của từ này cũng bị xoá.`)) return;
    try {
      await api(`/words/${w.id}`, { method: "DELETE" });
      li.remove();
      toast(`Đã xoá "${w.word}"`);
    } catch (err) {
      toast(err.message);
    }
  });
  actions.append(edit, del);
  li.append(info, actions);
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

async function reviewPage() {
  const root = mount("tpl-review");
  const card = $(root, "data-card");
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

  let i = 0;
  const score = { remembered: 0, forgot: 0 };
  const answer = $(root, "data-answer");
  const showBox = $(root, "data-actions-show");
  const gradeBox = $(root, "data-actions-grade");

  function render() {
    const w = words[i];
    $(root, "data-progress").textContent = `Thẻ ${i + 1} / ${words.length}`;
    $(root, "data-pos").textContent = w.part_of_speech || "";
    $(root, "data-word").textContent = w.word;
    $(root, "data-meaning").textContent = w.meaning_vi;
    $(root, "data-example").textContent = w.example || "";
    $(root, "data-note").textContent = w.usage_note || "";
    answer.hidden = true;
    showBox.hidden = false;
    gradeBox.hidden = true;
  }

  $(root, "data-show").addEventListener("click", () => {
    answer.hidden = false;
    showBox.hidden = true;
    gradeBox.hidden = false;
  });

  for (const btn of root.querySelectorAll("[data-grade]")) {
    btn.addEventListener("click", async () => {
      const result = btn.dataset.grade;
      btn.disabled = true;
      try {
        await api(`/words/${words[i].id}/reviews`, {
          method: "POST",
          body: JSON.stringify({ result }),
        });
      } catch (err) {
        toast(err.message);
        return;
      } finally {
        btn.disabled = false;
      }
      score[result]++;
      i++;
      if (i < words.length) return render();
      card.hidden = true;
      $(root, "data-progress").textContent = "";
      $(root, "data-done").hidden = false;
      $(root, "data-summary").textContent = `Nhớ: ${score.remembered} · Quên: ${score.forgot}`;
    });
  }
  $(root, "data-again").addEventListener("click", () => reviewPage());
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
}

window.addEventListener("hashchange", route);
route();
