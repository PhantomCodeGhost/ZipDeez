# 🎵 Telegram Media Packager Bot

A **private, high-performance Telegram bot** that collects forwarded audio files and documents, then packages them into a single ZIP archive — preserving **exact binary integrity** (no re-encoding, no compression, no metadata changes).

---

## ✨ Features

| Feature | Details |
|---|---|
| **Zero-loss packaging** | `ZIP_STORED` mode — files are stored verbatim |
| **Async architecture** | Built on `aiogram 3` + `asyncio` |
| **Per-user sessions** | Independent queues with TTL-based auto-expiry |
| **Smart deduplication** | Ignores re-forwarded duplicates by `file_unique_id` |
| **Auto-split archives** | Splits ZIP across multiple parts if > 2 GB |
| **Private access** | Whitelist-based user ID restriction |
| **Rate limiting** | Configurable `/zip` call limits per minute |
| **Retry logic** | Exponential back-off on failed downloads |
| **Graceful cleanup** | Temp files deleted after delivery |

---

## 📁 Project Structure

```
telegram-media-packager/
├── main.py                    # Entry point — bot bootstrap
├── config.py                  # Settings from .env
├── requirements.txt
├── .env.example               # Copy → .env and fill in values
│
├── bot/
│   ├── handlers/
│   │   ├── commands.py        # /start /status /clear /zip
│   │   └── media.py           # Audio & Document message handler
│   └── middlewares/
│       └── auth.py            # Whitelist-based auth
│
├── services/
│   ├── session.py             # Per-user file queue & TTL management
│   └── zipper.py              # ZIP creation & splitting logic
│
├── utils/
│   └── downloader.py          # Telegram file download with retries
│
├── storage/                   # (reserved for future Redis adapter)
└── tmp/                       # Auto-created: temp downloads & ZIPs
```

---

## 🚀 Quick Start

### 1 — Clone / download the project

```bash
git clone https://github.com/yourname/telegram-media-packager
cd telegram-media-packager
```

### 2 — Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Configure environment variables

```bash
cp .env.example .env
nano .env   # or open in any editor
```

**Minimum required settings:**

```env
BOT_TOKEN=123456789:ABCxxx         # From @BotFather
ALLOWED_USER_IDS=123456789         # Your Telegram user ID(s)
```

> **Find your user ID:** Message [@userinfobot](https://t.me/userinfobot) on Telegram.

### 5 — Run the bot

```bash
python main.py
```

You should see:
```
INFO  Starting Media Packager Bot...
INFO  Bot is ready. Polling...
```

---

## 🤖 Bot Commands

| Command | Action |
|---|---|
| `/start` | Initialize session & show help |
| `/status` | List all queued files |
| `/zip` | Download & package all files into ZIP |
| `/clear` | Clear your queue |

---

## 📲 Usage Walkthrough

1. Open your bot on Telegram
2. Send `/start`
3. **Forward** audio files or documents (from any chat or bot)
4. Bot confirms each: `✅ Added: song.mp3 · 4.2 MB (Total: 3 files)`
5. Send `/zip` — bot downloads all files and sends back a ZIP
6. Queue is auto-cleared after successful delivery

---

## ⚙️ Configuration Reference

All settings are in `.env`:

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | Telegram bot token from @BotFather |
| `ALLOWED_USER_IDS` | *(empty = all)* | Comma-separated list of allowed user IDs |
| `SESSION_TTL_SECONDS` | `3600` | Idle session expiry time (seconds) |
| `MAX_FILES_PER_USER` | `200` | Max files per session |
| `TEMP_DIR` | `./tmp` | Temporary storage path |
| `TG_FILE_SIZE_LIMIT` | `2147483648` | Telegram upload limit (2 GB) |
| `ZIP_FOLDER_PREFIX` | `Playlist` | Folder name prefix inside ZIP |
| `ZIP_RATE_LIMIT` | `3` | Max `/zip` calls per user per minute |
| `DOWNLOAD_RETRIES` | `3` | Download retry attempts |

---

## 🏗️ Architecture Notes

### File Integrity
- ZIP uses `zipfile.ZIP_STORED` — files are stored with zero compression
- `download_file()` from aiogram streams raw bytes directly to disk
- No intermediate processing, format conversion, or metadata stripping

### Session Lifecycle
```
/start or first file → session created
     ↓ files forwarded
     ↓ /zip → downloads → ZIP → sent → session cleared
     ↓ (or idle for SESSION_TTL_SECONDS → auto-expired)
```

### Split ZIP Logic
If total file size exceeds `TG_FILE_SIZE_LIMIT`:
- Files are greedily packed into parts (each under the limit)
- Sent as `Playlist_20250101_120000_part1.zip`, `_part2.zip`, etc.
- All parts share the same internal folder name

### Rate Limiting
- Simple sliding-window counter per user (in-memory)
- Resets every 60 seconds
- Configurable via `ZIP_RATE_LIMIT`

---

## 🛡️ Security

- **Whitelist-based access**: Only users in `ALLOWED_USER_IDS` can interact
- **No data persistence**: Files are cleaned up immediately after delivery
- **No external requests**: Bot only communicates with Telegram's API
- **Sanitized filenames**: Unsafe path characters stripped before writing to disk

---

## 🐛 Troubleshooting

**Bot doesn't respond**
- Check `BOT_TOKEN` is correct
- Ensure your user ID is in `ALLOWED_USER_IDS`
- Check `bot.log` for errors

**Download fails**
- Large files (>20 MB) require a local Bot API server or Telegram Premium bot
- Standard Bot API limits file downloads to 20 MB for bots
- Increase `DOWNLOAD_RETRIES` for flaky connections

**ZIP not delivered**
- File may exceed Telegram's 2 GB limit even after splitting
- Check available disk space in `TEMP_DIR`

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `aiogram` | Async Telegram bot framework |
| `python-dotenv` | `.env` file loading |
| `aiohttp` | HTTP client (used by aiogram) |
| `aiofiles` | Async file I/O |

All stdlib: `zipfile`, `asyncio`, `logging`, `pathlib`, `tempfile`

---

## 📝 License

MIT — use freely, modify as needed.
