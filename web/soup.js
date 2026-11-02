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

const fields = document.querySelector("#fields");
const log = document.querySelector("#log");
const boardHead = document.querySelector("#boardHead");
const board = document.querySelector("#board");
const answerWrap = document.querySelector("#answerWrap");
const statusText = document.querySelector("#status");
const form = document.querySelector("#guessForm");
const input = document.querySelector("#guessInput");
const suggestions = document.querySelector("#suggestions");
const submitGuess = document.querySelector("#submitGuess");
const giveUp = document.querySelector("#giveUp");
const restart = document.querySelector("#restart");

let heroes = [];
let options = null;
let game = null;
let chosen = "";
let busy = false;

boardHead.innerHTML = GameUI.head(COLUMNS);

function asked() {
  const found = new Map();
  for (const event of game?.events || []) {
    if (event.type === "question") found.set(`${event.field}:${event.value}`, event);
  }
  return found;
}

function render() {
  const used = asked();
  const finished = game && game.status !== "playing";
  fields.innerHTML = (options?.fields || []).map((field) => {
    const chips = field.values.map((value) => {
      const event = used.get(`${field.key}:${value}`);
      const level = event ? event.level : "";
      const hint = event ? GameUI.hintMark(event.hint) : "";
      return `<button type="button" class="chip ${level}" data-field="${GameUI.escapeHtml(field.key)}" data-value="${GameUI.escapeHtml(value)}" ${event || finished || busy ? "disabled" : ""}>${GameUI.escapeHtml(value)}${hint ? `<span class="hint">${hint}</span>` : ""}</button>`;
    }).join("");
    return `<section class="field-group"><h3>${GameUI.escapeHtml(field.label)}</h3><div class="chips">${chips}</div></section>`;
  }).join("");

  log.innerHTML = (game?.events || []).map((event) => {
    if (event.type === "guess") {
      const level = event.correct ? "correct" : "wrong";
      const verdict = event.correct ? "是" : "不是";
      return `<li class="${level}">点名 ${GameUI.escapeHtml(event.name)} · ${verdict}</li>`;
    }
    const hint = GameUI.hintMark(event.hint);
    return `<li class="${event.level}">${GameUI.escapeHtml(event.label)} · ${GameUI.escapeHtml(event.value)}${hint ? ` ${hint}` : ""}</li>`;
  }).join("");

  const playing = game && game.status === "playing";
  submitGuess.disabled = !playing || busy;
  giveUp.disabled = !playing || busy;
  input.disabled = !playing || busy;
  if (!game) {
    statusText.textContent = "";
    answerWrap.hidden = true;
    return;
  }
  statusText.className = `status ${game.status === "playing" ? "" : game.status}`.trim();
  if (game.status === "playing") {
    statusText.textContent = `已用 ${game.used} / ${game.maxAttempts}`;
    answerWrap.hidden = true;
    board.innerHTML = "";
    return;
  }
  const answer = game.answer;
  const exhausted = game.used >= game.maxAttempts;
  statusText.textContent = game.status === "won"
    ? `猜中了 ${answer.name} · ${answer.skill}`
    : exhausted
      ? `次数用完了。答案是 ${answer.name} · ${answer.skill}`
      : `答案是 ${answer.name} · ${answer.skill}`;
  answerWrap.hidden = false;
  board.innerHTML = GameUI.renderRow(COLUMNS, answer);
}

function showSuggestions(query) {
  const text = query.trim().toLowerCase();
  if (!text) {
    suggestions.hidden = true;
    suggestions.innerHTML = "";
    return;
  }
  const used = new Set((game?.events || []).filter((event) => event.type === "guess").map((event) => event.name));
  const matched = heroes.filter((hero) => !used.has(hero.name) && `${hero.name} ${hero.skill}`.toLowerCase().includes(text)).slice(0, 8);
  suggestions.hidden = matched.length === 0;
  suggestions.innerHTML = matched.map((hero) =>
    `<button type="button" data-name="${GameUI.escapeHtml(hero.name)}">${GameUI.escapeHtml(hero.name)}<em>${GameUI.escapeHtml(hero.skill)}</em></button>`
  ).join("");
}

async function startGame() {
  const response = await fetch("/api/soup-games", { method: "POST" });
  game = await response.json();
  chosen = "";
  input.value = "";
  suggestions.hidden = true;
  render();
}

async function ask(field, value) {
  if (!game || game.status !== "playing" || busy) return;
  busy = true;
  render();
  const response = await fetch(`/api/soup-games/${game.gameId}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ field, value }),
  });
  const payload = await response.json();
  busy = false;
  if (!response.ok) {
    statusText.textContent = GameUI.errorText(payload.code);
    render();
    return;
  }
  game = payload;
  render();
}

async function submitName(name) {
  if (!game || game.status !== "playing" || !name || busy) return;
  busy = true;
  const response = await fetch(`/api/soup-games/${game.gameId}/guess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const payload = await response.json();
  busy = false;
  if (!response.ok) {
    statusText.textContent = GameUI.errorText(payload.code);
    return;
  }
  game = payload;
  input.value = "";
  chosen = "";
  suggestions.hidden = true;
  render();
}

fields.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-field]");
  if (!button || button.disabled) return;
  ask(button.dataset.field, button.dataset.value);
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

giveUp.addEventListener("click", async () => {
  if (!game || game.status !== "playing") return;
  const response = await fetch(`/api/soup-games/${game.gameId}/giveup`, { method: "POST" });
  game = await response.json();
  render();
});

restart.addEventListener("click", startGame);

async function boot() {
  const [heroResponse, optionResponse] = await Promise.all([
    fetch("/api/heroes"),
    fetch("/api/soup/options"),
  ]);
  heroes = (await heroResponse.json()).heroes;
  options = await optionResponse.json();
  await startGame();
}

boot();
