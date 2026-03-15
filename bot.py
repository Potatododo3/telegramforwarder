import logging
import asyncio
import io
import os
from dotenv import load_dotenv

import discord
import aiohttp
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = int(os.getenv("TELEGRAM_CHAT_ID"))

print("TOKEN:", DISCORD_TOKEN[:10], "...")  # only prints first 10 chars

# Discord channel ID -> Telegram topic (thread) ID
CHANNEL_TOPIC_MAP = {
    1192138473637937193: 14,
    1410047255716692008: 16,
    1379938404082516148: 18,
    1363305237900951582: 20,
    1247912859141279784: 25,
    1182042555756597410: 27,
    1208146686158049352: 29,
}

MAX_CAPTION_LEN = 1024  # Telegram caption limit
MAX_TEXT_LEN    = 4096  # Telegram message limit

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("discord_tg_forwarder")

print("CHAT ID:", TELEGRAM_CHAT_ID)
print("MAP:", CHANNEL_TOPIC_MAP)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def escape_html(text: str) -> str:
    """Escape characters that break Telegram HTML mode."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )


def build_embed_text(embed: discord.Embed, author_name: str) -> str:
    """Convert a Discord embed into a Telegram HTML-formatted string."""
    parts = []

    if embed.author and embed.author.name:
        parts.append(f"<b>{escape_html(embed.author.name)}</b>")

    if embed.title:
        title = embed.title
        if embed.url:
            parts.append(f'<a href="{embed.url}"><b>{escape_html(title)}</b></a>')
        else:
            parts.append(f"<b>{escape_html(title)}</b>")

    if embed.description:
        parts.append(escape_html(embed.description))

    for field in embed.fields:
        parts.append(f"<b>{escape_html(field.name)}:</b> {escape_html(field.value)}")

    if embed.footer and embed.footer.text:
        parts.append(f"<i>{escape_html(embed.footer.text)}</i>")

    parts.append(f"Sent by: {escape_html(author_name)}")

    return "\n".join(parts)


def build_text_message(message: discord.Message) -> str:
    """Build a plain text forward from a normal Discord message."""
    parts = []
    header = f"<b>{escape_html(message.author.display_name)}</b>"
    if message.guild:
        header += f" in <b>#{escape_html(message.channel.name)}</b>"
    parts.append(header)

    if message.content:
        parts.append(escape_html(message.content))

    return "\n".join(parts)


def chunk_text(text: str, limit: int = MAX_TEXT_LEN) -> list[str]:
    """Split text into chunks that fit within Telegram's message limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunks.append(text[:limit])
        text = text[limit:]
    return chunks


# ─── Bot ──────────────────────────────────────────────────────────────────────

class Forwarder(discord.Client):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tg = Bot(token=TELEGRAM_BOT_TOKEN)

    async def on_ready(self):
        log.info("Logged in as %s (id=%s)", self.user, self.user.id)

    async def on_disconnect(self):
        log.warning("Discord disconnected - will auto-reconnect")

    async def on_message(self, message: discord.Message):
        # Ignore bots and DMs
        if message.author.bot:
            return

        topic_id = CHANNEL_TOPIC_MAP.get(message.channel.id)
        if topic_id is None:
            return

        log.info(
            "Forwarding message %s from channel %s to topic %s",
            message.id, message.channel.id, topic_id,
        )

        try:
            await self._forward(message, topic_id)
        except Exception as exc:
            log.error("Failed to forward message %s: %s", message.id, exc, exc_info=True)

    async def _forward(self, message: discord.Message, topic_id: int):
        # 1. Handle embeds
        for embed in message.embeds:
            text = build_embed_text(embed, message.author.display_name)
            # If embed has an image, send photo + text as caption
            img_url = None
            if embed.image and embed.image.url:
                img_url = embed.image.url
            elif embed.thumbnail and embed.thumbnail.url:
                img_url = embed.thumbnail.url

            if img_url:
                await self._send_url_photo(img_url, text, topic_id)
            else:
                for chunk in chunk_text(text):
                    await self.tg.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        message_thread_id=topic_id,
                        text=chunk,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=False,
                    )

        # 2. Handle attachments
        if message.attachments:
            async with aiohttp.ClientSession() as session:
                for attachment in message.attachments:
                    caption = escape_html(message.content or "")[:MAX_CAPTION_LEN] or None
                    await self._send_attachment(session, attachment, caption, topic_id)
            return  # attachments sent, done

        # 3. Plain text / link only message (no embeds, no attachments)
        if message.content or (not message.embeds and not message.attachments):
            text = build_text_message(message)
            for chunk in chunk_text(text):
                await self.tg.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    message_thread_id=topic_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False,
                )

    async def _send_url_photo(self, url: str, caption: str, topic_id: int):
        """Download a photo from a URL and send it to Telegram."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        log.warning("Could not download image %s (status %s)", url, resp.status)
                        return
                    data = await resp.read()

            await self.tg.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                message_thread_id=topic_id,
                photo=io.BytesIO(data),
                caption=caption[:MAX_CAPTION_LEN] if caption else None,
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            log.error("Telegram error sending photo: %s", e)
        except aiohttp.ClientError as e:
            log.error("HTTP error downloading image: %s", e)

    async def _send_attachment(
        self,
        session: aiohttp.ClientSession,
        attachment: discord.Attachment,
        caption: str | None,
        topic_id: int,
    ):
        """Download a Discord attachment and upload it to Telegram."""
        try:
            async with session.get(attachment.url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status != 200:
                    log.warning("Could not download attachment %s", attachment.url)
                    return
                data = await resp.read()

            file_obj = io.BytesIO(data)
            file_obj.name = attachment.filename
            ct = attachment.content_type or ""

            common = dict(
                chat_id=TELEGRAM_CHAT_ID,
                message_thread_id=topic_id,
                caption=caption,
                parse_mode=ParseMode.HTML if caption else None,
            )

            if ct.startswith("image/"):
                await self.tg.send_photo(photo=file_obj, **common)
            elif ct.startswith("video/"):
                await self.tg.send_video(video=file_obj, **common)
            else:
                await self.tg.send_document(document=file_obj, **common)

        except TelegramError as e:
            log.error("Telegram error sending attachment %s: %s", attachment.filename, e)
        except aiohttp.ClientError as e:
            log.error("HTTP error downloading attachment %s: %s", attachment.filename, e)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    client = Forwarder()
    log.info("Starting Discord forwarder...")
    try:
        client.run(DISCORD_TOKEN, reconnect=True, log_handler=None)
    except Exception as e:
        print("CRASHED:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
