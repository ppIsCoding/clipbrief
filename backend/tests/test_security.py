import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security import (  # noqa: E402
    UnsafeURLError,
    extract_share_url,
    normalize_video_url,
    validate_public_url,
)


class NormalizeVideoUrlTest(unittest.TestCase):
    def test_youtube_keeps_video_query(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s"
        self.assertEqual(normalize_video_url(url), url)

    def test_other_platform_query_untouched(self):
        url = "https://vimeo.com/123456?share=copy&p=2"
        self.assertEqual(normalize_video_url(url), url)

    def test_bilibili_keeps_part_and_drops_tracking(self):
        url = (
            "https://www.bilibili.com/video/BV1GJ411x7h7"
            "?p=5&vd_source=abc&spm_id_from=333.788"
        )
        self.assertEqual(
            normalize_video_url(url),
            "https://www.bilibili.com/video/BV1GJ411x7h7?p=5",
        )

    def test_bilibili_id_path_to_video(self):
        url = "https://www.bilibili.com/id/video/BV1GJ411x7h7?p=2"
        self.assertEqual(
            normalize_video_url(url),
            "https://www.bilibili.com/video/BV1GJ411x7h7?p=2",
        )

    def test_b23_short_link_unchanged(self):
        url = "https://b23.tv/abc123"
        self.assertEqual(normalize_video_url(url), url)


class ExtractShareUrlTest(unittest.TestCase):
    def test_extract_from_share_text(self):
        text = "【测试视频】 https://www.bilibili.com/video/BV1xx?p=63&vd_source=1 分享"
        self.assertEqual(
            extract_share_url(text),
            "https://www.bilibili.com/video/BV1xx?p=63&vd_source=1",
        )

    def test_pure_url_returns_itself(self):
        url = "https://www.bilibili.com/video/BV1xx"
        self.assertEqual(extract_share_url(url), url)

    def test_trailing_chinese_punctuation_removed(self):
        text = "看这个（https://b23.tv/abc123）。"
        self.assertEqual(extract_share_url(text), "https://b23.tv/abc123")

    def test_no_url_raises(self):
        with self.assertRaises(UnsafeURLError):
            extract_share_url("这段文字里没有链接")


class ValidatePublicUrlTest(unittest.TestCase):
    def test_rejects_non_http_scheme(self):
        with self.assertRaises(UnsafeURLError):
            validate_public_url("file:///etc/passwd")

    def test_rejects_localhost(self):
        for url in (
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://[::1]:8000",
            "http://192.168.1.1",
            "http://169.254.169.254/latest/meta-data",
        ):
            with self.subTest(url=url):
                with self.assertRaises(UnsafeURLError):
                    validate_public_url(url)


if __name__ == "__main__":
    unittest.main()
