import json
import unittest
from unittest.mock import patch

import main


class DailyBriefTests(unittest.TestCase):
    def test_hot_parser(self):
        payload = {"data": [{"title": "重要政策发布", "url": "https://example.com", "desc": "政策摘要"}]}
        with patch("main.fetch", return_value=json.dumps(payload).encode()):
            item = main.get_hot("百度热搜", "baidu")[0]
        self.assertEqual(item.category, "domestic")
        self.assertEqual(item.summary, "政策摘要")

    def test_filters_gossip_and_near_duplicates(self):
        items = [
            main.Item("某明星恋情曝光", "a", "百度热搜", "domestic"),
            main.Item("OpenAI 发布新模型 GPT-6", "b", "OpenAI", "ai"),
            main.Item("OpenAI发布全新模型GPT-6", "c", "Hacker News", "overseas"),
        ]
        result = main.rank_and_enrich(items)
        self.assertEqual(len(result), 1)
        self.assertIn("GPT-6", result[0].title)

    def test_mobile_format(self):
        item = main.Item("示例标题", "https://example.com", "OpenAI", "ai", "中文摘要。", "很重要。", 8)
        message = main.build_message(main.select_sections([item]))
        self.assertIn("【今日最值得看】", message)
        self.assertIn("【AI / 科技】", message)
        self.assertIn("值得关注：很重要。", message)

    def test_top_is_diverse(self):
        sections = {
            "domestic": [main.Item("国内", "", "百度", "domestic", score=5)],
            "ai": [main.Item(f"AI{i}", "", "OpenAI", "ai", score=10 - i) for i in range(4)],
            "github": [main.Item("项目", "", "GitHub", "github", score=6)],
            "overseas": [],
        }
        top = main.select_top(sections)
        self.assertEqual(sum(item.category == "ai" for item in top), 2)
        self.assertEqual({item.category for item in top}, {"ai", "domestic", "github"})

    def test_dry_run_never_sends_bark(self):
        with patch("main.collect", return_value=[]), patch("main.send_bark") as sender:
            self.assertEqual(main.main(["--dry-run"]), 0)
        sender.assert_not_called()


if __name__ == "__main__":
    unittest.main()
