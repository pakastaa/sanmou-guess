# -*- coding: utf-8 -*-
"""猜一猜的比较规则：橙将、通用战法、每日分档和海龟汤。"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "wujiang_database.json"
MAX_LEVEL = 50
LEVEL_STEPS = MAX_LEVEL - 1
MAX_GUESSES = 8
STAT_NAMES = ("武力", "智力", "统帅", "先攻")
SEASON_ORDER = ("s1", "s2", "s3", "s4+")
ROLE_MAP = {
    "兵刃": "兵刃",
    "谋略": "谋略",
    "辅助": "辅助",
    "文武": "文武",
    "防御": "辅助",
    "治疗": "辅助",
}
TROOP_ORDER = ("盾", "枪", "弓", "骑")
COLUMNS = (
    ("faction", "阵营"),
    ("troop", "兵种"),
    ("tacticType", "战法类型"),
    ("topStat", "最高属性"),
    ("bondCount", "缘分数量"),
    ("season", "登场赛季"),
    ("sex", "性别"),
    ("role", "武将类型"),
)


def season_bucket(season: str) -> str:
    number = int(str(season).lower().lstrip("s"))
    if number >= 4:
        return "s4+"
    return f"s{number}"


def level_50(base: str, growth: str) -> float:
    return round(float(base) + float(growth) * LEVEL_STEPS, 2)


def top_stat(stats: dict) -> str:
    values = {
        name: level_50(stats[name], stats[f"{name}成长"])
        for name in STAT_NAMES
    }
    best = max(values.values())
    for name in STAT_NAMES:
        if abs(values[name] - best) < 0.011:
            return name
    return STAT_NAMES[0]


def hero_view(hero: dict) -> dict:
    skill = hero.get("innate_skill") or {}
    effect = skill.get("effect_tag") or ""
    role = ROLE_MAP.get(effect)
    if role is None:
        raise ValueError(f"{hero.get('name')} 的效果标签无法归类: {effect}")
    troop = hero.get("troop_type") or ""
    if troop not in TROOP_ORDER:
        raise ValueError(f"{hero.get('name')} 的兵种无法归类: {troop}")
    avatar = str(hero.get("avatar_file") or "").replace("\\", "/").rsplit("/", 1)[-1]
    return {
        "name": hero["name"],
        "skill": skill.get("name") or "",
        "avatar": avatar,
        "faction": hero["faction"],
        "troop": troop,
        "tacticType": skill.get("tactic_type") or "",
        "topStat": top_stat(hero["stats"]),
        "bondCount": len(hero.get("bonds") or []),
        "season": season_bucket(hero.get("season") or "s1"),
        "sex": hero.get("sex") or "",
        "role": role,
    }


def load_heroes(path: Path = DATA_PATH) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    heroes = [
        hero_view(hero)
        for hero in document.get("heroes") or []
        if hero.get("rarity_color") == "orange"
    ]
    heroes.sort(key=lambda hero: hero["name"])
    return heroes


def _text(guess: str, target: str) -> dict:
    return {"value": guess, "level": "correct" if guess == target else "wrong"}


def _number(guess: int, target: int, close: int = 1) -> dict:
    if guess == target:
        return {"value": guess, "level": "correct"}
    return {
        "value": guess,
        "level": "close" if abs(guess - target) <= close else "wrong",
        "hint": "higher" if target > guess else "lower",
    }


def _season(guess: str, target: str) -> dict:
    if guess == target:
        return {"value": guess, "level": "correct"}
    guess_index = SEASON_ORDER.index(guess)
    target_index = SEASON_ORDER.index(target)
    return {
        "value": guess,
        "level": "close" if abs(guess_index - target_index) == 1 else "wrong",
        "hint": "higher" if target_index > guess_index else "lower",
    }


def compare_guess(guess: dict, target: dict) -> dict:
    cells = {
        "faction": _text(guess["faction"], target["faction"]),
        "troop": _text(guess["troop"], target["troop"]),
        "tacticType": _text(guess["tacticType"], target["tacticType"]),
        "topStat": _text(guess["topStat"], target["topStat"]),
        "bondCount": _number(guess["bondCount"], target["bondCount"]),
        "season": _season(guess["season"], target["season"]),
        "sex": _text(guess["sex"], target["sex"]),
        "role": _text(guess["role"], target["role"]),
    }
    return {
        "name": guess["name"],
        "skill": guess["skill"],
        "avatar": guess["avatar"],
        "correct": guess["name"] == target["name"],
        "cells": cells,
    }


def pick_target(heroes: list[dict], rng: random.Random | None = None) -> dict:
    return (rng or random.SystemRandom()).choice(heroes)


def public_hero(hero: dict) -> dict:
    return {"name": hero["name"], "skill": hero["skill"], "avatar": hero["avatar"]}


def hero_answer(hero: dict) -> dict:
    return {
        "name": hero["name"],
        "skill": hero["skill"],
        "avatar": hero["avatar"],
        "cells": compare_guess(hero, hero)["cells"],
    }


TACTIC_PATH = ROOT / "data" / "zhanfa_database.json"
MAX_SOUP = 24
RATE_CLOSE = 10
QUALITY_LABEL = {"orange": "橙", "purple": "紫"}
DAILY_TIERS = (
    ("easy", "入门", "S1 橙将"),
    ("normal", "标准", "S1 至 S3"),
    ("all", "全部", "全部橙将"),
)
ENUM_ORDER = {
    "faction": ("魏", "蜀", "吴", "群"),
    "troop": TROOP_ORDER,
    "tacticType": ("指挥", "主动", "被动", "追击"),
    "topStat": STAT_NAMES,
    "season": SEASON_ORDER,
    "sex": ("男", "女"),
    "role": ("兵刃", "谋略", "辅助", "文武"),
}
SHANGHAI = timezone(timedelta(hours=8))


def shanghai_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(SHANGHAI)
    if current.tzinfo is None:
        return current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI)


def shanghai_today(now: datetime | None = None) -> str:
    return shanghai_now(now).strftime("%Y-%m-%d")


def next_refresh_at(now: datetime | None = None) -> str:
    current = shanghai_now(now)
    tomorrow = current.date() + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=SHANGHAI).isoformat()


def format_rate(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return f"{int(round(value))}%"
    return f"{value:.1f}%"


def parse_rate(text: str) -> float:
    cleaned = str(text).strip().replace("％", "%").replace("%", "").strip()
    return float(cleaned)


def tactic_view(tactic: dict) -> dict:
    quality = QUALITY_LABEL.get(tactic.get("rarity_color") or "")
    if quality is None:
        raise ValueError(f"{tactic.get('name')} 的品质无法归类")
    effect = tactic.get("effect_tag") or ""
    tactic_type = tactic.get("tactic_type") or ""
    if not effect or not tactic_type:
        raise ValueError(f"{tactic.get('name')} 缺少类型或效果")
    avatar = str(tactic.get("avatar_file") or "").replace("\\", "/").rsplit("/", 1)[-1]
    return {
        "name": tactic["name"],
        "avatar": avatar,
        "quality": quality,
        "tacticType": tactic_type,
        "effect": effect,
        "season": season_bucket(tactic.get("season") or "s1"),
        "rate": parse_rate(tactic.get("rate_or_scaling_text") or ""),
        "description": tactic.get("description") or "",
    }


def load_tactics(path: Path = TACTIC_PATH) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    tactics = [tactic_view(tactic) for tactic in document.get("tactics") or []]
    names = [tactic["name"] for tactic in tactics]
    if len(names) != len(set(names)):
        raise ValueError("战法重名")
    tactics.sort(key=lambda tactic: tactic["name"])
    return tactics


def _rate(guess: float, target: float) -> dict:
    label = format_rate(guess)
    if abs(guess - target) < 0.011:
        return {"value": label, "level": "correct"}
    return {
        "value": label,
        "level": "close" if abs(guess - target) <= RATE_CLOSE else "wrong",
        "hint": "higher" if target > guess else "lower",
    }


def compare_tactic(guess: dict, target: dict) -> dict:
    cells = {
        "quality": _text(guess["quality"], target["quality"]),
        "tacticType": _text(guess["tacticType"], target["tacticType"]),
        "effect": _text(guess["effect"], target["effect"]),
        "season": _season(guess["season"], target["season"]),
        "rate": _rate(guess["rate"], target["rate"]),
    }
    return {
        "name": guess["name"],
        "avatar": guess["avatar"],
        "correct": guess["name"] == target["name"],
        "cells": cells,
    }


def public_tactic(tactic: dict) -> dict:
    return {"name": tactic["name"], "avatar": tactic["avatar"]}


def tactic_answer(tactic: dict) -> dict:
    return {
        "name": tactic["name"],
        "avatar": tactic["avatar"],
        "description": tactic["description"],
        "cells": compare_tactic(tactic, tactic)["cells"],
    }


def daily_pool(heroes: list[dict], tier: str) -> list[dict]:
    if tier == "easy":
        return [hero for hero in heroes if hero["season"] == "s1"]
    if tier == "normal":
        return [hero for hero in heroes if hero["season"] in {"s1", "s2", "s3"}]
    if tier == "all":
        return list(heroes)
    raise KeyError(tier)


def assign_daily(date: str, heroes: list[dict], existing: dict | None = None) -> dict[str, str]:
    by_name = {hero["name"]: hero for hero in heroes}
    kept: dict[str, str] = {}
    used: set[str] = set()
    for tier, _label, _detail in DAILY_TIERS:
        name = (existing or {}).get(tier)
        if isinstance(name, str) and name in by_name and name not in used:
            kept[tier] = name
            used.add(name)
    rng = random.Random(f"sanmou-daily:{date}:{','.join(sorted(used))}")
    for tier, _label, _detail in DAILY_TIERS:
        if tier in kept:
            continue
        pool = [hero["name"] for hero in daily_pool(heroes, tier) if hero["name"] not in used]
        if not pool:
            pool = [hero["name"] for hero in daily_pool(heroes, tier)]
        choice = rng.choice(pool)
        kept[tier] = choice
        used.add(choice)
    return kept


def soup_options(heroes: list[dict]) -> dict:
    fields = []
    for key, label in COLUMNS:
        if key == "bondCount":
            values = sorted({int(hero["bondCount"]) for hero in heroes})
            kind = "number"
        else:
            present = {hero[key] for hero in heroes}
            values = [item for item in ENUM_ORDER[key] if item in present]
            kind = "enum"
        fields.append({"key": key, "label": label, "kind": kind, "values": values})
    return {"maxAttempts": MAX_SOUP, "fields": fields}


def compare_soup_field(target: dict, field: str, value) -> dict:
    if field == "bondCount":
        return _number(int(value), int(target["bondCount"]))
    if field == "season":
        return _season(str(value), target["season"])
    return _text(str(value), str(target[field]))
