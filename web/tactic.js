const COLUMNS = [
  ["quality", "品质"],
  ["tacticType", "类型"],
  ["effect", "效果"],
  ["season", "赛季"],
  ["rate", "发动率"],
];

const boardHead = document.querySelector("#boardHead");
const board = document.querySelector("#board");
const detail = document.querySelector("#detail");
const statusText = document.querySelector("#status");
const form = document.querySelector("#guessForm");
const input = document.querySelector("#guessInput");
const suggestions = document.querySelector("#suggestions");
const submitGuess = document.querySelector("#submitGuess");
const giveUp = document.querySelector("#giveUp");
const restart = document.querySelector("#restart");

let tactics = [];
let game = null;
let chosen = "";

boardHead.innerHTML = GameUI.head(COLUMNS);

function render() {
  const guesses = game?.guesses || [];
  board.innerHTML = guesses.map((guess) => GameUI.renderRow(COLUMNS, guess)).join("");
  const finished = game && game.status !== "playing";
  submitGuess.disabled = finished;
  giveUp.disabled = finished;
  input.disabled = finished;
  detail.hidden = !(game && game.answer && game.answer.description);
  detail.textContent = game?.answer?.description || "";
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
  statusText.textContent = game.status === "won" ? `猜中了 ${answer.name}` : `答案是 ${answer.name}`;
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
  const matched = tactics.filter((tactic) => !used.has(tactic.name) && tactic.name.toLowerCase().includes(text)).slice(0, 8);
  suggestions.hidden = matched.length === 0;
  suggestions.innerHTML = matched.map((tactic) =>
    `<button type="button" data-name="${GameUI.escapeHtml(tactic.name)}">${GameUI.escapeHtml(tactic.name)}</button>`
  ).join("");
}

async function startGame() {
  const response = await fetch("/api/tactic-games", { method: "POST" });
  game = await response.json();
  chosen = "";
  input.value = "";
  suggestions.hidden = true;
  render();
  input.focus();
}

async function submitName(name) {
  if (!game || game.status !== "playing" || !name) return;
  const response = await fetch(`/api/tactic-games/${game.gameId}/guess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const payload = await response.json();
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
  const response = await fetch(`/api/tactic-games/${game.gameId}/giveup`, { method: "POST" });
  game = await response.json();
  render();
});

restart.addEventListener("click", startGame);

async function boot() {
  const response = await fetch("/api/tactics");
  tactics = (await response.json()).tactics;
  await startGame();
}

boot();
