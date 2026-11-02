# -*- coding: utf-8 -*-
"""用三谋资料库的兵种、阵营覆盖本地库里来自 sgmdtx 的错误字段。"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TRAD_TO_SIMP = str.maketrans(
    {
        "槍": "枪",
        "騎": "骑",
        "吳": "吴",
        "東": "东",
        "馬": "马",
        "張": "张",
        "劉": "刘",
        "關": "关",
        "黃": "黄",
        "孫": "孙",
        "趙": "赵",
        "華": "华",
        "諸": "诸",
        "葛": "葛",
        "呂": "吕",
        "喬": "乔",
        "許": "许",
        "陳": "陈",
        "鄧": "邓",
        "鄒": "邹",
        "賈": "贾",
        "詡": "诩",
        "龐": "庞",
        "統": "统",
        "淩": "凌",
        "寧": "宁",
        "豐": "丰",
        "術": "术",
        "紹": "绍",
        "醜": "丑",
        "顏": "颜",
        "魯": "鲁",
        "肅": "肃",
        "薑": "姜",
        "維": "维",
        "獲": "获",
        "週": "周",
        "雲": "云",
        "國": "国",
        "於": "于",
        "後": "后",
        "來": "来",
        "傑": "杰",
        "衛": "卫",
        "會": "会",
        "無": "无",
        "當": "当",
        "飛": "飞",
        "軍": "军",
        "龍": "龙",
        "鳳": "凤",
        "書": "书",
        "畫": "画",
        "樂": "乐",
        "進": "进",
        "雙": "双",
        "異": "异",
        "純": "纯",
        "懿": "懿",
        "權": "权",
        "備": "备",
        "禪": "禅",
        "蓋": "盖",
        "超": "超",
        "忠": "忠",
        "羽": "羽",
        "布": "布",
        "操": "操",
        "亮": "亮",
        "蒙": "蒙",
        "坚": "坚",
        "堅": "坚",
        "策": "策",
        "香": "香",
        "瑜": "瑜",
        "普": "普",
        "慈": "慈",
        "吉": "吉",
        "禁": "禁",
        "彧": "彧",
        "攸": "攸",
        "嘉": "嘉",
        "仁": "仁",
        "洪": "洪",
        "真": "真",
        "惇": "惇",
        "淵": "渊",
        "晃": "晃",
        "盛": "盛",
        "卓": "卓",
        "蟬": "蝉",
        "佗": "佗",
        "雄": "雄",
        "儒": "儒",
        "姬": "姬",
        "氏": "氏",
        "梁": "梁",
        "角": "角",
        "寶": "宝",
        "平": "平",
        "倉": "仓",
        "飛": "飞",
        "庶": "庶",
        "正": "正",
        "宮": "宫",
        "昱": "昱",
        "洛": "洛",
        "甄": "甄",
        "月": "月",
        "英": "英",
        "祿": "禄",
        "騰": "腾",
        "順": "顺",
        "延": "延",
        "抗": "抗",
        "遜": "逊",
        "當": "当",
        "欽": "钦",
        "襲": "袭",
        "璋": "璋",
        "武": "武",
        "曼": "曼",
        "成": "成",
        "嵩": "嵩",
        "甫": "甫",
        "皇": "皇",
        "左": "左",
        "慈": "慈",
        "昭": "昭",
        "郝": "郝",
        "雙": "双",
        "王": "王",
        "異": "异",
        "卞": "卞",
        "夫": "夫",
        "人": "人",
        "糜": "糜",
        "甘": "甘",
        "步": "步",
        "練": "练",
        "師": "师",
        "祝": "祝",
        "融": "融",
        "木": "木",
        "鹿": "鹿",
        "大": "大",
        "朱": "朱",
        "儁": "儁",
        "俊": "俊",
        "張": "张",
        "春": "春",
        "華": "华",
        "昭": "昭",
        "寧": "宁",
        "高": "高",
        "魏": "魏",
        "蜀": "蜀",
        "群": "群",
        "盾": "盾",
        "弓": "弓",
        "槍": "枪",
        "騎": "骑",
    }
)


def simp(text: str) -> str:
    return text.translate(TRAD_TO_SIMP)


def avatar_name(value: str | None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value.replace("\\", "/")).name


def main() -> None:
    wiki = json.loads((DATA / "_wiki_generals.json").read_text(encoding="utf-8"))
    by_avatar = {row["avatar"]: row for row in wiki if row.get("avatar")}
    wj_path = DATA / "wujiang_database.json"
    cat_path = DATA / "_catalog_out.json"
    wj = json.loads(wj_path.read_text(encoding="utf-8"))
    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    catalog_by_name = catalog.get("wj") or {}

    changes = []
    unmatched = []
    used_avatars: set[str] = set()
    for hero in wj["heroes"]:
        avatar = avatar_name(hero.get("avatar_file"))
        row = by_avatar.get(avatar or "")
        if row is None:
            unmatched.append(hero["name"])
            continue
        used_avatars.add(avatar)
        troop = simp(row["soldier_type"])
        faction = simp(row["camp"])
        old_troop = hero.get("troop_type")
        old_faction = hero.get("faction")
        if old_troop != troop or old_faction != faction:
            changes.append(
                {
                    "name": hero["name"],
                    "troop": [old_troop, troop],
                    "faction": [old_faction, faction],
                }
            )
        hero["troop_type"] = troop
        hero["faction"] = faction
        cat_hero = catalog_by_name.get(hero["name"])
        if isinstance(cat_hero, dict):
            cat_hero["bz"] = troop
            cat_hero["zy"] = faction

    wiki_unused = sorted(set(by_avatar) - used_avatars)
    wj.setdefault("meta", {})
    wj["meta"]["troop_type_source"] = "https://sanmou-wiki.vercel.app/generals"
    wj["meta"]["troop_type_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    wj["meta"]["troop_type_note"] = "兵种和阵营以三谋资料库 generals_info 为准，按头像文件名对齐。sgmdtx 的 bz 大量误标为盾，不再使用。"
    wj["meta"]["troop_type_counts"] = dict(Counter(hero.get("troop_type") for hero in wj["heroes"]))
    wj["meta"]["troop_type_unmatched"] = unmatched
    wj["meta"]["troop_type_changes"] = len(changes)
    wj_path.write_text(json.dumps(wj, ensure_ascii=False, indent=2), encoding="utf-8")
    cat_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"wiki {len(wiki)} local {len(wj['heroes'])} changed {len(changes)} unmatched {len(unmatched)}",
        "unmatched " + "、".join(unmatched),
        "wiki avatars unused " + "、".join(wiki_unused),
        "counts " + json.dumps(wj["meta"]["troop_type_counts"], ensure_ascii=False),
        "--- changes ---",
    ]
    for item in changes:
        troop = ""
        faction = ""
        if item["troop"][0] != item["troop"][1]:
            troop = f"兵种 {item['troop'][0]}→{item['troop'][1]}"
        if item["faction"][0] != item["faction"][1]:
            faction = f"阵营 {item['faction'][0]}→{item['faction'][1]}"
        lines.append(f"{item['name']}: {troop} {faction}".strip())
    (DATA / "_troop_update_report.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
