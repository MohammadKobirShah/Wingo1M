#!/usr/bin/env python3
"""
🌟 Kobir ✦ WinGo 1M Bot (Final Version, Aiogram 3.x)

Features:
- Fetches WinGo history every 60s
- Predicts BIG/SMALL with Martingale multiplier
- DB auto-prunes (last 15 rounds & predictions only)
- Multi-target broadcasting
- Admin control: /SetTarget /ClearTargets /StartPrediction /StopPrediction /Status /Stats /Notice
- Auto Daily Stats Summary every midnight Asia/Dhaka
- Fallback handler for unknown messages (no more "Update not handled" spam)
"""

import os, json, asyncio, logging, pytz
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple

import aiohttp, aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from aiogram.filters import Command

# ---------- Config ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
if not BOT_TOKEN or ADMIN_ID == 0:
    raise SystemExit("❌ Please set BOT_TOKEN and ADMIN_ID environment variables")

API_URL = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
DB_FILE = "win_go.db"
HISTORY_PAGE_SIZE, HISTORY_WINDOW, POST_INTERVAL = 20, 10, 60
HEADER_TITLE = "🌟 𝐊𝐎𝐁𝐈𝐑 ✦ 𝐖𝐈𝐍𝐆𝐎 𝟏𝐌 🌟"
MAX_DISPLAY = 15
DHAKA_TZ = pytz.timezone("Asia/Dhaka")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wingo_aiogram3")

# ---------- Globals ----------
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
prediction_task: Optional[asyncio.Task] = None

# ---------- Database ----------
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS rounds (issue TEXT PRIMARY KEY, number INTEGER, color TEXT, ts TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS predictions (issue TEXT PRIMARY KEY, predicted TEXT, confidence REAL, multiplier INTEGER, created_ts TEXT, result TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS targets (chat_id TEXT PRIMARY KEY)")
        await db.commit()

async def prune_old_rounds(): 
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM rounds WHERE issue NOT IN (SELECT issue FROM rounds ORDER BY issue DESC LIMIT 15)")
        await db.commit()

async def prune_old_predictions():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM predictions WHERE issue NOT IN (SELECT issue FROM predictions ORDER BY created_ts DESC LIMIT 15)")
        await db.commit()

# ---------- Target Mgmt ----------
async def add_target(chat_id: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("INSERT OR IGNORE INTO targets(chat_id) VALUES (?)", (chat_id,))
        await db.commit()

async def get_targets() -> List[str]:
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT chat_id FROM targets")
        return [r[0] for r in await cur.fetchall()]

async def clear_targets():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM targets")
        await db.commit()

# ---------- Prediction Storage ----------
async def store_rounds_async(rounds: List[Dict]):
    if not rounds: return
    async with aiosqlite.connect(DB_FILE) as db:
        for r in rounds:
            await db.execute("INSERT OR IGNORE INTO rounds(issue, number, color, ts) VALUES (?,?,?,?)",
                             (r["issue"], r["number"], r["color"], r["ts"]))
        await db.commit()
    await prune_old_rounds()

async def get_all_rounds():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT issue, number FROM rounds ORDER BY issue ASC")
        return await cur.fetchall()

async def save_prediction_async(issue, predicted, confidence, multiplier):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""INSERT OR REPLACE INTO predictions
            (issue,predicted,confidence,multiplier,created_ts,result)
            VALUES (?,?,?,?,?,NULL)""",
            (issue, predicted, confidence, multiplier, datetime.utcnow().isoformat()))
        await db.commit()
    await prune_old_predictions()

async def update_prediction_result_async(issue: str, result: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE predictions SET result=? WHERE issue=?", (result, issue))
        await db.commit()

async def get_prediction_by_issue(issue): 
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT predicted,multiplier,result FROM predictions WHERE issue=?",(issue,))
        return await cur.fetchone()

async def get_last_prediction():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT issue,predicted,multiplier,result FROM predictions ORDER BY created_ts DESC LIMIT 1")
        return await cur.fetchone()

async def get_stats():
    async with aiosqlite.connect(DB_FILE) as db:
        cur=await db.execute("""SELECT COUNT(*),
                                       SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END),
                                       SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END),
                                       SUM(CASE WHEN result IS NULL THEN 1 ELSE 0 END)
                                FROM predictions""")
        total,wins,losses,pending=await cur.fetchone()
        rate=round((wins/total)*100,2) if total>0 else 0
        return total,wins,losses,pending,rate

# ---------- Fetch API ----------
async def fetch_history(session):
    try:
        async with session.get(API_URL, params={"pageNo":1,"pageSize":HISTORY_PAGE_SIZE}, headers={"User-Agent":"Mozilla/5.0"}, timeout=20) as resp:
            raw=await resp.text()
            js=json.loads(raw)
            return [{"issue": str(i["issueNumber"]),
                     "number": int(i["number"]),
                     "color": i.get("color",""),
                     "ts": datetime.utcnow().isoformat()} for i in reversed(js["data"]["list"])]
    except Exception as e:
        log.error(f"fetch_history error: {e}"); return []

# ---------- Prediction Logic ----------
def label_big_small(num): return "BIG" if num>=5 else "SMALL"

async def predict_next_from_db():
    rows=await get_all_rounds()
    if not rows: return ("0","BIG",0.6,1)
    history=[{"issue":r[0],"number":r[1]} for r in rows][-HISTORY_WINDOW:]
    big=sum(1 for r in history if label_big_small(r["number"])=="BIG")
    small=len(history)-big
    if big>small: pred,conf="BIG",big/len(history)
    elif small>big: pred,conf="SMALL",small/len(history)
    else: pred,conf=label_big_small(history[-1]["number"]),0.5
    next_issue=str(int(history[-1]["issue"])+1) if history[-1]["issue"].isdigit() else history[-1]["issue"]+"-n"
    last=await get_last_prediction()
    mult=1 if not last or last[3]=="WIN" else min(last[2]*2,81)
    return next_issue,pred,round(conf,3),mult

async def update_results_with_new_rounds(new_rounds):
    for r in new_rounds:
        pr=await get_prediction_by_issue(r["issue"])
        if pr:
            actual=label_big_small(r["number"])
            result="WIN" if pr[0]==actual else "LOSS"
            await update_prediction_result_async(r["issue"],result)

# ---------- Message Builder ----------
async def build_message_text():
    rows=await get_all_rounds()
    if not rows: return ("❌ No results yet.","")
    recent=rows[-MAX_DISPLAY:]
    lines=["📜 <b>Recent Rounds (Last 15)</b>\n━━━━━━━━━━━━━━━━━━━━━━━"]
    for r in recent:
        pr=await get_prediction_by_issue(r[0])
        outcome="✅ WIN" if pr and pr[2]=="WIN" else "❌ LOSS" if pr and pr[2]=="LOSS" else "⏳ Waiting"
        lines.append(f"🎲 <code>{r[0][-3:]}</code> → {r[1]} ({label_big_small(r[1])}) | {outcome}")
    last=await get_last_prediction()
    next_issue,next_pred,mult=("???","BIG",1) if not last else (last[0],last[1],last[2])
    return (f"🔥 <b>{HEADER_TITLE}</b> 🔥\n━━━━━━━━━━━━━━━━━━━━━━━\n🤖 <b>Prime Predictions</b>\n"
            +"\n".join(lines)+
            f"\n━━━━━━━━━━━━━━━━━━━━━━━\n📊 <b>Next Trade:</b> <code>{next_issue[-3:]}</code>\n"
            f"🔮 Prediction: <b>{next_pred}</b>\n💸 Multiplier: <b>{mult}x</b>\n"
            f"⏱ Updates every {POST_INTERVAL}s\n\n⚠️ <b>🇵‌🇱‌🇦‌🇾‌ 🇦‌🇹‌ 🇴‌🇼‌🇳‌ 🇷‌🇮‌🇸‌🇰‌</b> 🎲",next_issue)

# ---------- Workers ----------
async def prediction_worker(tgts: List[str]):
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                hist=await fetch_history(session)
                if hist:
                    await store_rounds_async(hist)
                    await update_results_with_new_rounds(hist)
                    next_issue,pred,conf,mult=await predict_next_from_db()
                    last=await get_last_prediction()
                    if not last or last[0]!=next_issue: await save_prediction_async(next_issue,pred,conf,mult)
                    text,_=await build_message_text()
                    for t in tgts:
                        try:
                            cid=int(t) if t.lstrip("-").isdigit() else t
                            await bot.send_message(cid,text)
                        except Exception as e: log.error(f"send fail {t}: {e}")
                else: await asyncio.sleep(10)
            except asyncio.CancelledError: break
            except Exception as e: log.error(e)
            await asyncio.sleep(POST_INTERVAL)

async def daily_stats_worker():
    while True:
        now=datetime.now(DHAKA_TZ)
        next_midnight=DHAKA_TZ.localize(datetime.combine(now.date()+timedelta(days=1),datetime.min.time()))
        await asyncio.sleep((next_midnight-now).total_seconds())
        total,wins,losses,pending,rate=await get_stats()
        msg=(f"📊 <b>Daily Prediction Summary</b>\n━━━━━━━━━━━━━━━━━━━━━━━\n"
             f"✅ Wins: <b>{wins}</b>\n❌ Losses: <b>{losses}</b>\n⏳ Pending: <b>{pending}</b>\n"
             f"📋 Total: <b>{total}</b>\n🏆 Win Rate: <b>{rate}%</b>\n\n"
             f"⚠️ <b>🇵‌🇱‌🇦‌🇾‌ 🇦‌🇹‌ 🇴‌🇼‌🇳‌ 🇷‌🇮‌🇸‌🇰‌</b> 🎲")
        for t in await get_targets():
            try:
                cid=int(t) if t.lstrip("-").isdigit() else t
                await bot.send_message(cid,msg)
            except Exception as e: log.error(f"Daily stats fail {t}: {e}")

# ---------- Commands ----------
@dp.message(Command("SetTarget"))
async def cmd_set(message: Message):
    if message.from_user.id!=ADMIN_ID: return await message.reply("❌ Not authorized")
    args=message.text.split(maxsplit=1)
    if len(args)<2: return await message.reply("Usage: /SetTarget <chat_id>")
    await add_target(args[1]); await message.reply(f"✅ Added target: {args[1]}")

@dp.message(Command("ClearTargets"))
async def cmd_clear(message: Message):
    if message.from_user.id!=ADMIN_ID: return await message.reply("❌ Not authorized")
    await clear_targets(); await message.reply("🗑 All targets cleared")

@dp.message(Command("StartPrediction"))
async def cmd_start(message: Message):
    global prediction_task
    if message.from_user.id!=ADMIN_ID: return await message.reply("❌ Not authorized")
    tgts=await get_targets()
    if not tgts: return await message.reply("❌ No targets")
    if prediction_task and not prediction_task.done(): return await message.reply("⚠️ Already running")
    prediction_task=asyncio.create_task(prediction_worker(tgts))
    await message.reply("🚀 Prediction started!")

@dp.message(Command("StopPrediction"))
async def cmd_stop(message: Message):
    global prediction_task
    if message.from_user.id!=ADMIN_ID: return await message.reply("❌ Not authorized")
    if prediction_task and not prediction_task.done():
        prediction_task.cancel(); prediction_task=None
        await message.reply("🛑 Stopped")
    else: await message.reply("⚠️ Not running")

@dp.message(Command("Status"))
async def cmd_status(message: Message):
    tgts=await get_targets()
    running=prediction_task and not prediction_task.done()
    await message.reply(f"⚙️ Status: {'🟢 Running' if running else '🔴 Stopped'}\n📋 Targets: {tgts}")

@dp.message(Command("Notice"))
async def cmd_notice(message: Message):
    if message.from_user.id!=ADMIN_ID: return await message.reply("❌ Not authorized")
    args=message.text.split(maxsplit=1)
    if len(args)<2: return await message.reply("Usage: /Notice <msg>")
    for t in await get_targets():
        try: cid=int(t) if t.lstrip("-").isdigit() else t; await bot.send_message(cid,f"📢 <b>NOTICE</b>\n\n{args[1]}")
        except Exception as e: log.error(f"Notice fail {t}: {e}")
    await message.reply("✅ Notice sent")

@dp.message(Command("Stats"))
async def cmd_stats(message: Message):
    total,wins,losses,pending,rate=await get_stats()
    await message.reply(f"📊 Stats\n━━━━━━━━━━━\n✅ Wins: {wins}\n❌ Losses: {losses}\n⏳ Pending: {pending}\n📋 Total: {total}\n🏆 Win Rate: {rate}%")

# ---------- Fallback Handler ----------
@dp.message()
async def handle_fallback(message: Message):
    if message.text and message.text.startswith("/"):
        await message.reply("⚠️ Unknown command. Type /start to view available commands.")
    else:
        await message.reply("🤖 I only respond to commands. Type /start 📋.")

# ---------- Entry ----------
async def main():
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(daily_stats_worker())
    await dp.start_polling(bot)

if __name__=="__main__":
    try: asyncio.run(main())
    except (KeyboardInterrupt,SystemExit): pass
