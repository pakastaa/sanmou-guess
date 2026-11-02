# -*- coding: utf-8 -*-
"""猜一猜页面。答案只留在服务端，每日进度写在 data/runtime。"""
from __future__ import annotations

import copy
import json
import os
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from guess_core import (
    DAILY_TIERS,
    MAX_GUESSES,
    MAX_SOUP,
    assign_daily,
    compare_guess,
    compare_soup_field,
    compare_tactic,
    daily_pool,
    hero_answer,
    load_heroes,
    load_tactics,
    next_refresh_at,
    pick_target,
    public_hero,
    public_tactic,
    shanghai_now,
    shanghai_today,
    soup_options,
    tactic_answer,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
FIGURES = ROOT / "data" / "figure"
RUNTIME = ROOT / "data" / "runtime"
DAILY_PATH = RUNTIME / "daily.json"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8770"))
GUEST_RE = re.compile(r"[A-Za-z0-9-]{8,64}")
GAME_RE = re.compile(r"[a-f0-9]{32}")
TIER_KEYS = {tier for tier, _label, _detail in DAILY_TIERS}
TIER_META = {tier: (label, detail) for tier, label, detail in DAILY_TIERS}

HEROES = load_heroes()
TACTICS = load_tactics()
BY_NAME = {hero["name"]: hero for hero in HEROES}
TACTIC_BY_NAME = {tactic["name"]: tactic for tactic in TACTICS}
SOUP = soup_options(HEROES)
SOUP_LABELS = {field["key"]: field["label"] for field in SOUP["fields"]}
SOUP_VALUES = {
    field["key"]: set(field["values"])
    for field in SOUP["fields"]
}
GAMES: dict[str, dict] = {}
LOCK = threading.Lock()


def clean_name(raw: object) -> str:
    text = "".join(ch for ch in str(raw or "").strip() if ch.isprintable())
    text = text[:12].strip()
    return text or "访客"


def load_daily() -> dict:
    if not DAILY_PATH.exists():
        return {"assignments": {}, "attempts": {}}
    try:
        data = json.loads(DAILY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"assignments": {}, "attempts": {}}
    if not isinstance(data, dict):
        return {"assignments": {}, "attempts": {}}
    data.setdefault("assignments", {})
    data.setdefault("attempts", {})
    return data


def save_daily(state: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    temporary = DAILY_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(DAILY_PATH)


def ensure_daily(state: dict, date: str) -> None:
    current = state["assignments"].get(date)
    if not isinstance(current, dict):
        current = {}
    state["assignments"][date] = assign_daily(date, HEROES, current)


def attempt_key(date: str, tier: str, guest: str) -> str:
    return f"{date}|{tier}|{guest}"


def hero_payload(game: dict) -> dict:
    target = BY_NAME[game["target"]]
    guesses = []
    for item in game["guesses"]:
        hero = BY_NAME.get(item.get("name"))
        guesses.append(compare_guess(hero, target) if hero else copy.deepcopy(item))
    payload = {
        "gameId": game["id"],
        "status": game["status"],
        "maxGuesses": MAX_GUESSES,
        "guesses": guesses,
    }
    if game["status"] != "playing":
        payload["answer"] = hero_answer(BY_NAME[game["target"]])
    return payload


def tactic_payload(game: dict) -> dict:
    payload = {
        "gameId": game["id"],
        "status": game["status"],
        "maxGuesses": MAX_GUESSES,
        "guesses": copy.deepcopy(game["guesses"]),
    }
    if game["status"] != "playing":
        payload["answer"] = tactic_answer(TACTIC_BY_NAME[game["target"]])
    return payload


def soup_payload(game: dict) -> dict:
    payload = {
        "gameId": game["id"],
        "status": game["status"],
        "maxAttempts": MAX_SOUP,
        "used": len(game["events"]),
        "events": copy.deepcopy(game["events"]),
    }
    if game["status"] != "playing":
        payload["answer"] = hero_answer(BY_NAME[game["target"]])
    return payload


def new_game(kind: str, target: str) -> dict:
    return {
        "id": uuid.uuid4().hex,
        "kind": kind,
        "target": target,
        "status": "playing",
        "guesses": [],
        "events": [],
        "asked": [],
    }


def stamp(game: dict) -> None:
    if game["status"] != "playing" and not game.get("finishedAt"):
        game["finishedAt"] = shanghai_now().isoformat()


def apply_hero_guess(game: dict, name: str) -> str | None:
    if game["status"] != "playing":
        return "GAME_FINISHED"
    hero = BY_NAME.get(name)
    if hero is None:
        return "HERO_NOT_FOUND"
    if any(item["name"] == name for item in game["guesses"]):
        return "ALREADY_GUESSED"
    feedback = compare_guess(hero, BY_NAME[game["target"]])
    game["guesses"].append(feedback)
    if feedback["correct"]:
        game["status"] = "won"
    elif len(game["guesses"]) >= MAX_GUESSES:
        game["status"] = "lost"
    stamp(game)
    return None


def apply_tactic_guess(game: dict, name: str) -> str | None:
    if game["status"] != "playing":
        return "GAME_FINISHED"
    tactic = TACTIC_BY_NAME.get(name)
    if tactic is None:
        return "TACTIC_NOT_FOUND"
    if any(item["name"] == name for item in game["guesses"]):
        return "ALREADY_GUESSED"
    feedback = compare_tactic(tactic, TACTIC_BY_NAME[game["target"]])
    game["guesses"].append(feedback)
    if feedback["correct"]:
        game["status"] = "won"
    elif len(game["guesses"]) >= MAX_GUESSES:
        game["status"] = "lost"
    stamp(game)
    return None


def error_status(code: str) -> int:
    if code in {"GAME_NOT_FOUND", "HERO_NOT_FOUND", "TACTIC_NOT_FOUND"}:
        return 404
    return 400


def parse_soup_value(field: object, value: object):
    if not isinstance(field, str) or field not in SOUP_VALUES:
        return None
    allowed = SOUP_VALUES[field]
    if isinstance(value, bool) or value is None:
        return None
    if field == "bondCount":
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        if number not in allowed:
            return None
        return number
    text = str(value).strip()
    if text not in allowed:
        return None
    return text


def leaderboard(state: dict, date: str, tier: str) -> list[dict]:
    rows = []
    for attempt in state["attempts"].values():
        if attempt.get("date") == date and attempt.get("tier") == tier and attempt.get("status") == "won":
            rows.append(attempt)
    rows.sort(key=lambda item: (len(item.get("guesses") or []), item.get("finishedAt") or ""))
    return [
        {"displayName": item.get("displayName") or "访客", "guessCount": len(item.get("guesses") or [])}
        for item in rows[:10]
    ]


def daily_overview(state: dict, guest: str) -> dict:
    date = shanghai_today()
    ensure_daily(state, date)
    tiers = []
    for tier, label, detail in DAILY_TIERS:
        attempt = state["attempts"].get(attempt_key(date, tier, guest)) if guest else None
        tiers.append({
            "key": tier,
            "label": label,
            "detail": detail,
            "pool": len(daily_pool(HEROES, tier)),
            "status": attempt["status"] if attempt else "idle",
            "guessCount": len(attempt["guesses"]) if attempt else 0,
            "maxGuesses": MAX_GUESSES,
        })
    return {
        "date": date,
        "nextRefreshAt": next_refresh_at(),
        "tiers": tiers,
        "leaderboards": {tier: leaderboard(state, date, tier) for tier, _label, _detail in DAILY_TIERS},
    }


def remember_name(attempt: dict, payload: dict) -> None:
    if attempt["status"] == "playing" and "displayName" in payload:
        attempt["displayName"] = clean_name(payload.get("displayName"))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(fmt % args, flush=True)

    def _send(self, code: int, body: bytes, content_type: str, cache: str = "no-store") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(code, body, "application/json; charset=utf-8")

    def _read_json(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 20000:
            return None
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return data

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = self.headers.get("Host") or ""
        return origin in {f"http://{host}", f"https://{host}"}

    def _guest(self) -> str:
        raw = (self.headers.get("X-Guest-Id") or "").strip()
        if GUEST_RE.fullmatch(raw):
            return raw
        return ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        parts = [part for part in path.split("/") if part]
        if parts == ["api", "heroes"]:
            self._json(200, {"heroes": [public_hero(hero) for hero in HEROES]})
            return
        if parts == ["api", "tactics"]:
            self._json(200, {"tactics": [public_tactic(tactic) for tactic in TACTICS]})
            return
        if parts == ["api", "soup", "options"]:
            self._json(200, SOUP)
            return
        if parts == ["api", "daily"]:
            with LOCK:
                state = load_daily()
                payload = daily_overview(state, self._guest())
                save_daily(state)
            self._json(200, payload)
            return
        if len(parts) == 3 and parts[:2] == ["api", "games"] and GAME_RE.fullmatch(parts[2]):
            self._read_memory(parts[2], "classic", hero_payload)
            return
        if len(parts) == 3 and parts[:2] == ["api", "tactic-games"] and GAME_RE.fullmatch(parts[2]):
            self._read_memory(parts[2], "tactic", tactic_payload)
            return
        if len(parts) == 3 and parts[:2] == ["api", "soup-games"] and GAME_RE.fullmatch(parts[2]):
            self._read_memory(parts[2], "soup", soup_payload)
            return
        if parts and parts[0] == "api":
            self._json(404, {"code": "NOT_FOUND"})
            return
        if parts[:1] == ["figures"] and len(parts) == 2:
            self._figure(parts[1])
            return
        self._static("/" if path == "/" else path)

    def _read_memory(self, game_id: str, kind: str, viewer) -> None:
        with LOCK:
            game = GAMES.get(game_id)
            if game is None or game.get("kind") != kind:
                payload = None
            else:
                payload = viewer(game)
        if payload is None:
            self._json(404, {"code": "GAME_NOT_FOUND"})
            return
        self._json(200, payload)

    def _figure(self, name: str) -> None:
        file_path = (FIGURES / name).resolve()
        if FIGURES.resolve() not in file_path.parents or not file_path.is_file():
            self._send(404, b"", "text/plain; charset=utf-8")
            return
        self._send(200, file_path.read_bytes(), "image/png", cache="public, max-age=86400")

    def _static(self, path: str) -> None:
        if path in ("/", "/index.html"):
            file_path = WEB / "index.html"
        else:
            file_path = (WEB / path.lstrip("/")).resolve()
            if WEB.resolve() not in file_path.parents and file_path != WEB.resolve():
                self._send(404, b"", "text/plain; charset=utf-8")
                return
        if not file_path.is_file():
            self._send(404, b"", "text/plain; charset=utf-8")
            return
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }.get(file_path.suffix, "application/octet-stream")
        self._send(200, file_path.read_bytes(), content_type)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        parts = [part for part in path.split("/") if part]
        if not self._origin_ok():
            self._json(403, {"code": "BAD_ORIGIN"})
            return
        payload = self._read_json()
        if payload is None:
            self._json(400, {"code": "BAD_JSON"})
            return
        if parts == ["api", "games"]:
            self._create("classic", HEROES, hero_payload)
            return
        if parts == ["api", "tactic-games"]:
            self._create("tactic", TACTICS, tactic_payload)
            return
        if parts == ["api", "soup-games"]:
            self._create("soup", HEROES, soup_payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "games"] and parts[3] == "guess":
            self._memory_guess(parts[2], "classic", payload, apply_hero_guess, hero_payload, "name")
            return
        if len(parts) == 4 and parts[:2] == ["api", "games"] and parts[3] == "giveup":
            self._memory_giveup(parts[2], "classic", hero_payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "tactic-games"] and parts[3] == "guess":
            self._memory_guess(parts[2], "tactic", payload, apply_tactic_guess, tactic_payload, "name")
            return
        if len(parts) == 4 and parts[:2] == ["api", "tactic-games"] and parts[3] == "giveup":
            self._memory_giveup(parts[2], "tactic", tactic_payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "soup-games"] and parts[3] == "ask":
            self._soup_ask(parts[2], payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "soup-games"] and parts[3] == "guess":
            self._soup_guess(parts[2], payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "soup-games"] and parts[3] == "giveup":
            self._memory_giveup(parts[2], "soup", soup_payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "daily"] and parts[2] in TIER_KEYS and parts[3] == "start":
            self._daily_start(parts[2], payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "daily"] and parts[2] in TIER_KEYS and parts[3] == "guess":
            self._daily_guess(parts[2], payload)
            return
        if len(parts) == 4 and parts[:2] == ["api", "daily"] and parts[2] in TIER_KEYS and parts[3] == "giveup":
            self._daily_giveup(parts[2], payload)
            return
        self._json(404, {"code": "NOT_FOUND"})

    def _create(self, kind: str, pool: list[dict], viewer) -> None:
        with LOCK:
            game = new_game(kind, pick_target(pool)["name"])
            GAMES[game["id"]] = game
            body = viewer(game)
        self._json(201, body)

    def _memory_guess(self, game_id: str, kind: str, payload: dict, apply, viewer, field: str) -> None:
        if not GAME_RE.fullmatch(game_id):
            self._json(404, {"code": "GAME_NOT_FOUND"})
            return
        name = str(payload.get(field) or "").strip()
        with LOCK:
            game = GAMES.get(game_id)
            if game is None or game.get("kind") != kind:
                code = "GAME_NOT_FOUND"
                body = None
            else:
                code = apply(game, name)
                body = None if code else viewer(game)
        if code:
            self._json(error_status(code), {"code": code})
            return
        self._json(200, body)

    def _memory_giveup(self, game_id: str, kind: str, viewer) -> None:
        if not GAME_RE.fullmatch(game_id):
            self._json(404, {"code": "GAME_NOT_FOUND"})
            return
        with LOCK:
            game = GAMES.get(game_id)
            if game is None or game.get("kind") != kind:
                body = None
            else:
                if game["status"] == "playing":
                    game["status"] = "lost"
                    stamp(game)
                body = viewer(game)
        if body is None:
            self._json(404, {"code": "GAME_NOT_FOUND"})
            return
        self._json(200, body)

    def _soup_ask(self, game_id: str, payload: dict) -> None:
        if not GAME_RE.fullmatch(game_id):
            self._json(404, {"code": "GAME_NOT_FOUND"})
            return
        value = parse_soup_value(payload.get("field"), payload.get("value"))
        field = payload.get("field")
        if value is None or not isinstance(field, str):
            self._json(400, {"code": "BAD_QUESTION"})
            return
        mark = f"{field}={value}"
        with LOCK:
            game = GAMES.get(game_id)
            if game is None or game.get("kind") != "soup":
                code = "GAME_NOT_FOUND"
            elif game["status"] != "playing":
                code = "GAME_FINISHED"
            elif mark in game["asked"]:
                code = "ALREADY_ASKED"
            else:
                cell = compare_soup_field(BY_NAME[game["target"]], field, value)
                game["asked"].append(mark)
                game["events"].append({
                    "type": "question",
                    "field": field,
                    "label": SOUP_LABELS[field],
                    "value": value,
                    "level": cell["level"],
                    "hint": cell.get("hint"),
                })
                if len(game["events"]) >= MAX_SOUP:
                    game["status"] = "lost"
                    stamp(game)
                code = None
            body = None if code else soup_payload(game)
        if code:
            self._json(error_status(code), {"code": code})
            return
        self._json(200, body)

    def _soup_guess(self, game_id: str, payload: dict) -> None:
        if not GAME_RE.fullmatch(game_id):
            self._json(404, {"code": "GAME_NOT_FOUND"})
            return
        name = str(payload.get("name") or "").strip()
        with LOCK:
            game = GAMES.get(game_id)
            hero = BY_NAME.get(name)
            if game is None or game.get("kind") != "soup":
                code = "GAME_NOT_FOUND"
            elif game["status"] != "playing":
                code = "GAME_FINISHED"
            elif hero is None:
                code = "HERO_NOT_FOUND"
            elif any(event.get("type") == "guess" and event.get("name") == name for event in game["events"]):
                code = "ALREADY_GUESSED"
            else:
                correct = name == game["target"]
                game["events"].append({
                    "type": "guess",
                    "name": name,
                    "skill": hero["skill"],
                    "avatar": hero["avatar"],
                    "correct": correct,
                })
                if correct:
                    game["status"] = "won"
                elif len(game["events"]) >= MAX_SOUP:
                    game["status"] = "lost"
                stamp(game)
                code = None
            body = None if code else soup_payload(game)
        if code:
            self._json(error_status(code), {"code": code})
            return
        self._json(200, body)

    def _daily_attempt(self, tier: str, payload: dict, create: bool):
        guest = self._guest()
        if not guest:
            return 400, {"code": "GUEST_REQUIRED"}
        date = shanghai_today()
        key = attempt_key(date, tier, guest)
        state = load_daily()
        ensure_daily(state, date)
        attempt = state["attempts"].get(key)
        if attempt is None:
            if not create:
                save_daily(state)
                return 404, {"code": "GAME_NOT_FOUND"}
            attempt = {
                "id": uuid.uuid4().hex,
                "date": date,
                "tier": tier,
                "guest": guest,
                "displayName": clean_name(payload.get("displayName")),
                "target": state["assignments"][date][tier],
                "status": "playing",
                "guesses": [],
                "finishedAt": None,
            }
            state["attempts"][key] = attempt
        else:
            remember_name(attempt, payload)
        return state, attempt

    def _daily_start(self, tier: str, payload: dict) -> None:
        with LOCK:
            found = self._daily_attempt(tier, payload, create=True)
            if isinstance(found[0], int):
                code, body = found
            else:
                state, attempt = found
                save_daily(state)
                code, body = 200, hero_payload(attempt)
        self._json(code, body)

    def _daily_guess(self, tier: str, payload: dict) -> None:
        name = str(payload.get("name") or "").strip()
        with LOCK:
            found = self._daily_attempt(tier, payload, create=False)
            if isinstance(found[0], int):
                code, body = found
            else:
                state, attempt = found
                error = apply_hero_guess(attempt, name)
                save_daily(state)
                if error:
                    code, body = error_status(error), {"code": error}
                else:
                    code, body = 200, hero_payload(attempt)
        self._json(code, body)

    def _daily_giveup(self, tier: str, payload: dict) -> None:
        with LOCK:
            found = self._daily_attempt(tier, payload, create=False)
            if isinstance(found[0], int):
                code, body = found
            else:
                state, attempt = found
                if attempt["status"] == "playing":
                    attempt["status"] = "lost"
                    stamp(attempt)
                save_daily(state)
                code, body = 200, hero_payload(attempt)
        self._json(code, body)


def main() -> None:
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"橙将 {len(HEROES)}，战法 {len(TACTICS)}，监听 {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
