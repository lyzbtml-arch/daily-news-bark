import urllib.request
import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime, timezone, timedelta


# ===== 你自己的 DailyHotApi 地址 =====
HOT_API_BASE = "https://daily-hot-api-vercel-smoky.vercel.app"


# ===== RSS 新闻源 =====
RSS_SOURCES = [
    {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "limit": 5,
    },
    {
        "name": "少数派",
        "url": "https://sspai.com/feed",
        "limit": 5,
    },
    {
        "name": "GitHub Trending",
        "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml",
        "limit": 5,
    },
]


# ===== 中文热榜 =====
HOT_SOURCES = [
    {
        "name": "百度热搜",
        "route": "baidu",
        "limit": 5,
    },
    {
        "name": "36氪",
        "route": "36kr",
        "limit": 5,
    },
    {
        "name": "抖音热点",
        "route": "douyin",
        "limit": 5,
    },
]


def get_rss(name, url, limit=5):
    results = []

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            data = response.read()

        root = ET.fromstring(data)

        # RSS
        items = root.findall(".//item")

        for item in items[:limit]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()

            if title:
                results.append({
                    "source": name,
                    "title": title,
                    "link": link,
                })

        # Atom
        if not results:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall(".//atom:entry", ns)

            for entry in entries[:limit]:
                title = (
                    entry.findtext(
                        "atom:title",
                        default="",
                        namespaces=ns
                    ) or ""
                ).strip()

                link = ""
                link_node = entry.find("atom:link", ns)

                if link_node is not None:
                    link = link_node.attrib.get("href", "")

                if title:
                    results.append({
                        "source": name,
                        "title": title,
                        "link": link,
                    })

        print(f"{name}: 获取 {len(results)} 条")

    except Exception as e:
        print(f"{name} 获取失败: {e}")

    return results


def get_hot(name, route, limit=5):
    results = []

    try:
        url = f"{HOT_API_BASE}/{route}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")

        data = json.loads(raw)
        items = data.get("data", [])

        for item in items[:limit]:
            title = str(item.get("title", "")).strip()
            link = str(item.get("url", "")).strip()

            if title:
                results.append({
                    "source": name,
                    "title": title,
                    "link": link,
                })

        print(f"{name}: 获取 {len(results)} 条")

    except Exception as e:
        print(f"{name} 获取失败: {e}")

    return results


def remove_duplicates(news):
    seen = set()
    result = []

    for item in news:
        key = item["title"].strip().lower()

        if key and key not in seen:
            seen.add(key)
            result.append(item)

    return result


def send_bark(title, body):
    bark_url = os.environ.get("BARK_URL")

    if not bark_url:
        raise ValueError("没有设置 BARK_URL")

    payload = {
        "title": title,
        "body": body,
        "group": "每日热点",
        "level": "active",
    }

    data = json.dumps(
        payload,
        ensure_ascii=False
    ).encode("utf-8")

    req = urllib.request.Request(
        bark_url,
        data=data,
        headers={
            "Content-Type": "application/json; charset=utf-8"
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        result = response.read().decode("utf-8")
        print("Bark:", result)


def build_message(news):
    grouped = {}

    for item in news:
        grouped.setdefault(
            item["source"],
            []
        ).append(item)

    emoji_map = {
        "百度热搜": "🔎",
        "36氪": "💰",
        "抖音热点": "🎵",
        "GitHub Trending": "🔥",
        "Hacker News": "🌍",
        "少数派": "💻",
    }

    parts = []

    order = [
        "百度热搜",
        "抖音热点",
        "36氪",
        "GitHub Trending",
        "Hacker News",
        "少数派",
    ]

    for source in order:
        items = grouped.get(source, [])

        if not items:
            continue

        emoji = emoji_map.get(source, "📰")
        parts.append(f"{emoji} {source}")

        for i, item in enumerate(items, 1):
            parts.append(f"{i}. {item['title']}")

            if item["link"]:
                parts.append(item["link"])

        parts.append("")

    return "\n".join(parts)


def main():
    all_news = []

    # 中文热榜
    for source in HOT_SOURCES:
        all_news.extend(
            get_hot(
                source["name"],
                source["route"],
                source["limit"],
            )
        )

    # RSS
    for source in RSS_SOURCES:
        all_news.extend(
            get_rss(
                source["name"],
                source["url"],
                source["limit"],
            )
        )

    all_news = remove_duplicates(all_news)

    if not all_news:
        send_bark(
            "每日热点",
            "今天暂时没有抓到新闻。"
        )
        return

    china_time = timezone(
        timedelta(hours=8)
    )

    now = datetime.now(china_time)

    title = f"📰 每日热点 {now.strftime('%m-%d')}"
    body = build_message(all_news)

    send_bark(title, body)


if __name__ == "__main__":
    main()
