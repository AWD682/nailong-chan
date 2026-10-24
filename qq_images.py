"""将 QQ 消息里的图片临时转换为模型可读取的 Data URL。"""

import base64
from dataclasses import dataclass
from io import BytesIO
import ipaddress
from urllib.parse import urlsplit

import aiohttp
from PIL import Image, UnidentifiedImageError


MAX_IMAGES = 3
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_GIF_FRAMES = 8
MAX_GIF_SOURCE_FRAMES = 300
MAX_GIF_PIXELS = 6_000_000


class ImageLoadError(Exception):
    """QQ 图片无法安全读取或格式不受支持。"""


@dataclass(frozen=True)
class PreparedImage:
    frames: tuple[str, ...]
    frame_numbers: tuple[int, ...]
    total_frames: int

    @property
    def animated(self) -> bool:
        return self.total_frames > 1


def image_attachments(event) -> list:
    def images(items):
        return [
            item for item in (items or [])
            if ((item.content_type or "").lower().split(";", 1)[0].strip() == "image"
                or (item.content_type or "").lower().startswith("image/"))
            and item.url
        ]

    direct = images(getattr(event, "attachments", None))
    if direct:
        return direct
    quoted = getattr(event, "reply", None)
    from_reply = images(getattr(quoted, "attachments", None))
    if from_reply:
        return from_reply
    # QQ 的引用图片常在 msg_elements，而适配器可能没能构建 event.reply。
    if getattr(event, "message_type", None) != 103:
        return []
    elements = getattr(event, "msg_elements", None) or []
    scene = getattr(event, "message_scene", None)
    reference = next(
        (value.removeprefix("ref_msg_idx=")
         for value in (getattr(scene, "ext", None) or [])
         if value.startswith("ref_msg_idx=")),
        None,
    )
    if reference:
        matched = next((item for item in elements if item.msg_idx == reference), None)
        if matched:
            from_element = images(getattr(matched, "attachments", None))
            if from_element:
                return from_element
    for item in elements:
        from_element = images(getattr(item, "attachments", None))
        if from_element:
            return from_element
    return []


def _image_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _safe_image_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if parsed.scheme not in ("https", "http") or not host or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 80 if parsed.scheme == "http" else 443) or host.lower() == "localhost":
            return False
        if parsed.scheme == "http" and not any(
            host == domain or host.endswith("." + domain)
            for domain in ("qq.com", "qpic.cn", "gtimg.cn")
        ):
            return False
        try:
            ipaddress.ip_address(host)
        except ValueError:
            return "." in host
        return False
    except ValueError:
        return False


def _prepare_image(data: bytes, mime: str) -> PreparedImage:
    if mime != "image/gif":
        url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
        return PreparedImage((url,), (1,), 1)
    try:
        with Image.open(BytesIO(data)) as gif:
            total = gif.n_frames
            if total > MAX_GIF_SOURCE_FRAMES or gif.width * gif.height > MAX_GIF_PIXELS:
                raise ImageLoadError("动图尺寸或帧数过大")
            count = min(total, MAX_GIF_FRAMES)
            indices = [round(i * (total - 1) / (count - 1)) for i in range(count)] if count > 1 else [0]
            frames = []
            for index in indices:
                gif.seek(index)
                rgba = gif.convert("RGBA")
                canvas = Image.new("RGB", rgba.size, "white")
                canvas.paste(rgba, mask=rgba.getchannel("A"))
                canvas.thumbnail((768, 768), Image.Resampling.LANCZOS)
                output = BytesIO()
                canvas.save(output, format="JPEG", quality=82)
                frames.append("data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii"))
            return PreparedImage(tuple(frames), tuple(i + 1 for i in indices), total)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageLoadError("动图解码失败") from exc


async def load_image_inputs(event) -> list[PreparedImage]:
    """图片仅在本次请求中使用，不写入磁盘或会话历史。"""
    attachments = image_attachments(event)[:MAX_IMAGES]
    if not attachments:
        return []
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        results = []
        for attachment in attachments:
            if not _safe_image_url(attachment.url):
                raise ImageLoadError("图片链接不是可用的 HTTPS 地址")
            if attachment.size is not None and attachment.size > MAX_IMAGE_BYTES:
                raise ImageLoadError("图片文件过大")
            try:
                async with session.get(attachment.url, allow_redirects=False) as response:
                    if response.status != 200:
                        raise ImageLoadError("QQ 图片链接无法访问")
                    if response.content_length and response.content_length > MAX_IMAGE_BYTES:
                        raise ImageLoadError("图片文件过大")
                    image = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        image.extend(chunk)
                        if len(image) > MAX_IMAGE_BYTES:
                            raise ImageLoadError("图片文件过大")
            except (aiohttp.ClientError, TimeoutError) as exc:
                raise ImageLoadError("QQ 图片下载失败") from exc
            mime = _image_mime(image)
            if mime is None:
                raise ImageLoadError("图片格式不受支持")
            results.append(_prepare_image(bytes(image), mime))
        return results
