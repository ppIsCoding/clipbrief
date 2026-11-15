"""AI 视频总结相关 API 路由（独立模块，通过 include_router 挂载）"""

import asyncio
import json
from collections.abc import AsyncIterable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from openai import APIConnectionError, APITimeoutError, AuthenticationError, RateLimitError
from pydantic import BaseModel

from auth import get_optional_user
from database import check_summary_quota, increment_summary, FREE_DAILY_SUMMARY_LIMIT
from security import UnsafeURLError, validate_public_url

router = APIRouter(prefix="/api", tags=["AI 总结"])


class SummarizeRequest(BaseModel):
    url: str
    language: str = "zh"


class ChatRequest(BaseModel):
    url: str
    question: str
    subtitle_text: str = ""


def _check_summary_permission(user: dict | None):
    """Check permission without consuming quota. Returns (allowed, remaining, message)."""
    if not user:
        return False, 0, "请先登录后使用 AI 总结功能"

    allowed, remaining = check_summary_quota(user["id"])
    if not allowed:
        return False, 0, f"今日免费 AI 总结次数已用完（每日 {FREE_DAILY_SUMMARY_LIMIT} 次），明天再来"

    return True, remaining, None


def _get_summarizer():
    """延迟初始化 VideoSummarizer（仅在首次调用时创建）"""
    from summarizer import VideoSummarizer
    if not hasattr(_get_summarizer, "_instance"):
        try:
            _get_summarizer._instance = VideoSummarizer()
        except ValueError:
            raise HTTPException(
                status_code=503, detail="AI 总结服务未配置（缺少 API Key）"
            )
    return _get_summarizer._instance


def _friendly_ai_error(exc: Exception, action: str = "总结") -> str:
    """把模型 SDK 异常转成用户能看懂的提示"""
    if isinstance(exc, AuthenticationError):
        return "AI 服务鉴权失败，请检查 API Key 配置"
    if isinstance(exc, RateLimitError):
        return "AI 服务额度不足或请求过于频繁，请稍后重试"
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return "AI 服务连接超时，请稍后重试"
    return f"{action}失败: {str(exc)[:200]}"


def _get_extractor():
    """延迟初始化 SubtitleExtractor"""
    from summarizer import SubtitleExtractor
    if not hasattr(_get_extractor, "_instance"):
        _get_extractor._instance = SubtitleExtractor()
    return _get_extractor._instance


@router.post("/summarize", response_class=EventSourceResponse)
async def summarize_video(req: SummarizeRequest, user: dict | None = Depends(get_optional_user)) -> AsyncIterable[ServerSentEvent]:
    """
    AI 视频总结（SSE 流式）
    事件类型: subtitle / summary / mindmap / done / error / quota
    """
    try:
        validate_public_url(req.url)
    except UnsafeURLError as exc:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": str(exc)}, ensure_ascii=False),
            event="error",
        )
        return

    allowed, remaining, message = _check_summary_permission(user)
    if not allowed:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": message, "need_login": user is None}, ensure_ascii=False),
            event="error",
        )
        return

    try:
        loop = asyncio.get_event_loop()
        extractor = _get_extractor()
        subtitle_data = await loop.run_in_executor(
            None, extractor.extract, req.url
        )

        yield ServerSentEvent(
            raw_data=json.dumps(subtitle_data, ensure_ascii=False),
            event="subtitle",
        )

        if not subtitle_data["has_subtitle"]:
            yield ServerSentEvent(
                raw_data=json.dumps({"message": "该视频没有可用的字幕，无法生成总结"}, ensure_ascii=False),
                event="error",
            )
            return

        full_text = subtitle_data["full_text"]
        summarizer = _get_summarizer()

        for token in summarizer.summarize_stream(full_text, req.language):
            yield ServerSentEvent(raw_data=json.dumps(token, ensure_ascii=False), event="summary")

        mindmap_md = await loop.run_in_executor(
            None, summarizer.generate_mindmap, full_text, req.language
        )
        yield ServerSentEvent(
            raw_data=json.dumps({"markdown": mindmap_md}, ensure_ascii=False),
            event="mindmap",
        )

        quota_info = {"remaining": increment_summary(user["id"]), "limit": FREE_DAILY_SUMMARY_LIMIT}
        yield ServerSentEvent(
            raw_data=json.dumps(quota_info, ensure_ascii=False),
            event="quota",
        )

        yield ServerSentEvent(raw_data="[DONE]", event="done")

    except HTTPException as e:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": str(e.detail)}, ensure_ascii=False),
            event="error",
        )
    except Exception as e:
        yield ServerSentEvent(
            raw_data=json.dumps(
                {"message": _friendly_ai_error(e, "总结")}, ensure_ascii=False
            ),
            event="error",
        )


@router.post("/chat", response_class=EventSourceResponse)
async def chat_with_video(req: ChatRequest, user: dict | None = Depends(get_optional_user)) -> AsyncIterable[ServerSentEvent]:
    """AI 视频问答（SSE 流式）"""
    try:
        validate_public_url(req.url)
    except UnsafeURLError as exc:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": str(exc)}, ensure_ascii=False),
            event="error",
        )
        return

    try:
        if not req.subtitle_text.strip():
            loop = asyncio.get_event_loop()
            extractor = _get_extractor()
            subtitle_data = await loop.run_in_executor(
                None, extractor.extract, req.url
            )
            if not subtitle_data["has_subtitle"]:
                yield ServerSentEvent(
                    raw_data=json.dumps({"message": "该视频没有可用的字幕，无法回答问题"}, ensure_ascii=False),
                    event="error",
                )
                return
            subtitle_text = subtitle_data["full_text"]
        else:
            subtitle_text = req.subtitle_text

        summarizer = _get_summarizer()
        for token in summarizer.chat_stream(subtitle_text, req.question):
            yield ServerSentEvent(raw_data=json.dumps(token, ensure_ascii=False), event="answer")

        yield ServerSentEvent(raw_data="[DONE]", event="done")

    except HTTPException as e:
        yield ServerSentEvent(
            raw_data=json.dumps({"message": str(e.detail)}, ensure_ascii=False),
            event="error",
        )
    except Exception as e:
        yield ServerSentEvent(
            raw_data=json.dumps(
                {"message": _friendly_ai_error(e, "回答")}, ensure_ascii=False
            ),
            event="error",
        )
