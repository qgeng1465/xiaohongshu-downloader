# -*- coding: utf-8 -*-
"""xhs_dl 单元 + 集成测试（离线 stub，不依赖真实网络）。"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xhs_dl as x

NOTE_ID = "64e9f2f00000000012018b8b"
IMG_URL = "https://sns-webpic-qc.xhscdn.com/1_orig.webp?imageView2/format/webp"
VIDEO_URL = "https://sns-video-bd.xhscdn.com/stream/abc/master.m3u8?x=1"
VIDEO_BACKUP = "https://sns-video-al.xhscdn.com/stream/abc/backup.m3u8?x=1"


def _make_state(note_id=NOTE_ID, title="旅行笔记", nickname="小鹿", kind="images", n_img=3, video_url=""):
    note = {
        "type": "normal" if kind == "images" else "video",
        "title": title,
        "desc": title,
        "user": {"nickname": nickname},
        "interactInfo": {"likedCount": "123"},
    }
    if kind == "images":
        note["imageList"] = [
            {"urlDefault": f"https://sns-webpic-qc.xhscdn.com/{i}_default.webp?imageView2/format/webp",
             "url": f"https://sns-webpic-qc.xhscdn.com/{i}_orig.webp?imageView2/format/webp"}
            for i in range(1, n_img + 1)
        ]
    else:
        note["video"] = {
            "media": {"stream": {"h264": [{"masterUrl": video_url,
                                           "backupUrls": [VIDEO_BACKUP] if video_url else []}]}},
            "cover": {"urlDefault": "https://sns-webpic-qc.xhscdn.com/cover.webp"},
        }
    state = {"note": {"noteDetailMap": {note_id: {"note": note}}}}
    return f"<html><script>window.__INITIAL_STATE__ = {json.dumps(state)};</script></html>"


def _dead_state():
    # 笔记 id 键存在但 note 为空 → 已删除/私密
    return '<html><script>window.__INITIAL_STATE__ = {"note":{"noteDetailMap":{"abc123":{"note":{}}}}};</script></html>'


class FakeResp:
    def __init__(self, payload, url="", status=200):
        self._payload = payload
        self.url = url
        self.status_code = status
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_content(self, chunk_size=1 << 16):
        body = self.content
        for i in range(0, len(body), chunk_size):
            yield body[i:i + chunk_size]

    @property
    def text(self):
        if isinstance(self._payload, bytes):
            return self._payload.decode("utf-8", "replace")
        return json.dumps(self._payload, ensure_ascii=False) if isinstance(self._payload, (dict, list)) else str(self._payload)

    @property
    def content(self):
        return self._payload if isinstance(self._payload, bytes) else self.text.encode("utf-8")


class FakeSession:
    """按 URL 特征分发：explore 页 / xhslink 重定向 / 图片视频字节。"""

    def __init__(self, page_html=None, kind="images", img_body=b"IMG" * 300,
                 video_body=b"VIDEO" * 400, note_id=NOTE_ID, video_url=""):
        self.page_html = page_html or _make_state(note_id=note_id, kind=kind, video_url=video_url)
        self.img_body = img_body
        self.video_body = video_body
        self.note_id = note_id
        self.kind = kind
        self.calls = []

    def get(self, url, params=None, **kw):
        self.calls.append(url)
        if "xiaohongshu.com/explore" in url or "xiaohongshu.com/discovery/item" in url:
            return FakeResp(self.page_html, url=url)
        if "xhslink.com" in url:
            return FakeResp("", url=f"https://www.xiaohongshu.com/explore/{self.note_id}")
        if "xhscdn.com" in url and "stream" in url:
            return FakeResp(self.video_body, url=url)
        if "xhscdn.com" in url:
            return FakeResp(self.img_body, url=url)
        raise AssertionError(f"unexpected url: {url}")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestParseCookie(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(x.parse_cookie("a1=abc; webId=xyz; c_key=1"), {"a1": "abc", "webId": "xyz", "c_key": "1"})

    def test_whitespace_and_empty(self):
        self.assertEqual(x.parse_cookie("  a=1 ;   b=2 ;"), {"a": "1", "b": "2"})

    def test_empty(self):
        self.assertEqual(x.parse_cookie(""), {})


class TestExtractUrl(unittest.TestCase):
    def test_explore(self):
        self.assertEqual(x.extract_url("https://www.xiaohongshu.com/explore/abc123"),
                         "https://www.xiaohongshu.com/explore/abc123")

    def test_share_text(self):
        u = x.extract_url("我在小红书看到了 https://xhslink.com/abc 分享给你")
        self.assertEqual(u, "https://xhslink.com/abc")

    def test_punctuation(self):
        self.assertEqual(x.extract_url("链接：https://www.xiaohongshu.com/explore/abc。"),
                         "https://www.xiaohongshu.com/explore/abc")

    def test_none(self):
        self.assertIsNone(x.extract_url("无链接"))


class TestResolveNoteId(unittest.TestCase):
    def test_explore(self):
        self.assertEqual(x.resolve_note_id("https://www.xiaohongshu.com/explore/64e9f2f00000000012018b8b", x.requests.Session()),
                         "64e9f2f00000000012018b8b")

    def test_discovery_item(self):
        self.assertEqual(x.resolve_note_id("https://www.xiaohongshu.com/discovery/item/64e9f2f00000000012018b8b?source=web", x.requests.Session()),
                         "64e9f2f00000000012018b8b")

    def test_with_query(self):
        self.assertEqual(x.resolve_note_id("https://www.xiaohongshu.com/explore/64e9f2f00000000012018b8b?xsec_token=abc", x.requests.Session()),
                         "64e9f2f00000000012018b8b")

    def test_short_link(self):
        self.assertEqual(x.resolve_note_id("https://xhslink.com/AbC123", FakeSession()), NOTE_ID)

    def test_invalid(self):
        self.assertIsNone(x.resolve_note_id("https://example.com/abc", x.requests.Session()))


class TestParseState(unittest.TestCase):
    def test_images(self):
        detail = x.parse_state(_make_state())
        self.assertEqual(detail["title"], "旅行笔记")

    def test_missing_state(self):
        with self.assertRaises(x.XhsError) as cm:
            x.parse_state("<html><body>no state</body></html>")
        self.assertEqual(cm.exception.reason, "no_state")

    def test_dead(self):
        with self.assertRaises(x.XhsError) as cm:
            x.parse_state(_dead_state())
        self.assertEqual(cm.exception.reason, "dead")

    def test_bad_json(self):
        with self.assertRaises(x.XhsError) as cm:
            x.parse_state("<html><script>window.__INITIAL_STATE__ = {broken}};</script></html>")
        self.assertEqual(cm.exception.reason, "bad_json")


class TestExtractContent(unittest.TestCase):
    def test_images(self):
        info = x.extract_content(x.parse_state(_make_state()))
        self.assertEqual(info["type"], "images")
        self.assertEqual(len(info["images"]), 3)
        self.assertEqual(info["title"], "旅行笔记")
        self.assertEqual(info["author"], "小鹿")
        self.assertTrue(all(u.startswith("http") for u in info["images"]))

    def test_video_candidates(self):
        info = x.extract_content(x.parse_state(_make_state(kind="video", video_url=VIDEO_URL)))
        self.assertEqual(info["type"], "video")
        self.assertEqual(info["video"], VIDEO_URL)
        self.assertEqual(info["video_candidates"], [VIDEO_URL, VIDEO_BACKUP])

    def test_video_fallback_src(self):
        # 构造仅有 video.src 的情况
        state = {"note": {"noteDetailMap": {"n": {"note": {
            "type": "video", "title": "t",
            "video": {"src": "https://cdn.example.com/fallback.mp4"},
        }}}}}
        html = f"<script>window.__INITIAL_STATE__ = {json.dumps(state)};</script>"
        info = x.extract_content(x.parse_state(html))
        self.assertEqual(info["video"], "https://cdn.example.com/fallback.mp4")

    def test_sanitize(self):
        self.assertEqual(x.sanitize_name('a/b:c*d?e"f<g>h|i'), "a_b_c_d_e_f_g_h_i")

    def test_img_ext(self):
        self.assertEqual(x._img_ext("https://cdn/a.PNG?x=1"), ".png")
        self.assertEqual(x._img_ext("https://cdn/a.webp"), ".webp")
        self.assertEqual(x._img_ext("https://cdn/noext"), ".jpg")


class TestDownloadCandidates(unittest.TestCase):
    def test_first_fails_second_ok(self):
        import requests as _r
        class S:
            def get(self, url, **kw):
                if "bad" in url:
                    raise _r.ConnectionError("refused")
                r = FakeResp(b"DATA" * 50, url=url)
                r.headers = {"Content-Length": str(len(b"DATA" * 50))}
                return r

        dest = Path(tempfile.mkdtemp()) / "out.mp4"
        ok = x.download_candidates(["https://bad/a", "https://good/b"], dest, S(), quiet=True)
        self.assertTrue(ok)
        self.assertTrue(dest.stat().st_size > 0)


class TestDownloadNote(unittest.TestCase):
    def test_images(self):
        d = Path(tempfile.mkdtemp())
        info = x.download_note("https://www.xiaohongshu.com/explore/64e9f2f00000000012018b8b",
                               d, FakeSession(kind="images"), "zh")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "images")
        files = list(Path(info["dir"]).glob("*.webp"))
        self.assertEqual(len(files), 3)

    def test_video(self):
        d = Path(tempfile.mkdtemp())
        info = x.download_note("https://www.xiaohongshu.com/explore/64e9f2f00000000012018b8b",
                               d, FakeSession(kind="video", video_url=VIDEO_URL), "zh")
        self.assertIsNotNone(info)
        self.assertEqual(info["type"], "video")
        mp4 = list(Path(info["dir"]).glob("*.mp4"))
        self.assertEqual(len(mp4), 1)

    def test_dead(self):
        logs = []
        d = Path(tempfile.mkdtemp())
        info = x.download_note("https://www.xiaohongshu.com/explore/64e9f2f00000000012018b8b",
                               d, FakeSession(page_html=_dead_state()), "zh", log=logs.append)
        self.assertIsNone(info)
        self.assertTrue(any("不存在" in m for m in logs))

    def test_short_link(self):
        d = Path(tempfile.mkdtemp())
        info = x.download_note("https://xhslink.com/AbC123", d, FakeSession(kind="images"), "zh")
        self.assertIsNotNone(info)


class TestI18n(unittest.TestCase):
    def test_zh_en(self):
        self.assertIn("小红书", x.t("zh", "proj"))
        self.assertIn("Xiaohongshu", x.t("en", "proj"))
        self.assertEqual(x.t("zh", "note_info", title="T", author="A"), "《T》 by A")
        self.assertEqual(x.t("en", "note_info", title="T", author="A"), "T by A")

    def test_missing_key_fallback(self):
        self.assertEqual(x.t("zh", "no_such_key"), "no_such_key")


class TestDetectLang(unittest.TestCase):
    def test_env(self):
        old = os.environ.get("LANG")
        os.environ["LANG"] = "zh_CN.UTF-8"
        self.assertEqual(x.detect_lang(None), "zh")
        os.environ["LANG"] = "en_US.UTF-8"
        self.assertEqual(x.detect_lang(None), "en")
        if old is None:
            os.environ.pop("LANG")
        else:
            os.environ["LANG"] = old

    def test_arg(self):
        self.assertEqual(x.detect_lang("zh"), "zh")
        self.assertEqual(x.detect_lang("en"), "en")


class TestConfig(unittest.TestCase):
    def test_roundtrip(self):
        tmp = Path(tempfile.mkdtemp()) / "cfg.json"
        old = x.CONFIG_PATH
        x.CONFIG_PATH = tmp
        try:
            self.assertEqual(x.load_config(), {})
            x.save_config({"output": "d:/xhs", "cookie": "a=1"})
            self.assertEqual(x.load_config()["cookie"], "a=1")
        finally:
            x.CONFIG_PATH = old


class TestCLI(unittest.TestCase):
    def test_version(self):
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                x.arg_parser().parse_args(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("2.0.0", buf.getvalue())

    def test_help(self):
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                x.arg_parser().parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("--gui", buf.getvalue())


if __name__ == "__main__":
    x.RETRY_DELAY = 0
    unittest.main(verbosity=2)
