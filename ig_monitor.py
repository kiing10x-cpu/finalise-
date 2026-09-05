from handlers_download import *


def _ig_monitor_state() -> dict:
    state = BOT_DATA.setdefault("instagram_monitor", {})
    state.setdefault("failures", [])
    state.setdefault("successes", [])
    state.setdefault("outage_active", False)
    state.setdefault("last_alert_at", None)
    state.setdefault("last_recovery_at", None)
    state.setdefault("last_error_category", None)
    state.setdefault("last_error_detail", None)
    state.setdefault("alert_count", 0)
    state.setdefault("recovery_count", 0)
    return state


def _ig_monitor_cfg(key: str, default):
    return BOT_DATA.get("settings", {}).get(key, default)


def _ig_error_category(error: Exception | str) -> str:
    msg = str(error).lower()
    # These are normally properties of one URL, not an Instagram-wide outage.
    individual = (
        "private", "deleted", "not found", "does not exist", "invalid url",
        "unsupported url", "login required", "not available", "removed",
        "page isn't available", "page is unavailable",
    )
    if any(x in msg for x in individual):
        return "individual_link"
    if any(x in msg for x in ("timed out", "timeout", "connection", "network",
                              "dns", "temporarily unavailable", "502", "503",
                              "504", "429", "rate limit")):
        return "network_temporary"
    if any(x in msg for x in ("no video formats found", "unable to extract",
                              "requested format is not available",
                              "extractor", "instagram")):
        return "instagram_extractor"
    if "ffmpeg" in msg or "ffprobe" in msg:
        return "local_media"
    return "download_other"


def _ig_monitor_prune(now: datetime | None = None):
    now = now or datetime.utcnow()
    st = _ig_monitor_state()
    window = timedelta(minutes=int(_ig_monitor_cfg("instagram_monitor_window_minutes", 10)))
    cutoff = now - window
    for key in ("failures", "successes"):
        kept = []
        for e in st.get(key, []):
            try:
                dt = datetime.fromisoformat(e["time"])
                if dt >= cutoff:
                    kept.append(e)
            except Exception:
                continue
        st[key] = kept[-100:]


async def _ig_monitor_admin_ids(context: ContextTypes.DEFAULT_TYPE) -> list[int]:
    raw = BOT_DATA.get("settings", {}).get("instagram_monitor_owner_ids")
    ids = raw if isinstance(raw, list) else []
    if not ids and OWNER_ID:
        ids = [OWNER_ID]
    out = []
    for value in ids:
        try:
            iv = int(value)
            if iv and iv not in out:
                out.append(iv)
        except Exception:
            pass
    return out


async def _ig_monitor_send_alert(context: ContextTypes.DEFAULT_TYPE, recovered: bool = False):
    st = _ig_monitor_state()
    now = datetime.utcnow()
    if recovered:
        text = (
            "🟢 " + to_title_small_caps("Instagram Download System") + "\n\n"
            "✓ " + to_small_caps("downloading has recovered.") + "\n\n"
            + f"{to_title_small_caps('Status')} : 🟢 " + to_small_caps("Operational") + "\n"
            + f"{to_title_small_caps('Successful Checks')} : {len(st.get('successes', []))}\n"
            + f"{to_title_small_caps('Failures')} : {len(st.get('failures', []))}\n"
            + f"{to_title_small_caps('Time')} : {now_ist_str('%d %b %Y, %I:%M:%S %p')} IST\n\n"
            + to_small_caps("the Instagram downloader is working normally again.")
        )
    else:
        failures = st.get("failures", [])
        categories = {}
        for e in failures:
            categories[e.get("category", "unknown")] = categories.get(e.get("category", "unknown"), 0) + 1
        reason = max(categories, key=categories.get) if categories else "unknown"
        text = (
            "🚨 " + to_title_small_caps("Instagram Download Alert") + "\n\n"
            "⚠️ " + to_small_caps("possible system issue detected") + "\n\n"
            + to_small_caps("Instagram reel downloads are failing unusually.") + "\n\n"
            + f"{to_title_small_caps('Failures')} : {len(failures)}\n"
            + f"{to_title_small_caps('Affected Users')} : {len({e.get('user_id') for e in failures})}\n"
            + f"{to_title_small_caps('Status')} : 🔴 " + to_small_caps("Unstable") + "\n"
            + f"{to_title_small_caps('Category')} : {html.escape(reason.replace('_', ' ').title())}\n"
            + f"{to_title_small_caps('Window')} : {int(_ig_monitor_cfg('instagram_monitor_window_minutes', 10))} min\n"
            + f"{to_title_small_caps('Time')} : {now_ist_str('%d %b %Y, %I:%M:%S %p')} IST\n\n"
            + to_small_caps("the bot will continue monitoring the system.")
        )
    kb = InlineKeyboardMarkup([[styled_button("🔄 " + to_small_caps("Check Status"), callback_data="ai_check")]])
    for aid in await _ig_monitor_admin_ids(context):
        try:
            await context.bot.send_message(aid, text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            log.exception("Instagram monitor notification failed for admin %s", aid)


async def instagram_monitor_failure(context: ContextTypes.DEFAULT_TYPE, user_id: int, error: Exception | str):
    """Record a REAL Instagram Reel download failure without blocking the downloader."""
    try:
        now = datetime.utcnow()
        st = _ig_monitor_state()
        category = _ig_error_category(error)
        _ig_monitor_prune(now)
        # Ignore failures that are clearly local/individual when deciding on an IG-wide outage.
        event = {"time": now.isoformat(), "user_id": str(user_id), "category": category,
                 "detail": str(error)[:500]}
        st["failures"].append(event)
        st["last_error_category"] = category
        st["last_error_detail"] = str(error)[:500]
        _ig_monitor_prune(now)

        candidates = [e for e in st["failures"]
                      if e.get("category") == category
                      and category not in ("individual_link", "local_media", "network_temporary")]
        threshold = int(_ig_monitor_cfg("instagram_monitor_threshold", 5))
        distinct_users = len({e.get("user_id") for e in candidates})
        likely_systemic = len(candidates) >= threshold and (distinct_users >= 2 or len(candidates) >= threshold + 2)

        if likely_systemic and not st.get("outage_active"):
            cooldown = timedelta(minutes=int(_ig_monitor_cfg("instagram_monitor_cooldown_minutes", 60)))
            last = None
            try:
                last = datetime.fromisoformat(st.get("last_alert_at")) if st.get("last_alert_at") else None
            except Exception:
                pass
            if last is None or now - last >= cooldown:
                st["outage_active"] = True
                st["last_alert_at"] = now.isoformat()
                st["alert_count"] = int(st.get("alert_count", 0)) + 1
                save_data()
                await _ig_monitor_send_alert(context, recovered=False)
                return
        save_data()
    except Exception:
        # Monitoring must NEVER break the main Reel Downloader.
        log.exception("Instagram failure monitor crashed")


async def instagram_monitor_success(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Record a successful Reel delivery and detect recovery after an outage."""
    try:
        now = datetime.utcnow()
        st = _ig_monitor_state()
        _ig_monitor_prune(now)
        st["successes"].append({"time": now.isoformat(), "user_id": str(user_id)})
        _ig_monitor_prune(now)
        if st.get("outage_active"):
            threshold = int(_ig_monitor_cfg("instagram_monitor_recovery_successes", 3))
            if len(st["successes"]) >= threshold:
                st["outage_active"] = False
                st["last_recovery_at"] = now.isoformat()
                st["recovery_count"] = int(st.get("recovery_count", 0)) + 1
                save_data()
                await _ig_monitor_send_alert(context, recovered=True)
                return
        save_data()
    except Exception:
        log.exception("Instagram recovery monitor crashed")


__all__ = [_n for _n in dir() if not _n.startswith("__")]
