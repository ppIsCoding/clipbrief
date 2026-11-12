"""Mock API server for frontend development.

Run: python server.py
Port: 8000 (same as real backend)
No third-party dependencies.
"""

import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

SAMPLE_FORMATS = [
    {
        "format_id": "137",
        "ext": "mp4",
        "resolution": "1080p",
        "filesize": 128974321,
        "has_video": True,
        "has_audio": False,
        "note": "1080P video stream (audio merged by ffmpeg)",
    },
    {
        "format_id": "18",
        "ext": "mp4",
        "resolution": "360p",
        "filesize": 18234567,
        "has_video": True,
        "has_audio": True,
        "note": "360P video + audio",
    },
]

SAMPLE_SUBTITLE = (
    "大家好，今天我们来聊一聊 Python 的全栈开发。"
    "第一部分先讲需求分析，第二部分讲核心功能的实现，最后做测试和优化。"
)

SUMMARY_CHUNKS = [
    "## 视频总结\n\n",
    "### 核心内容\n",
    "1. 从需求分析出发，先确认下载和总结两条主链路。\n",
    "2. 下载基于开源引擎，重点处理防盗链和特殊平台适配。\n",
    "3. 总结先取字幕，再调用大模型流式输出。\n\n",
    "### 结论\n",
    "先跑通主链路，再补体验和推广。",
]

MINDMAP = """# 视频总结
## 需求分析
### 下载痛点
### 总结痛点
## 核心功能
### 解析下载
### AI 总结
## 测试优化
### 性能
### 兼容性
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print("[mock]", fmt % args)

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _text(self, text, content_type="text/plain; charset=utf-8", status=200, filename=None):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _sse_start(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

    def _sse(self, event, data):
        payload = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.wfile.write(payload.encode("utf-8"))
        self.wfile.flush()

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._json({"status": "ok", "mock": True})
        if parsed.path == "/api/proxy/thumbnail":
            return self._thumbnail()
        if parsed.path == "/api/subtitle":
            return self._subtitle(parsed)
        if parsed.path == "/api/auth/me":
            return self._me()
        self._json({"code": "NOT_FOUND", "message": "not found", "detail": None}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        routes = {
            "/api/parse": self._parse,
            "/api/download": self._download,
            "/api/direct-url": self._direct_url,
            "/api/subtitle/download": self._subtitle_download,
            "/api/summarize": self._summarize,
            "/api/chat": self._chat,
            "/api/auth/register": self._auth,
            "/api/auth/login": self._auth,
        }
        handler = routes.get(parsed.path)
        if not handler:
            return self._json({"code": "NOT_FOUND", "message": "not found", "detail": None}, 404)
        handler()

    def _parse(self):
        body = self._body()
        url = (body.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return self._json({"code": "INVALID_URL", "message": "url must start with http/https", "detail": None}, 400)
        platform = "douyin" if "douyin" in url else ("youtube" if "youtu" in url else "bilibili")
        self._json(
            {
                "success": True,
                "data": {
                    "url": url,
                    "platform": platform,
                    "video_id": "MOCK123456",
                    "title": "示例视频：Python 全栈项目开发",
                    "thumbnail": "/api/proxy/thumbnail?url=demo",
                    "duration": 632,
                    "uploader": "示例 UP 主",
                    "formats": SAMPLE_FORMATS,
                },
            }
        )

    def _download(self):
        body = self._body()
        if not body.get("format_id"):
            return self._json({"code": "FORMAT_NOT_FOUND", "message": "format_id required", "detail": None}, 400)
        self._text("mock video bytes", content_type="video/mp4", filename="mock-video.mp4")

    def _direct_url(self):
        self._json(
            {
                "success": True,
                "data": {
                    "direct_url": "https://example.com/mock.mp4",
                    "ext": "mp4",
                    "filesize": 128974321,
                    "title": "示例视频：Python 全栈项目开发",
                },
            }
        )

    def _thumbnail(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">'
            '<rect width="100%" height="100%" fill="#1f2937"/>'
            '<text x="50%" y="50%" fill="#ffffff" font-size="28" text-anchor="middle">MOCK</text>'
            "</svg>"
        )
        self._text(svg, content_type="image/svg+xml")

    def _subtitle(self, parsed):
        params = parse_qs(parsed.query)
        if not params.get("url"):
            return self._json({"code": "INVALID_URL", "message": "url required", "detail": None}, 400)
        self._json(
            {
                "available": True,
                "language": "zh-CN",
                "source": "platform",
                "text": SAMPLE_SUBTITLE,
                "segments": [
                    {"start": 0.0, "end": 3.2, "text": "大家好，今天我们来聊一聊 Python 的全栈开发。"},
                    {"start": 3.2, "end": 8.5, "text": "第一部分先讲需求分析，第二部分讲核心功能的实现，最后做测试和优化。"},
                ],
            }
        )

    def _subtitle_download(self):
        body = self._body()
        fmt = body.get("format", "txt")
        if fmt == "srt":
            text = "1\n00:00:00,000 --> 00:00:03,200\n大家好，今天我们来聊一聊 Python 的全栈开发。\n"
            return self._text(text, filename="subtitle.srt")
        if fmt == "vtt":
            text = "WEBVTT\n\n00:00:00.000 --> 00:00:03.200\n大家好，今天我们来聊一聊 Python 的全栈开发。\n"
            return self._text(text, content_type="text/vtt; charset=utf-8", filename="subtitle.vtt")
        return self._text(SAMPLE_SUBTITLE, filename="subtitle.txt")

    def _summarize(self):
        self._body()
        self._sse_start()
        self._sse(
            "subtitle",
            {
                "has_subtitle": True,
                "language": "zh-CN",
                "subtitle_type": "manual",
                "segments": [
                    {"start": 0.0, "end": 3.2, "text": "大家好，今天我们来聊一聊 Python 的全栈开发。"},
                    {"start": 3.2, "end": 8.5, "text": "第一部分先讲需求分析，第二部分讲核心功能的实现，最后做测试和优化。"},
                ],
                "full_text": SAMPLE_SUBTITLE,
            },
        )
        for chunk in SUMMARY_CHUNKS:
            time.sleep(0.15)
            self._sse("summary", chunk)
        self._sse("mindmap", {"markdown": MINDMAP})
        self._sse("quota", {"remaining": 2, "limit": 3})
        self._sse("done", "[DONE]")

    def _chat(self):
        self._body()
        self._sse_start()
        for chunk in ["视频里提到", "三个部分：", "需求、实现、测试。"]:
            time.sleep(0.2)
            self._sse("answer", chunk)
        self._sse("done", "[DONE]")

    def _auth(self):
        body = self._body()
        email = (body.get("email") or "").strip()
        password = body.get("password") or ""
        if "@" not in email or len(password) < 6:
            return self._json(
                {"code": "UNAUTHORIZED", "message": "email or password invalid", "detail": None}, 401
            )
        self._json(
            {
                "success": True,
                "data": {
                    "token": "mock-token",
                    "user": {"id": 1, "email": email},
                },
            }
        )

    def _me(self):
        self._json(
            {
                "success": True,
                "data": {"id": 1, "email": "mock@example.com"},
            }
        )


if __name__ == "__main__":
    print("Mock API: http://localhost:8000/api/health")
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
