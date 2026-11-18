# qzone_post.py
# QQ空间发说说（taotao / emotion_cgi_publish_v6）

from __future__ import annotations

import base64
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

UPLOAD_URL = "https://up.qzone.qq.com/cgi-bin/upload/cgi_upload_image"


def _get_gtk(p_skey: str) -> int:
    hash_val = 5381
    for ch in p_skey:
        hash_val += (hash_val << 5) + ord(ch)
    return hash_val & 0x7FFFFFFF


def _extract_cookie_value(cookie: str, key: str) -> str:
    if not cookie:
        return ""
    for item in cookie.split(";"):
        item = item.strip()
        if item.startswith(key + "="):
            return item.split("=", 1)[1]
    return ""


def _try_extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    t = text.strip()

    # raw JSON
    if t.startswith("{") and t.endswith("}"):
        try:
            return json.loads(t)
        except Exception:
            return None

    # callback({...}) / cb({...})
    m = re.search(r"\b(?:callback|cb)\s*\(\s*(\{.*\})\s*\)\s*;?\s*$", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    # HTML wrapper: frameElement.callback({...})
    m = re.search(r"frameElement\.callback\s*\(\s*(\{.*?\})\s*\)", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    # HTML wrapper: cb=frameElement.callback; ... cb({...})
    m = re.search(r"\bcb\s*\(\s*(\{.*?\})\s*\)", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    # Any single top-level wrapper such as _Callback({...}) or foo.bar({...})
    m = re.search(r"^[A-Za-z_$][\w.$]*\s*\(\s*(\{.*\})\s*\)\s*;?\s*$", t, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    return None


@dataclass
class PublishResult:
    ok: bool
    code: Optional[int]
    message: str
    raw_head: str
    tid: str
    image: str = ""
    image_error: str = ""


class QzonePoster:
    def __init__(self, my_qq: str, cookie: str):
        # Supports publish + delete.
        self.my_qq = str(my_qq).strip()

        cookie = (cookie or "").strip()
        if cookie.lower().startswith("cookie:"):
            cookie = cookie.split(":", 1)[1].strip()
        self.cookie = cookie

        p_skey = _extract_cookie_value(cookie, "p_skey")
        if not p_skey:
            raise ValueError("cookie 缺少 p_skey=...（无法计算 g_tk）")
        self.p_skey = p_skey
        self.skey = _extract_cookie_value(cookie, "skey")
        self.g_tk = _get_gtk(p_skey)
        self.last_image: Dict[str, Any] = {}

        self.headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
            ),
            "cookie": cookie,
            "origin": "https://user.qzone.qq.com",
            "referer": f"https://user.qzone.qq.com/{self.my_qq}",
            "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
        }

    def upload_image(self, image_path: str) -> Dict[str, Any]:
        """Upload one local image to the mood album and return its metadata.

        Args:
            image_path: Absolute path of a local image file.

        Returns:
            The ``data`` object returned by cgi_upload_image (albumid, lloc,
            sloc, type, height, width, url).

        Raises:
            RuntimeError: The upload response has no usable image metadata.
        """
        path = Path(image_path)
        params: Dict[str, Any] = {
            "filename": "dafeiyu" + path.suffix.lower(),
            "zzpanelkey": "",
            "uploadtype": "1",
            "albumtype": "7",
            "exttype": "0",
            "skey": self.skey,
            "zzpaneluin": self.my_qq,
            "p_uin": self.my_qq,
            "uin": self.my_qq,
            "p_skey": self.p_skey,
            "output_type": "json",
            "qzonetoken": "",
            "refer": "shuoshuo",
            "charset": "utf-8",
            "output_charset": "utf-8",
            "upload_hd": "1",
            "hd_width": "2048",
            "hd_height": "10000",
            "hd_quality": "96",
            "backUrls": "http://upbak.photo.qzone.qq.com/cgi-bin/upload/cgi_upload_image",
            "url": f"{UPLOAD_URL}?g_tk={self.g_tk}",
            "base64": "1",
            "picfile": base64.b64encode(path.read_bytes()).decode(),
            "qzreferrer": f"https://user.qzone.qq.com/{self.my_qq}",
        }
        res = requests.post(f"{UPLOAD_URL}?g_tk={self.g_tk}", headers=self.headers, data=params, timeout=40)
        payload = _try_extract_json(res.text or "")
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not data.get("lloc"):
            head = (res.text or "")[:200].replace("\n", " ").replace("\r", " ")
            raise RuntimeError(f"upload http {res.status_code}: {head}")
        self.last_image = data
        return data

    def _richval(self, image: Dict[str, Any]) -> Tuple[str, str]:
        """Build the richval and pic_bo strings for one uploaded image."""
        richval = ",{albumid},{lloc},{sloc},{type},{height},{width},,{height},{width}".format(
            albumid=image.get("albumid", ""),
            lloc=image["lloc"],
            sloc=image.get("sloc", ""),
            type=image.get("type", ""),
            height=image.get("height", ""),
            width=image.get("width", ""),
        )
        match = re.search(r"bo=([^&]+)", str(image.get("url", "")))
        return richval, (match.group(1) if match else "")

    def publish_text(self, content: str, image_path: str = "") -> Tuple[int, PublishResult]:
        """Publish a mood post, optionally with one locally hosted image.

        Args:
            content: Mood text; must not be empty.
            image_path: Optional local image. When the upload fails the post is
                still published as text only so a daily entry is never lost.

        Returns:
            The HTTP status and a PublishResult describing the published mood.
        """
        text = (content or "").strip()
        if not text:
            return 0, PublishResult(False, None, "empty content", "", "")

        url = (
            "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com"
            f"/cgi-bin/emotion_cgi_publish_v6?&g_tk={self.g_tk}"
        )

        data: Dict[str, Any] = {
            "syn_tweet_verson": "1",
            "paramstr": "1",
            "who": "1",
            "con": text,
            "feedversion": "1",
            "ver": "1",
            "ugc_right": "1",
            "to_sign": "0",
            "hostuin": self.my_qq,
            "code_version": "1",
            "format": "fs",
            "qzreferrer": f"https://user.qzone.qq.com/{self.my_qq}",
        }

        attached = ""
        image_error = ""
        if image_path:
            try:
                image = self.upload_image(image_path)
                richval, pic_bo = self._richval(image)
                if richval and pic_bo:
                    data.update(
                        richtype="1", subrichtype="1", richval=richval,
                        pic_bo=pic_bo, richflag="1", pic_template="",
                    )
                    attached = Path(image_path).name
                else:
                    image_error = "richval/pic_bo incomplete"
            except Exception as exc:
                image_error = type(exc).__name__ + ": " + str(exc)[:200]

        data["rand"] = str(int(time.time() * 1000)) + str(random.randint(100, 999))

        res = requests.post(url, headers=self.headers, data=data, timeout=25)
        head = (res.text or "")[:300].replace("\n", " ").replace("\r", " ")

        payload = _try_extract_json(res.text or "")
        if isinstance(payload, dict):
            code = None
            try:
                if "code" in payload:
                    code = int(payload.get("code"))
            except Exception:
                code = None
            msg = str(payload.get("message") or payload.get("msg") or "")
            tid = str(payload.get("tid") or payload.get("t1") or payload.get("feedid") or "")
            ok = code == 0
            return res.status_code, PublishResult(ok, code, msg, head, tid, attached, image_error)

        return res.status_code, PublishResult(False, None, "non-json response", head, "", attached, image_error)

    def verify_post(self, tid: str) -> Dict[str, Any]:
        """Check the newest self feed for a published mood and its picture.

        Args:
            tid: Mood id returned by publish_text.

        Returns:
            ``{"found": bool, "image_seen": bool, "snippet": str}``; found is
            False when the mood is not in the readable feed.
        """
        url = (
            "https://user.qzone.qq.com/proxy/domain/ic2.qzone.qq.com/cgi-bin/feeds/feeds_html_act_all"
            f"?uin={self.my_qq}&hostuin={self.my_qq}"
            "&scope=0&filter=all&flag=1&refresh=0&firstGetGroup=0&mixnocache=0&scene=0"
            "&begintime=undefined&icServerTime=&start=0&count=5"
            f"&sidomain=qzonestyle.gtimg.cn&useutf8=1&outputhtmlfeed=1&refer=2&r={random.random()}&g_tk={self.g_tk}"
        )
        html = requests.get(url, headers=self.headers, timeout=20).text or ""
        if not tid or tid not in html:
            return {"found": False, "image_seen": False, "snippet": html[:600]}
        start = max(html.find(tid) - 200, 0)
        snippet = html[start:start + 9000]
        lloc = str(self.last_image.get("lloc") or "")
        image_seen = any(mark in snippet for mark in ("photo.store.qq.com", "qpic.cn")) or (
            bool(lloc) and lloc in snippet
        )
        return {"found": True, "image_seen": image_seen, "snippet": snippet}

    def delete_by_tid(self, tid: str) -> Tuple[int, PublishResult]:
        """Delete a mood by tid.

        Note: we rely on the tid returned by publish.
        """
        t = (tid or "").strip()
        if not t:
            return 0, PublishResult(False, None, "empty tid", "", "")

        url = (
            "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com"
            f"/cgi-bin/emotion_cgi_delete_v6?&g_tk={self.g_tk}"
        )

        data: Dict[str, Any] = {
            "hostuin": self.my_qq,
            "tid": t,
            "t1": t,
            "format": "fs",
            "qzreferrer": f"https://user.qzone.qq.com/{self.my_qq}",
        }

        res = requests.post(url, headers=self.headers, data=data, timeout=20)
        head = (res.text or "")[:300].replace("\n", " ").replace("\r", " ")

        payload = _try_extract_json(res.text or "")
        if isinstance(payload, dict):
            code = None
            try:
                if "code" in payload:
                    code = int(payload.get("code"))
            except Exception:
                code = None
            msg = str(payload.get("message") or payload.get("msg") or "")
            ok = code == 0
            return res.status_code, PublishResult(ok, code, msg, head, t)

        return res.status_code, PublishResult(False, None, "non-json response", head, t)
