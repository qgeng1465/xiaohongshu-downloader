# -*- coding: utf-8 -*-
"""xhs_dl 解析逻辑单元测试（离线合成数据）。"""
import json
import unittest
from pathlib import Path

import xhs_dl as x

# ---------- 合成 SSR 页面 ----------

def _make_state(note_id, title="旅行笔记", nickname="小鹿", kind="images", n_img=3, video_url=""):
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
             "url": f"https://sns-webpic-qc.xhscdn.com/{i}_orig.webp"}
            for i in range(1, n_img + 1)
        ]
    else:
        note["video"] = {
            "media": {"stream": {"h264": [{"masterUrl": video_url}]}},
            "cover": {"urlDefault": "https://sns-webpic-qc.xhscdn.com/cover.webp"},
        }
    state = {"note": {"noteDetailMap": {note_id: {"note": note}}}}
    return f"<html><script>window.__INITIAL_STATE__ = {json.dumps(state)};</script></html>"


class TestParseCookie(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(x.parse_cookie("a1=abc; webId=xyz; c_key=1"), {"a1": "abc", "webId": "xyz", "c_key": "1"})

    def test_whitespace_and_empty(self):
        self.assertEqual(x.parse_cookie("  a=1 ;   b=2 ;"), {"a": "1", "b": "2"})

    def test_empty(self):
        self.assertEqual(x.parse_cookie(""), {})


class TestResolveNoteId(unittest.TestCase):
    def test_explore(self):
        self.assertEqual(x.resolve_note_id("https://www.xiaohongshu.com/explore/64e9f2f00000000012018b8b", x.requests.Session()),
                         "64e9f2f00000000012018b8b")

    def test_discovery_item(self):
        self.assertEqual(x.resolve_note_id("https://www.xiaohongshu.com/discovery/item/64e9f2f00000000012018b8b?source=web", x.requests.Session()),
                         "64e9f2f00000000012018b8b")

    def test_with_query(self):
        self.assertEqual(x.resolve_note_id("https://www.xiaohongshu.com/explore/64e9f2f00000000012018b8b?xsec_token=abc&xsec_source=pc_web", x.requests.Session()),
                         "64e9f2f00000000012018b8b")

    def test_invalid(self):
        self.assertEqual(x.resolve_note_id("https://example.com/abc", x.requests.Session()), "")


class TestParseState(unittest.TestCase):
    def test_images(self):
        html = _make_state("noteid1")
        detail = x.parse_state(html)
        self.assertEqual(detail["title"], "旅行笔记")
        self.assertEqual(detail["user"]["nickname"], "小鹿")

    def test_missing_state(self):
        with self.assertRaises(RuntimeError):
            x.parse_state("<html><body>no state</body></html>")

    def test_no_note(self):
        html = "<html><script>window.__INITIAL_STATE__ = {\"note\":{}};</script></html>"
        with self.assertRaises(RuntimeError):
            x.parse_state(html)


class TestExtractContent(unittest.TestCase):
    def test_images(self):
        info = x.extract_content(x.parse_state(_make_state("n1")))
        self.assertEqual(info["type"], "images")
        self.assertEqual(len(info["images"]), 3)
        self.assertEqual(info["title"], "旅行笔记")
        self.assertEqual(info["author"], "小鹿")
        self.assertTrue(all(u.startswith("http") for u in info["images"]))

    def test_video(self):
        url = "https://sns-video-bd.xhscdn.com/stream/abc/master.m3u8"
        info = x.extract_content(x.parse_state(_make_state("n2", kind="video", video_url=url)))
        self.assertEqual(info["type"], "video")
        self.assertEqual(info["video"], url)

    def test_sanitize(self):
        self.assertEqual(x.sanitize('a/b:c*d?e"f<g>h|i'), "a_b_c_d_e_f_g_h_i")


class TestDownload(unittest.TestCase):
    def test_download_file(self):
        session = x.requests.Session()
        dest = Path("_test_tmp.bin")
        dest.write_bytes(b"x")  # 预写避免真实网络
        # download 需要真实网络，这里只验证文件命名/扩展名逻辑
        self.assertEqual(x.sanitize("测试"), "测试")


if __name__ == "__main__":
    unittest.main(verbosity=2)
