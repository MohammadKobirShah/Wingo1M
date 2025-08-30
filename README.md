# 🎰 🌟 KOBIR ✦ WINGO 1M BOT 🌟

> 🚀 A feature-packed **Telegram Prediction Bot** built with **Aiogram 3.x**.  
> It predicts **BIG/SMALL** every minute for WinGo 1M games, manages multipliers smartly,  
> supports **multiple channels/groups**, and sends **daily stats at 12:00 AM (🇧🇩 Dhaka time)**.  

---

## ✨ Features

✅ **Smart Dynamic Multiplier**  
  • WIN → reset to **1x**  
  • LOSS → **double multiplier (Martingale)** up to **81x**

✅ **Stylish Messages** with Emojis 🎲📊  

✅ **Multi‑Target Support** 📌  
  • Add multiple groups/channels with `/SetTarget`  
  • Broadcast predictions & notices to ALL targets  

✅ **Admin Commands** 🔑  
  • `/StartPrediction` → Start auto posting  
  • `/StopPrediction` → Stop predictions  
  • `/Status` → Check bot + targets  
  • `/Stats` → Show wins, losses & win rate %  
  • `/Notice <msg>` → Broadcast custom message 📢  
  • `/SetTarget <chat_id_or_username>` → Add groups/channels  
  • `/ClearTargets` → Remove all targets  

✅ **Database Auto-Clean** 🗄️  
  • Only last **15 rounds & predictions** stored  

✅ **Daily Auto Summary** 🌙  
  • Posts recap of Wins, Losses, Win rate `%`  
  • Scheduled at **12:00 AM Asia/Dhaka timezone**  

---

## 🛠️ Requirements

- Python **3.10+**
- Telegram Bot Token (from **[@BotFather](https://t.me/BotFather)**)
- Your Telegram `ADMIN_ID` (get via [@userinfobot](https://t.me/userinfobot))
- A VPS or computer to host the bot (24/7 recommended)

---

## 📦 Installation

1. **Clone Repo**
   ```bash
   git clone https://github.com/MohammadKobirShah/Wingo1M.git
   cd Wingo1M
   ```

2. **Create Virtual Env**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set Environment Variables**
   ```bash
   export BOT_TOKEN="123456:ABC-YOUR-TOKEN"
   export ADMIN_ID="123456789"
   ```

---

## 🚀 Run the Bot

```bash
source venv/bin/activate
python bot.py
```

---

## 🌍 Hosting on VPS (Ubuntu/Debian) [Step‑by‑Step]

### 1. Update & Install Essentials
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git
```

### 2. Clone the Repo
```bash
git clone https://github.com/MohammadKobirShah/Wingo1M.git
cd Wingo1M
```

### 3. Setup Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Add Bot Token Permanently
Edit `~/.bashrc`
```bash
nano ~/.bashrc
```
Add at bottom:
```bash
export BOT_TOKEN="123456:ABC-YOUR-TOKEN"
export ADMIN_ID="123456789"
```
Reload:
```bash
source ~/.bashrc
```

### 5. Test Run
```bash
python3 bot.py
```

✅ If bot responds to `/start` → working.

---

### 6. Run 24/7 with `systemd`

Create service file:
```bash
sudo nano /etc/systemd/system/wingo-bot.service
```

Paste:
```ini
[Unit]
Description=Kobir WinGo Bot
After=network.target

[Service]
User=yourusername
WorkingDirectory=/home/yourusername/wingo-bot
ExecStart=/home/yourusername/wingo-bot/venv/bin/python bot.py
Restart=always
Environment=BOT_TOKEN=123456:ABC-YOUR-TOKEN
Environment=ADMIN_ID=123456789

[Install]
WantedBy=multi-user.target
```

Save & close.

---

### 7. Enable & Start Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable Wingo1M
sudo systemctl start Wingo1M
```

Check logs:
```bash
journalctl -u Wingo1M -f
```

Now bot runs **24/7**, restarts if VPS reboots.

---

## 🎯 Example Bot Messages

```
🔥 𝐊𝐎𝐁𝐈𝐑 ✦ 𝐖𝐈𝐍𝐆𝐎 𝟏𝐌 🔥
━━━━━━━━━━━━━━━━━━━━━━━
🤖 Prime Predictions

📜 Recent Rounds (Last 15)
━━━━━━━━━━━━━━━━━━━━━━━
🎲 506 → 8 (BIG) | ✅ WIN
🎲 505 → 9 (BIG) | ❌ LOSS

━━━━━━━━━━━━━━━━━━━━━━━
📊 Next Trade: 507
🔮 Prediction: BIG
💸 Multiplier: 2x
⏱ Updates every 60s

⚠️ 🇵‌🇱‌🇦‌🇾‌ 🇦‌🇹‌ 🇴‌🇼‌🇳‌ 🇷‌🇮‌🇸‌🇰‌ 🎲
```

---

## 🌙 Daily Auto Summary (Asia/Dhaka 12:00 AM)

```
📊 Daily Prediction Summary
━━━━━━━━━━━━━━━━━━━━━━━
✅ Wins: 14
❌ Losses: 5
⏳ Pending: 0
📋 Total: 19
🏆 Win Rate: 73.68%

⚠️ 🇵‌🇱‌🇦‌🇾‌ 🇦‌🇹‌ 🇴‌🇼‌🇳‌ 🇷‌🇮‌🇸‌🇰‌ 🎲
```

---

## ⚠️ Disclaimer
This bot is for **educational/predictive fun use only**.  
Trading/gambling involves risk. **Use at your own responsibility!**

---

## 👨‍💻 Author
Developed for **Kobir ✦ WinGo 1M Bot** 💖  
```

---

✅ With this setup:  
- Your **bot is deployable** on **any VPS** (DigitalOcean, Contabo, AWS, etc.)  
- README is **sexy, emoji‑rich & professional** ✨  
- Deployment is **step‑by‑step** for beginners  

---

👉 Do you also want me to add a **Dockerfile + docker‑compose.yml** so you can run this bot with a single `docker-compose up -d` command on any VPS?
