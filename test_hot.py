import urllib.request
import json


BASE_URL = "https://hot.imsyy.top"

SOURCES = {
    "微博": "weibo",
    "知乎": "zhihu",
    "百度": "baidu",
    "36氪": "36kr",
}


def fetch_hot(name, route):
    url = f"{BASE_URL}/{route}"

    try:
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

        print("\n" + "=" * 50)
        print(f"{name}：成功，获取 {len(items)} 条")

        for i, item in enumerate(items[:5], 1):
            title = item.get("title", "")
            hot = item.get("hot", "")
            item_url = item.get("url", "")

            print(f"{i}. {title}")
            print(f"   热度：{hot}")
            print(f"   链接：{item_url}")

    except Exception as e:
        print("\n" + "=" * 50)
        print(f"{name}：获取失败")
        print(f"错误：{e}")


def main():
    for name, route in SOURCES.items():
        fetch_hot(name, route)


if __name__ == "__main__":
    main()
