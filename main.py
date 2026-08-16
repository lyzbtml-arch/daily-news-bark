"""生成一份经过筛选的中文个人信息早报，并通过 Bark 推送。"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Optional


HOT_API_BASE = os.getenv("HOT_API_BASE", "https://daily-hot-api-vercel-smoky.vercel.app").rstrip("/")
USER_AGENT = "daily-news-bark/2.0 (+https://github.com/)"
BARK_MAX_BODY_BYTES = 2800

HOT_SOURCES = (
    ("百度热搜", "baidu"),
    ("36氪", "36kr"),
    ("抖音热点", "douyin"),
)

RSS_SOURCES = (
    ("OpenAI", "https://openai.com/news/rss.xml", "ai"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml", "ai"),
    ("NVIDIA", "https://developer.nvidia.com/blog/feed/", "ai"),
    ("Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss", "ai"),
    ("少数派", "https://sspai.com/feed", "domestic"),
    ("Hacker News", "https://hnrss.org/frontpage", "overseas"),
)

AI_TERMS = (
    "ai", "artificial intelligence", "model", "llm", "agent", "openai",
    "anthropic", "claude", "codex", "gemini", "deepmind", "llama", "gpt",
    "nvidia", "amd", "apple intelligence", "copilot", "developer", "tool",
)
GITHUB_TERMS = ("ai", "agent", "automation", "productivity", "workflow", "llm", "assistant", "tool")
LOW_VALUE_TERMS = (
    "恋情", "绯闻", "离婚", "出轨", "红毯", "票房", "综艺", "明星", "爱豆",
    "粉丝", "塌房", "剧透", "路透", "演唱会", "夺冠庆祝", "颜值", "穿搭",
    "第二季", "电影", "电视剧", "本周看什么", "值得一看的", "演员", "歌手",
)
IMPORTANT_TERMS = (
    "发布", "上线", "开源", "突破", "政策", "监管", "事故", "安全", "召回",
    "融资", "收购", "裁员", "模型", "agent", "codex", "claude", "gpt",
    "gemini", "芯片", "nvidia", "amd", "漏洞", "禁令",
)


@dataclass(frozen=True)
class Item:
    title: str
    link: str
    source: str
    category: str
    summary: str = ""
    why: str = ""
    score: int = 0


def clean_text(value: object, limit: int = 180) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def fetch(url: str, headers: Optional[dict[str, str]] = None, timeout: int = 20) -> bytes:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*"}
    request_headers.update(headers or {})
    req = urllib.request.Request(url, headers=request_headers)
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1)
    raise RuntimeError(f"请求失败: {last_error}")


def get_hot(name: str, route: str, limit: int = 15) -> list[Item]:
    try:
        payload = json.loads(fetch(f"{HOT_API_BASE}/{route}").decode("utf-8"))
        results = []
        for raw in payload.get("data", [])[:limit]:
            title = clean_text(raw.get("title"), 100)
            if title:
                results.append(Item(title, str(raw.get("url") or ""), name, "domestic", clean_text(raw.get("desc") or raw.get("description"))))
        print(f"{name}: 获取 {len(results)} 条")
        return results
    except Exception as exc:
        print(f"{name}: 获取失败（{exc}）")
        return []


def _node_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for child in list(node):
        local_name = child.tag.rsplit("}", 1)[-1]
        if local_name in names and child.text:
            return child.text.strip()
    return ""


def get_rss(name: str, url: str, category: str, limit: int = 12) -> list[Item]:
    try:
        root = ET.fromstring(fetch(url))
        nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] in ("item", "entry")]
        results = []
        for node in nodes[:limit]:
            title = clean_text(_node_text(node, ("title",)), 120)
            link = _node_text(node, ("link",))
            if not link:
                link_node = next((c for c in list(node) if c.tag.rsplit("}", 1)[-1] == "link" and c.attrib.get("href")), None)
                link = link_node.attrib["href"] if link_node is not None else ""
            summary = clean_text(_node_text(node, ("description", "summary", "content")))
            if title:
                results.append(Item(title, link, name, category, summary))
        print(f"{name}: 获取 {len(results)} 条")
        return results
    except Exception as exc:
        print(f"{name}: 获取失败（{exc}）")
        return []


def get_github_projects(limit: int = 12) -> list[Item]:
    since = (datetime.now(timezone.utc) - timedelta(days=21)).date().isoformat()
    # GitHub Search 对多个关键词的 OR 组合支持不稳定；搜索宽泛的 AI，
    # 再根据描述和 topics 做本地筛选，结果更可预测。
    query = f"created:>={since} stars:>=20 ai in:name,description,topics"
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": limit})
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        payload = json.loads(fetch(url, headers=headers).decode("utf-8"))
        projects = []
        for raw in payload.get("items", []):
            topics = raw.get("topics") or []
            description = clean_text(raw.get("description"), 140)
            searchable = f"{raw.get('name', '')} {description} {' '.join(topics)}".lower()
            if not any(term in searchable for term in GITHUB_TERMS):
                continue
            if "agent" in searchable or "assistant" in searchable:
                purpose = "用于构建或运行 AI Agent / 智能助手"
            elif "automation" in searchable or "workflow" in searchable:
                purpose = "用于自动化重复任务和工作流"
            elif "productivity" in searchable:
                purpose = "面向个人或团队的开源效率工具"
            elif "llm" in searchable or "ai" in searchable:
                purpose = "围绕大模型应用、部署或实验提供工具"
            else:
                purpose = "一个新近受到关注的开源实用工具"
            stars = int(raw.get("stargazers_count") or 0)
            summary = f"这是一个{purpose}的项目；可从项目文档查看支持的平台、部署方式和示例。"
            why = f"近三周创建，已获 {stars} stars，早期增长值得观察。" if stars >= 100 else "项目较新，定位贴近日常自动化与开发效率。"
            projects.append(Item(raw.get("full_name", ""), raw.get("html_url", ""), "GitHub", "github", summary, why, 7 + min(stars // 100, 4)))
        print(f"GitHub Search: 获取 {len(projects)} 条")
        return projects
    except Exception as exc:
        print(f"GitHub Search: 获取失败（{exc}）")
        return []


def normalized_title(title: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", title.lower())


def deduplicate(items: list[Item]) -> list[Item]:
    result: list[Item] = []
    for item in items:
        key = normalized_title(item.title)
        if not key or any(key == normalized_title(old.title) or (min(len(key), len(normalized_title(old.title))) >= 8 and SequenceMatcher(None, key, normalized_title(old.title)).ratio() >= 0.76) for old in result):
            continue
        result.append(item)
    return result


def rank_and_enrich(items: list[Item]) -> list[Item]:
    ranked = []
    for item in items:
        haystack = f"{item.title} {item.summary}".lower()
        if item.category == "domestic" and any(term in haystack for term in LOW_VALUE_TERMS):
            continue
        if item.source == "Apple Newsroom" and not any(term in haystack for term in AI_TERMS):
            continue
        score = item.score + (3 if any(term in haystack for term in IMPORTANT_TERMS) else 0)
        if item.category == "ai":
            score += 4 if any(term in haystack for term in AI_TERMS) else 0
        summary = item.summary
        if item.category == "ai":
            if any(term in haystack for term in ("agent", "codex", "developer", "tool", "api")):
                summary = f"{item.source} 官方更新，重点涉及 AI Agent、编程或开发工具能力；产品名保留英文便于检索。"
            elif any(term in haystack for term in ("model", "gpt", "gemini", "llm")):
                summary = f"{item.source} 官方发布模型或能力更新，具体名称保留英文便于查找原文。"
            else:
                summary = f"{item.source} 发布新的 AI 产品、研究或行业动态。"
        elif item.category == "overseas":
            if any(term in haystack for term in AI_TERMS):
                summary = "该话题聚焦 AI 产品或开发生态，正在 Hacker News 技术社区受到讨论。"
            elif "github.com" in item.link:
                summary = "这是 Hacker News 社区正在讨论的开源项目，可从原文查看功能与使用方式。"
            else:
                summary = "这是 Hacker News 当日受到关注的海外技术或产业话题。"
        elif not summary:
            if item.category == "domestic":
                summary = f"该事件进入{item.source}当日榜单，已过滤明显娱乐八卦后保留。"
            else:
                summary = "该话题正在海外技术社区获得较多讨论。"
        why = item.why
        if not why and score >= 3:
            why = "可能影响产品使用、开发工作流或后续行业走向。"
        ranked.append(replace(item, summary=clean_text(summary, 150), why=why, score=score))
    return sorted(deduplicate(ranked), key=lambda x: x.score, reverse=True)


def select_sections(items: list[Item]) -> dict[str, list[Item]]:
    limits = {"domestic": 5, "ai": 5, "github": 4, "overseas": 4}
    return {category: [x for x in items if x.category == category][:limit] for category, limit in limits.items()}


def select_top(sections: dict[str, list[Item]], limit: int = 5) -> list[Item]:
    """头条保持栏目多样性，避免单一高热来源包揽整版。"""
    pool = sorted((item for values in sections.values() for item in values), key=lambda x: x.score, reverse=True)
    counts: dict[str, int] = {}
    result = []
    for item in pool:
        if counts.get(item.category, 0) >= 2:
            continue
        result.append(item)
        counts[item.category] = counts.get(item.category, 0) + 1
        if len(result) == limit:
            break
    return result


def build_message(sections: dict[str, list[Item]]) -> str:
    top = select_top(sections)
    labels = (("今日最值得看", top), ("国内热点", sections["domestic"]), ("AI / 科技", sections["ai"]), ("GitHub 新项目", sections["github"]), ("海外科技", sections["overseas"]))
    parts: list[str] = []
    for label, values in labels:
        if not values:
            continue
        parts.append(f"【{label}】")
        for index, item in enumerate(values, 1):
            parts.append(f"{index}. {item.title}\n{item.summary}")
            if item.why:
                parts.append(f"值得关注：{item.why}")
            if item.link:
                parts.append(item.link)
        parts.append("")
    return "\n".join(parts).strip()


def split_bark_message(body: str, max_bytes: int = BARK_MAX_BODY_BYTES) -> list[str]:
    """按 UTF-8 字节数拆分正文，并尽量保留原有换行边界。"""
    if max_bytes <= 0:
        raise ValueError("Bark 单条消息字节上限必须大于 0")
    if not body:
        return [""]

    chunks: list[str] = []
    current = ""
    current_bytes = 0

    for line in body.splitlines(keepends=True):
        line_bytes = len(line.encode("utf-8"))
        if line_bytes <= max_bytes:
            if current and current_bytes + line_bytes > max_bytes:
                chunks.append(current)
                current = ""
                current_bytes = 0
            current += line
            current_bytes += line_bytes
            continue

        if current:
            chunks.append(current)
            current = ""
            current_bytes = 0
        piece = ""
        piece_bytes = 0
        for character in line:
            character_bytes = len(character.encode("utf-8"))
            if piece and piece_bytes + character_bytes > max_bytes:
                chunks.append(piece)
                piece = ""
                piece_bytes = 0
            piece += character
            piece_bytes += character_bytes
        current = piece
        current_bytes = piece_bytes

    if current:
        chunks.append(current)
    return chunks


def _validate_bark_response(raw: bytes) -> dict[str, object]:
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Bark 返回了无法识别的响应") from exc
    if not isinstance(result, dict) or result.get("code") != 200:
        raise RuntimeError(f"Bark 推送失败: {result}")
    return result


def send_bark(title: str, body: str) -> None:
    bark_url = os.getenv("BARK_URL")
    if not bark_url:
        raise ValueError("没有设置 BARK_URL；请在 GitHub Actions Secrets 中配置")
    chunks = split_bark_message(body)
    for index, chunk in enumerate(chunks, 1):
        chunk_title = title if len(chunks) == 1 else f"{title}（{index}/{len(chunks)}）"
        payload = json.dumps({"title": chunk_title, "body": chunk, "group": "个人信息早报", "level": "active"}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(bark_url, data=payload, headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            result = _validate_bark_response(response.read())
        print(f"Bark {index}/{len(chunks)}: 推送成功（code={result['code']}）")


def collect() -> list[Item]:
    items = []
    for name, route in HOT_SOURCES:
        items.extend(get_hot(name, route))
    for name, url, category in RSS_SOURCES:
        items.extend(get_rss(name, url, category))
    items.extend(get_github_projects())
    return rank_and_enrich(items)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="生成个人信息早报")
    parser.add_argument("--dry-run", action="store_true", help="只输出早报，不发送 Bark")
    args = parser.parse_args(argv)
    sections = select_sections(collect())
    body = build_message(sections)
    if not body:
        body = "今天暂时没有抓到可靠内容，请稍后重试。"
    now = datetime.now(timezone(timedelta(hours=8)))
    title = f"📰 个人信息早报 {now:%m-%d}"
    if args.dry_run:
        print(f"\n{title}\n{body}")
    else:
        send_bark(title, body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
