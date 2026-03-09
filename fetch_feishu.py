"""
fetch_feishu.py

通过飞书开放平台 API 拉取指定日期（默认昨天，Asia/Shanghai）的 P2P 消息，
输出为 JSONL 文件（格式与 convert_record.py 生成的一致）。

依赖：requests
用法：
    python fetch_feishu.py                  # 拉取昨天
    python fetch_feishu.py --date 20260309  # 拉取指定日期
    python fetch_feishu.py --dry-run        # 打印消息，不写文件
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

# ── 常量 ───────────────────────────────────────────────────────────────────
FEISHU_BASE = "https://open.feishu.cn/open-apis"
TZ_CST = timezone(timedelta(hours=8))
# 本地代理环境（如 Clash/V2Ray）可能导致 HTTPS CONNECT 隧道 SSL 握手失败，
# 关闭 verify 可规避此问题；GitHub Actions 环境无代理，此设置无影响
REQUESTS_VERIFY = os.environ.get("FEISHU_SSL_VERIFY", "1") != "0"


# ── 飞书 API ────────────────────────────────────────────────────────────────

def get_tenant_access_token(app_id: str, app_secret: str) -> str:
    """获取 tenant_access_token（有效期 2 小时）"""
    url = f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal"
    resp = requests.post(url, json={"app_id": app_id, "app_secret": app_secret}, timeout=15, verify=REQUESTS_VERIFY)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败：{data}")
    return data["tenant_access_token"]


def fetch_messages(token: str, chat_id: str, start_ts: int, end_ts: int,
                   container_type: str = "chat") -> list[dict]:
    """
    拉取指定会话中 [start_ts, end_ts) 时间段内的所有消息（自动翻页）。

    container_type: "chat"（群聊，默认）或 "p2p"（单聊）
    返回列表，每项：{"time": "YYYY/MM/DD HH:MM", "message": "..."}
    """
    url = f"{FEISHU_BASE}/im/v1/messages"
    headers = {"Authorization": f"Bearer {token}"}
    entries = []
    page_token = None

    while True:
        params = {
            "container_id_type": container_type,
            "container_id": chat_id,
            "start_time": str(start_ts),
            "end_time": str(end_ts),
            "sort_type": "ByCreateTimeAsc",
            "page_size": 50,
        }
        if page_token:
            params["page_token"] = page_token

        resp = requests.get(url, headers=headers, params=params, timeout=15, verify=REQUESTS_VERIFY)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"拉取消息失败：{data}")

        items = data.get("data", {}).get("items") or []
        for item in items:
            # 只处理文本消息
            msg_type = item.get("msg_type", "")
            if msg_type != "text":
                continue

            body = item.get("body", {})
            try:
                content = json.loads(body.get("content", "{}"))
                text = content.get("text", "").strip()
            except (json.JSONDecodeError, AttributeError):
                text = body.get("content", "").strip()

            if not text:
                continue

            # create_time 是毫秒级 Unix 时间戳（字符串）
            create_time_ms = int(item.get("create_time", 0))
            dt = datetime.fromtimestamp(create_time_ms / 1000, tz=TZ_CST)
            time_str = dt.strftime("%Y/%m/%d %H:%M")

            entries.append({"time": time_str, "message": text})

        has_more = data.get("data", {}).get("has_more", False)
        page_token = data.get("data", {}).get("page_token")
        if not has_more or not page_token:
            break

    return entries


# ── 辅助函数 ────────────────────────────────────────────────────────────────

def date_to_cst_range(date_str: str) -> tuple[int, int]:
    """
    将 YYYYMMDD 字符串转换为当天 CST 00:00:00 ~ 次日 00:00:00 的 Unix 时间戳（秒）。
    """
    d = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=TZ_CST)
    start = int(d.timestamp())
    end = int((d + timedelta(days=1)).timestamp())
    return start, end


def yesterday_cst() -> str:
    """返回北京时间昨天的 YYYYMMDD 字符串"""
    now = datetime.now(tz=TZ_CST)
    yesterday = now - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


def date_to_short(date_str: str) -> str:
    """20260309 → 260309（与现有文件名风格一致）"""
    return date_str[2:]


# ── 主流程 ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="从飞书 API 拉取每日消息并保存为 JSONL")
    parser.add_argument("--date", default=None, help="日期，格式 YYYYMMDD，默认昨天（北京时间）")
    parser.add_argument("--output-dir", default="json", help="输出目录，默认 json/")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    args = parser.parse_args()

    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    chat_id = os.environ.get("FEISHU_CHAT_ID")
    # "chat"（群聊，默认）或 "p2p"（单聊）
    chat_type = os.environ.get("FEISHU_CHAT_TYPE", "chat")

    if not all([app_id, app_secret, chat_id]):
        sys.exit("错误：请设置环境变量 FEISHU_APP_ID、FEISHU_APP_SECRET、FEISHU_CHAT_ID")

    date_str = args.date or yesterday_cst()
    start_ts, end_ts = date_to_cst_range(date_str)

    print(f"[fetch_feishu] 拉取日期：{date_str}（CST {start_ts} ~ {end_ts}）")
    print(f"[fetch_feishu] 会话类型：{chat_type}，chat_id：{chat_id}")

    token = get_tenant_access_token(app_id, app_secret)
    entries = fetch_messages(token, chat_id, start_ts, end_ts, container_type=chat_type)

    print(f"[fetch_feishu] 共拉取 {len(entries)} 条消息")

    if not entries:
        print("[fetch_feishu] 消息为空，跳过写文件")
        return

    if args.dry_run:
        for e in entries:
            print(json.dumps(e, ensure_ascii=False))
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{date_to_short(date_str)}.jsonl"

    with open(out_file, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"[fetch_feishu] 已写入 {out_file}")


if __name__ == "__main__":
    main()
