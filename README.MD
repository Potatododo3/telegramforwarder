# Discord to Telegram Forwarder

Forwards messages from specific Discord channels to specific Telegram forum topics in real time.

Supports text, embeds, images, videos, and file attachments.

---

## Requirements

- Python 3.10+
- A Discord bot token
- A Telegram bot token
- A Telegram group with Topics (forum mode) enabled

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourname/discord-tg-forwarder.git
cd discord-tg-forwarder
```

### 2. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If aiohttp fails to build on Windows:
```bash
pip install "aiohttp==3.9.3" --only-binary=aiohttp
```

If you get a `No module named 'audioop'` error (Python 3.13):
```bash
pip install audioop-lts
```

### 4. Create your .env file

Create a file named `.env` in the same folder as `bot.py` and fill in your values:

```dotenv
DISCORD_TOKEN=your_discord_bot_token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=-1001234567890
```

### 5. Configure the channel mapping

Open `bot.py` and edit `CHANNEL_TOPIC_MAP`:

```python
CHANNEL_TOPIC_MAP = {
    123456789012345678: 111,  # Discord channel ID : Telegram topic thread ID
    234567890123456789: 222,
}
```

**How to get Discord channel IDs:**
- Enable Developer Mode in Discord (Settings > Advanced > Developer Mode)
- Right-click any channel and click Copy Channel ID

**How to get Telegram chat ID:**
- Add your bot to the group as admin
- Send a message in the group
- Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in your browser
- Find `"chat":{"id":` in the result

**How to get Telegram topic IDs:**
- Send a message inside each topic
- Check getUpdates again and find `"message_thread_id"`

### 6. Discord bot setup

Go to https://discord.com/developers/applications/ and:
- Under **Bot**, enable **Message Content Intent** under Privileged Gateway Intents
- Invite the bot to your server with `Read Messages` and `Read Message History` permissions

### 7. Run the bot

```bash
python bot.py
```

---

## What gets forwarded

| Discord content | Telegram output |
|---|---|
| Plain text | Text message with author name |
| Links | Text message with link preview |
| Embeds | Formatted text with title, description, fields |
| Embed with image | Photo with embed text as caption |
| Images | Photo |
| Videos | Video |
| Other files | Document |

---

## Project structure

```
discord-tg-forwarder/
├── bot.py            # Main bot script
├── requirements.txt  # Python dependencies
├── .env.example      # Example environment variables
├── .env              # Your actual secrets (never commit this)
└── .gitignore
```

---

## License

MIT