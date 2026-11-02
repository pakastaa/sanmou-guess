# -*- coding: utf-8 -*-
"""从 sgmdtx.com 更新本目录 data/ 下的武将、战法和头像。

目录数据来自官网前端 chunk 里的 getWjs/getZfs。
缘分说明和自带战法全文来自对应详情页的 __NEXT_DATA__。
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FIGURE = DATA / "figure"
BASE = "https://www.sgmdtx.com"
CDN_IMG = "https://cdn.sgmdtx.com/img/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SanmouGuess/1.0"
NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(?P<j>.*?)</script>',
    re.DOTALL,
)
CHUNK_RE = re.compile(r"https://cdn\.sgmdtx\.com/_next/static/chunks/[^\"']+\.js")


def find_node() -> str:
    found = shutil.which("node")
    if found:
        return found
    local = os.environ.get("LOCALAPPDATA")
    if local:
        bundled = Path(local) / "Programs" / "cursor" / "resources" / "app" / "resources" / "helpers" / "node.exe"
        if bundled.is_file():
            return str(bundled)
    raise RuntimeError("找不到 node，无法从官网 chunk 解出目录")


def curl(url: str, dest: Path, timeout: int = 40) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["curl.exe", "-sL", "--max-time", str(timeout), "-A", UA, "-o", str(dest), url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl {result.returncode} {url} {(result.stderr or '')[:200]}")
    if not dest.is_file() or dest.stat().st_size < 32:
        raise RuntimeError(f"empty response {url}")


def fetch_text(url: str, timeout: int = 40) -> str:
    fd, tmp_name = tempfile.mkstemp(prefix="sgmdtx_", suffix=".html")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        curl(url, tmp, timeout)
        return tmp.read_text(encoding="utf-8", errors="replace")
    finally:
        tmp.unlink(missing_ok=True)


def page_props(html: str) -> dict:
    match = NEXT_DATA_RE.search(html)
    if not match:
        raise RuntimeError("页面中没有 __NEXT_DATA__")
    data = json.loads(match.group("j"))
    props = data.get("props", {}).get("pageProps", {})
    if not isinstance(props, dict):
        raise RuntimeError("pageProps 不是对象")
    return props


def quote_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.quote(parsed.path, safe="/")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


def refresh_catalog() -> dict:
    print("下载武将列表页，定位数据 chunk", flush=True)
    html = fetch_text(f"{BASE}/wujiang/")
    urls = sorted(set(CHUNK_RE.findall(html)))
    if not urls:
        raise RuntimeError("列表页没有前端 chunk")
    with tempfile.TemporaryDirectory(prefix="sgmdtx_chunks_") as tmp:
        chunk_dir = Path(tmp)
        for url in urls:
            name = url.rsplit("/", 1)[-1]
            if name.startswith(("framework-", "main-", "polyfills-", "webpack-")):
                continue
            print(f"  chunk {name}", flush=True)
            curl(url, chunk_dir / name, timeout=60)
        out = chunk_dir / "catalog.json"
        node = find_node()
        extractor = Path(__file__).with_name("extract_sgmdtx_catalog.cjs")
        result = subprocess.run(
            [node, str(extractor), str(chunk_dir), str(out)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not out.is_file():
            raise RuntimeError((result.stderr or result.stdout or "catalog extract failed")[:500])
        print(result.stdout.strip(), flush=True)
        return json.loads(out.read_text(encoding="utf-8"))


def load_previous_heroes() -> dict[str, dict]:
    path = DATA / "wujiang_database.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {hero["name"]: hero for hero in data.get("heroes") or [] if hero.get("name")}


def sex_label(value) -> str | None:
    text = str(value).strip()
    if text == "1":
        return "男"
    if text == "2":
        return "女"
    return None


def figure_path(filename: str | None) -> str | None:
    if not isinstance(filename, str) or not filename.strip():
        return None
    return f"data/figure/{Path(filename.replace(chr(92), '/')).name}"


def fetch_named(kind: str, name: str) -> dict:
    url = quote_url(f"{BASE}/{kind}/{name}/")
    html = fetch_text(url)
    props = page_props(html)
    record = props.get("wj" if kind == "wj" else "zf")
    if not isinstance(record, dict):
        raise RuntimeError(f"no {kind} payload")
    record["_fetch_url"] = url
    return record


def build_hero(catalog_hero: dict, page: dict | None, skill_page: dict | None, previous: dict | None) -> dict:
    source = page or catalog_hero
    name = source.get("name") or catalog_hero.get("name")
    skill_name = source.get("skill") or catalog_hero.get("skill")
    bonds = source.get("jb") if isinstance(source.get("jb"), list) else catalog_hero.get("jb") or []
    prev_skill = (previous or {}).get("innate_skill") if isinstance((previous or {}).get("innate_skill"), dict) else {}
    skill = skill_page or {}
    innate = {
        "name": skill.get("name") or skill_name,
        "description": (skill.get("desc") or prev_skill.get("description") or "").strip(),
        "tactic_type": skill.get("ty") or prev_skill.get("tactic_type"),
        "effect_tag": skill.get("tx") or prev_skill.get("effect_tag"),
        "rarity_color": skill.get("color") or prev_skill.get("rarity_color"),
        "rate_or_scaling_text": skill.get("gl") or prev_skill.get("rate_or_scaling_text"),
        "ranked_description": (skill.get("mj_desc") or prev_skill.get("ranked_description") or "").strip(),
        "ranked_rate_text": skill.get("mj_gl") or prev_skill.get("ranked_rate_text"),
        "avatar_file_zhanfa": figure_path(skill.get("avatar")) or prev_skill.get("avatar_file_zhanfa"),
        "troop_eligibility": skill.get("bz") if isinstance(skill.get("bz"), list) else prev_skill.get("troop_eligibility"),
        "tags": skill.get("tags") if skill.get("tags") is not None else prev_skill.get("tags"),
        "zhanfa_source_url": skill.get("_fetch_url") or prev_skill.get("zhanfa_source_url"),
    }
    return {
        "source_url": (page or {}).get("_fetch_url") or f"{BASE}/wj/{name}/",
        "name": name,
        "faction": source.get("zy") or catalog_hero.get("zy"),
        "troop_type": source.get("bz") or catalog_hero.get("bz"),
        "season": source.get("sj") or catalog_hero.get("sj"),
        "sex": sex_label(source.get("sexy", catalog_hero.get("sexy"))),
        "rarity_color": source.get("color") or catalog_hero.get("color"),
        "avatar_file": figure_path(source.get("avatar") or catalog_hero.get("avatar")),
        "stats": {
            "武力": source.get("wl"),
            "智力": source.get("zl"),
            "统帅": source.get("ts"),
            "先攻": source.get("xg"),
            "武力成长": source.get("wl_incr"),
            "智力成长": source.get("zl_incr"),
            "统帅成长": source.get("ts_incr"),
            "先攻成长": source.get("xg_incr"),
        },
        "innate_skill": innate,
        "bonds": bonds,
        "suggested_skills": source.get("suggest_skills") if isinstance(source.get("suggest_skills"), list) else [],
        "tags": source.get("tags") if isinstance(source.get("tags"), list) else [],
    }


def build_tactic(item: dict) -> dict:
    name = item.get("name")
    return {
        "source_url": f"{BASE}/zf/{name}/",
        "name": name,
        "description": (item.get("desc") or "").strip(),
        "tactic_type": item.get("ty"),
        "effect_tag": item.get("tx"),
        "rarity_color": item.get("color"),
        "rate_or_scaling_text": item.get("gl"),
        "ranked_description": (item.get("mj_desc") or "").strip(),
        "ranked_rate_text": item.get("mj_gl"),
        "avatar_file": figure_path(item.get("avatar")),
        "season": item.get("sj"),
        "troop_eligibility": item.get("bz") if isinstance(item.get("bz"), list) else [],
        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
        "obtain": item.get("purch") if isinstance(item.get("purch"), list) else [],
    }


def download_figures(names: set[str]) -> tuple[int, list[str]]:
    FIGURE.mkdir(parents=True, exist_ok=True)
    missing = []
    for name in sorted(names):
        if not name:
            continue
        dest = FIGURE / name
        if dest.is_file() and dest.stat().st_size > 32:
            continue
        missing.append(name)

    failed: list[str] = []

    def one(name: str) -> tuple[str, bool]:
        dest = FIGURE / name
        for url in (CDN_IMG + name, CDN_IMG + name + "?v=v3.1.3"):
            try:
                curl(url, dest, timeout=45)
            except RuntimeError:
                continue
            if dest.is_file() and dest.stat().st_size > 32:
                return name, True
        return name, False

    if missing:
        print(f"下载缺失头像 {len(missing)}", flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for name, ok in pool.map(one, missing):
                if not ok:
                    failed.append(name)
    return len(missing) - len(failed), failed


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    previous = load_previous_heroes()
    catalog = refresh_catalog()
    heroes_catalog = catalog.get("wj") or {}
    tactics_catalog = catalog.get("zf") or {}
    (DATA / "_catalog_out.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"目录武将 {len(heroes_catalog)}，通用战法 {len(tactics_catalog)}", flush=True)

    page_errors: list[dict] = []
    hero_pages: dict[str, dict] = {}
    skill_pages: dict[str, dict] = {}

    def pull(kind: str, name: str) -> tuple[str, str, dict | None, str | None]:
        try:
            return kind, name, fetch_named(kind, name), None
        except Exception as exc:  # noqa: BLE001 - keep one hero from aborting the batch
            return kind, name, None, str(exc)

    jobs: list[tuple[str, str]] = [("wj", name) for name in heroes_catalog]
    skill_names = []
    seen_skills: set[str] = set()
    for item in heroes_catalog.values():
        skill = item.get("skill")
        if isinstance(skill, str) and skill and skill not in seen_skills:
            seen_skills.add(skill)
            skill_names.append(skill)
            jobs.append(("zf", skill))

    print(f"抓取详情页 {len(jobs)}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(pull, kind, name) for kind, name in jobs]
        for future in as_completed(futures):
            kind, name, record, error = future.result()
            done += 1
            if error or record is None:
                page_errors.append({"kind": kind, "name": name, "error": error or "empty"})
            elif kind == "wj":
                hero_pages[name] = record
            else:
                skill_pages[name] = record
            if done % 40 == 0 or done == len(jobs):
                print(f"  详情 {done}/{len(jobs)} 失败 {len(page_errors)}", flush=True)

    heroes = []
    description_changes = 0
    for name, item in heroes_catalog.items():
        hero = build_hero(item, hero_pages.get(name), skill_pages.get(item.get("skill")), previous.get(name))
        old = previous.get(name) or {}
        old_desc = ((old.get("innate_skill") or {}).get("description") or "").strip()
        new_desc = (hero["innate_skill"].get("description") or "").strip()
        if old_desc and new_desc and old_desc != new_desc:
            description_changes += 1
        heroes.append(hero)
    heroes.sort(key=lambda hero: hero["name"])

    tactics = [build_tactic(item) for item in tactics_catalog.values()]
    tactics.sort(key=lambda item: item["name"])

    filenames: set[str] = set()
    for hero in heroes:
        avatar = hero.get("avatar_file")
        if isinstance(avatar, str):
            filenames.add(Path(avatar).name)
        skill_avatar = (hero.get("innate_skill") or {}).get("avatar_file_zhanfa")
        if isinstance(skill_avatar, str):
            filenames.add(Path(skill_avatar).name)
    for tactic in tactics:
        avatar = tactic.get("avatar_file")
        if isinstance(avatar, str):
            filenames.add(Path(avatar).name)
    downloaded, figure_failed = download_figures(filenames)

    now = datetime.now(timezone.utc).isoformat()
    from collections import Counter

    troop_counts = Counter(hero.get("troop_type") for hero in heroes)
    wj_doc = {
        "meta": {
            "source_site": BASE,
            "source_page": f"{BASE}/wujiang/",
            "scraped_at_utc": now,
            "count_ok": len(heroes),
            "count_error": sum(1 for item in page_errors if item["kind"] == "wj"),
            "discover_source": "wujiang page chunks getWjs + detail __NEXT_DATA__",
            "previous_count": len(previous),
            "added": sorted(set(heroes_catalog) - set(previous)),
            "innate_description_changes": description_changes,
            "troop_type_counts": dict(troop_counts),
            "troop_type_note": "troop_type 直接使用源站字段 bz。2026-11 源站页面仍把赵云等多数武将标为盾，此分布不是本地统计误差。",
            "figure_dir": "data/figure",
            "figure_downloaded_now": downloaded,
            "figure_failed": figure_failed,
        },
        "heroes": heroes,
        "errors": [item for item in page_errors if item["kind"] == "wj"],
    }
    zf_doc = {
        "meta": {
            "source_site": BASE,
            "source_page": f"{BASE}/zhanfa/",
            "scraped_at_utc": now,
            "count_ok": len(tactics),
            "discover_source": "wujiang page chunks getZfs；自带战法已留在武将 innate_skill",
            "figure_dir": "data/figure",
            "figure_failed": figure_failed,
        },
        "tactics": tactics,
        "errors": [item for item in page_errors if item["kind"] == "zf"],
    }
    (DATA / "wujiang_database.json").write_text(json.dumps(wj_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "zhanfa_database.json").write_text(json.dumps(zf_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "heroes": len(heroes),
                "added": wj_doc["meta"]["added"],
                "tactics": len(tactics),
                "page_errors": len(page_errors),
                "innate_description_changes": description_changes,
                "troop_type_counts": wj_doc["meta"]["troop_type_counts"],
                "figures_downloaded": downloaded,
                "figure_failed": figure_failed,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
