"""Env vars, paths, logging and optional-dependency detection. See README.md for setup."""

import os
import io
import html
import re
import json
import csv
import time
import shutil
import subprocess
import asyncio
import logging
import tempfile
from datetime import datetime, timedelta
from urllib.parse import quote

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    CopyTextButton,
    MessageEntity,
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ApplicationHandlerStop,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    ChatJoinRequestHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import Forbidden, BadRequest, RetryAfter, TelegramError

import yt_dlp

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or 0)
MONGO_URI = os.environ.get("MONGO_URI", "").strip()
BACKUP_INTERVAL_HOURS = int(os.environ.get("BACKUP_INTERVAL_HOURS", "12"))

DATA_FILE = "bot_data.json"
# "Update Backup" seed files — see _apply_seed_files_if_present() and the
# 📦 Update Backup admin-panel button. Drop both, with these EXACT names,
# next to bot.py in the GitHub repo before pushing a code update. If the
# host wipes local storage on deploy (no bot_data.json, empty MongoDB),
# the bot auto-loads these back in on startup — no manual restore needed.
SEED_SETTINGS_FILE = "bot_settings_seed.json"
SEED_USERS_FILE = "bot_users_seed.json"
BACKUP_DIR = "backups"
DOWNLOAD_DIR = "downloads"
PLUGIN_DIR = "plugins"
MAX_LOCAL_BACKUPS = 10
BACKUP_KEY_FILE = "backup.key"  # local Fernet key — never put this in the repo/git

# ----------------------------------------------------------------------------
# 🗄 Mongo Plugin — lets the owner paste a MongoDB URI live from the Admin
# Panel (🍭 Update Backup > 🗄 Mongo Plugin) instead of only via the
# MONGO_URI env var. Precedence: MONGO_URI env var ALWAYS wins if set (it's
# the infra-managed path) — the panel-set URI is only used when no env var
# is present. Whatever is set via the panel is persisted to this small
# local file (separate from bot_data.json) so it survives a restart even
# before BOT_DATA itself has loaded — same pattern as BACKUP_KEY_FILE.
# ----------------------------------------------------------------------------
MONGO_CONFIG_FILE = "mongo_config.json"
MONGO_URI_SOURCE = "env" if MONGO_URI else None   # "env" | "admin_panel" | None
MONGO_CONNECTED_AT = None   # ISO timestamp of when this URI was first attached
if not MONGO_URI and os.path.exists(MONGO_CONFIG_FILE):
    try:
        with open(MONGO_CONFIG_FILE, "r", encoding="utf-8") as _f:
            _mc = json.load(_f)
        if _mc.get("uri"):
            MONGO_URI = _mc["uri"].strip()
            MONGO_URI_SOURCE = "admin_panel"
            MONGO_CONNECTED_AT = _mc.get("connected_at")
    except Exception:
        pass  # corrupt/unreadable file — just start unconfigured, never fatal

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(PLUGIN_DIR, exist_ok=True)


# ffmpeg is only needed when yt-dlp has to merge separate video+audio
# streams. Most reels are already muxed, so try a system install first and
# fall back to the portable imageio-ffmpeg binary if that's missing.
FFMPEG_PATH = shutil.which("ffmpeg")
FFPROBE_PATH = shutil.which("ffprobe")
if not FFMPEG_PATH:
    try:
        import imageio_ffmpeg

        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_PATH = None
FFMPEG_AVAILABLE = bool(FFMPEG_PATH)
# imageio-ffmpeg only ships the ffmpeg binary, not ffprobe, so we track this
# separately and do audio extraction via a direct ffmpeg call (cb_get_audio)
# instead of yt-dlp's ffprobe-dependent postprocessor.
FFPROBE_AVAILABLE = bool(FFPROBE_PATH)


def _ytdlp_extract_with_retry(opts: dict, url: str, download: bool = True):
    """Run yt-dlp's extract_info with one automatic retry.

    A stale extractor cache is a common cause of "No video formats found"
    or "Unable to extract" errors after Instagram changes something on
    their end. On those known-transient signatures we clear the cache once
    and retry before giving up. Genuinely private/deleted/invalid links
    still fail immediately since retrying can't help those.
    """
    transient_markers = (
        "no video formats found",
        "requested format is not available",
        "unable to extract",
    )
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            return ydl.extract_info(url, download=download)
        except Exception as e:
            msg = str(e).lower()
            if not any(m in msg for m in transient_markers):
                raise
            log.warning("yt-dlp extraction hit a possibly-stale-cache error, clearing cache and retrying once: %s", e)
            try:
                ydl.cache.remove()
            except Exception:
                pass
    # Retry with a fresh YoutubeDL instance so the cleared cache actually takes effect.
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=download)

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")

if FFMPEG_AVAILABLE:
    log.info("ffmpeg found at: %s", FFMPEG_PATH)
else:
    log.warning(
        "ffmpeg not found. Downloads will use a no-merge format (still works, "
        "occasionally slightly lower max quality). Install ffmpeg or "
        "`pip install imageio-ffmpeg` to always get the absolute best quality."
    )

# ----------------------------------------------------------------------------
# Local branded QR generation (replaces the old api.qrserver.com URL, which
# gave a plain black-on-white square and depended on a third-party service
# being reachable, separately from the bot itself). Same graceful-fallback
# pattern as ffmpeg above: works best with `qrcode[pil]` installed, degrades
# to a plain local QR if only `qrcode` is present, and falls all the way
# back to the old remote-URL QR only if `qrcode` isn't installed at all.
# ----------------------------------------------------------------------------
QRCODE_AVAILABLE = False
QRCODE_STYLED_AVAILABLE = False
try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    from qrcode.image.styles.colormasks import SolidFillColorMask

    QRCODE_AVAILABLE = True
    QRCODE_STYLED_AVAILABLE = True
except ImportError:
    try:
        import qrcode

        QRCODE_AVAILABLE = True
    except ImportError:
        pass

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

if QRCODE_AVAILABLE and PIL_AVAILABLE:
    log.info(
        "QR generation: local %s QR enabled.",
        "styled (rounded + branded)" if QRCODE_STYLED_AVAILABLE else "plain",
    )
else:
    log.warning(
        "qrcode/Pillow not found — payment QR codes will fall back to the "
        "remote api.qrserver.com URL. Run `pip install \"qrcode[pil]\"` for "
        "nicer, fully local QR codes that don't depend on a third party."
    )

# ----------------------------------------------------------------------------
# PDF report (charts) + encrypted backup — same graceful-fallback pattern as
# qrcode/Pillow above. Neither is a hard requirement to run the bot; the
# admin panel just tells you what to `pip install` if a feature is missing.
# ----------------------------------------------------------------------------
PDF_REPORT_AVAILABLE = False
try:
    import matplotlib
    matplotlib.use("Agg")  # headless — no display server on a bot host
    import matplotlib.pyplot as plt
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors as rl_colors
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage,
    )
    from reportlab.lib.styles import getSampleStyleSheet

    PDF_REPORT_AVAILABLE = True
except ImportError:
    log.warning(
        "matplotlib/reportlab not found — 📊 PDF Report will be unavailable. "
        "Run `pip install matplotlib reportlab` to enable it."
    )

BACKUP_ENCRYPTION_AVAILABLE = False
try:
    from cryptography.fernet import Fernet, InvalidToken

    BACKUP_ENCRYPTION_AVAILABLE = True
except ImportError:
    log.warning(
        "`cryptography` not found — backups will be saved unencrypted. "
        "Run `pip install cryptography` to enable encrypted backups."
    )


__all__ = [_n for _n in dir() if not _n.startswith("__")]
