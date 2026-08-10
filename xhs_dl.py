#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Xiaohongshu Downloader · 小红书图文/视频下载器
==============================================
基于"登录态 Cookie + 页面 SSR 数据"解析，下载笔记原图与视频。
需要你自己从浏览器复制登录 Cookie（见 README 教程），仅保存在本机。

⚠️ 仅用于学习研究及个人合理使用，请遵守小红书社区规范，尊重创作者版权。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# Windows 控制台 UTF-8 健壮性
for _s in (sys.stdout, sys.stderr):
    try:
        if getattr(_s, "encoding", "").lower() not in ("utf-8", "utf8"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__version__ = "1.0.0"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

ID_RE = re.compile(r"(?:explore|discovery/item|item)/([0-9a-zA-Z]{20,})")
SHORT_RE = re.compile(r"https?://xhslink\.com/\S+|https?://www\.xiaohongshu\.com/discovery/item/\S+|https?://www\.xiaohongshu\.com/explore/\S+", re.I)
STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});?\s*</script>", re.S)


def sanitize(name, n=80):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip().strip(".")
    return (name or "xiaohongshu")[:n]


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


def resolve_note_id(url: str, session: requests.Session) -> str:
    """从链接解析笔记 id（支持短链重定向）。"""
    if url.startswith("http"):
        m = ID_RE.search(url)
        if m:
            return m.group(1)
        try:
            r = session.get(url, headers={"User-Agent": UA}, allow_redirects=True, timeout=15)
            m = ID_RE.search(r.url or url)
            if m:
                return m.group(1)
        except requests.RequestException:
            pass
    return ""


def fetch_note_page(note_id: str, session: requests.Session) -> str:
    url = f"https://www.xiaohongshu.com/explore/{note_id}"
    r = session.get(url, headers={"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"}, timeout=20)
    r.raise_for_status()
    return r.text


def parse_state(html: str) -> dict:
    """提取 __INITIAL_STATE__ 并返回笔记详情。"""
    m = STATE_RE.search(html)
    if not m:
        raise RuntimeError("页面未包含 __INITIAL_STATE__，可能是未登录或需要验证")
    try:
        state = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"解析 __INITIAL_STATE__ 失败: {e}")

    note_map = (state.get("note", {}) or {}).get("noteDetailMap", {}) or {}
    for note in note_map.values():
        if isinstance(note, dict):
            detail = note.get("note")
            if isinstance(detail, dict):
                return detail
    raise RuntimeError("未在页面数据中找到笔记详情")


def extract_content(detail: dict) -> dict:
    """从笔记详情提取标题/作者/图片/视频。"""
    info = {"type": "images", "title": "", "author": "", "images": [], "video": None}
    info["title"] = (detail.get("title") or detail.get("desc") or "").strip()
    user = detail.get("user") or {}
    info["author"] = (user.get("nickname") or "").strip()
    img_list = detail.get("imageList") or []
    if img_list:
        for im in img_list:
            if not isinstance(im, dict):
                continue
            url = im.get("urlDefault") or im.get("url") or im.get("info_list", [{}])[0].get("url")
            if url:
                info["images"].append(url)
    video = detail.get("video")
    if isinstance(video, dict):
        media = video.get("media") or {}
        stream = media.get("stream") or {}
        h264 = stream.get("h264") or []
        if h264:
            info["video"] = h264[0].get("masterUrl")
        if not info["video"]:
            # 兜底：video.src
            info["video"] = video.get("src")
    if info["video"]:
        info["type"] = "video"
    elif info["images"]:
        info["type"] = "images"
    return info


def download(url: str, dest: Path, session: requests.Session, label: str = ""):
    if not url.startswith("http"):
        return False
    try:
        r = session.get(url, headers={"User-Agent": UA, "Referer": "https://www.xiaohongshu.com/"}, timeout=(10, 60))
        r.raise_for_status()
        dest.write_bytes(r.content)
        if dest.stat().st_size == 0:
            raise ValueError("empty")
        print(f"  [✓] {label} {dest.name} ({dest.stat().st_size // 1024} KB)")
        return True
    except (requests.RequestException, ValueError) as e:
        print(f"  [!] {label} 下载失败: {e}")
        return False


def download_note(url: str, out_dir: Path, session: requests.Session):
    note_id = resolve_note_id(url, session)
    if not note_id:
        print("  [!] 无法解析笔记 id")
        return
    print(f"  [*] 笔记: {note_id}")
    html = fetch_note_page(note_id, session)
    info = extract_content(parse_state(html))

    base = sanitize(f"{info['author']}_{info['title']}") or note_id
    folder = out_dir / base
    folder.mkdir(parents=True, exist_ok=True)
    print(f"  [*] 《{info['title'][:40]}》 by {info['author']}")

    if info["type"] == "video" and info["video"]:
        dest = folder / f"video_{info['video'].split('?')[0].split('/')[-1] or '1'}.mp4"
        if not dest.name.endswith(".mp4"):
            dest = folder / "video.mp4"
        download(info["video"], dest, session, "视频")
    elif info["images"]:
        ok = 0
        for i, u in enumerate(info["images"], 1):
            ext = Path(u.split("?")[0]).suffix or ".jpg"
            if len(ext) > 5:
                ext = ".jpg"
            if download(u, folder / f"{i:02d}{ext}", session, f"图片{i}"):
                ok += 1
        print(f"  [✓] 已保存 {ok}/{len(info['images'])} 张 → {folder}")
    else:
        print("  [!] 未识别到图文或视频内容")
        return
    # 元数据
    (folder / "info.json").write_text(json.dumps({
        "title": info["title"], "author": info["author"], "note_id": note_id,
        "url": f"https://www.xiaohongshu.com/explore/{note_id}", "type": info["type"]},
        ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="小红书图文/视频下载器（需要登录 Cookie，仅供学习使用）")
    ap.add_argument("input", help="笔记链接 / xhslink 短链 / 含链接的 txt 文件")
    ap.add_argument("-c", "--cookie", default="cookie.txt",
                    help="Cookie：cookie.txt 文件，或直接粘贴 Cookie 字符串")
    ap.add_argument("-o", "--output", default="downloads", help="保存目录 (默认 downloads)")
    ap.add_argument("-b", "--batch", action="store_true", help="输入是 txt 文件")
    args = ap.parse_args()

    # 加载 cookie
    cookie_raw = args.cookie
    if os.path.isfile(cookie_raw):
        cookie_raw = Path(cookie_raw).read_text(encoding="utf-8").strip()
    cookie = parse_cookie(cookie_raw)
    if not cookie:
        sys.exit("未读取到有效 Cookie。请在浏览器登录小红书后复制 Cookie（见 README），或写入 cookie.txt")
    print(f"[*] Cookie 加载: {len(cookie)} 个键")

    session = requests.Session()
    session.headers.update({"Accept-Language": "zh-CN,zh;q=0.9"})
    session.cookies.update(cookie)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.batch:
        urls = [l.strip() for l in Path(args.input).read_text(encoding="utf-8").splitlines() if l.strip()]
        for i, u in enumerate(urls, 1):
            print(f"[{i}/{len(urls)}]")
            try:
                download_note(u, out_dir, session)
            except Exception as e:
                print(f"  [!] 失败: {e}")
            time.sleep(1.5)
    else:
        try:
            download_note(args.input, out_dir, session)
        except Exception as e:
            sys.exit(f"失败: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\n已取消")
