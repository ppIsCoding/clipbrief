import asyncio
import json
import os
import threading
import time
import uuid
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
from security import (
    UnsafeURLError,
    extract_share_url,
    normalize_video_url,
    validate_public_url,
)

downloader = VideoDownloader()
douyin_parser = DouyinParser(download_dir=downloader.DOWNLOAD_DIR)

# 下载任务表：task_id -> 进度/结果，供 SSE 与文件下载使用
DOWNLOAD_TASKS: dict[str, dict] = {}
BACKGROUND_TASKS: set = set()
TASKS_LOCK = threading.Lock()
TASK_TTL_SECONDS = 15 * 60

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


def _check_url(url: str) -> None:
    try:
        validate_public_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": str(exc)},
        )


def _prepare_url(raw: str) -> str:
    """从分享文案提取链接、校验公网地址并做平台归一化"""
    try:
        url = extract_share_url(raw)
        validate_public_url(url)
    except UnsafeURLError as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": str(exc)},
        )
    return normalize_video_url(url)


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str = "bestvideo+bestaudio/best"
    expected_size: int | None = None


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "视频解析下载与 AI 总结服务运行中"}


@app.post("/api/parse")
async def parse_video(req: ParseRequest):
    """解析视频信息（抖音走专用模块，其他走 yt-dlp）"""
    url = _prepare_url(req.url)
    try:
        loop = asyncio.get_event_loop()
        if is_douyin_url(url):
            result = await loop.run_in_executor(None, douyin_parser.parse, url)
        else:
            result = await loop.run_in_executor(None, downloader.parse_video, url)
        return {"success": True, "data": result}
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": friendly_error("解析失败", exc)},
        )


@app.post("/api/download")
async def download_video(req: DownloadRequest):
    """服务端下载视频后返回文件（抖音走专用模块）"""
    url = _prepare_url(req.url)
    try:
        loop = asyncio.get_event_loop()
        if is_douyin_url(url):
            result = await loop.run_in_executor(None, douyin_parser.download, url)
        else:
            result = await loop.run_in_executor(
                None, downloader.download_video, url, req.format_id
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


def _remove_task_file(task_id: str):
    with TASKS_LOCK:
        task = DOWNLOAD_TASKS.pop(task_id, None)
    filepath = task.get("filepath") if task else None
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass


def _cleanup_tasks():
    """清掉过期任务和下载目录里的残留文件"""
    now = time.time()
    with TASKS_LOCK:
        expired = [
            task_id
            for task_id, task in DOWNLOAD_TASKS.items()
            if now - task.get("created", now) > TASK_TTL_SECONDS
        ]
        for task_id in expired:
            DOWNLOAD_TASKS.pop(task_id, None)

    download_dir = downloader.DOWNLOAD_DIR
    if not os.path.isdir(download_dir):
        return
    for name in os.listdir(download_dir):
        path = os.path.join(download_dir, name)
        try:
            if now - os.path.getmtime(path) > TASK_TTL_SECONDS:
                os.remove(path)
        except OSError:
            pass


async def _run_download_task(
    task_id: str, url: str, format_id: str, expected_size: int | None = None
):
    loop = asyncio.get_running_loop()

    def on_progress(progress: dict):
        with TASKS_LOCK:
            task = DOWNLOAD_TASKS.get(task_id)
            if task:
                task.update(progress)

    try:
        if is_douyin_url(url):
            result = await loop.run_in_executor(None, douyin_parser.download, url)
        else:
            result = await loop.run_in_executor(
                None, downloader.download_video, url, format_id, on_progress, expected_size
            )

        filepath = result["filepath"]
        if not os.path.exists(filepath):
            raise RuntimeError("下载的文件不存在")

        with TASKS_LOCK:
            task = DOWNLOAD_TASKS.get(task_id)
            if task:
                task.update(
                    status="done",
                    percent=100.0,
                    filepath=filepath,
                    filename=result["filename"],
                    speed=None,
                    eta=0,
                )
    except Exception as exc:
        with TASKS_LOCK:
            task = DOWNLOAD_TASKS.get(task_id)
            if task:
                task.update(
                    status="error",
                    error=friendly_error("下载失败", exc),
                    speed=None,
                    eta=None,
                )


@app.post("/api/download/start")
async def start_download(req: DownloadRequest):
    """创建下载任务，立即返回 task_id；进度通过 SSE 推送"""
    url = _prepare_url(req.url)
    _cleanup_tasks()
    task_id = uuid.uuid4().hex
    with TASKS_LOCK:
        DOWNLOAD_TASKS[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "percent": None,
            "downloaded": 0,
            "total": None,
            "speed": None,
            "eta": None,
            "filename": None,
            "filepath": None,
            "error": None,
            "created": time.time(),
        }
    background_task = asyncio.create_task(
        _run_download_task(task_id, url, req.format_id, req.expected_size)
    )
    BACKGROUND_TASKS.add(background_task)
    background_task.add_done_callback(BACKGROUND_TASKS.discard)
    return {"success": True, "data": {"task_id": task_id}}


@app.get("/api/download/progress/{task_id}")
async def download_progress(task_id: str):
    """SSE 推送下载进度，任务结束或出错后关闭"""
    with TASKS_LOCK:
        if task_id not in DOWNLOAD_TASKS:
            raise HTTPException(status_code=404, detail="下载任务不存在或已过期")

    async def event_stream():
        last_payload = None
        while True:
            with TASKS_LOCK:
                task = DOWNLOAD_TASKS.get(task_id)
                if not task:
                    yield 'data: {"status":"error","error":"下载任务已过期"}\n\n'
                    return
                payload = {
                    key: task.get(key)
                    for key in (
                        "status",
                        "percent",
                        "downloaded",
                        "total",
                        "speed",
                        "eta",
                        "filename",
                        "error",
                    )
                }
            if payload != last_payload:
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                last_payload = payload
            if payload["status"] in ("done", "error"):
                return
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/download/file/{task_id}")
async def download_task_file(task_id: str):
    """下载任务完成后取文件，响应结束后删除临时文件和任务"""
    with TASKS_LOCK:
        task = DOWNLOAD_TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="下载任务不存在或已过期")
        if task["status"] != "done":
            raise HTTPException(status_code=400, detail="文件尚未准备好")
        filepath = task["filepath"]
        filename = task["filename"]

    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=410, detail="文件已过期，请重新下载")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream",
        background=BackgroundTask(_remove_task_file, task_id),
    )


@app.post("/api/direct-url")
async def get_direct_url(req: DownloadRequest):
    """获取视频直链"""
    url = _prepare_url(req.url)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, downloader.get_direct_url, url, req.format_id
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
    _check_url(url)
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
