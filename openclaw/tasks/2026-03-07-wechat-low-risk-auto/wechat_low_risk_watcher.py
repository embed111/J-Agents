from __future__ import annotations

import json
import re
import shutil
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Config:
    target_contact: str
    auto_reply_text: str
    poll_seconds: int
    cooldown_seconds: int
    workdir: Path


BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
STATE_PATH = BASE / "state.json"
LOG_PATH = BASE / "watcher.log"
STOP_PATH = BASE / "STOP"
DB_PATH = Path(r"C:\Users\jmqj\AppData\Local\Microsoft\Windows\Notifications\wpndatabase.db")


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_config() -> Config:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return Config(
        target_contact=data["target_contact"],
        auto_reply_text=data["auto_reply_text"],
        poll_seconds=int(data.get("poll_seconds", 6)),
        cooldown_seconds=int(data.get("cooldown_seconds", 120)),
        workdir=Path(data.get("workdir", str(BASE))),
    )


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"seen_ids": [], "last_sent_ts": 0}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"seen_ids": [], "last_sent_ts": 0}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def decode_payload(payload: object) -> str:
    if payload is None:
        return ""
    if isinstance(payload, bytes):
        text = payload.decode("utf-8", "ignore")
    else:
        text = str(payload)
    text = re.sub(r"<[^>]+>", " ", text)
    text = " ".join(text.split())
    return text


def read_recent_notifications(limit: int = 120) -> list[dict]:
    if not DB_PATH.exists():
        return []

    temp_db = Path(tempfile.gettempdir()) / "wpndb-openclaw-copy.db"
    shutil.copy2(DB_PATH, temp_db)

    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT n.Id, n.ArrivalTime, n.Payload, h.PrimaryId
        FROM Notification n
        LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
        ORDER BY n.ArrivalTime DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    out = []
    for row in rows:
        out.append(
            {
                "id": int(row["Id"]),
                "arrival": int(row["ArrivalTime"] or 0),
                "primary_id": row["PrimaryId"] or "",
                "text": decode_payload(row["Payload"]),
            }
        )
    return out


def should_trigger(notification: dict, target: str) -> bool:
    text = notification["text"].lower()
    primary = notification["primary_id"].lower()
    target_lower = target.lower()

    # 尽量收窄：必须命中目标联系人名；可选命中微信相关标识
    hits_target = target_lower in text
    hits_wechat = any(k in primary for k in ["weixin", "wechat", "tencent", "mm"]) or any(
        k in text for k in ["微信", "wechat", "weixin"]
    )
    return hits_target and (hits_wechat or True)


def send_wechat_message(target_contact: str, message: str) -> bool:
    try:
        import win32clipboard
        from win32clipboard import CF_UNICODETEXT
        import win32con
        import win32gui
        import win32api
        import pythoncom
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        activated = shell.AppActivate("微信")
        if not activated:
            return False
        time.sleep(0.5)

        def key_combo(keys: Iterable[int]) -> None:
            keys = list(keys)
            for k in keys:
                win32api.keybd_event(k, 0, 0, 0)
            for k in reversed(keys):
                win32api.keybd_event(k, 0, win32con.KEYEVENTF_KEYUP, 0)

        key_combo([win32con.VK_CONTROL, ord("F")])
        time.sleep(0.2)

        # 粘贴联系人
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(CF_UNICODETEXT, target_contact)
        win32clipboard.CloseClipboard()

        key_combo([win32con.VK_CONTROL, ord("V")])
        time.sleep(0.2)
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.4)

        # 粘贴消息并发送
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(CF_UNICODETEXT, message)
        win32clipboard.CloseClipboard()

        key_combo([win32con.VK_CONTROL, ord("V")])
        time.sleep(0.2)
        win32api.keybd_event(win32con.VK_RETURN, 0, 0, 0)
        win32api.keybd_event(win32con.VK_RETURN, 0, win32con.KEYEVENTF_KEYUP, 0)

        return True
    except Exception as e:
        log(f"send error: {e}")
        return False


def main() -> None:
    cfg = load_config()
    state = load_state()
    seen_ids: set[int] = set(int(x) for x in state.get("seen_ids", []))
    last_sent_ts = int(state.get("last_sent_ts", 0))

    log("watcher started")
    log(f"target_contact={cfg.target_contact}; poll={cfg.poll_seconds}s; cooldown={cfg.cooldown_seconds}s")

    while True:
        if STOP_PATH.exists():
            log("STOP file detected, exit")
            break

        try:
            notifs = read_recent_notifications()
            triggered = False
            for item in reversed(notifs):
                nid = int(item["id"])
                if nid in seen_ids:
                    continue
                seen_ids.add(nid)

                if should_trigger(item, cfg.target_contact):
                    now = int(time.time())
                    if now - last_sent_ts >= cfg.cooldown_seconds:
                        ok = send_wechat_message(cfg.target_contact, cfg.auto_reply_text)
                        if ok:
                            last_sent_ts = now
                            log(f"auto-replied for notif={nid}")
                        else:
                            log(f"matched notif={nid} but send failed")
                    else:
                        log(f"matched notif={nid} but in cooldown")
                    triggered = True

            state = {"seen_ids": sorted(list(seen_ids))[-500:], "last_sent_ts": last_sent_ts}
            save_state(state)

            if not triggered:
                log("tick: no target notification")
        except Exception as e:
            log(f"loop error: {e}")

        time.sleep(cfg.poll_seconds)


if __name__ == "__main__":
    main()
