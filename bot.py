#!/usr/bin/env python3
"""
✨ WinGo Prediction Bot (Aiogram 3.x)

Features:
- Fetches WinGo history every minute ⏱
- Predicts BIG / SMALL with confidence 👁
- Multiplier adjusts with confidence 📈
- Stores rounds & predictions in SQLite (aiosqlite) 🗄️
- Automatically posts predictions in configured chat 🎯
- Simple commands for admin control ⚙️
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import aiohttp
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or ADMIN_ID == 0:
    raise SystemExit("❌ Please set BOT_TOKEN and ADMIN_ID environment variables")

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"

DB_FILE = "win_go.db"
HISTORY_PAGE_SIZE = 20
HISTORY_WINDOW = 10
POST_INTERVAL = 60
HEADER_TITLE = "[51GAME] k1Nɢ mAκεя"
MAX_DISPLAY = 12

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wingo_aiogram3")

# ---------- Globals ----------
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
prediction_task: Optional[asyncio.Task] = None
_cached_target_chat: Optional[int] = None


# ---------- Database ----------
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rounds (
            issue TEXT PRIMARY KEY,
            number INTEGER,
            color TEXT,
            ts TEXT
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            issue TEXT PRIMARY KEY,
            predicted TEXT,
            confidence REAL,
            multiplier INTEGER,
            created_ts TEXT,
            result TEXT
        );
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS config (
            k TEXT PRIMARY KEY,
            v TEXT
        );
        """)
        await db.commit()


async def db_set_config(key: str, value: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR REPLACE INTO config(k,v) VALUES (?,?)", (key, value))
        await db.commit()


async def db_get_config(key: str) -> Optional[str]:
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT v FROM config WHERE k=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def store_rounds_async(rounds: List[Dict]):
    if not rounds:
        return
    async with aiosqlite.connect(DB_FILE) as db:
        for r in rounds:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO rounds(issue, number, color, ts) VALUES (?,?,?,?)",
                    (r["issue"], r["number"], r["color"], r["ts"])
                )
            except Exception:
                log.exception("Error inserting round %s", r)
        await db.commit()


async def get_all_rounds() -> List[Tuple[str, int]]:
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT issue, number FROM rounds ORDER BY issue ASC")
        rows = await cur.fetchall()
        return rows


async def save_prediction_async(issue: str, predicted: str, confidence: float, multiplier: int):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT OR REPLACE INTO predictions(issue,predicted,confidence,multiplier,created_ts,result) VALUES (?,?,?,?,?,NULL)",
            (issue, predicted, confidence, multiplier, datetime.utcnow().isoformat())
        )
        await db.commit()


async def update_prediction_result_async(issue: str, result: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE predictions SET result=? WHERE issue=?", (result, issue))
        await db.commit()


async def get_prediction_by_issue(issue: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT predicted, multiplier, result FROM predictions WHERE issue=?", (issue,))
        return await cur.fetchone()


async def get_last_prediction():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT issue, predicted, multiplier FROM predictions ORDER BY created_ts DESC LIMIT 1")
        return await cur.fetchone()


# ---------- API fetch ----------
async def fetch_history(session: aiohttp.ClientSession, page_size: int = HISTORY_PAGE_SIZE) -> List[Dict]:
    try:
        params = {"pageNo": 1, "pageSize": page_size}
        async with session.get(API_URL, params=params, timeout=20) as resp:
            resp.raise_for_status()
            js = await resp.json()
            items = js.get("data", {}).get("list", [])
            normalized = []
            for item in reversed(items):  # oldest-first
                issue = str(item.get("issueNumber"))
                number = int(item.get("number", 0))
                color = item.get("color", "")
                normalized.append({
                    "issue": issue,
                    "number": number,
                    "color": color,
                    "ts": datetime.utcnow().isoformat()
                })
            return normalized
    except Exception:
        log.exception("fetch_history error")
        return []


# ---------- Prediction logic ----------
def label_big_small(number: int) -> str:
    return "BIG" if number >= 5 else "SMALL"


def confidence_to_multiplier(conf: float) -> int:
    if conf >= 0.95: return 81
    if conf >= 0.85: return 27
    if conf >= 0.75: return 9
    if conf >= 0.65: return 5
    if conf >= 0.6: return 3
    if conf >= 0.55: return 2
    return 1


async def predict_next_from_db() -> Tuple[str, str, float, int]:
    rows = await get_all_rounds()
    history = [{"issue": r[0], "number": r[1]} for r in rows]
    if not history:
        return ("0", "BIG", 0.6, 1)

    window = history[-HISTORY_WINDOW:] if len(history) >= HISTORY_WINDOW else history
    big_count = sum(1 for r in window if label_big_small(r["number"]) == "BIG")
    small_count = len(window) - big_count

    if big_count > small_count:
        pred, conf = "BIG", big_count / len(window)
    elif small_count > big_count:
        pred, conf = "SMALL", small_count / len(window)
    else:
        pred, conf = label_big_small(window[-1]["number"]), 0.5

    last_issue = window[-1]["issue"]
    try:
        next_issue = str(int(last_issue) + 1)
    except Exception:
        next_issue = last_issue + "-n"

    multiplier = confidence_to_multiplier(conf)
    return next_issue, pred, round(conf, 3), multiplier


async def update_results_with_new_rounds(new_rounds: List[Dict]):
    for r in new_rounds:
        issue = r["issue"]
        actual_label = label_big_small(r["number"])
        pr = await get_prediction_by_issue(issue)
        if pr:
            predicted = pr[0]
            result = "WIN" if predicted == actual_label else "LOSS"
            await update_prediction_result_async(issue, result)


# ---------- Message builder ----------
async def build_message_text(display_count: int = MAX_DISPLAY) -> Tuple[str, str]:
    rows = await get_all_rounds()
    if not rows:
        return ("❌ No results yet.", "")

    recent = rows[-display_count:]
    lines = ["🎰 <b>Recent Rounds</b>\n"]
    for r in recent:
        issue, num = r[0], r[1]
        label = label_big_small(num)
        pr = await get_prediction_by_issue(issue)
        if pr:
            predicted, mult, result = pr
            outcome = "✅ WIN" if result == "WIN" else "❌ LOSS" if result else "⏳ Pending"
        else:
            outcome = "⏳ Pending"
        lines.append(f"<code>{issue[-3:]}</code> → 🎲 {num} → {label:<5} | {outcome}")

    last_pred = await get_last_prediction()
    if last_pred:
        next_issue, next_predicted, mult = last_pred
    else:
        next_issue, next_predicted, mult = "???", "BIG", 1

    header = f"🎯 <b>{HEADER_TITLE}</b>\n🔥 PRIME PREDICTIONS 🔥\n\n"
    body = "\n".join(lines)
    footer = f"\n\n➡️ <b>Next Bet:</b> <code>{next_issue[-3:]}</code> → {next_predicted} ({mult}x)"
    return header + body + footer, next_issue


# ---------- Prediction worker ----------
async def prediction_worker(chat_id: int):
    log.info("Prediction worker started for chat %s", chat_id)
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                history = await fetch_history(session)
                if not history:
                    log.warning("No history fetched; retrying soon")
                    await asyncio.sleep(10)
                    continue

                await store_rounds_async(history)
                await update_results_with_new_rounds(history)

                next_issue, predicted, confidence, multiplier = await predict_next_from_db()
                last_pred = await get_last_prediction()
                if not last_pred or last_pred[0] != next_issue:
                    await save_prediction_async(next_issue, predicted, confidence, multiplier)

                text, posted_issue = await build_message_text()
                try:
                    await bot.send_message(chat_id, text)
                    log.info("Posted to chat %s (pred_issue=%s)", chat_id, posted_issue)
                except Exception:
                    log.exception("Failed to post to chat %s", chat_id)

            except asyncio.CancelledError:
                log.info("Prediction worker cancelled")
                break
            except Exception:
                log.exception("Unhandled error in prediction worker")
            await asyncio.sleep(POST_INTERVAL)


# ---------- Commands ----------
@dp.message(Command(commands=["start"]))
async def handle_start(message: Message):
    start_text = (
        "👋 <b>Welcome to WinGo Prediction Bot</b>\n\n"
        "📊 <b>Features:</b>\n"
        "• Auto-fetches WinGo results every minute\n"
        "• Predicts <b>BIG / SMALL</b> with confidence 📈\n"
        "• Stores history locally 🗄️\n"
        "• Posts predictions to your channel/group 🎯\n\n"
        "⚙️ <b>Commands:</b>\n"
        "▫️ /SetTarget <chat_id> → Save target chat\n"
        "▫️ /StartPrediction → Begin posting\n"
        "▫️ /StopPrediction → Stop predictions\n"
        "▫️ /Status → Show current status\n"
    )
    await message.answer(start_text)


@dp.message(Command(commands=["SetTarget"]))
async def handle_set_target(message: Message):
    global _cached_target_chat
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Not authorized")
        return

    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Usage: /SetTarget <chat_id_or_channel_username>")
        return

    target = args[1].strip()
    await db_set_config("target_chat", target)
    _cached_target_chat = None
    await message.reply(f"🎯 Target saved:\n<b>{target}</b>\n\nRun <b>/StartPrediction</b> to begin!")


@dp.message(Command(commands=["StartPrediction"]))
async def handle_start_prediction(message: Message):
    global prediction_task, _cached_target_chat
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Not authorized")
        return

    target = await db_get_config("target_chat")
    chat_id = int(target) if target and target.isdigit() else (target or message.chat.id)

    await db_set_config("target_chat", str(chat_id))
    _cached_target_chat = chat_id

    if prediction_task and not prediction_task.done():
        await message.reply("⚠️ Prediction already running!")
        return

    prediction_task = asyncio.create_task(prediction_worker(chat_id))
    await message.reply(
        f"🚀 Prediction started!\n\n📌 Posting to: <b>{chat_id}</b>\n⏱ Interval: {POST_INTERVAL}s"
    )


@dp.message(Command(commands=["StopPrediction"]))
async def handle_stop_prediction(message: Message):
    global prediction_task
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Not authorized")
        return

    if prediction_task and not prediction_task.done():
        prediction_task.cancel()
        try:
            await prediction_task
        except asyncio.CancelledError:
            pass
        prediction_task = None
        await message.reply("🛑 Prediction worker stopped.")
    else:
        await message.reply("⚠️ No prediction worker running.")


@dp.message(Command(commands=["Status"]))
async def handle_status(message: Message):
    running = "🟢 <b>Running</b>" if prediction_task and not prediction_task.done() else "🔴 <b>Stopped</b>"
    target = await db_get_config("target_chat") or "❌ Not set"
    await message.reply(f"⚙️ <b>Status Report</b>\n\n{running}\n🎯 Target: <b>{target}</b>")


# ---------- Entry ----------
async def main():
    await init_db()
    log.info("Bot is starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped manually.")
