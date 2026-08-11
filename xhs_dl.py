#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xiaohongshu Downloader · 小红书图文/视频下载器
==============================================
基于"登录态 Cookie + 页面 SSR 数据"解析，下载笔记原图与视频。
需要你自己从浏览器复制登录 Cookie（见 README 教程），仅保存在本机。

原理：
  1. 解析分享链接 / 短链 xhslink.com / 任意分享文案
  2. 用带登录 Cookie 的会话请求 explore 页面
  3. 提取 window.__INITIAL_STATE__ 内嵌 JSON
  4. 下载原图 / 视频流（多候选地址自动回退）

⚠️ 仅用于学习研究及个人合理使用，请遵守小红书社区规范，尊重创作者版权。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖 requests，请先执行:  pip install requests\nMissing dependency requests, run:  pip install requests")

# Windows 下 stdout 可能是 GBK，含 ✓ 等字符时管道重定向会崩溃；统一 UTF-8 + 容错
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__version__ = "2.0.0"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

ID_RE = re.compile(r"(?:explore|discovery/item|item)/([0-9a-zA-Z]{20,})")
URL_RE = re.compile(
    r"https?://(?:xhslink\.com/\S+|www\.xiaohongshu\.com/(?:explore|discovery/item)/\S+)", re.I
)
SHARE_HTTP_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>", re.S)

# ---------- i18n（中文 / English） ----------
_ZH = {
    "proj": "小红书下载器",
    "parsing": "解析链接",
    "resolve_fail": "无法解析笔记 id，链接可能已失效或被删",
    "no_link": "未在输入中找到小红书链接",
    "no_cookie": "未读取到有效 Cookie。请在浏览器登录小红书后复制 Cookie（见 README），或写入 cookie.txt / 使用 --gui 粘贴",
    "cookie_loaded": "Cookie 加载: {n} 个键",
    "page_fail": "请求失败: {e}（可稍后重试）",
    "no_state": "页面未包含数据，可能未登录、被风控拦截或需要验证码",
    "bad_json": "解析页面数据失败",
    "dead_note": "该笔记不存在、已删除或为私密/不可见内容",
    "note_info": "《{title}》 by {author}",
    "video_saved": "视频已保存: {path}",
    "album_saved": "已保存 {ok}/{total} 张 → {dir}",
    "img_saved": "图片{i}",
    "unknown_type": "未识别到图文或视频内容",
    "download_fail": "第 {n} 次下载失败: {e}",
    "empty_file": "空文件（可能 UA 不对或被限流）",
    "batch_mode": "批量模式: {n} 条链接",
    "batch_item": "[{i}/{total}]",
    "batch_ratio": "成功 {ok}/{total}",
    "rate_limit": "已暂停 {s}s 避免触发风控",
    "proxy_hint": "提示：检测到代理环境变量 {k}，如解析失败请尝试清除后重试",
    "clipboard_hint": "已从剪贴板读取链接",
    "clipboard_empty": "剪贴板中没有可用的链接",
    "gui_no_tk": "当前 Python 环境缺少 tkinter，无法启动图形界面；请安装带 tk 的 Python 或改用命令行。",
    "gui_title": "小红书下载器 v{ver}",
    "gui_link": "笔记链接 / 分享文案",
    "gui_cookie": "登录 Cookie（浏览器 F12 → Network → 请求 Headers → Cookie，整段粘贴）",
    "gui_cookie_hint": "Cookie 仅保存在本机配置文件，不会上传",
    "gui_out": "保存目录",
    "gui_browse": "浏览…",
    "gui_download": "下载",
    "gui_paste": "粘贴剪贴板",
    "gui_downloading": "下载中，请稍候…",
    "gui_ok": "完成",
    "ok": "OK",
}
_EN = {
    "proj": "Xiaohongshu Downloader",
    "parsing": "Resolving link",
    "resolve_fail": "Cannot resolve note id; the link may be expired or removed",
    "no_link": "No Xiaohongshu link found in the input",
    "no_cookie": "No valid Cookie found. Log in on xiaohongshu.com and copy your Cookie (see README), or write cookie.txt / paste via --gui",
    "cookie_loaded": "Cookie loaded: {n} key(s)",
    "page_fail": "Request failed: {e} (retry later)",
    "no_state": "Page contains no data; maybe not logged in, blocked, or a captcha is required",
    "bad_json": "Failed to parse page data",
    "dead_note": "This note does not exist, was removed, or is private / not visible",
    "note_info": "{title} by {author}",
    "video_saved": "Video saved: {path}",
    "album_saved": "Saved {ok}/{total} image(s) → {dir}",
    "img_saved": "img{i}",
    "unknown_type": "Could not recognize any image or video content",
    "download_fail": "Attempt {n} failed: {e}",
    "empty_file": "Empty file (wrong UA or rate limited)",
    "batch_mode": "Batch mode: {n} link(s)",
    "batch_item": "[{i}/{total}]",
    "batch_ratio": "Success {ok}/{total}",
    "rate_limit": "Pausing {s}s to avoid risk control",
    "proxy_hint": "Hint: proxy env {k} detected; clear it if requests fail",
    "clipboard_hint": "Read link from clipboard",
    "clipboard_empty": "No usable link in clipboard",
    "gui_no_tk": "tkinter is not available; install Python with tk support or use the CLI.",
    "gui_title": "Xiaohongshu Downloader v{ver}",
    "gui_link": "Note link / share text",
    "gui_cookie": "Login Cookie (browser F12 → Network → request Headers → Cookie; paste the whole value)",
    "gui_cookie_hint": "Cookie is stored locally only and never uploaded",
    "gui_out": "Output folder",
    "gui_browse": "Browse…",
    "gui_download": "Download",
    "gui_paste": "Paste clipboard",
    "gui_downloading": "Downloading, please wait…",
    "gui_ok": "Done",
    "ok": "OK",
}


def t(lang: str, key: str, **kw) -> str:
    """按语言取文案（zh / en）。"""
    table = _ZH if lang == "zh" else _EN
    s = table.get(key, key)
    return s.format(**kw) if kw else s


def detect_lang(arg_lang: Optional[str]) -> str:
    if arg_lang:
        return arg_lang
    env = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    if env:
        return "zh" if env.startswith("zh") else "en"
    try:
        import locale
        loc = (locale.getdefaultlocale()[0] or "").lower()
    except Exception:
        loc = ""
    return "zh" if loc.startswith("zh") else "en"


# ---------- 配置持久化 ----------
CONFIG_PATH = Path.home() / ".xhs_dl_config.json"


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


# ---------- 基础工具 ----------
def sanitize_name(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip().strip(".")
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = "xiaohongshu"
    return name[:max_len]


def parse_cookie(cookie_str: str) -> dict:
    """把浏览器复制的 Cookie 字符串解析为 dict。"""
    out = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _clean_url(u: str) -> str:
    return u.rstrip("/").rstrip(")").rstrip("，。；！…）\"")


def extract_url(text: str) -> Optional[str]:
    """从任意文本中提取小红书链接。"""
    m = URL_RE.search(text)
    if m:
        return _clean_url(m.group(0))
    m = SHARE_HTTP_RE.search(text)
    return _clean_url(m.group(0)) if m else None


def resolve_note_id(url: str, session: requests.Session) -> Optional[str]:
    """从链接解析笔记 id（支持短链重定向）。"""
    if url.startswith("http"):
        m = ID_RE.search(url)
        if m:
            return m.group(1)
        try:
            r = session.get(url, headers={"User-Agent": UA}, allow_redirects=True, timeout=(8, 15))
            m = ID_RE.search(r.url or url)
            if m:
                return m.group(1)
        except requests.RequestException:
            pass
    return None


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / 1048576:.1f}MB"
    return f"{n / 1024:.0f}KB"


def _fmt_eta(secs: float) -> str:
    if secs >= 3600:
        return f"{secs / 3600:.1f}h"
    if secs >= 60:
        return f"{secs / 60:.0f}m{secs % 60:02.0f}s"
    return f"{secs:.0f}s"


RETRY_DELAY = 2.0  # 下载失败重试的等待基数（秒），测试可置 0


def download(url: str, dest: Path, session: requests.Session, label: str = "",
             log: Callable[[str], None] = print, quiet: bool = False) -> bool:
    """下载到 dest，带进度（百分比/速度/剩余时间）与重试。"""
    if not url.startswith("http"):
        return False
    for attempt in range(3):
        try:
            with session.get(url, headers={"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"},
                             stream=True, timeout=(10, 90)) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                t0 = time.time()
                last_pct = -10
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 16):
                        if not chunk:
                            continue
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            pct = done * 100 // total
                            if pct >= last_pct + 2 or done >= total:
                                last_pct = pct
                                elapsed = time.time() - t0
                                speed = done / elapsed if elapsed > 0 else 0
                                eta = _fmt_eta((total - done) / speed) if speed > 0 else "-"
                                line = (f"\r  {label} {pct:3d}% {_fmt_size(done)}/{_fmt_size(total)} "
                                        f"{speed / 1048576:.1f}MB/s ETA {eta}")
                                if quiet:
                                    log(line + "\n")
                                else:
                                    sys.stdout.write(line)
                                    sys.stdout.flush()
                if not quiet:
                    sys.stdout.write("\r" + " " * 70 + "\r")
                if os.path.getsize(dest) == 0:
                    raise ValueError("empty file")
                return True
        except (requests.RequestException, ValueError) as e:
            log(f"  [!] {t('zh', 'download_fail', n=attempt + 1, e=e)}")
            time.sleep(RETRY_DELAY * (attempt + 1))
    return False


def download_candidates(urls: list, dest: Path, session: requests.Session, label: str = "",
                        log: Callable[[str], None] = print, quiet: bool = False) -> bool:
    """按顺序尝试多个候选地址，全部失败才返回 False。"""
    if not urls:
        return False
    for i, u in enumerate(urls):
        ok = download(u, dest, session, label=f"{label}#{i + 1}" if i else label, log=log, quiet=quiet)
        if ok:
            return True
    return False


# ---------- 页面解析 ----------
def fetch_note_page(note_id: str, session: requests.Session) -> str:
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    r = session.get(url, headers={"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"}, timeout=(8, 20))
    r.raise_for_status()
    return r.text


class XhsError(RuntimeError):
    """带原因 key 的小红书解析异常。"""

    def __init__(self, reason: str, message: str = ""):
        super().__init__(message or reason)
        self.reason = reason


def parse_state(html: str) -> dict:
    """提取 __INITIAL_STATE__ 并返回笔记详情；不存在/已删除抛 XhsError。"""
    m = STATE_RE.search(html)
    if not m:
        raise XhsError("no_state")
    try:
        state = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise XhsError("bad_json", str(e))

    note_map = (state.get("note", {}) or {}).get("noteDetailMap", {}) or {}
    for note in note_map.values():
        if isinstance(note, dict):
            detail = note.get("note")
            if isinstance(detail, dict) and detail:
                return detail
    raise XhsError("dead" if note_map else "no_state")


def extract_content(detail: dict) -> dict:
    """从笔记详情提取标题/作者/图片/视频（含多候选地址）。"""
    info = {"type": "images", "title": "", "author": "", "images": [], "video": None, "video_candidates": []}
    info["title"] = (detail.get("title") or detail.get("desc") or "").strip()
    user = detail.get("user") or {}
    info["author"] = (user.get("nickname") or "").strip()
    img_list = detail.get("imageList") or []
    if img_list:
        for im in img_list:
            if not isinstance(im, dict):
                continue
            url = im.get("urlDefault") or im.get("url") or (im.get("info_list") or [{}])[0].get("url")
            if url:
                info["images"].append(url)
    video = detail.get("video")
    if isinstance(video, dict):
        media = video.get("media") or {}
        stream = media.get("stream") or {}
        h264 = stream.get("h264") or []
        cands = []
        if h264:
            first = h264[0]
            for k in ("masterUrl", "master_url"):
                v = first.get(k)
                if isinstance(v, str) and v.startswith("http") and v not in cands:
                    cands.append(v)
            for k in ("backupUrls", "backup_urls", "backupUrl"):
                for v in (first.get(k) or []):
                    if isinstance(v, str) and v.startswith("http") and v not in cands:
                        cands.append(v)
        if not cands and video.get("src"):
            cands.append(video["src"])
        info["video_candidates"] = cands
        info["video"] = cands[0] if cands else None
    if info["video"]:
        info["type"] = "video"
    elif info["images"]:
        info["type"] = "images"
    return info


def _img_ext(url: str) -> str:
    path = url.split("?")[0]
    ext = Path(path).suffix.lower()
    if ext and len(ext) <= 5 and ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic", ".bmp"):
        return ext
    return ".jpg"


# ---------- 单个笔记处理 ----------
def download_note(url: str, out_dir: Path, session: requests.Session, lang: str,
                  log: Callable[[str], None] = print) -> Optional[dict]:
    """下载单个笔记，返回摘要。"""
    quiet = log is not print
    url = extract_url(url) or url
    log(f"  [*] {t(lang, 'parsing')}: {url[:80]}")
    note_id = resolve_note_id(url, session)
    if not note_id:
        log(f"  [!] {t(lang, 'resolve_fail')}")
        return None
    log(f"  [*] note: {note_id}")

    html = None
    for attempt in range(3):
        try:
            html = fetch_note_page(note_id, session)
            break
        except requests.RequestException as e:
            if attempt == 2:
                log(f"  [!] {t(lang, 'page_fail', e=e)}")
                return None
            time.sleep(2 * (attempt + 1))
    try:
        detail = parse_state(html)
    except XhsError as e:
        if e.reason == "dead":
            log(f"  [!] {t(lang, 'dead_note')}")
        elif e.reason == "bad_json":
            log(f"  [!] {t(lang, 'bad_json')}")
        else:
            log(f"  [!] {t(lang, 'no_state')}")
        return None

    info = extract_content(detail)
    base = sanitize_name(f"{info['author']}_{info['title']}") or note_id
    folder = out_dir / base
    folder.mkdir(parents=True, exist_ok=True)
    log(f"  [*] {t(lang, 'note_info', title=info['title'][:40] or '(无标题)', author=info['author'] or '未知')}")

    if info["type"] == "video":
        video_name = Path(info["video_candidates"][0].split("?")[0]).name if info["video_candidates"] else ""
        dest = folder / (video_name if video_name.endswith((".mp4", ".m4s", ".ts")) else "video.mp4")
        if download_candidates(info["video_candidates"], dest, session,
                               label="视频" if lang == "zh" else "video", log=log, quiet=quiet):
            log(f"  [✓] {t(lang, 'video_saved', path=dest)}")
        else:
            log(f"  [!] {t(lang, 'unknown_type')}")
            return None
    elif info["images"]:
        ok = 0
        for i, u in enumerate(info["images"], 1):
            if download(u, folder / f"{i:02d}{_img_ext(u)}", session,
                        label=t(lang, "img_saved", i=i), log=log, quiet=quiet):
                ok += 1
        log(f"  [✓] {t(lang, 'album_saved', ok=ok, total=len(info['images']), dir=folder)}")
        if ok == 0:
            return None
    else:
        log(f"  [!] {t(lang, 'unknown_type')}")
        return None

    (folder / "info.json").write_text(json.dumps({
        "title": info["title"], "author": info["author"], "note_id": note_id,
        "url": f"https://www.xiaohongshu.com/explore/{note_id}", "type": info["type"]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return {"note_id": note_id, "title": info["title"], "author": info["author"],
            "type": info["type"], "dir": str(folder)}


def get_clipboard() -> Optional[str]:
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception:
        return None


def make_session(cookie: dict) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept-Language": "zh-CN,zh;q=0.9"})
    session.cookies.update(cookie)
    return session


# ---------- 图形界面 ----------
def run_gui(lang: str) -> int:
    try:
        import queue
        import tkinter as tk
        from tkinter import filedialog, scrolledtext
    except ImportError:
        print(t(lang, "gui_no_tk"))
        return 1

    cfg = load_config()
    root = tk.Tk()
    root.title(t(lang, "gui_title", ver=__version__))
    root.geometry("680x640")
    root.minsize(600, 500)

    q = queue.Queue()

    tk.Label(root, text=t(lang, "gui_link")).pack(anchor="w", padx=12, pady=(12, 2))
    link_entry = tk.Entry(root)
    link_entry.pack(fill="x", padx=12)
    link_entry.insert(0, get_clipboard() or "")

    tk.Label(root, text=t(lang, "gui_cookie")).pack(anchor="w", padx=12, pady=(10, 2))
    cookie_box = scrolledtext.ScrolledText(root, height=5, wrap="char")
    cookie_box.pack(fill="x", padx=12)
    cookie_box.insert("1.0", cfg.get("cookie", ""))
    tk.Label(root, text=t(lang, "gui_cookie_hint"), fg="#888").pack(anchor="w", padx=12, pady=(2, 0))

    tk.Label(root, text=t(lang, "gui_out")).pack(anchor="w", padx=12, pady=(10, 2))
    out_row = tk.Frame(root)
    out_row.pack(fill="x", padx=12)
    out_entry = tk.Entry(out_row)
    out_entry.pack(side="left", fill="x", expand=True)
    out_entry.insert(0, cfg.get("output", "downloads"))

    def browse():
        d = filedialog.askdirectory()
        if d:
            out_entry.delete(0, tk.END)
            out_entry.insert(0, d)
    tk.Button(out_row, text=t(lang, "gui_browse"), command=browse).pack(side="left", padx=(6, 0))

    btn = tk.Button(root, text=t(lang, "gui_download"), width=18)
    btn.pack(pady=10)
    log_box = scrolledtext.ScrolledText(root, height=12, state="disabled", wrap="word")
    log_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def append(msg):
        log_box.configure(state="normal")
        log_box.insert(tk.END, msg + "\n")
        log_box.see(tk.END)
        log_box.configure(state="disabled")

    def worker(text, out_str, cookie_raw):
        def log(msg):
            print(msg)
            q.put(msg)
        try:
            cookie = parse_cookie(cookie_raw)
            if not cookie:
                q.put(f"[!] {t(lang, 'no_cookie')}")
                return
            save_config({"output": out_str, "cookie": cookie_raw})
            session = make_session(cookie)
            info = download_note(text, Path(out_str), session, lang=lang, log=log)
            if info:
                q.put(f"[✓] {t(lang, 'gui_ok')}: {info['dir']}")
        except Exception as e:
            q.put(f"[!] {e}")
        finally:
            q.put("__DONE__")

    def on_download():
        text = link_entry.get().strip()
        if not text:
            text = get_clipboard() or ""
        if not text:
            append(f"[!] {t(lang, 'clipboard_empty')}")
            return
        btn.configure(state="disabled", text=t(lang, "gui_downloading"))
        out_str = out_entry.get().strip() or "downloads"
        cookie_raw = cookie_box.get("1.0", tk.END).strip()
        import threading
        threading.Thread(target=worker, args=(text, out_str, cookie_raw), daemon=True).start()

    def poll():
        try:
            while True:
                m = q.get_nowait()
                if m == "__DONE__":
                    btn.configure(state="normal", text=t(lang, "gui_download"))
                else:
                    append(m)
        except queue.Empty:
            pass
        root.after(100, poll)

    btn.configure(command=on_download)
    root.after(100, poll)
    root.mainloop()
    return 0


# ---------- 命令行入口 ----------
def arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="xhs_dl",
        description=f"小红书图文/视频下载器 v{__version__} · Xiaohongshu downloader（需要登录 Cookie，仅供学习使用）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("input", nargs="?", help="笔记链接 / xhslink 短链 / 含链接的 txt 文件")
    ap.add_argument("-c", "--cookie", default=None,
                    help="Cookie：cookie.txt 文件，或直接粘贴 Cookie 字符串（默认取配置/配置文件）")
    ap.add_argument("-o", "--output", default=None, help="保存目录 (默认 downloads，记住上次选择)")
    ap.add_argument("-b", "--batch", action="store_true", help="输入是 txt 文件，每行一条链接")
    ap.add_argument("--clipboard", action="store_true", help="从系统剪贴板读取链接")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON 摘要")
    ap.add_argument("--lang", choices=["zh", "en"], default=None, help="界面语言 (默认自动)")
    ap.add_argument("--gui", action="store_true", help="启动图形界面")
    ap.add_argument("--no-config", action="store_true", help="不使用配置文件记住上次设置")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return ap


def main():
    ap = arg_parser()
    args = ap.parse_args()

    lang = detect_lang(args.lang)

    if args.gui:
        return run_gui(lang)

    if args.clipboard:
        args.input = get_clipboard() or args.input
        if args.input:
            print(f"  [i] {t(lang, 'clipboard_hint')}")
        else:
            print(f"  [!] {t(lang, 'clipboard_empty')}")

    if not args.input:
        ap.print_help()
        return 1

    cfg = load_config()
    out_str = args.output or ("" if args.no_config else cfg.get("output")) or "downloads"
    out_dir = Path(out_str)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Cookie 加载优先级：命令行 > cookie.txt 默认文件 > 配置
    cookie_raw = args.cookie
    if cookie_raw is None and not args.no_config:
        cookie_raw = cfg.get("cookie")
    if cookie_raw is None and Path("cookie.txt").exists():
        cookie_raw = Path("cookie.txt").read_text(encoding="utf-8").strip()
    if cookie_raw is None:
        cookie_raw = ""
    if os.path.isfile(cookie_raw):
        cookie_raw = Path(cookie_raw).read_text(encoding="utf-8").strip()
    cookie = parse_cookie(cookie_raw)
    if not cookie:
        sys.exit(t(lang, "no_cookie"))
    print(f"  [i] {t(lang, 'cookie_loaded', n=len(cookie))}")
    if not args.no_config:
        save_config({"output": str(out_dir), "cookie": cookie_raw, "lang": lang})

    session = make_session(cookie)
    for k in ("ALL_PROXY", "all_proxy"):
        if os.environ.get(k):
            print(f"  [i] {t(lang, 'proxy_hint', k=k)}")

    if args.batch:
        urls = [l.strip() for l in Path(args.input).read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"[*] {t(lang, 'batch_mode', n=len(urls))}")
        results, ok = [], 0
        for i, u in enumerate(urls, 1):
            print(t(lang, "batch_item", i=i, total=len(urls)))
            r = download_note(u, out_dir, session, lang=lang)
            if r:
                results.append(r)
                ok += 1
            if i < len(urls):
                sleep = 1.5
                print(f"  [i] {t(lang, 'rate_limit', s=sleep)}")
                time.sleep(sleep)
        print(f"[*] {t(lang, 'batch_ratio', ok=ok, total=len(urls))}")
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        r = download_note(args.input, out_dir, session, lang=lang)
        if args.json and r:
            print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n已取消 / Canceled")
        sys.exit(130)
