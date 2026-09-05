from qr import *


START_TIME = time.time()

INSTAGRAM_URL_RE = re.compile(
    r"(https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_\-]+/?\S*)"
)


def _is_private_chat(update: Update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type == "private")


def _message_mentions_this_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True when a message explicitly tags this bot. Useful in groups where
    privacy mode is disabled and we must never answer unrelated chatter."""
    try:
        username = (context.bot.username or "").lower()
    except Exception:
        username = ""
    text = (update.effective_message.text or "").lower() if update.effective_message else ""
    return bool(username and f"@{username}" in text)


def _safe_filename(value: str, fallback: str = "Instagram_Audio") -> str:
    value = re.sub(r'[\\/:*?"<>|]+', " ", str(value or ""))
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value[:80] or fallback)

# ----------------------------------------------------------------------------
# Unicode "style" helpers (#1 — Style Text)
# ----------------------------------------------------------------------------

SMALL_CAPS_MAP = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ", "g": "ɢ",
    "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
    "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "ꜱ", "t": "ᴛ", "u": "ᴜ",
    "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
}


def to_small_caps(text: str) -> str:
    """Bot-wide house style: Initial Capital + Unicode small caps.

    Every normal user/admin UI string that passes through this helper now
    follows the same typography, e.g. ``Stats & Activity`` ->
    ``Sᴛᴀᴛꜱ & Aᴄᴛɪᴠɪᴛʏ``. This keeps old generated messages from drifting
    between plain lowercase and all-small-caps styles.
    """
    out = []
    word_start = True
    for ch in str(text):
        if ch.isalpha() and ch.isascii():
            if word_start:
                out.append(ch.upper())
                word_start = False
            else:
                out.append(SMALL_CAPS_MAP.get(ch.lower(), ch))
        else:
            out.append(ch)
            # Start a new styled word after whitespace/punctuation, but not
            # after an already-styled Unicode small-cap glyph.
            word_start = not (ch.isalnum() or ch in "'’")
    return "".join(out)


def to_title_small_caps(text: str) -> str:
    """Alias for the single bot-wide Initial-Capital small-caps house style."""
    return to_small_caps(text)


# ----------------------------------------------------------------------------
# v2 build prompt — centralized small-caps strings (Section 10)
# ----------------------------------------------------------------------------
STR = {
    "processing": to_small_caps("processing your reel...") + "\n📥 " + to_small_caps("fetching") + " • 🔄 "
                  + to_small_caps("optimizing") + " • ✅ " + to_small_caps("almost done"),
    "done": "✅ " + to_small_caps("your reel is ready!") + "\n🎬 " + to_small_caps("saved and sent below"),
    "usage_title": to_small_caps("usage overview"),
    "how_to_use": (
        "<blockquote>"
        "𝐇𝐎𝐖 𝐓𝐎 𝐔𝐒𝐄\n\n"
        "➤ Cᴏᴘʏ ᴀɴʏ Iɴsᴛᴀɢʀᴀᴍ Rᴇᴇʟ ʟɪɴᴋ\n\n"
        "➤ Pᴀsᴛᴇ ᴛʜᴇ ʟɪɴᴋ ʜᴇʀᴇ ɪɴ ᴄʜᴀᴛ\n\n"
        "➤ Wᴀɪᴛ ᴀ ғᴇᴡ sᴇᴄᴏɴᴅs\n\n"
        "➤ Gᴇᴛ ʏᴏᴜʀ Rᴇᴇʟ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ɪɴsᴛᴀɴᴛʟʏ\n\n"
        "➤ 𝐍𝐎𝐓𝐄 : Oɴʟʏ Pᴜʙʟɪᴄ Iɴsᴛᴀɢʀᴀᴍ Rᴇᴇʟ ʟɪɴᴋs ᴀʀᴇ sᴜᴘᴘᴏʀᴛᴇᴅ"
        "</blockquote>"
    ),
    "support_prompt": to_small_caps("describe your issue (text/photo/video)"),
    "ticket_created": lambda tid: "✅ " + to_small_caps(f"ticket #{tid} created. we'll reply soon"),
    "ticket_closed": lambda tid: "🔒 " + to_small_caps(f"ticket #{tid} closed. need help again? tap") + " 🎧 " + to_small_caps("support"),
}

# Wrapped in to_small_caps() right here (not just at render time) so the
# `if rkb_action == "download":` string-matching in handle_text() still lines up
# with what the reply-keyboard button actually sends back — to_small_caps()
# is idempotent (re-applying it to already-styled text is a safe no-op), so
# this can't get out of sync with styled_kb_button()'s own wrapping below.
RKB_DOWNLOAD = to_title_small_caps("Download Reel")
RKB_USAGE = to_title_small_caps("My Usage")
RKB_GIFT = to_title_small_caps("Send A Gift")
RKB_LANGUAGE = to_title_small_caps("Language")
RKB_DEVELOPER = to_title_small_caps("Developer")
RKB_HOWTO = to_title_small_caps("How To Use")
RKB_SUPPORT = to_title_small_caps("Support")
RKB_ADMINPANEL = to_title_small_caps("Admin Panel")


def main_reply_keyboard(is_admin_user: bool = False, lang: str = None) -> ReplyKeyboardMarkup:
    """Persistent bottom keyboard, localized to the user's selected language.

    The callback/routing identifiers remain the same; only the visible labels
    change. This keeps existing bot functionality intact while making the
    whole persistent keyboard follow the selected language."""
    labels = _get_rkb_labels(lang)
    rows = [
        [styled_kb_button(labels["download"], style="success")],
        [styled_kb_button(labels["usage"], style="primary"), styled_kb_button(labels["gift"], style="primary")],
        [styled_kb_button(labels["language"], style="primary"), styled_kb_button(labels["developer"], style="primary")],
        [styled_kb_button(labels["howto"], style="danger"), styled_kb_button(labels["support"], style="danger")],
    ]
    if is_admin_user:
        rows.append([styled_kb_button(labels["admin"], style="primary")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)



def _map_alpha_digit(text: str, upper_base: int, lower_base: int, digit_base=None) -> str:
    out = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr(upper_base + (ord(ch) - ord("A"))))
        elif "a" <= ch <= "z":
            out.append(chr(lower_base + (ord(ch) - ord("a"))))
        elif digit_base and "0" <= ch <= "9":
            out.append(chr(digit_base + (ord(ch) - ord("0"))))
        else:
            out.append(ch)
    return "".join(out)


def to_bold_sans(text: str) -> str:
    return _map_alpha_digit(text, 0x1D5D4, 0x1D5EE, 0x1D7EC)


def to_bold_italic_sans(text: str) -> str:
    return _map_alpha_digit(text, 0x1D63C, 0x1D656, 0x1D7EC)


# -----------------------------------------------------------------------------
# User-facing error messages
# -----------------------------------------------------------------------------
# Keep technical exceptions (yt-dlp / ffmpeg / Telegram / network details)
# in the server/admin logs only. Users should always receive short, clean
# messages in the same typography as the rest of the bot UI.
USER_ERR_WRONG_FORMAT = (
    "❌ I" + to_small_caps("nvalid ") + "L" + to_small_caps("ink") + "\n\n"
    + "T" + to_small_caps("he link you sent is not a valid ")
    + "I" + to_small_caps("nstagram ") + "R" + to_small_caps("eel link.") + "\n\n"
    + "P" + to_small_caps("lease send a valid reel link to continue.") + "\n"
    + "F" + to_small_caps("or help, contact ") + "S" + to_small_caps("upport.")
)

USER_ERR_NOT_AVAILABLE = (
    "<blockquote>❌ " + to_title_small_caps("Not Available") + "\n\n"
    + to_title_small_caps("This Reel Can't Be Downloaded Right Now.") + "\n"
    + to_title_small_caps("Please Try Again Later Or Contact Support.")
    + "</blockquote>"
)


USER_ERR_AUDIO_NOT_AVAILABLE = (
    "<blockquote>❌ " + to_title_small_caps("Audio Not Available") + "\n\n"
    + to_title_small_caps("This Reel Doesn't Have An Audio Track To Extract.") + "\n"
    + to_title_small_caps("Please Try Again Later Or Contact Support.")
    + "</blockquote>"
)


USER_ERR_GENERIC = (
    "❌ " + to_bold_sans("Something went wrong") + "\n\n"
    + to_small_caps("Please try again later or contact support.")
)


def to_monospace(text: str) -> str:
    return _map_alpha_digit(text, 0x1D670, 0x1D68A, 0x1D7F6)


def to_fullwidth(text: str) -> str:
    out = []
    for ch in text:
        if ch == " ":
            out.append("\u3000")
        elif "!" <= ch <= "~":
            out.append(chr(ord(ch) + 0xFEE0))
        else:
            out.append(ch)
    return "".join(out)


def to_deco(text: str) -> str:
    return f"『 {text} 』"


STYLE_OPTIONS = [
    ("Small Caps", to_small_caps),
    ("Bold", to_bold_sans),
    ("Bold Italic", to_bold_italic_sans),
    ("Monospace", to_monospace),
    ("Fullwidth", to_fullwidth),
    ("Decorative", to_deco),
]

# ----------------------------------------------------------------------------
# Native colorful buttons (Bot API 9.4+ `style` field) — graceful fallback
# ----------------------------------------------------------------------------

try:
    InlineKeyboardButton(text="probe", callback_data="probe", style="primary")
    SUPPORTS_BUTTON_STYLE = True
except TypeError:
    SUPPORTS_BUTTON_STYLE = False
    log.warning(
        "Installed python-telegram-bot does not support button `style` "
        "(needs v22.7+). Colorful buttons will fall back to default look. "
        "Run: pip install -U python-telegram-bot"
    )

try:
    KeyboardButton(text="probe", style="primary")
    SUPPORTS_KB_BUTTON_STYLE = True
except TypeError:
    SUPPORTS_KB_BUTTON_STYLE = False


def premium_button_text(text: str) -> str:
    """First alphabetic character of EVERY word uppercase, rest of that
    word in small caps — same house style as to_title_small_caps(), used
    as the single place every button (inline + reply-keyboard) gets its
    typography from. Idempotent, so pre-styled constants stay stable even
    after passing through this a second time at render."""
    return to_title_small_caps(str(text))


# House style (requested): every inline button shows its emoji/icon at the
# END of the label instead of at the front — "Support Settings 🛠" instead
# of "🛠 Support Settings". Rather than hand-editing every one of the
# hundreds of styled_button(...) call sites across the file, this is done
# once, centrally, inside styled_button() itself, so it automatically
# applies to every button everywhere (top-level Admin Panel, every
# submenu, every confirm/cancel row, etc.) with zero risk of missing one.
_EMOJI_CHAR_RE = re.compile(
    "[\U0001F000-\U0001FFFF\u2190-\u21FF\u2300-\u27BF\u2B00-\u2BFF\uFE0F\u200D]"
)


def _move_emoji_to_end(text: str) -> str:
    """If `text` starts with one or more emoji (optionally separated by
    single spaces, e.g. '✅ 🛠 Label'), strip that leading emoji run and
    re-attach it to the end of the label instead: 'Label ✅ 🛠'. Text with
    no leading emoji, or that is emoji-only, is returned unchanged."""
    text = str(text)
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if _EMOJI_CHAR_RE.match(ch):
            i += 1
        elif ch == " " and i + 1 < n and _EMOJI_CHAR_RE.match(text[i + 1]):
            i += 1
        else:
            break
    prefix, rest = text[:i].strip(), text[i:].strip()
    if not prefix or not rest:
        return text
    return f"{rest} {prefix}"


def styled_button(text, callback_data=None, url=None, style=None):
    """Central inline-button renderer with premium typography."""
    kwargs = {}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style and SUPPORTS_BUTTON_STYLE:
        kwargs["style"] = style
    return InlineKeyboardButton(premium_button_text(_move_emoji_to_end(text)), **kwargs)


# ---- Activity Log: categorization + plain-English fix hints -----------------
# Every entry logged to BOT_DATA["error_log"] carries a "kind" so the panel
# can show *what* went wrong, *why* it likely happened, and *how* to fix it —
# instead of a raw, undated exception string nobody but a developer could
# read.
ERROR_KIND_INFO = {
    "force_join": (
        "🔒 Force-Join Check",
        "Couldn't verify a user's membership in the force-join channel.",
        "Make sure the bot is an admin in that channel, and that the "
        "channel is set correctly (use @username, or the -100... id for "
        "private channels) in Settings & Admins → Force-Join.",
    ),
    "broadcast": (
        "📢 Broadcast Delivery",
        "A message failed to send during a broadcast.",
        "Usually harmless — the recipient blocked the bot or never started "
        "a DM. Check the Broadcast Log for the full breakdown.",
    ),
    "mongo": (
        "🗄 Database",
        "Couldn't reach or sync with MongoDB.",
        "Check the connection string is correct (via Admin Panel > 🍭 "
        "Update Backup > 🗄 Mongo Plugin, or the MONGO_URI env var) and that the "
        "database allows connections from this server's IP. The bot keeps "
        "working on local storage meanwhile, so nothing is lost.",
    ),
    "download": (
        "⬇️ Download",
        "A reel/audio download failed.",
        "Usually the link was private, deleted, or Instagram briefly "
        "rate-limited the server. Ask the user to retry in a minute.",
    ),
    "conflict": (
        "⚔️ Duplicate Bot Instance",
        "Telegram rejected polling because another process is already "
        "polling with this same BOT_TOKEN.",
        "Stop the other running copy of this bot (an old deployment, a "
        "second terminal, a duplicate server) — only one instance can poll "
        "at a time. This can't be fixed from inside this process, since "
        "the conflicting instance is the other one.",
    ),
    "unhandled": (
        "🐞 Unexpected Error",
        "Something failed outside the usual error handling.",
        "Check the message below for the exact exception — if it keeps "
        "repeating for the same action, that action likely has a bug.",
    ),
}


def log_error(kind: str, detail: str) -> None:
    """Central place every part of the bot reports a problem to. Keeps the
    Activity Log screen consistent (same field names, always categorized)
    instead of every call site hand-rolling its own dict shape."""
    entries = BOT_DATA.setdefault("error_log", [])
    next_id = BOT_DATA.get("error_log_next_id", 1)
    entries.append({
        "id": next_id,
        "time": datetime.utcnow().isoformat(),
        "kind": kind if kind in ERROR_KIND_INFO else "unhandled",
        "detail": str(detail)[:400],
    })
    BOT_DATA["error_log_next_id"] = next_id + 1
    if len(entries) > 200:
        del entries[: len(entries) - 200]


def _short_btn_label(label: str, limit: int = 22) -> str:
    """Trims a long button label in admin list screens (e.g. Manage
    Buttons) so the row stays readable on a phone instead of the button
    text overflowing/getting cut off by Telegram."""
    label = str(label)
    return label if len(label) <= limit else label[: limit - 1].rstrip() + "…"


def toggle_label(base: str, is_on: bool) -> str:
    """Consistent ON/OFF rendering for every toggle button in the admin
    panel — a green tick when ON, a red cross when OFF, instead of the bare
    'ON'/'OFF' text every toggle used to hand-roll separately."""
    return f"{base}: {'✅ ON' if is_on else '❌ OFF'}"


def styled_kb_button(text, style=None):
    """Reply-keyboard button renderer with premium typography."""
    text = premium_button_text(text)
    if style and SUPPORTS_KB_BUTTON_STYLE:
        return KeyboardButton(text, style=style)
    return KeyboardButton(text)


# ----------------------------------------------------------------------------
# Default data / menu records (#1, #2, #4, #7)
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
