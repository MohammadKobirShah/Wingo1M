# 🌟 Kobir ✦ WinGo 1M Bot

A Telegram bot that:
- Fetches WinGo 1M results every 60s
- Predicts BIG/SMALL with dynamic Martingale multipliers
- Keeps last 15 trades in DB
- Broadcasts predictions to multiple groups/channels
- Supports admin commands for control
- Auto-sends **Daily Stats Summary** at 12:00 AM Asia/Dhaka timezone 🌙

---

## ⚙️ Features
✅ Dynamic Multiplier (Martingale: WIN=reset, LOSS=double)  
✅ Stylish prediction messages with emojis  
✅ Multi-target support (`/SetTarget`)  
✅ Admin-only commands:
- `/StartPrediction`
- `/StopPrediction`
- `/Status`
- `/Stats`
- `/Notice <msg>`
- `/SetTarget <chat_id>`
- `/ClearTargets`

✅ Database always pruned (last 15 only)  
✅ Daily Auto Stats summary at Dhaka midnight 🌙  

---

## 📦 Setup

1. Clone project:
```bash
git clone https://github.com/MohammadKobirShah/Wingo1M.git
cd Wingo1M
