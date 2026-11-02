const COLUMNS = [
  ["faction", "阵营"],
  ["troop", "兵种"],
  ["tacticType", "战法类型"],
  ["topStat", "最高属性"],
  ["bondCount", "缘分数量"],
  ["season", "登场赛季"],
  ["sex", "性别"],
  ["role", "武将类型"],
];

const lobby = document.querySelector("#lobby");
const tiers = document.querySelector("#tiers");
const play = document.querySelector("#play");
const boardHead = document.querySelector("#boardHead");
const board = document.querySelector("#board");
const statusText = document.querySelector("#status");
const form = document.querySelector("#guessForm");
const input = document.querySelector("#guessInput");
const suggestions = document.querySelector("#suggestions");
const submitGuess = document.querySelector("#submitGuess");
const giveUp = document.querySelector("#giveUp");
const back = document.querySelector("#back");
const nameInput = document.querySelector("#displayName");
const dateText = document.querySelector("#dateText");

const guest = (() => {
  const key = "sanmou-guest";
  let id = localStorage.getItem(key);
  if (!id || !/^[A-Za-z0-9-]{8,64}$/.test(id)) {
    id = crypto.randomUUID();
    localStorage.setItem(key, id);
  }
  return id;
})();

let heroes = [];
let overview = null;
let game = null;
let tier = "";
let chosen = "";
let busy = false;

boardHead.innerHTML = GameUI.head(COLUMNS);
nameInput.value = localStorage.getItem("sanmou-name") || "";

function displayName() {
  return nameInput.value.trim().slice(0, 12);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-Guest-Id": guest, ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));
  return { response, payload };
}

function post(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...body, displayName: displayName() }),
  });
}

function statusLabel(item) {
  if (item.status === "playing") return item.guessCount ? `继续 · 已猜 ${item.guessCount}` : "继续";
  if (item.status === "won") return `已猜中 · ${item.guessCount} 次`;
  if (item.status === "lost") return "今天未猜中";
  return "开始";
}

function renderLobby() {
  dateText.textContent = `${overview.date} · 上海时间每天 0 点换题`;
  tiers.innerHTML = overview.tiers.map((item) => {
    const scores = overview.leaderboards[item.key] || [];
    const rows = scores.length
      ? scores.map((score, index) =>
        `<li><span>${index + 1}. ${GameUI.escapeHtml(score.displayName)}</span><span>${score.guessCount} 次</span></li>`
      ).join("")
      : `<li><span>今天还没有人通关</span><span></span></li>`;
    return `<article class="tier-card">
      <p class="eyebrow">${GameUI.escapeHtml(item.detail)} · ${item.pool} 人</p>
      <h2>${GameUI.escapeHtml(item.label)}</h2>
      <button type="button" class="primary" data-tier="${item.key}">${statusLabel(item)}</button>
      <ol class="scores">${rows}</ol>
    </article>`;
  }).join("");
}

function renderBoard() {
  const guesses = game?.guesses || [];
  board.innerHTML = guesses.map((guess) => GameUI.renderRow(COLUMNS, guess)).join("");
  const finished = game && game.status !== "playing";
  submitGuess.disabled = finished || busy;
  giveUp.disabled = finished || busy;
  input.disabled = finished || busy;
  if (!game) return;
  if (game.status === "playing") {
    statusText.className = "status";
    statusText.textContent = `已猜 ${guesses.length} / ${game.maxGuesses}`;
    return;
  }
  const answer = game.answer;
  statusText.className = `status ${game.status}`;
  statusText.textContent = game.status === "won"
    ? `猜中了 ${answer.name} · ${answer.skill}`
    : `答案是 ${answer.name} · ${answer.skill}`;
  if (answer && !guesses.some((item) => item.name === answer.name)) {
    board.insertAdjacentHTML("beforeend", GameUI.renderRow(COLUMNS, answer));
  }
}

function showSuggestions(query) {
  const text = query.trim().toLowerCase();
  if (!text) {
    suggestions.hidden = true;
    suggestions.innerHTML = "";
    return;
  }
  const used = new Set((game?.guesses || []).map((item) => item.name));
  const matched = heroes.filter((hero) => {
    if (used.has(hero.name)) return false;
    return `${hero.name} ${hero.skill}`.toLowerCase().includes(text);
  }).slice(0, 8);
  suggestions.hidden = matched.length === 0;
  suggestions.innerHTML = matched.map((hero) =>
    `<button type="button" data-name="${GameUI.escapeHtml(hero.name)}">${GameUI.escapeHtml(hero.name)}<em>${GameUI.escapeHtml(hero.skill)}</em></button>`
  ).join("");
}

async function loadLobby() {
  const { response, payload } = await api("/api/daily");
  if (!response.ok) {
    dateText.textContent = "今日题目没有载入";
    return;
  }
  overview = payload;
  renderLobby();
}

async function enter(nextTier) {
  if (busy) return;
  busy = true;
  const { response, payload } = await post(`/api/daily/${nextTier}/start`, {});
  busy = false;
  if (!response.ok) {
    dateText.textContent = GameUI.errorText(payload.code);
    return;
  }
  tier = nextTier;
  game = payload;
  chosen = "";
  input.value = "";
  suggestions.hidden = true;
  lobby.hidden = true;
  play.hidden = false;
  location.hash = nextTier;
  renderBoard();
  if (game.status === "playing") input.focus();
}

async function submitName(name) {
  if (!game || game.status !== "playing" || !name || busy) return;
  busy = true;
  const { response, payload } = await post(`/api/daily/${tier}/guess`, { name });
  busy = false;
  if (!response.ok) {
    statusText.textContent = GameUI.errorText(payload.code);
    return;
  }
  game = payload;
  input.value = "";
  chosen = "";
  suggestions.hidden = true;
  renderBoard();
}

tiers.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-tier]");
  if (!button) return;
  enter(button.dataset.tier);
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  submitName(chosen || input.value.trim());
});

input.addEventListener("input", () => {
  chosen = "";
  showSuggestions(input.value);
});

suggestions.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  chosen = button.dataset.name;
  input.value = chosen;
  suggestions.hidden = true;
});

nameInput.addEventListener("input", () => {
  localStorage.setItem("sanmou-name", displayName());
});

giveUp.addEventListener("click", async () => {
  if (!game || game.status !== "playing" || busy) return;
  busy = true;
  const { response, payload } = await post(`/api/daily/${tier}/giveup`, {});
  busy = false;
  if (!response.ok) {
    statusText.textContent = GameUI.errorText(payload.code);
    return;
  }
  game = payload;
  renderBoard();
});

back.addEventListener("click", async () => {
  play.hidden = true;
  lobby.hidden = false;
  history.replaceState(null, "", location.pathname);
  await loadLobby();
});

async function boot() {
  const heroResponse = await fetch("/api/heroes");
  heroes = (await heroResponse.json()).heroes;
  await loadLobby();
  const opening = location.hash.replace("#", "");
  if (["easy", "normal", "all"].includes(opening)) await enter(opening);
}

boot();
