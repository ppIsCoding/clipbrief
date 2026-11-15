"""请求 URL 安全校验：阻止 SSRF（内网、回环、链路本地、元数据地址）。"""

import ipaddress
import socket
from urllib.parse import urlparse


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
