(function () {
  function escapeHtml(text) {
    return String(text ?? "").replace(/[&<>"']/g, (ch) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[ch]));
  }

  function avatarUrl(file) {
    return `/figures/${encodeURIComponent(file)}`;
  }

  function hintMark(hint) {
    if (hint === "higher") return "↑";
    if (hint === "lower") return "↓";
    return "";
  }

  function renderRow(columns, guess) {
    const cells = columns.map(([key]) => {
      const cell = guess.cells[key];
      const level = ["correct", "close", "wrong"].includes(cell.level) ? cell.level : "wrong";
      const hint = hintMark(cell.hint);
      return `<div class="cell ${level}">${escapeHtml(cell.value)}${hint ? `<span class="hint">${hint}</span>` : ""}</div>`;
    }).join("");
    const skill = guess.skill ? `<em>${escapeHtml(guess.skill)}</em>` : "";
    return `<article class="guess-row">
      <div class="who">
        <img alt="" src="${avatarUrl(guess.avatar)}">
        <div><strong>${escapeHtml(guess.name)}</strong>${skill}</div>
      </div>
      ${cells}
    </article>`;
  }

  function head(columns) {
    return `<span></span>${columns.map(([, label]) => `<span>${escapeHtml(label)}</span>`).join("")}`;
  }

  const errors = {
    ALREADY_GUESSED: "已经猜过",
    ALREADY_ASKED: "这个问题问过了",
    HERO_NOT_FOUND: "请从列表里选择武将",
    TACTIC_NOT_FOUND: "请从列表里选择战法",
    GAME_FINISHED: "这一局已经结束",
    BAD_QUESTION: "这个问题不能这么问",
    GUEST_REQUIRED: "浏览器没有访客标识",
    GAME_NOT_FOUND: "还没有开始这一档",
  };

  window.GameUI = {
    escapeHtml,
    avatarUrl,
    hintMark,
    renderRow,
    head,
    errorText(code) {
      return errors[code] || "没有完成，请再试一次";
    },
  };
})();
