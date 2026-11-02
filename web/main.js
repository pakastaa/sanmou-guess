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

const boardHead = document.querySelector("#boardHead");
const board = document.querySelector("#board");
const statusText = document.querySelector("#status");
const form = document.querySelector("#guessForm");
const input = document.querySelector("#guessInput");
const suggestions = document.querySelector("#suggestions");
const submitGuess = document.querySelector("#submitGuess");
const giveUp = document.querySelector("#giveUp");
const restart = document.querySelector("#restart");

let heroes = [];
let game = null;
let chosen = "";

boardHead.innerHTML = GameUI.head(COLUMNS);

function renderGuess(guess) {
  return GameUI.renderRow(COLUMNS, guess);
}

function render() {
  const guesses = game?.guesses || [];
  board.innerHTML = guesses.map(renderGuess).join("");
  const finished = game && game.status !== "playing";
  submitGuess.disabled = finished;
  giveUp.disabled = finished;
  input.disabled = finished;
  if (!game) {
    statusText.textContent = "";
    statusText.className = "status";
    return;
  }
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
    board.insertAdjacentHTML("beforeend", renderGuess({ ...answer, correct: true }));
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
    const blob = `${hero.name} ${hero.skill}`.toLowerCase();
    return blob.includes(text);
  }).slice(0, 8);
  suggestions.hidden = matched.length === 0;
  suggestions.innerHTML = matched.map((hero) =>
    `<button type="button" data-name="${GameUI.escapeHtml(hero.name)}">${GameUI.escapeHtml(hero.name)}<em>${GameUI.escapeHtml(hero.skill)}</em></button>`
  ).join("");
}

async function startGame() {
  const response = await fetch("/api/games", { method: "POST" });
  game = await response.json();
  chosen = "";
  input.value = "";
  suggestions.hidden = true;
  render();
  input.focus();
}

async function submitName(name) {
  if (!game || game.status !== "playing" || !name) return;
  const response = await fetch(`/api/games/${game.gameId}/guess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const payload = await response.json();
  if (!response.ok) {
    statusText.textContent = payload.code === "ALREADY_GUESSED" ? "这名武将已经猜过" : "请从橙将列表里选择";
    return;
  }
  game = payload;
  input.value = "";
  chosen = "";
  suggestions.hidden = true;
  render();
}

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
  const response = await fetch(`/api/games/${game.gameId}/giveup`, { method: "POST" });
  game = await response.json();
  render();
});

restart.addEventListener("click", startGame);

async function boot() {
  const heroResponse = await fetch("/api/heroes");
  heroes = (await heroResponse.json()).heroes;
  await startGame();
}

boot();
