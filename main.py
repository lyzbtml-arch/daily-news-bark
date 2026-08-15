import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import os
import json
from datetime import datetime


# ===== 新闻源 =====
RSS_SOURCES = {
    "Hacker News": "https://hnrss.org/frontpage",
    "少数派": "https://sspai.com/feed",
}


def get_rss(name, url, limit=5):
    """读取 RSS，返回前几条新闻"""
    results = []

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read()

        root = ET.fromstring(data)

        for item in root.findall(".//item")[:limit]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()

            if title:
                results.append({
                    "source": name,
                    "title": title,
                    "link": link
                })

    except Exception as e:
        print(f"{name} 获取失败: {e}")

    return results


def send_bark(title, body):
    """发送 Bark 通知"""
    bark_url = os.environ.get("BARK_URL")

    if not bark_url:
        raise ValueError("没有设置 BARK_URL")

    payload = {
        "title": title,
        "body": body,
        "group": "每日热点"
    }

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        bark_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        print(response.read().decode("utf-8"))


def main():
    news = []

    for name, url in RSS_SOURCES.items():
        news.extend(get_rss(name, url))

    if not news:
        send_bark("每日热点", "今天暂时没有抓到新闻。")
        return

    lines = []

    for i, item in enumerate(news, 1):
        lines.append(
            f"{i}. [{item['source']}] {item['title']}\n{item['link']}"
        )

    today = datetime.now().strftime("%Y-%m-%d")

    body = "\n\n".join(lines)

    send_bark(
        f"📰 每日热点 {today}",
        body
    )


if __name__ == "__main__":
    main()
