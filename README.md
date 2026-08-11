# 🔴 小红书下载器 · Xiaohongshu Downloader

> 下载小红书**图文原图**与**视频**，无需安装任何额外依赖（只需 `requests`）。
> 基于你浏览器登录态的 Cookie 解析页面数据，你**自己的账号能看的笔记**就能下。
> 支持 **图形界面**、**下载进度（速度/剩余时间）**、**多候选视频流回退**、**剪贴板一键下载**。

```bash
python xhs_dl.py "https://www.xiaohongshu.com/explore/xxxxxxx"
# 或双击 xhs_gui.bat 打开图形界面
```

## ✨ 功能特性

- ✅ **图形界面**：`--gui` 或双击 `xhs_gui.bat`（tkinter，界面内直接粘贴 Cookie + 链接 + 选保存目录）
- ✅ **图文原图**：自动按顺序下载笔记全部原图（webp / jpg 原始图）
- ✅ **视频下载**：解析最高清视频流保存为 MP4，**主源失效自动切换备用流**
- ✅ **下载进度**：百分比 + 速度（MB/s）+ 剩余时间（ETA），失败自动重试
- ✅ **剪贴板**：`--clipboard` 一键读取系统剪贴板里的链接
- ✅ **短链支持**：自动解析 `xhslink.com` 分享短链
- ✅ **批量下载**：txt 每行一条链接，自动限速防封
- ✅ **死链友好提示**：笔记已删除 / 私密 / 未登录 / 被风控各有明确提示
- ✅ **配置记忆**：记住上次的保存目录与 Cookie（仅存本机 `~/.xhs_dl_config.json`）
- ✅ **元数据导出**：每篇笔记自动生成 `info.json`（标题/作者/原链接）
- ✅ **双语界面**：`--lang zh|en`（默认按系统区域自动选择）
- ✅ 仅依赖 `requests`，Windows / macOS / Linux 通用

## 📦 安装

```bash
pip install requests
```

## 🚀 使用

### 第一步：获取你的 Cookie（约 30 秒）

小红书必须登录才能看图看视频，工具需要借用你**自己浏览器里的登录态**：

1. 用电脑浏览器（Chrome / Edge）打开 [xiaohongshu.com](https://www.xiaohongshu.com) 并**登录**
2. 按 `F12` 打开开发者工具 → 切到 **Network（网络）** 标签
3. 刷新页面，点任意一条请求（如 `explore`）→ **Headers** → 找到 **Request Headers** 里的 **Cookie** 一项
4. 右键 Cookie 的值 → **Copy value（复制值）**，粘贴到同目录下的 `cookie.txt` 文件保存（或使用 GUI 直接粘贴）

> 🔒 Cookie 只在你的本机使用，不会上传到任何服务器。退出登录后需重新复制。

### 图形界面

```bash
python xhs_dl.py --gui
# 或双击 xhs_gui.bat
```

界面里直接粘贴链接 + Cookie 即可，Cookie 与目录会自动记住。

### 单篇下载

```bash
python xhs_dl.py "https://www.xiaohongshu.com/explore/笔记ID"
# 或粘贴分享短链 / 带链接的整段文字
python xhs_dl.py "我在小红书看到了 https://xhslink.com/xxx 分享给你"
# 或从剪贴板
python xhs_dl.py --clipboard
```

### 批量下载

```bash
# links.txt 每行一条链接
python xhs_dl.py links.txt -b
```

### 更多选项

```bash
python xhs_dl.py "<链接>" -o ./out        # 指定保存目录
python xhs_dl.py "<链接>" -c "a1=xxx; webId=yyy; ..."   # 直接粘贴 Cookie 字符串
python xhs_dl.py "<链接>" --json          # JSON 输出
python xhs_dl.py "<链接>" --lang en       # English UI
```

## 📂 输出结构

```
downloads/
└── 作者昵称_笔记标题/
    ├── 01.webp / 02.webp …    (图文原图)
    └── video.mp4               (视频笔记)
    └── info.json               (标题/作者/原链接)
```

## 🔧 工作原理

1. 解析链接（短链 `xhslink.com` 自动跟随重定向）
2. 用带登录 Cookie 的会话请求 `explore/<id>` 页面
3. 提取 `window.__INITIAL_STATE__` 内嵌 JSON，定位笔记详情
4. 图文：下载 `imageList` 全部原图；视频：取最高清 h264 流（含备用流多候选回退）
5. 每篇笔记写 `info.json` 元数据

## ⚠️ 免责声明

本工具**仅用于学习研究及个人合理使用**（如备份自己收藏过的公开笔记）。

- 请遵守您所在国家/地区的法律法规及小红书社区规范，**尊重创作者版权**。
- 请勿将本工具用于任何**商业用途**、**侵权用途**，或批量抓取、再分发他人内容。
- 使用本工具产生的任何风险与法律责任由使用者自行承担。
- 如内容侵犯了您的合法权益，请联系我们，我们将第一时间移除相关链接与内容。

## ☕ 支持作者

如果这个工具帮到了你，欢迎扫码赞赏支持，让我有动力持续更新下去～

<img src="assets/donate.png" alt="赞赏码" width="200">

## 📚 更多工具 More Tools

> 我做的所有免费工具与智能体都在这：[qgeng1465](https://github.com/qgeng1465) · 全部开源、本地优先、即装即用。

| 类别 | 项目 |
|---|---|
| ✈️ 可视化 | [飞行足迹 3D](https://github.com/qgeng1465/flight-trajectory-visualizer) · [TS→MP4](https://github.com/qgeng1465/ts-to-mp4-converter) · [MP4转换](https://github.com/qgeng1465/mp4-converter) · [音频工具箱](https://github.com/qgeng1465/audio-toolbox) |
| 🎬 下载 | [抖音](https://github.com/qgeng1465/douyin-watermark-free-downloader) · [TikTok](https://github.com/qgeng1465/tiktok-watermark-free-downloader) · [B站](https://github.com/qgeng1465/bilibili-video-downloader) · [YouTube](https://github.com/qgeng1465/youtube-downloader) · [小红书](https://github.com/qgeng1465/xiaohongshu-downloader) · [公众号](https://github.com/qgeng1465/wechat-article-exporter) · [直播录制](https://github.com/qgeng1465/LiveRecorder) |
| 🧬 AI 智能体 | [AI4Bio](https://github.com/qgeng1465/ai4bio-agents) · [AI4Chem](https://github.com/qgeng1465/ai4chem-agents) · [AI4科研](https://github.com/qgeng1465/ai4research-agents) · [日常生活](https://github.com/qgeng1465/daily-agents) |

## 📄 License

[MIT](./LICENSE) © 2026 qgeng1465
