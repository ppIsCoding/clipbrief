import os
import re
import shutil
import uuid
import yt_dlp
from typing import Optional


def _find_ffmpeg_path() -> Optional[str]:
    """查找 ffmpeg 可执行文件路径"""
    if shutil.which("ffmpeg"):
        return os.path.dirname(shutil.which("ffmpeg"))
    try:
        import static_ffmpeg
        paths = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        return os.path.dirname(paths[0])
    except Exception:
        return None


class VideoDownloader:
    """yt-dlp 封装层，提供视频解析、下载、直链获取能力"""

    DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")

    def __init__(self):
        os.makedirs(self.DOWNLOAD_DIR, exist_ok=True)
        self.ffmpeg_path = _find_ffmpeg_path()
        self.has_ffmpeg = self.ffmpeg_path is not None

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "_", name)

    @staticmethod
    def _format_filesize(size: Optional[int]) -> str:
        if not size:
            return "未知大小"
        if size < 1024 * 1024:
            return f"{size / 1024:.0f}KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}MB"
        return f"{size / (1024 * 1024 * 1024):.2f}GB"

    @staticmethod
    def _format_duration(seconds: Optional[int]) -> str:
        if not seconds:
            return "00:00"
        hours, remainder = divmod(int(seconds), 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes}:{secs:02d}"

    @staticmethod
    def _codec_priority(vcodec: Optional[str]) -> int:
        """编码兼容性优先级：H.264 最通用，AV1/VP9 部分播放器打不开"""
        codec = (vcodec or "").split(".")[0].lower()
        if codec in ("h264", "avc1"):
            return 0
        if codec in ("hevc", "h265", "hev1", "hvc1"):
            return 1
        if codec in ("av01", "av1"):
            return 2
        if codec in ("vp9", "vp09"):
            return 3
        return 5

    @staticmethod
    def _codec_label(vcodec: Optional[str]) -> str:
        codec = (vcodec or "").split(".")[0].lower()
        return {
            "h264": "H.264",
            "avc1": "H.264",
            "hevc": "H.265",
            "h265": "H.265",
            "hev1": "H.265",
            "hvc1": "H.265",
            "av01": "AV1",
            "av1": "AV1",
            "vp9": "VP9",
            "vp09": "VP9",
        }.get(codec, codec.upper() or "未知")

    def parse_video(self, url: str) -> dict:
        """解析视频信息，不下载文件"""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ValueError("无法解析该链接")

        formats = self._extract_formats(info)
        platform = info.get("extractor", info.get("extractor_key", "Unknown"))

        return {
            "id": info.get("id", ""),
            "title": info.get("title", "未知标题"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration"),
            "duration_string": self._format_duration(info.get("duration")),
            "uploader": info.get("uploader", info.get("channel", "未知")),
            "platform": platform,
            "view_count": info.get("view_count"),
            "upload_date": info.get("upload_date", ""),
            "description": (info.get("description") or "")[:200],
            "formats": formats,
            "subtitles": list(info.get("subtitles", {}).keys()),
            "automatic_captions": list(info.get("automatic_captions", {}).keys())[:5],
        }

    def _extract_formats(self, info: dict) -> list:
        """从 yt-dlp info 中提取并整理可用格式"""
        raw_formats = info.get("formats", [])
        if not raw_formats:
            return []

        # 同清晰度优先保留 H.264，兼容 Windows 自带播放器
        raw_formats = sorted(
            raw_formats,
            key=lambda f: (
                f.get("height") or 0,
                -self._codec_priority(f.get("vcodec")),
            ),
            reverse=True,
        )

        seen = set()
        results = []

        for f in raw_formats:
            vcodec = f.get("vcodec", "none")
            acodec = f.get("acodec", "none")
            height = f.get("height")
            ext = f.get("ext", "mp4")

            has_video = vcodec and vcodec != "none"
            has_audio = acodec and acodec != "none"

            if not has_video:
                continue

            resolution = f"{f.get('width', '?')}x{height}" if height else "未知"
            filesize = f.get("filesize") or f.get("filesize_approx")
            size_label = self._format_filesize(filesize)
            codec_label = self._codec_label(vcodec)

            if has_audio:
                label = f"{height}p {ext.upper()} · {codec_label} ({size_label})"
                key = (height, ext, "av")
            else:
                label = f"{height}p {ext.upper()} · {codec_label} (仅视频, {size_label})"
                key = (height, ext, "v")

            if key in seen:
                continue
            seen.add(key)

            results.append({
                "format_id": f.get("format_id", ""),
                "ext": ext,
                "resolution": resolution,
                "height": height or 0,
                "filesize": filesize,
                "filesize_approx": filesize,
                "vcodec": vcodec,
                "acodec": acodec if has_audio else None,
                "has_audio": has_audio,
                "label": label,
            })

        results.sort(key=lambda x: x["height"], reverse=True)

        if not any(r["has_audio"] for r in results) and results:
            best_video = results[0]
            audio_size = max(
                (
                    f.get("filesize") or f.get("filesize_approx") or 0
                    for f in raw_formats
                    if (f.get("vcodec") in (None, "none"))
                    and f.get("acodec") not in (None, "none")
                ),
                default=0,
            )
            merged_size = (best_video.get("filesize") or 0) + audio_size
            merged = {
                **best_video,
                "format_id": f"bestvideo+bestaudio/best",
                "filesize": merged_size or best_video.get("filesize"),
                "filesize_approx": merged_size or best_video.get("filesize_approx"),
                "label": (
                    f"{best_video['height']}p 最佳 ({self._codec_label(best_video.get('vcodec'))}, "
                    f"视频+音频合并, {self._format_filesize(merged_size)})"
                    if merged_size
                    else f"{best_video['height']}p 最佳 "
                    f"({self._codec_label(best_video.get('vcodec'))}, 视频+音频合并)"
                ),
                "has_audio": True,
                "acodec": "merged",
            }
            results.insert(0, merged)

        return results[:15]

    def download_video(
        self,
        url: str,
        format_id: str,
        progress_callback=None,
        expected_bytes: int | None = None,
    ) -> dict:
        """下载视频到服务器临时目录，返回文件路径和元数据

        progress_callback: 可选，接收下载进度 dict（percent/downloaded/total/speed/eta/status）
        """
        if not self.has_ffmpeg and "+" in format_id:
            format_id = "best"

        token = uuid.uuid4().hex[:8]
        ydl_opts = {
            "format": format_id,
            "outtmpl": os.path.join(self.DOWNLOAD_DIR, f"%(title)s-{token}.%(ext)s"),
            "format_sort": ["vcodec:h264", "acodec:aac"],
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        if self.has_ffmpeg:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
            ydl_opts["merge_output_format"] = "mp4"

        if cookies_file := os.getenv("COOKIES_FILE"):
            ydl_opts["cookiefile"] = cookies_file

        if progress_callback is not None:
            # 预解析一次，拿到实际会下载的流和大小，避免合并档进度分母不准
            probe_opts = dict(ydl_opts)
            try:
                with yt_dlp.YoutubeDL(probe_opts) as probe:
                    probe_info = probe.extract_info(url, download=False)
                requested = probe_info.get("requested_formats") or []
                probed_size = sum(
                    (f.get("filesize") or f.get("filesize_approx") or 0)
                    for f in requested
                )
                if not probed_size:
                    probed_size = (
                        probe_info.get("filesize")
                        or probe_info.get("filesize_approx")
                        or 0
                    )
                if probed_size:
                    expected_bytes = probed_size
            except Exception:
                pass

        downloaded_by_file: dict[str, int] = {}
        finished_files: set[str] = set()

        def _progress_hook(data):
            if progress_callback is None:
                return
            status = data.get("status")
            if status not in ("downloading", "finished"):
                return

            filename = data.get("filename") or ""
            downloaded = data.get("downloaded_bytes") or 0
            if filename:
                downloaded_by_file[filename] = max(
                    downloaded_by_file.get(filename, 0), downloaded
                )
                if status == "finished":
                    finished_files.add(filename)

            total_downloaded = sum(downloaded_by_file.values())
            info = data.get("info_dict") or {}
            requested = info.get("requested_formats") or []
            expected = expected_bytes or 0
            if not expected:
                expected = sum(
                    (f.get("filesize") or f.get("filesize_approx") or 0)
                    for f in requested
                )
            if not expected:
                expected = data.get("total_bytes") or data.get("total_bytes_estimate") or 0

            all_files_done = len(finished_files) >= len(requested) if requested else True
            reached_expected = bool(expected) and total_downloaded >= expected * 0.98
            if status == "finished" and (reached_expected or (not expected and all_files_done)):
                progress_callback({
                    "status": "processing",
                    "percent": 99.0,
                    "downloaded": total_downloaded,
                    "total": expected or None,
                    "speed": None,
                    "eta": None,
                })
                return

            percent = None
            if expected:
                percent = min(total_downloaded / expected * 100, 99.0)
            progress_callback({
                "status": "downloading",
                "percent": round(percent, 1) if percent is not None else None,
                "downloaded": total_downloaded,
                "total": expected or None,
                "speed": data.get("speed"),
                "eta": data.get("eta"),
            })

        if progress_callback is not None:
            ydl_opts["progress_hooks"] = [_progress_hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except Exception:
                for name in os.listdir(self.DOWNLOAD_DIR):
                    if token in name:
                        try:
                            os.remove(os.path.join(self.DOWNLOAD_DIR, name))
                        except OSError:
                            pass
                raise

        if not info:
            raise ValueError("下载失败")

        title = self._sanitize_filename(info.get("title", "video"))
        ext = info.get("ext", "mp4")
        filename = f"{title}.{ext}"

        downloaded = [name for name in os.listdir(self.DOWNLOAD_DIR) if token in name]
        if not downloaded:
            raise ValueError("下载完成但未找到文件")

        return {
            "filepath": os.path.join(self.DOWNLOAD_DIR, downloaded[0]),
            "filename": filename,
            "title": info.get("title", "video"),
            "ext": ext,
        }

    def get_direct_url(self, url: str, format_id: str) -> dict:
        """获取视频直链"""
        ydl_opts = {
            "format": format_id,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ValueError("无法获取直链")

        direct_url = info.get("url")
        if not direct_url:
            requested = info.get("requested_formats")
            if requested and len(requested) > 0:
                direct_url = requested[0].get("url")

        if not direct_url:
            raise ValueError("该视频不支持直链下载，请使用服务端下载模式")

        return {
            "direct_url": direct_url,
            "ext": info.get("ext", "mp4"),
            "filesize": info.get("filesize") or info.get("filesize_approx"),
            "title": info.get("title", "video"),
        }
