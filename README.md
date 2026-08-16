# Daily News Bark

每天北京时间 8:00 自动生成一份适合手机阅读的中文个人信息早报，并通过 Bark 推送。

内容分为「今日最值得看、国内热点、AI / 科技、GitHub 新项目、海外科技」。采集失败会按来源隔离，不会因单个 RSS 不可用而中断整份早报。

## 数据源

- 国内：现有 DailyHotApi 的百度热搜、36氪、抖音热点，以及少数派 RSS（不依赖知乎）
- AI / 科技：OpenAI、Google DeepMind、NVIDIA、Apple Newsroom 官方 RSS；Apple 源会再做 AI 关键词过滤，其他重点公司的重大动态也会从技术社区来源进入候选池
- GitHub：GitHub Search API，筛选近 21 天创建且已有一定关注度的 AI、Agent、自动化和效率项目
- 海外：Hacker News RSS

所有筛选均为本地规则，不会把内容或密钥发送给额外的 AI 服务。英文标题会保留产品/项目原名；第一阶段用中文模板和来源摘要解释内容，完整翻译与更高质量摘要留待后续可选的模型增强。

Anthropic 官网当前没有可用的官方 RSS，Microsoft AI 的旧 RSS 已返回 410，因此第一阶段没有硬接无效地址，也没有使用不透明的第三方镜像。

## 配置与运行

仓库只需要一个 GitHub Actions Secret：`BARK_URL`。不要把 Bark 地址写进代码。工作流自带的 `GITHUB_TOKEN` 仅用于提高 GitHub API 限额，无需手动创建。

```bash
# 只抓取并在终端预览，绝不发送 Bark
python main.py --dry-run

# 运行单元测试（不联网、不推送）
python -m unittest -v

# 确认 BARK_URL 已设置后实际推送
python main.py
```

可用 `HOT_API_BASE` 环境变量替换国内热榜服务地址。
