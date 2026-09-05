from permissions import *


async def log_event(context: ContextTypes.DEFAULT_TYPE, text: str, parse_mode: str = None):
    """#14 — send a short line to the admin-configured logger channel, if any."""
    settings = BOT_DATA.get("settings", {})
    if not settings.get("logger_enabled") or not settings.get("logger_channel_id"):
        return
    try:
        await context.bot.send_message(chat_id=settings["logger_channel_id"], text=text, parse_mode=parse_mode)
    except Exception:
        log.exception("Failed to send to logger channel")


async def dm_all_admins(context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode: str = None):
    """Send a message to every admin's private chat (owner + BOT_DATA['admins']).
    One admin having blocked the bot / never opened a DM must never stop the
    others from getting it, so each send is isolated."""
    targets = set(BOT_DATA.get("admins", []))
    if OWNER_ID:
        targets.add(OWNER_ID)
    for admin_id in targets:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            log.warning("Could not DM admin %s (bot blocked / never started a DM)", admin_id)


def clickable_user(user_obj) -> str:
    """HTML mention link to a user's Telegram profile — same pattern used by
    the Support flow, reused everywhere a user's name is shown to an admin
    (Live Activity, admin DMs, Support tickets, join alerts, etc.). Falls
    back to a plain @username link when a username exists (works even if
    the user has since blocked the bot), tg://user?id otherwise."""
    name = html.escape(user_obj.full_name or str(user_obj.id))
    if getattr(user_obj, "username", None):
        return f'<a href="https://t.me/{user_obj.username}">{name}</a>'
    return f'<a href="tg://user?id={user_obj.id}">{name}</a>'


_LANGUAGE_NAME_MAP = {
    "en": "English", "hi": "Hindi", "ur": "Urdu", "bn": "Bengali", "ta": "Tamil",
    "te": "Telugu", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "pa": "Punjabi", "ar": "Arabic", "es": "Spanish", "fr": "French", "de": "German",
    "pt": "Portuguese", "ru": "Russian", "id": "Indonesian", "tr": "Turkish", "zh": "Chinese",
    "ja": "Japanese", "ko": "Korean", "it": "Italian", "vi": "Vietnamese", "fa": "Persian",
}


def build_join_details(update: Update, is_new: bool) -> str:
    """Full detail card for a /start — new user OR bot started inside a
    group — so admins get the complete picture in one glance. HTML: Name
    is a clickable link straight to the user's profile."""
    user = update.effective_user
    chat = update.effective_chat
    lbl = to_title_small_caps
    username_display = f"@{user.username}" if user.username else "Not Set"
    saved_lang = BOT_DATA.get("users", {}).get(str(user.id), {}).get("lang")
    lang_code = (saved_lang or user.language_code or "").lower()
    lang_display = _LANGUAGE_NAME_MAP.get(lang_code, user.language_code or "Unknown")

    lines = [
        "🆕 " + lbl("New User Started Bot" if is_new else "Bot Started In Group"),
        "",
        _CARD_SEP,
        "",
        "👤 " + lbl("User Information"),
        "",
        f"{lbl('Name')} : {clickable_user(user)}",
        f"{lbl('Username')} : {html.escape(username_display)}",
        f"{lbl('User Id')} : {user.id}",
    ]

    if chat.type in ("group", "supergroup"):
        lines += [
            "",
            "👨‍👩‍👧 " + lbl("Group Details"),
            "",
            f"{lbl('Group')} : {html.escape(chat.title or '')}",
            f"{lbl('Group Id')} : {chat.id}",
        ]
    else:
        lines += [
            "",
            "🌐 " + lbl("Account Details"),
            "",
            f"{lbl('Language')} : {lbl(lang_display)}",
            f"{lbl('Chat Type')} : {lbl(chat.type.capitalize())}",
            f"{lbl('Telegram Premium')} : {lbl('Yes') if getattr(user, 'is_premium', False) else lbl('No')}",
        ]

    lines += [
        "",
        "🕒 " + lbl("Started At"),
        "",
        now_ist_str("%d %B %Y • %H:%M:%S") + " IST",
        "",
        _CARD_SEP,
    ]
    return "\n".join(lines)


async def notify_admins_new_start(context: ContextTypes.DEFAULT_TYPE, update: Update, is_new: bool):
    """New user starts the bot, or the bot is (re-)started inside a group —
    full details go to every admin's DM, and to the logger group if set."""
    if not BOT_DATA["settings"].get("detailed_join_alerts", True):
        return
    is_group = update.effective_chat.type in ("group", "supergroup")
    if not (is_new or is_group):
        return
    text = build_join_details(update, is_new)
    await dm_all_admins(context, text, parse_mode="HTML")
    await log_event(context, text, parse_mode="HTML")


async def log_user_activity(context: ContextTypes.DEFAULT_TYPE, update: Update, url: str):
    """Anti-misuse monitoring: record what a user pastes into the bot and
    surface it live to the owner's DM (+ logger group), with a one-tap Ban
    button — this is a check/monitoring tool only, not automatic action."""
    user = update.effective_user
    chat = update.effective_chat
    entry = {
        "time": datetime.utcnow().isoformat(),
        "user_id": user.id,
        "name": user.full_name,
        "username": user.username,
        "chat_type": chat.type,
        "url": url,
    }
    buf = BOT_DATA.setdefault("activity_log", [])
    buf.append(entry)
    if len(buf) > 300:
        del buf[: len(buf) - 300]
    save_data()

    # The admin-DM ping for this happens once the reel is actually
    # delivered, via build_reel_delivered_card / send_reel_delivered_card
    # (same "📡 Feed To Admin DM" toggle), so only one message goes out per
    # request instead of two differently-formatted ones.


def track_sent_message(chat_id: int, message_id: int):
    """Small per-chat ring buffer backing 'Delete All Bot Messages'."""
    key = str(chat_id)
    buf = BOT_DATA.setdefault("sent_messages", {}).setdefault(key, [])
    buf.append(message_id)
    if len(buf) > 200:
        del buf[: len(buf) - 200]


def bump_usage(uid: str):
    """Daily/monthly download counters, resetting on date/month change."""
    u = BOT_DATA["users"].get(uid)
    if not u:
        return
    today = datetime.utcnow().strftime("%Y-%m-%d")
    month = datetime.utcnow().strftime("%Y-%m")
    if u.get("downloads_today_date") != today:
        u["downloads_today"] = 0
        u["downloads_today_date"] = today
    if u.get("downloads_month_key") != month:
        u["downloads_month"] = 0
        u["downloads_month_key"] = month
    u["downloads_today"] += 1
    u["downloads_month"] += 1


IST_OFFSET = timedelta(hours=5, minutes=30)


def to_ist(dt: datetime) -> datetime:
    """All timestamps are stored in UTC internally (unchanged, so old data
    and any external tooling stays correct) — this only converts for
    on-screen display, since admins kept asking why times looked wrong."""
    return dt + IST_OFFSET


def now_ist_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return to_ist(datetime.utcnow()).strftime(fmt)


def iso_to_ist_str(iso_str: str, fmt: str = "%d %b %Y, %H:%M") -> str:
    """Safely convert a stored UTC ISO timestamp to an IST display string.
    Falls back to the raw stored value if it can't be parsed, rather than
    ever raising."""
    if not iso_str:
        return "?"
    try:
        return to_ist(datetime.fromisoformat(iso_str)).strftime(fmt)
    except Exception:
        return str(iso_str)


def human_uptime() -> str:
    secs = int(time.time() - START_TIME)
    d, secs = divmod(secs, 86400)
    h, secs = divmod(secs, 3600)
    m, _ = divmod(secs, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    parts.append(f"{m}m")
    return " ".join(parts)


def human_uptime_full() -> str:
    """Same as human_uptime() but with seconds, in the small-caps
    'Xᴅᴀʏs, Yʜ:Zᴍ:Ws' style used by the /ping quote block."""
    secs = int(time.time() - START_TIME)
    d, secs = divmod(secs, 86400)
    h, secs = divmod(secs, 3600)
    m, s = divmod(secs, 60)
    if d:
        return f"{d}ᴅᴀʏs, {h}ʜ:{m:02d}ᴍ:{s:02d}s"
    return f"{h}ʜ:{m:02d}ᴍ:{s:02d}s"


def get_memory_usage_mb():
    try:
        import psutil

        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
    except Exception:
        try:
            import resource

            return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
        except Exception:
            return None


def get_cpu_percent():
    """System-wide CPU usage %, or None if psutil isn't installed."""
    try:
        import psutil

        return psutil.cpu_percent(interval=0.3)
    except Exception:
        return None


def get_ram_percent():
    """System-wide RAM usage %, or None if psutil isn't installed."""
    try:
        import psutil

        return psutil.virtual_memory().percent
    except Exception:
        return None


def get_disk_percent():
    """Disk usage % of the filesystem the bot runs on, or None if psutil
    isn't installed."""
    try:
        import psutil

        return psutil.disk_usage(os.getcwd()).percent
    except Exception:
        return None


async def _delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except Exception:
        pass


async def schedule_delete(context, chat_id, message_id, seconds):
    if seconds and seconds > 0:
        context.job_queue.run_once(
            _delete_message_job, when=timedelta(seconds=seconds),
            data={"chat_id": chat_id, "message_id": message_id},
        )


# ----------------------------------------------------------------------------
# Dynamic menu engine — render_menu is the ONE function every command/callback
# uses to show a menu (#1, #2, #3). Same-message edit-in-place navigation.
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
