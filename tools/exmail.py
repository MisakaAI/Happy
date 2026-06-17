#!/usr/bin/env python3
# 邮件推送（腾讯企业邮箱）

import argparse
import html
import logging
import mimetypes
import re
import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

ENV = dotenv_values()

_SMTP_HOST = "smtp.exmail.qq.com"
_SMTP_PORT = 465
_SMTP_TIMEOUT = 10  # 连接/读写超时（秒）
_MAX_RETRIES = 3  # 发送失败最大重试次数
_RETRY_BACKOFF = 2  # 重试退避基数（秒），第 n 次等待 n * 该值

_TAG_RE = re.compile(r"<[^>]+>")


# 根据文件名猜测 maintype/subtype，猜不到则按二进制流处理
def guess_type(path: str) -> tuple[str, str]:
    ctype, _ = mimetypes.guess_type(path)
    if not ctype:
        return "application", "octet-stream"
    maintype, subtype = ctype.split("/", 1)
    return maintype, subtype


# 判断内容是否已经是 HTML（含形如 <p>、<br/>、<!doctype> 的标签）
def looks_like_html(text: str) -> bool:
    return bool(re.search(r"<[a-zA-Z/!][^<>]*>", text))


# 将内容转为 HTML 正文：纯文本按段落包裹 <p>，已是 HTML 的原样返回
def text_to_html(content: str) -> str:
    if looks_like_html(content):
        return content.strip()

    escaped = html.escape(content)
    paragraphs = re.split(r"\n\s*\n", escaped)
    return "".join(
        f"<p>{'<br>'.join(p.splitlines())}</p>" for p in paragraphs if p.strip()
    )


# 去除 HTML 标签得到纯文本（用作不支持 HTML 客户端的回退）
def strip_tags(html_str: str) -> str:
    return html.unescape(_TAG_RE.sub("", html_str))


# 获取图片尺寸
def get_image_size(image_path: str) -> tuple[int, int] | None:
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            return img.size
    except ImportError:
        # 如果没有 PIL，尝试用其他方法获取尺寸
        pass
    return None


# 根据图片宽度推算内联样式：超宽则限幅，否则按原宽，取不到尺寸则不约束
def _image_style(image_path: str) -> str:
    width, _ = get_image_size(image_path) or (None, None)
    if not width:
        return ""
    if width > 900:
        return "max-width: 900px; height: auto;"
    return f"width: {width}px; height: auto;"


@dataclass(frozen=True)
class InlineImage:
    """一张待内嵌到 HTML 正文里的图片及其 multipart/related 投递信息。"""

    tag: str  # 拼入正文的 <img> 标签（src 指向 cid）
    cid: str  # Content-ID（含尖括号），用于 add_related
    data: bytes
    maintype: str
    subtype: str


# 封装单张内嵌图片：校验类型、生成 CID、读取数据并组装 <img> 标签
def prepare_inline_image(path: str) -> InlineImage:
    maintype, subtype = guess_type(path)
    if maintype != "image":
        raise ValueError(f"{path} 不是图片类型")

    cid = make_msgid(domain="happy.local")
    style_attr = _image_style(path)
    style = f' style="{style_attr}"' if style_attr else ""
    tag = f'<br><img src="cid:{cid.strip("<>")}" alt="image"{style}>'

    return InlineImage(
        tag=tag,
        cid=cid,
        data=Path(path).read_bytes(),
        maintype=maintype,
        subtype=subtype,
    )


# 发送邮件，对网络/SMTP 抖动做有限次重试，认证错误直接抛出友好提示
def _send_with_retry(msg: EmailMessage, user: str, password: str) -> None:
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            with smtplib.SMTP_SSL(
                _SMTP_HOST, _SMTP_PORT, timeout=_SMTP_TIMEOUT
            ) as smtp:
                smtp.login(user, password)
                smtp.send_message(msg)
            logger.info("邮件发送成功（第 %d 次尝试）", attempt)
            return
        except smtplib.SMTPAuthenticationError as e:
            # 认证失败重试无意义，直接抛出友好提示
            raise RuntimeError(
                "邮箱认证失败，请检查 EXMAIL_USER / EXMAIL_KEY 是否正确"
            ) from e
        except (TimeoutError, smtplib.SMTPException, OSError) as e:
            last_error = e
            logger.warning("邮件发送失败（第 %d/%d 次）：%s", attempt, _MAX_RETRIES, e)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF * attempt)
    raise RuntimeError(
        f"邮件发送失败，已重试 {_MAX_RETRIES} 次，请检查网络后稍后重试。"
        f" 最后错误：{last_error}"
    ) from last_error


def send_mail(
    subject: str,
    content: str,
    to: str | None = None,
    images: list[str] | None = None,
    attachments: list[str] | None = None,
) -> None:
    user = ENV.get("EXMAIL_USER")
    password = ENV.get("EXMAIL_KEY")

    if not user:
        raise RuntimeError("缺少 EXMAIL_USER")
    if not password:
        raise RuntimeError("缺少 EXMAIL_KEY")

    receiver = to or ENV.get("EXMAIL_DEFAULT_TO")
    if not receiver:
        raise RuntimeError("缺少收件人")

    # 1. 先组装完整 HTML 正文（含所有内嵌图片标签），再一次写入邮件
    body = text_to_html(content)
    inline_images = [prepare_inline_image(p) for p in images or []]
    if inline_images:
        body += "".join(img.tag for img in inline_images)

    # 2. 纯文本回退与 HTML 均派生自同一份 body，避免两者不一致
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = receiver
    msg.set_content(strip_tags(body))
    msg.add_alternative(body, subtype="html")

    # 3. 内嵌图片作为 multipart/related 挂到 HTML 部分
    if inline_images:
        html_part = msg.get_body(preferencelist=("html",))
        for img in inline_images:
            html_part.add_related(
                img.data,
                maintype=img.maintype,
                subtype=img.subtype,
                cid=img.cid,
            )

    # 4. 附件挂在最外层
    for path in attachments or []:
        maintype, subtype = guess_type(path)
        msg.add_attachment(
            Path(path).read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=Path(path).name,
        )

    # 5. 发送（含重试与友好提示）
    _send_with_retry(msg, user, password)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="发送邮件")
    parser.add_argument("-s", "--subject", required=True, help="邮件标题")
    parser.add_argument(
        "--html",
        required=True,
        help="邮件内容（纯文本自动包 <p>，HTML 原样保留）",
    )
    parser.add_argument(
        "-r",
        "--receiver",
        default=ENV.get("EXMAIL_DEFAULT_TO"),
        help=f"收件人邮箱（默认：{ENV.get('EXMAIL_DEFAULT_TO')}）",
    )
    parser.add_argument(
        "-i",
        "--image",
        action="append",
        default=[],
        help="正文末尾追加的内嵌图片路径（可多次指定）",
    )
    parser.add_argument(
        "-a",
        "--attachment",
        action="append",
        default=[],
        help="附件路径（可多次指定）",
    )

    args = parser.parse_args()
    send_mail(
        args.subject,
        args.html,
        args.receiver,
        images=args.image or None,
        attachments=args.attachment or None,
    )
