"""请求 URL 安全校验：阻止 SSRF（内网、回环、链路本地、元数据地址）。"""

import ipaddress
import re
import socket
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


class UnsafeURLError(ValueError):
    """URL 指向内网或不允许的地址"""


def _is_blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> None:
    """校验用户提交的 URL，失败时抛 UnsafeURLError。"""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("仅支持 http/https 视频链接")

    host = parsed.hostname
    if not host:
        raise UnsafeURLError("链接缺少域名")

    host = host.lower()
    if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        raise UnsafeURLError("不支持内网或本地地址")

    try:
        addrinfo = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise UnsafeURLError("无法解析该域名，请检查链接")

    for info in addrinfo:
        address = info[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise UnsafeURLError("不支持内网或本地地址")


_SHARE_URL_RE = re.compile(r"https?://[^\s<>\"'，。！？、；：）】》]+", re.IGNORECASE)


def extract_share_url(text: str) -> str:
    """从复制来的分享文案里提取第一个 http(s) 链接。

    例：``【视频标题】https://www.bilibili.com/video/BV...?p=63&vd_source=...``
    """
    text = (text or "").strip()
    if text.startswith(("http://", "https://")):
        return text

    match = _SHARE_URL_RE.search(text)
    if not match:
        raise UnsafeURLError("没有识别到视频链接，请粘贴完整分享内容")

    return match.group(0).rstrip(".,;:!?)]}>")


def normalize_video_url(url: str) -> str:
    """把平台的特殊路径和跟踪参数归一化，交给 yt-dlp 前调用。

    - B站 `/id/video/BV...` -> `/video/BV...`（否则会走 generic 解析，拿不到格式）
    - 去掉 vd_source / spm_id_from 等跟踪参数，只保留分 P 的 p
    - 非 B站链接原样返回，不动 query（如 YouTube 的 v=）
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    # 只处理 B站。其他平台的 query 往往承载视频 ID（如 YouTube 的 v=），
    # 统一裁剪会直接导致解析失败。
    if not host.endswith("bilibili.com"):
        return url

    path = parsed.path
    if path.startswith("/id/"):
        path = path[len("/id"):]

    query = parse_qs(parsed.query)
    keep = {key: value for key, value in query.items() if key == "p"}
    new_query = urlencode(keep, doseq=True)

    return urlunparse(
        (parsed.scheme, parsed.netloc, path, parsed.params, new_query, parsed.fragment)
    )
