import asyncio
import os
from contextlib import asynccontextmanager
from urllib.parse import unquote

from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from database import init_db
from douyin import DouyinParser, is_douyin_url
from downloader import VideoDownloader

downloader = VideoDownloader()
douyin_parser = DouyinParser(download_dir=downloader.DOWNLOAD_DIR)

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    download_dir = downloader.DOWNLOAD_DIR
    if os.path.exists(download_dir):
        for name in os.listdir(download_dir):
            try:
                os.remove(os.path.join(download_dir, name))
            except OSError:
                pass


app = FastAPI(
    title="AI 万能视频下载总结器 API",
    description="基于 yt-dlp 的视频解析下载与 AI 总结服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def friendly_error(prefix: str, exc: Exception) -> str:
    """把 yt-dlp 的英文异常转成用户能看懂的中文提示"""
    text = str(exc)
    lowered = text.lower()
    if "unsupported url" in lowered or "is not a valid url" in lowered:
        return "不支持的平台或链接，请换一个视频地址"
    if "unable to download webpage" in lowered or "http error 404" in lowered:
        return "无法访问该链接，请确认地址有效或换一个平台"
    if "http error 403" in lowered:
        return "该平台拒绝了请求，请稍后重试或配置 cookies"
    if (
        "unable to download api page" in lowered
        or "connection" in lowered
        or "timed out" in lowered
        or "timeout" in lowered
    ):
        return "当前网络无法访问该平台，请检查网络后重试"
    if "private video" in lowered or "login required" in lowered or "sign in" in lowered:
        return "该视频需要登录或没有访问权限"
    if "requested format is not available" in lowered:
        return "所选清晰度不可用，请重新解析后再选"
    return f"{prefix}: {text[:200]}"


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str = "bestvideo+bestaudio/best"


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "视频解析下载与 AI 总结服务运行中"}


@app.post("/api/parse")
async def parse_video(req: ParseRequest):
    """解析视频信息（抖音走专用模块，其他走 yt-dlp）"""
    try:
        loop = asyncio.get_event_loop()
        if is_douyin_url(req.url):
            result = await loop.run_in_executor(None, douyin_parser.parse, req.url)
        else:
            result = await loop.run_in_executor(None, downloader.parse_video, req.url)
        return {"success": True, "data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": friendly_error("解析失败", exc)},
        )


@app.post("/api/download")
async def download_video(req: DownloadRequest):
    """服务端下载视频后返回文件（抖音走专用模块）"""
    try:
        loop = asyncio.get_event_loop()
        if is_douyin_url(req.url):
            result = await loop.run_in_executor(None, douyin_parser.download, req.url)
        else:
            result = await loop.run_in_executor(
                None, downloader.download_video, req.url, req.format_id
            )
        filepath = result["filepath"]
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="下载的文件不存在")

        return FileResponse(
            path=filepath,
            filename=result["filename"],
            media_type="application/octet-stream",
            background=BackgroundTask(os.remove, filepath),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": friendly_error("下载失败", exc)},
        )


@app.post("/api/direct-url")
async def get_direct_url(req: DownloadRequest):
    """获取视频直链"""
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, downloader.get_direct_url, req.url, req.format_id
        )
        return {"success": True, "data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": friendly_error("获取直链失败", exc)},
        )


@app.get("/api/proxy/thumbnail")
async def proxy_thumbnail(url: str = Query(..., description="缩略图 URL")):
    """代理获取视频缩略图，绕过防盗链"""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="仅支持 http/https 链接")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36",
                    "Referer": unquote(url),
                },
            )
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "image/jpeg")
            return StreamingResponse(
                iter([resp.content]),
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception:
        raise HTTPException(status_code=502, detail="缩略图加载失败")


from api_auth import router as auth_router
from api_summarize import router as summarize_router

app.include_router(summarize_router)
app.include_router(auth_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
