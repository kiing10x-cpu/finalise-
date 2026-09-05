from text_style import *


DEFAULT_MENUS = {
    "start": {
        "text": (
            "<blockquote>"
            "Hᴇʟʟᴏ, {username}!\n\n"
            "𝐖𝐄𝐋𝐂𝐎𝐌𝐄 ᴛᴏ {bot_link}\n\n"
            "Yᴏᴜʀ ᴘᴇʀsᴏɴᴀʟ Iɴsᴛᴀɢʀᴀᴍ Rᴇᴇʟ ᴀssɪsᴛᴀɴᴛ.\n\n"
            "𝐓𝐇𝐈𝐒 𝐁𝐎𝐓 𝐂𝐀𝐍\n\n"
            "<u>➤ Dᴏᴡɴʟᴏᴀᴅ Iɴsᴛᴀɢʀᴀᴍ Rᴇᴇʟs</u>\n\n"
            "<u>➤ Gᴇᴛ Rᴇᴇʟ Cᴀᴘᴛɪᴏɴs</u>\n\n"
            "<u>➤ Gᴇᴛ Rᴇᴇʟ Aᴜᴅɪᴏ</u>\n\n"
            "𝐖𝐇𝐘 𝐂𝐇𝐎𝐎𝐒𝐄 𝐔𝐒?\n\n"
            "<u>➤ Nᴏ Wᴀᴛᴇʀᴍᴀᴋs</u>\n\n"
            "<u>➤ Hɪɢʜ-Qᴜᴀʟɪᴛʏ Rᴇᴇʟ Dᴏᴡɴʟᴏᴀᴅs</u>\n\n"
            "<u>➤ Fᴀsᴛ ᴀɴᴅ Sᴍᴏᴏᴛʜ Sᴇʀᴠɪᴄᴇ</u>\n\n"
            "<u>➤ Hᴀssʟᴇ-Fʀᴇᴇ ᴀɴᴅ Eᴀsʏ ᴛᴏ Uꜱᴇ</u>\n\n"
            "<u>➤ Sᴀᴠᴇs Tɪᴍᴇ ᴀɴᴅ Eғғᴏʀᴛ</u>\n\n"
            "<u>➤ Rᴇᴇʟ, Cᴀᴘᴛɪᴏɴ ᴀɴᴅ Aᴜᴅɪᴏ ɪɴ Oɴᴇ Pʟᴀᴄᴇ</u>\n\n"
            "<u>➤ Nᴏ Exᴛʀᴀ Tᴏᴏʟs ᴏʀ Cᴏᴍᴘʟɪᴄᴀᴛᴇᴅ Sᴛᴇᴘs</u>"
            "</blockquote>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "help_user": {
        "text": (
            f"{to_deco(to_small_caps('guide'))}\n\n"
            f"<u>➤ {to_small_caps('send a reel link')}</u>\n"
            f"<u>➤ {to_small_caps('get it in best quality')}</u>\n"
            f"<u>➤ {to_small_caps('tap get caption for a short quote')}</u>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "reel_result": {
        "text": STR["done"],
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [
            {"label": to_small_caps("📝 caption"), "type": "callback", "value": "get_caption", "row": 1, "style": "primary"},
            {"label": to_small_caps("🎵 audio"), "type": "callback", "value": "get_audio", "row": 1, "style": "primary"},
        ],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "disclaimer": {
        "text": (
            "<blockquote expandable>"
            "<b>Disclaimer &amp; Terms of Use</b>\n\n"
            "This bot is a general-purpose media-downloading tool provided for "
            "personal and fair-use purposes only. It does not host, store, own, "
            "or claim any rights over the content it retrieves.\n\n"
            "By using this bot, you confirm that:\n"
            "• You have the necessary rights or permissions to download the "
            "content you request, or that your use qualifies as fair use / "
            "fair dealing under applicable law.\n"
            "• You will not use this bot to download, redistribute, or "
            "republish copyrighted material without the rights holder's consent.\n"
            "• You are solely and fully responsible for how you use any content "
            "obtained through this bot.\n\n"
            "The bot operator does not monitor, endorse, or verify the "
            "ownership of any content requested by users, and accepts no "
            "liability for any misuse, copyright infringement, or violation of "
            "third-party rights arising from your use of this service. Files "
            "are delivered directly to you and are not permanently stored on "
            "the bot's servers.\n\n"
            "This service is provided \"as is\", without warranty of any kind, "
            "and may be modified, suspended, or discontinued at any time "
            "without prior notice. Continued use of this bot after any "
            "changes to these terms constitutes acceptance of the updated "
            "terms.\n\n"
            "Tap <b>Agree &amp; Continue</b> to confirm you have read and "
            "accepted these terms."
            "</blockquote>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [
            {"label": "✅ Agree & Continue", "type": "callback", "value": "agree_terms", "row": 1, "style": "success"}
        ],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "maintenance": {
        "text": (
            "ᴛʜᴇ ʙᴏᴛ ɪꜱ ᴛᴇᴍᴘᴏʀᴀʀɪʟʏ ᴏꜰꜰʟɪɴᴇ ꜰᴏʀ\n"
            "ꜱᴄʜᴇᴅᴜʟᴇᴅ ᴜᴘɢʀᴀᴅᴇꜱ ᴀɴᴅ ɪᴍᴘʀᴏᴠᴇᴍᴇɴᴛꜱ.\n\n"
            "ᴡᴇ'ʀᴇ ᴡᴏʀᴋɪɴɢ ᴛᴏ ᴍᴀᴋᴇ ᴛʜᴇ ʙᴏᴛ\n"
            "ꜰᴀꜱᴛᴇʀ, ꜱᴍᴏᴏᴛʜᴇʀ ᴀɴᴅ ʙᴇᴛᴛᴇʀ\n"
            "ꜰᴏʀ ᴇᴠᴇʀʏᴏɴᴇ.\n\n"
            "⏳ ᴡᴇ'ʟʟ ʙᴇ ʙᴀᴄᴋ ꜱʜᴏʀᴛʟʏ.\n\n"
            "ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ʏᴏᴜʀ\n"
            "ᴘᴀᴛɪᴇɴᴄᴇ & ꜱᴜᴘᴘᴏʀᴛ."
        ),
        "parse_mode": None,
        "image_file_id": None,
        "buttons": [
            {"label": "🔔 " + to_small_caps("notify me"), "type": "callback", "value": "maint_notify_me", "row": 1, "style": "danger"}
        ],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "bot_live": {
        "text": (
            "✅ 𝐁𝐎𝐓 𝐈𝐒 𝐋𝐈𝐕𝐄\n\n"
            "ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ ɪꜱ ᴄᴏᴍᴘʟᴇᴛᴇ — ᴛʜᴇ ʙᴏᴛ ɪꜱ ʙᴀᴄᴋ ᴜᴘ ᴀɴᴅ ʀᴜɴɴɪɴɢ ɴᴏʀᴍᴀʟʟʏ.\n\n"
            "🚀 ᴇᴠᴇʀʏᴛʜɪɴɢ ɪꜱ ʙᴀᴄᴋ ᴏɴʟɪɴᴇ ᴀɴᴅ ʀᴇᴀᴅʏ ᴛᴏ ᴜꜱᴇ.\n\n"
            "ᴛʜᴀɴᴋ ʏᴏᴜ ꜰᴏʀ ᴡᴀɪᴛɪɴɢ.\n\n"
            "ᴇɴᴊᴏʏ ᴛʜᴇ ɪᴍᴘʀᴏᴠᴇᴍᴇɴᴛꜱ. ✨"
        ),
        "parse_mode": None,
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "help_admin": {
        "text": (
            "<blockquote>"
            "<u>❓ " + to_small_caps("admin help") + "</u>\n\n"
            "<u>➤ " + to_small_caps("📊 stats & activity — view the bot's live numbers") + "</u>\n\n"
            "<u>➤ " + to_small_caps("👥 users & groups — list or message any user") + "</u>\n\n"
            "<u>➤ " + to_small_caps("📢 broadcast — message everyone, with forward-lock") + "</u>\n\n"
            "<u>➤ " + to_small_caps("🎨 menu & ui — edit any menu's text, image or buttons") + "</u>\n\n"
            "<u>➤ " + to_small_caps("⚙️ settings & admins — welcome, admins, maintenance, languages") + "</u>\n\n"
            "<u>➤ " + to_small_caps("📦 update backup — save every live setting + all users to 2 files, so a code update on github never wipes them") + "</u>\n\n"
            "<u>➤ " + to_small_caps("🛑 danger zone — destructive, irreversible actions") + "</u>"
            "</blockquote>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [
            {"label": "📦 " + to_small_caps("update backup — how it works"), "type": "callback", "value": "help_update_backup_info", "row": 1, "style": "primary"},
            {"label": "🔙 Admin Panel", "type": "callback", "value": "adm_home", "row": 2, "style": "primary"},
        ],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "download": {
        "text": (
            "<blockquote>"
            "𝘞𝘢𝘯𝘵 𝘵𝘰 𝘥𝘰𝘸𝘯𝘭𝘰𝘢𝘥 𝘢 𝘙𝘦𝘦𝘭?\n\n"
            "<u>➤ 𝘊𝘰𝘱𝘺 𝘵𝘩𝘦 𝘙𝘦𝘦𝘭 𝘭𝘪𝘯𝘬 𝘧𝘳𝘰𝘮 𝘐𝘯𝘴𝘵𝘢𝘨𝘳𝘢𝘮</u>\n\n"
            "<u>➤ 𝘗𝘢𝘴𝘵𝘦 𝘵𝘩𝘦 𝘭𝘪𝘯𝘬 𝘩𝘦𝘳𝘦</u>\n\n"
            "𝘛𝘩𝘢𝘵'𝘴 𝘪𝘵 — 𝘐'𝘭𝘭 𝘥𝘰 𝘵𝘩𝘦 𝘳𝘦𝘴𝘵."
            "</blockquote>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "howto": {
        "text": (
            "<blockquote>"
            "𝐇𝐎𝐖 𝐓𝐎 𝐔𝐒𝐄\n\n"
            "➤ Cᴏᴘʏ ᴀɴʏ Iɴsᴛᴀɢʀᴀᴍ Rᴇᴇʟ ʟɪɴᴋ\n\n"
            "➤ Pᴀsᴛᴇ ᴛʜᴇ ʟɪɴᴋ ʜᴇʀᴇ ɪɴ ᴄʜᴀᴛ\n\n"
            "➤ Wᴀɪᴛ ᴀ ғᴇᴡ sᴇᴄᴏɴᴅs\n\n"
            "➤ Gᴇᴛ ʏᴏᴜʀ Rᴇᴇʟ ᴅᴏᴡɴʟᴏᴀᴅᴇᴅ ɪɴsᴛᴀɴᴛʟʏ\n\n"
            "➤ 𝐍𝐎𝐓𝐄 : Oɴʟʏ Pᴜʙʟɪᴄ Iɴsᴛᴀɢʀᴀᴍ Rᴇᴇʟ ʟɪɴᴋs ᴀʀᴇ sᴜᴘᴘᴏʀᴛᴇᴅ"
            "</blockquote>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    # v10 — these 5 are new: the intro banner (and optional image) for each
    # of Send A Gift / Language / Developer / Support / Admin Panel is now
    # admin-editable from Menu & UI too, same as every other menu. Only the
    # BANNER text/image is stored here — the live functional buttons on
    # each screen (Stars/UPI, the language list, the developer contact
    # link, the actual open-a-ticket flow, the admin dashboard's own
    # buttons) stay code-driven and are appended after this banner, since
    # those carry real logic that can't be hand-typed as plain buttons.
    "gift": {
        "text": (
            "<blockquote>"
            "<u>✨ 𝐒𝐔𝐏𝐏𝐎𝐑𝐓 𝐎𝐔𝐑 𝐁𝐎𝐓</u>\n\n"
            "<u>➤ Tʜɪꜱ ꜱᴜᴘᴘᴏʀᴛ ɪꜱ ᴄᴏᴍᴘʟᴇᴛᴇʟʏ ᴏᴘᴛɪᴏɴᴀʟ.</u>\n"
            "<u>➤ Wᴇ ɴᴇᴠᴇʀ ꜰᴏʀᴄᴇ ᴀɴʏᴏɴᴇ ᴛᴏ ꜱᴇɴᴅ ᴀ ᴘᴀʏᴍᴇɴᴛ.</u>\n\n"
            "<u>➤ Iꜰ ʏᴏᴜ ᴇɴᴊᴏʏ ᴜꜱɪɴɢ ᴛʜᴇ ʙᴏᴛ ᴀɴᴅ ᴡᴀɴᴛ ᴛᴏ ꜱᴜᴘᴘᴏʀᴛ ɪᴛ,</u> "
            "<u>ʏᴏᴜ ᴄᴀɴ ᴄᴏɴᴛʀɪʙᴜᴛᴇ ᴀɴʏ ᴀᴍᴏᴜɴᴛ ʏᴏᴜ ᴘʀᴇꜰᴇʀ.</u>\n\n"
            "<u>➤ Yᴏᴜʀ ꜱᴜᴘᴘᴏʀᴛ ʜᴇʟᴘꜱ ᴜꜱ ᴋᴇᴇᴘ ᴡᴏʀᴋɪɴɢ ᴏɴ ᴛʜᴇ ʙᴏᴛ, ɪᴍᴘʀᴏᴠɪɴɢ "
            "ᴇxɪꜱᴛɪɴɢ ꜰᴇᴀᴛᴜʀᴇꜱ, ᴀᴅᴅɪɴɢ ɴᴇᴡ ꜰᴜɴᴄᴛɪᴏɴꜱ ᴀɴᴅ ʙʀɪɴɢɪɴɢ ᴍᴏʀᴇ ᴜꜱᴇꜰᴜʟ ᴜᴘɢʀᴀᴅᴇꜱ.</u>\n\n"
            "Wᴇ ꜱɪɴᴄᴇʀᴇʟʏ ᴀᴘᴘʀᴇᴄɪᴀᴛᴇ ᴇᴠᴇʀʏ ʙɪᴛ ᴏꜰ ꜱᴜᴘᴘᴏʀᴛ. ❤️"
            "</blockquote>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "language": {
        "text": "🌐 <u>" + to_small_caps("choose your language:") + "</u>",
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "developer": {
        "text": "<u>➤ " + to_small_caps("tap below to message the developer:") + "</u>",
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "support": {
        "text": (
            "<blockquote>"
            + "<u>" + to_title_small_caps("Please type your message below.") + "</u>\n\n"
            + "<u>🛠️ " + to_title_small_caps("Report a problem") + "</u>\n"
            + "<u>💡 " + to_title_small_caps("Share your feedback") + "</u>\n"
            + "<u>❓ " + to_title_small_caps("Ask a question") + "</u>\n"
            + "💭 " + to_title_small_caps("Suggest a feature") + "\n\n"
            + to_title_small_caps("We'll review your message and get back to you as soon as possible.")
            + "</blockquote>"
        ),
        "parse_mode": "HTML",
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
    "admin": {
        "text": f"│ {to_title_small_caps('Admin Dashboard')} │",
        "parse_mode": None,
        "image_file_id": None,
        "buttons": [],
        "auto_delete_seconds": None,
        "updated_by": None,
        "updated_at": None,
        "translations": {},
    },
}

# ----------------------------------------------------------------------------
# language_pack.json — ships next to bot.py with ready-made translations
# (10 languages) for the language picker plus real per-menu text for start,
# language, and (a shorter) disclaimer, howto, gift, support, developer,
# download. Loaded once at import time and merged into DEFAULT_MENUS so
# fresh installs have working translations out of the box — and again at
# runtime in load_data() so already-deployed bots pick it up too, without
# ever overwriting a translation an admin has since customized by hand.
# Missing/corrupt file is never fatal — the bot just falls back to the
# untranslated (English) text, same as before this file existed.
# ----------------------------------------------------------------------------
_LANGUAGE_PACK_CACHE = None


def _load_language_pack() -> dict:
    global _LANGUAGE_PACK_CACHE
    if _LANGUAGE_PACK_CACHE is not None:
        return _LANGUAGE_PACK_CACHE
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "language_pack.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            pack = json.load(f)
        if not isinstance(pack, dict):
            raise ValueError("language_pack.json is not a JSON object")
        _LANGUAGE_PACK_CACHE = pack
    except FileNotFoundError:
        _LANGUAGE_PACK_CACHE = {}
    except Exception as e:
        log.warning("language_pack.json present but couldn't be read/parsed (%s) — continuing without it.", e)
        _LANGUAGE_PACK_CACHE = {}
    return _LANGUAGE_PACK_CACHE


def _get_rkb_labels(lang: str = None) -> dict:
    """Return localized persistent reply-keyboard labels.

    Falls back to English if the selected language is unavailable or the
    optional keyboard section is missing from an older language pack.
    """
    pack = _load_language_pack()
    all_labels = pack.get("reply_keyboard", {})
    selected = all_labels.get(lang) if lang else None
    selected = selected if isinstance(selected, dict) else all_labels.get("en", {})
    fallback = {
        "download": RKB_DOWNLOAD, "usage": RKB_USAGE, "gift": RKB_GIFT,
        "language": RKB_LANGUAGE, "developer": RKB_DEVELOPER,
        "howto": RKB_HOWTO, "support": RKB_SUPPORT, "admin": RKB_ADMINPANEL,
    }
    for key, value in fallback.items():
        if not selected.get(key):
            selected[key] = value
    return selected


def _rkb_action_for_text(text: str, lang: str = None):
    """Map a localized reply-keyboard label back to its stable action key."""
    labels = _get_rkb_labels(lang)
    for action, label in labels.items():
        if text == label or text == to_title_small_caps(label):
            return action
    # Keep old/English keyboards working after an update.
    legacy = {
        RKB_DOWNLOAD: "download", RKB_USAGE: "usage", RKB_GIFT: "gift",
        RKB_LANGUAGE: "language", RKB_DEVELOPER: "developer",
        RKB_HOWTO: "howto", RKB_SUPPORT: "support", RKB_ADMINPANEL: "admin",
    }
    return legacy.get(text)


def _apply_language_pack_to_menus(menus: dict) -> None:
    """Fills in menu[lang] translations that are missing, for every menu the
    pack covers. Never overwrites a translation that's already there (so an
    admin's own edit, or a previous run's merge, always wins)."""
    pack = _load_language_pack()
    for menu_id, per_lang in pack.get("menus", {}).items():
        menu = menus.get(menu_id)
        if not menu or not isinstance(per_lang, dict):
            continue
        translations = menu.setdefault("translations", {})
        for lang, content in per_lang.items():
            # "en" is deliberately never stored as a translation — English
            # always falls through to the base text written in bot.py
            # (see DEFAULT_MENUS), even if language_pack.json ships an
            # "en" entry of its own.
            if lang == "en":
                continue
            if lang not in translations and isinstance(content, dict) and content.get("text"):
                translations[lang] = {"text": content["text"]}


# Populate DEFAULT_MENUS itself at import time, so brand-new installs (no
# saved bot_data.json / Mongo doc yet) start with working translations.
_apply_language_pack_to_menus(DEFAULT_MENUS)

DEFAULT_DATA = {
    "users": {},
    "groups": {},
    "admins": [OWNER_ID] if OWNER_ID else [],
    # Granular admin access — str(admin_id) -> [permission_key, ...]. An
    # admin with NO entry here (i.e. added before this feature existed) is
    # treated as full-access, so nobody already trusted silently loses
    # access. Only admins added from now on get an explicit, owner-chosen
    # list. See ADMIN_PERMISSIONS / get_admin_perms() / has_admin_perm().
    "admin_permissions": {},
    "blocked": [],
    "menus": json.loads(json.dumps(DEFAULT_MENUS)),
    "settings": {
        "maintenance": False,
        "protect_broadcasts": True,
        "global_auto_delete_seconds": 0,
        "small_caps_buttons_default": True,
        "auto_replies": {},
        "rate_limit_max": 20,
        "rate_limit_window_seconds": 60,
        "inactive_reengage_days": 0,
        # Pre-populated from language_pack.json (minus "en", which is
        # always shown anyway) so the language picker has real options out
        # of the box. Admin can still add/remove languages in Settings >
        # Languages as before — this is just the starting default.
        "languages": [c for c in _load_language_pack().get("languages", {}) if c != "en"],
        "lock_all_content": False,  # master forwarding/sharing lock
        "logger_channel_id": None,  # dedicated logger channel
        "logger_enabled": False,
        "owner_display_user_id": None,  # credit/contact button
        "owner_display_label": None,
        "support_chat_id": None,  # where support messages land; None = all admins
        "premium_enabled": False,
        "upi_id": None,
        "developer_id": None,
        "developer_link": None,
        "daily_limit": 20,
        "admin_group_id": None,   # ticket cards posted here
        "owner_id": None,         # /export gate
        "force_join_channel": None,   # legacy single force-join target
        "force_join_channels": [],   # [{"chat_id": @username/-100id or None, "link": https://...}]
        "force_join_request_verified": {}, # user_id -> [channel keys] accepted via join request
        "send_as_document": False,    # send reels as document instead of video
        "document_mode_threshold_mb": 45,  # auto-switch to document above this size
        "premium_plans": [],  # admin-defined plans: {id, name, days, price_inr, price_stars, enabled}
        "detailed_join_alerts": True,  # new-user/group-start full details -> admin DMs + logger
        "user_activity_dm": True,      # every reel-link a user sends -> owner DM (misuse monitoring)
        "notify_route": "all",         # where the Reel-Delivered activity card goes: logger | activity | dm | all
        "leaderboard_enabled": False,  # admin toggle — top-donor ranking shown inside Send Gift
        "share_enabled": True,         # admin toggle — "📤 Share" button under My Usage
        "share_url": None,             # link the Share button points to; falls back to the bot link
        "share_text": "Try this Instagram Reel Downloader bot.",
        "premium_emoji_enabled": False,   # greeting uses a Premium custom emoji
        "premium_emoji_id": None,         # custom_emoji_id captured from the admin's sample message
        "premium_emoji_char": "🌟",       # fallback glyph shown to non-Premium users automatically
        "activity_channel_id": None,      # dedicated channel for the Reel Delivered card
        "activity_channel_enabled": False,
        # Owner-only Instagram failure monitor / AI Check dashboard.
        "instagram_monitor_threshold": 5,
        "instagram_monitor_window_minutes": 10,
        "instagram_monitor_cooldown_minutes": 60,
        "instagram_monitor_recovery_successes": 3,
        "instagram_monitor_owner_ids": [OWNER_ID] if OWNER_ID else [],
    },
    "broadcast_log": [],
    "activity_log": [],         # ring buffer: {time, user_id, name, username, chat_type, url}
    "restore_log": [],
    "sent_messages": {},        # chat_id (str) -> [message_id, ...] ring buffer, last 200
    "copyright_reports": [],    # DMCA-style user reports
    "blocked_links": [],        # specific links blocked by admin
    "blocked_domains": [],      # whole domains blocked by admin
    "error_log": [],            # capped ring buffer of recent errors
    "metrics": {"reels_downloaded": 0, "audio_gets": 0, "caption_gets": 0, "start_count": 0, "broadcasts_sent": 0},
    # Rolling Instagram-only monitoring state. Old events are pruned automatically.
    "instagram_monitor": {
        "failures": [], "successes": [], "outage_active": False,
        "last_alert_at": None, "last_recovery_at": None,
        "last_error_category": None, "last_error_detail": None,
        "alert_count": 0, "recovery_count": 0,
    },
    "tickets": {},               # ticket_id(str) -> {...}
    "ticket_msg_map": {},        # admin_group_message_id(str) -> ticket_id
    "support_msg_map": {},       # one-shot support admin-message-id(str) -> user_id(str)
    "support_requests": {},      # request_id(str) -> {user_id, chat_id, confirm_chat_id,
                                  #   confirm_message_id, admin_message_ids: [...], status, text, created_at}
    "support_admin_msg_map": {}, # one-shot support admin-message-id(str) -> request_id(str)
    "next_support_id": 100000,   # 6-digit request IDs, e.g. #100000, #100001, ...
    "next_ticket_id": 1,
    "panel_msg": {},              # chat_id(str) -> last panel message_id
    "gift_orders": {},            # order_id(str) -> {...} (UPI pending payments)
    "next_gift_id": 1,
    "next_plan_id": 1,            # admin-defined premium plans
    "donations": {},              # uid(str) -> {"name", "stars", "inr", "score"} — leaderboard source
    "maintenance_notified": [],   # chat_id(int) list — everyone shown the maintenance notice,
                                   # so we know exactly who to ping with BOT_LIVE_TEXT on toggle-off
    "maintenance_notice_msg": {},  # chat_id(str) -> message_id(int) of that chat's LATEST maintenance
                                    # notice — lets us delete the old one before sending a new one
                                    # (no more duplicate notices piling up), and delete it automatically
                                    # the moment maintenance is switched off.
}

# ----------------------------------------------------------------------------
# Storage layer — menus/settings merge into it
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
