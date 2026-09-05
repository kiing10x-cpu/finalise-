from storage import *


def is_owner(user_id: int) -> bool:
    return OWNER_ID != 0 and user_id == OWNER_ID


def is_admin(user_id: int) -> bool:
    return is_owner(user_id) or user_id in BOT_DATA.get("admins", [])


# ----------------------------------------------------------------------------
# Granular admin permissions — every grantable Admin Panel section. Keys
# match the panel's callback_data with the "adm_" prefix stripped (see
# _perm_key_for_screen). 📦 Update Backup, ☠️ Danger Zone, and 👤 Manage
# Admins are intentionally NOT in this list — they stay owner-only no
# matter what, since they can export all data, do irreversible damage, or
# hand out access, respectively.
# ----------------------------------------------------------------------------
ADMIN_PERMISSIONS = [
    ("stats", "📊 Statistics"),
    ("users", "👥 Users & Groups"),
    ("live", "🍃 Live User Feed"),
    ("broadcast", "📢 Broadcast"),
    ("premium", "💎 Premium"),
    ("leaderboard", "🏆 Leaderboard"),
    ("share", "🎚 Share Settings"),
    ("devsettings", "😎 Developer Settings"),
    ("support_settings", "🛠 Support Settings"),
    ("tickets", "📬 Tickets"),
    ("menu_ui", "🪄 Menu & UI"),
    ("plugins", "🧩 Feature Plugins"),
    ("notifications", "🔔 Notifications"),
    ("activity", "📜 Activity Log"),
    ("selftest", "🗽 Self-Test"),
    ("cmdtest", "📟 Test Commands"),
    ("ai_check", "🤖 AI Check"),
    ("settings", "⚙️ Settings"),
]
ADMIN_PERMISSION_KEYS = [k for k, _ in ADMIN_PERMISSIONS]
ADMIN_PERMISSION_LABELS = dict(ADMIN_PERMISSIONS)


def _perm_key_for_screen(screen_key: str) -> str:
    return screen_key[4:] if screen_key.startswith("adm_") else screen_key


def get_admin_perms(user_id: int) -> set:
    """Owner -> every permission. An admin with NO explicit entry in
    admin_permissions (i.e. added before this feature existed) also gets
    every permission, so upgrading the bot never silently locks out an
    already-trusted admin. Only admins added AFTER this feature exists get
    the exact list the owner picked for them at add-time (can be empty)."""
    if is_owner(user_id):
        return set(ADMIN_PERMISSION_KEYS)
    uid = str(user_id)
    perms_map = BOT_DATA.get("admin_permissions", {})
    if uid not in perms_map:
        return set(ADMIN_PERMISSION_KEYS)  # legacy admin, added before permissions existed
    return set(perms_map.get(uid) or [])


def has_admin_perm(user_id: int, perm_key: str) -> bool:
    return is_owner(user_id) or perm_key in get_admin_perms(user_id)


def touch_user(update: Update) -> bool:
    """Records/updates the user record. Returns True if this is a brand-new user."""
    user = update.effective_user
    if not user:
        return False
    uid = str(user.id)
    now = datetime.utcnow().isoformat()
    users = BOT_DATA["users"]
    is_new = uid not in users
    if is_new:
        users[uid] = {
            "name": user.full_name, "username": user.username,
            "joined": now, "last_active": now, "last_reengaged": None,
            "lang": None, "lang_prompted": False,
            "accepted_terms": False, "accepted_terms_at": None,
            "downloads_today": 0, "downloads_today_date": None,
            "downloads_month": 0, "downloads_month_key": None,
            "reels_count": 0, "audio_count": 0, "caption_count": 0,
            "plan": "Free", "open_ticket_id": None,
        }
    else:
        users[uid]["last_active"] = now
        users[uid]["name"] = user.full_name
    save_data()
    return is_new


def is_blocked(user_id: int) -> bool:
    return user_id in BOT_DATA.get("blocked", [])


def is_premium_active(uid: str) -> bool:
    """A user counts as premium only while plan != Free AND (no expiry
    set, or expiry is in the future)."""
    u = BOT_DATA["users"].get(uid, {})
    if u.get("plan", "Free") == "Free":
        return False
    exp = u.get("plan_expires_at")
    if not exp:
        return True
    try:
        return datetime.fromisoformat(exp) > datetime.utcnow()
    except Exception:
        return True


def grant_premium(uid: str, days: int = 30):
    """Used by both Stars payments and admin-confirmed UPI orders."""
    u = BOT_DATA["users"].setdefault(uid, {})
    u["plan"] = "Premium"
    u["plan_expires_at"] = (datetime.utcnow() + timedelta(days=days)).isoformat()
    save_data()


def check_daily_limit(uid: str) -> bool:
    """Premium users are unlimited; everyone else is capped per day."""
    if is_premium_active(uid):
        return True
    u = BOT_DATA["users"].get(uid, {})
    today = datetime.utcnow().strftime("%Y-%m-%d")
    today_count = u.get("downloads_today", 0) if u.get("downloads_today_date") == today else 0
    limit = BOT_DATA["settings"].get("daily_limit", 20)
    return today_count < limit


async def cm_track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Keeps BOT_DATA['groups'] in sync so the admin panel's group count
    reflects reality."""
    cmu = update.my_chat_member
    if not cmu or cmu.chat.type not in ("group", "supergroup"):
        return
    gid = str(cmu.chat.id)
    new_status = cmu.new_chat_member.status
    if new_status in ("member", "administrator"):
        BOT_DATA["groups"][gid] = {
            "title": cmu.chat.title, "added_at": datetime.utcnow().isoformat(),
        }
    elif new_status in ("left", "kicked"):
        BOT_DATA["groups"].pop(gid, None)
    save_data()


def _force_join_targets():
    """Return normalized multi-force-join targets, while migrating legacy data."""
    settings = BOT_DATA["settings"]
    targets = settings.get("force_join_channels") or []
    if not targets and settings.get("force_join_channel"):
        legacy = settings["force_join_channel"]
        targets = [{"chat_id": legacy if not str(legacy).startswith("http") else None,
                    "link": legacy if str(legacy).startswith("http") else None}]
        settings["force_join_channels"] = targets
    normalized = []
    for item in targets:
        if isinstance(item, str):
            item = {"chat_id": item if not item.startswith("http") else None,
                    "link": item if item.startswith("http") else None}
        if isinstance(item, dict) and (item.get("chat_id") or item.get("link")):
            normalized.append(item)
    return normalized


def normalize_channel_id(raw: str) -> str:
    """Auto-fix the #1 real-world force-join bug: an admin pastes a numeric
    channel ID that's missing Telegram's mandatory "-100" prefix for
    channels/supergroups (very common — many ID-lookup bots/forwarded
    messages show the bare internal number, e.g. "-5080988402" instead of
    the actual Bot-API-usable "-1005080988402"). Using the bare form makes
    every get_chat_member call fail with "chat not found", which silently
    blocks every single user — exactly the "force-join doesn't work at
    all" symptom. Public @usernames and already-correct IDs pass through
    unchanged."""
    raw = str(raw).strip()
    if raw.startswith("@") or not raw.lstrip("-").isdigit():
        return raw
    digits = raw.lstrip("-")
    if raw.startswith("-") and not digits.startswith("100"):
        return f"-100{digits}"
    return raw


async def is_force_join_ok(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Require membership in every configured force-join channel.

    Join requests are also accepted: when Telegram sends the bot a
    ChatJoinRequest update, that user is temporarily/explicitly marked as
    verified for that target, so they can start using the bot without waiting
    for a manual re-check.
    """
    targets = _force_join_targets()
    if not targets or is_admin(user_id):
        return True
    verified = BOT_DATA["settings"].get("force_join_request_verified", {}).get(str(user_id), [])
    for target in targets:
        chat_id = normalize_channel_id(target.get("chat_id")) if target.get("chat_id") else None
        key = str(chat_id or target.get("link"))
        if key in verified:
            continue
        if not chat_id:
            # Link-only targets cannot be queried by getChatMember. They can
            # still be verified through a join-request update.
            return False
        try:
            member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if member.status in ("left", "kicked", "restricted"):
                return False
        except Exception as e:
            log.warning("Force-join check failed (target=%s, user=%s): %s", target, user_id, e)
            log_error("force_join", f"target={target}, user={user_id}: {e}")
            return False
    return True


async def resolve_force_join_link(context: ContextTypes.DEFAULT_TYPE, channel) -> str | None:
    if not channel:
        return None
    ch = normalize_channel_id(channel)
    if ch.startswith("http"):
        return ch
    if ch.lstrip("-").isdigit():
        try:
            chat = await context.bot.get_chat(int(ch))
            if chat.username:
                return f"https://t.me/{chat.username}"
            if getattr(chat, "invite_link", None):
                return chat.invite_link
            return await context.bot.export_chat_invite_link(int(ch))
        except Exception as e:
            # This is the #1 real cause of "no usable join link found" on the
            # user-facing prompt: either the ID is still wrong (not a real
            # channel the bot can see), or the bot IS in the channel but
            # isn't an admin there (export_chat_invite_link needs admin
            # rights). Logged so it shows up in Activity Log instead of
            # silently failing with zero diagnosis.
            log.warning("Force-join: could not resolve invite link for %s: %s", ch, e)
            log_error("force_join", f"could not resolve a join link for channel {ch}: {e}")
            return None
    return f"https://t.me/{ch.lstrip('@')}"


async def get_force_join_links(context):
    links = []
    for target in _force_join_targets():
        link = target.get("link") or await resolve_force_join_link(context, target.get("chat_id"))
        if link:
            links.append(link)
    return links


async def handle_force_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Accept a received join request as verification for force-join."""
    req = update.chat_join_request
    if not req:
        return
    uid = str(req.from_user.id)
    verified_map = BOT_DATA["settings"].setdefault("force_join_request_verified", {})
    keys = set(verified_map.get(uid, []))
    for target in _force_join_targets():
        chat_id = normalize_channel_id(target.get("chat_id")) if target.get("chat_id") else None
        if chat_id and str(chat_id) == str(req.chat.id):
            keys.add(str(chat_id))
        # Match the actual invite link if Telegram exposes it.
        inv = getattr(req, "invite_link", None)
        if inv and target.get("link") and getattr(inv, "invite_link", None) == target.get("link"):
            keys.add(str(target.get("link")))
    if keys:
        verified_map[uid] = list(keys)
        save_data()


def is_link_blocked(url: str) -> bool:
    if url in BOT_DATA.get("blocked_links", []):
        return True
    for domain in BOT_DATA.get("blocked_domains", []):
        if domain.lower() in url.lower():
            return True
    return False


def check_rate_limit(user_id: int) -> bool:
    if is_admin(user_id):
        return True
    limit = BOT_DATA["settings"].get("rate_limit_max", 20)
    window = BOT_DATA["settings"].get("rate_limit_window_seconds", 60)
    if limit <= 0:
        return True
    now = time.time()
    bucket = _rate_state.setdefault(user_id, [])
    while bucket and now - bucket[0] > window:
        bucket.pop(0)
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True


__all__ = [_n for _n in dir() if not _n.startswith("__")]
