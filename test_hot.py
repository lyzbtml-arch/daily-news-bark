import urllib.request
import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime, timezone, timedelta


# ===== 新闻源 =====
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
        "name": "36氪",
        "url": "https://36kr.com/feed",
        "limit": 5,
    },
    {
        "name": "GitHub Trending",
        "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml",
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

        # Atom 格式兼容
        if not results:
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall(".//atom:entry", ns)

            for entry in entries[:limit]:
                title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()

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


def remove_duplicates(news):
    seen = set()
    result = []

    for item in news:
        key = item["title"].strip().lower()

        if key not in seen:
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

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        bark_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        result = response.read().decode("utf-8")
        print("Bark:", result)


def build_message(news):
    grouped = {}

    for item in news:
        grouped.setdefault(item["source"], []).append(item)

    parts = []

    emoji_map = {
        "Hacker News": "🌍",
        "少数派": "💻",
        "36氪": "🇨🇳",
        "GitHub Trending": "🔥",
    }

    for source, items in grouped.items():
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
        send_bark("每日热点", "今天暂时没有抓到新闻。")
        return

    china_time = timezone(timedelta(hours=8))
    now = datetime.now(china_time)

    title = f"📰 每日热点 {now.strftime('%m-%d')}"
    body = build_message(all_news)

    send_bark(title, body)


if __name__ == "__main__":
    main()
