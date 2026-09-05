from handlers_fallback import *


def require_premium(handler):
    """Decorator for plugin (or future core) handlers that should only run
    for active premium users. Non-premium users get the same 🎁 upgrade
    prompt used everywhere else in the bot, instead of the feature silently
    doing nothing or erroring."""
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        uid = str(update.effective_user.id)
        if is_premium_active(uid) or is_admin(update.effective_user.id):
            return await handler(update, context, *a, **kw)
        text = "💎 " + to_small_caps("this feature is for premium users only.")
        kb = InlineKeyboardMarkup([[styled_button("🎁 Upgrade to Premium", callback_data="gift_menu", style="success")]])
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(text, reply_markup=kb)
        elif update.message:
            await update.message.reply_text(text, reply_markup=kb)
    return wrapped


_LOADED_PLUGINS = []   # [{"file": name, "ok": bool, "error": str|None}]


def load_plugins(app: Application) -> None:
    """Scans plugins/ once at startup and registers every valid plugin
    found. Never lets one bad file take down the others or the bot."""
    global _LOADED_PLUGINS
    _LOADED_PLUGINS = []
    if not os.path.isdir(PLUGIN_DIR):
        return
    import importlib.util
    for fname in sorted(os.listdir(PLUGIN_DIR)):
        if not fname.endswith(".py") or fname.startswith("_"):
            continue
        path = os.path.join(PLUGIN_DIR, fname)
        try:
            spec = importlib.util.spec_from_file_location(f"plugins.{fname[:-3]}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, "register"):
                raise AttributeError("plugin file has no register(app) function")
            module.register(app)
            _LOADED_PLUGINS.append({"file": fname, "ok": True, "error": None})
            log.info("Loaded plugin: %s", fname)
        except Exception as e:
            log.exception("Failed to load plugin %s", fname)
            log_error("plugin", f"{fname}: {e}")
            _LOADED_PLUGINS.append({"file": fname, "ok": False, "error": str(e)[:200]})


async def _render_adm_plugins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _LOADED_PLUGINS:
        body = (
            "🧩 " + to_small_caps("feature plugins") + "\n\n"
            + to_small_caps(f"no plugin files found in '{PLUGIN_DIR}/'.") + "\n\n"
            + to_small_caps("to add a feature: drop a .py file into that folder (with a register(app) function) and restart the bot.")
        )
    else:
        lines = ["🧩 " + to_small_caps("feature plugins") + "\n"]
        for p in _LOADED_PLUGINS:
            if p["ok"]:
                lines.append(f"✅ {p['file']}")
            else:
                lines.append(f"❌ {p['file']} — {p['error']}")
        lines.append("")
        lines.append(to_small_caps("uploaded a new file? restart the bot to load it — plugins are only scanned at startup."))
        body = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        back_row(), home_row(),
    ])
    await query.edit_message_text(body, reply_markup=kb)


async def cb_adm_plugins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not is_admin(update.effective_user.id):
        return
    await _render_adm_plugins(update, context)


# Registered here, after _render_adm_plugins is defined — the earlier
# SCREEN_RENDERERS.update({...}) block runs before this function exists.
SCREEN_RENDERERS["adm_plugins"] = _render_adm_plugins


# ----------------------------------------------------------------------------
# 🗄 Mongo Plugin — live MongoDB connect/disconnect from the Admin Panel,
# no env var or restart required. See set_mongo_uri()/disconnect_mongo()/
# get_mongo_status() near the top of the file for the actual logic.
# ----------------------------------------------------------------------------

def _format_mongo_status_text(explain: bool = True) -> str:
    st = get_mongo_status()
    lbl = to_title_small_caps
    if st["connected"]:
        state_line = "✅ " + to_small_caps("connected & live")
    elif st["configured"]:
        state_line = "❌ " + to_small_caps("configured but not reachable")
    else:
        state_line = "⚪ " + to_small_caps("not configured — using local json file")

    source_map = {
        "env": to_small_caps("environment variable (MONGO_URI)"),
        "admin_panel": to_small_caps("set from this admin panel"),
    }
    lines = [
        "🗄 <b>" + to_small_caps("mongo plugin") + "</b>",
        "",
        "<blockquote>",
        f"{lbl('Status')} : {state_line}",
        f"{lbl('Backend In Use')} : {to_small_caps('mongodb') if st['connected'] else to_small_caps('local json file')}",
    ]
    if st["configured"]:
        lines.append(f"{lbl('Source')} : {source_map.get(st['source'], to_small_caps('unknown'))}")
        lines.append(f"{lbl('Database')} : {html.escape(st['masked_uri'] or '—')}")
        lines.append(f"{lbl('Attached Since')} : " + (iso_to_ist_str(st['connected_at'], '%d %b %Y, %H:%M') + ' IST' if st['connected_at'] else '—'))
        lines.append(f"{lbl('Last Checked')} : " + (iso_to_ist_str(st['last_checked_at'], '%d %b %Y, %H:%M:%S') + ' IST' if st['last_checked_at'] else '—'))
        if st["connected"] and st["doc_count"] is not None:
            lines.append(f"{lbl('Documents Stored')} : {st['doc_count']}")
        if not st["connected"] and st["last_error"]:
            lines.append(f"{lbl('Last Error')} : {html.escape(str(st['last_error'])[:200])}")
    lines.append("</blockquote>")

    if explain:
        lines += [
            "",
            "<u>➤ " + to_small_caps("how this works") + "</u>",
            "<blockquote>" + to_small_caps(
                "attach a mongodb connection string below and this bot's entire "
                "database — every user, setting, menu and ticket — switches over "
                "to it immediately, live, with no restart needed. all existing "
                "data is copied across automatically the moment you connect."
            ) + "\n\n" + to_small_caps(
                "if you never attach one, the bot keeps working exactly as "
                "before, saving everything to a local file on this server "
                "instead — nothing breaks either way."
            ) + "</blockquote>",
        ]
    return "\n".join(lines)


def _build_mongo_plugin_view():
    text = _format_mongo_status_text()
    rows = [[styled_button("🔄 Refresh Status", callback_data="adm_mongo_plugin")]]
    if MONGO_URI_SOURCE == "env":
        rows.append([styled_button("🧪 Test Connection", callback_data="adm_mongo_test")])
    else:
        rows.append([styled_button(
            "🔌 " + ("Update" if MONGO_URI else "Connect") + " URI",
            callback_data="adm_mongo_set", style="success",
        )])
        if MONGO_URI:
            rows.append([styled_button("🗑 Disconnect", callback_data="adm_mongo_disconnect_confirm", style="danger")])
    rows.append(back_row())
    rows.append(home_row())
    return text, InlineKeyboardMarkup(rows)


async def _render_adm_mongo_plugin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    text, kb = _build_mongo_plugin_view()
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)


async def cb_adm_mongo_plugin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if not is_admin(update.effective_user.id):
        return
    await _render_adm_mongo_plugin(update, context)


async def cb_adm_mongo_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔎 " + to_small_caps("checking..."))
    await _render_adm_mongo_plugin(update, context)


async def cb_adm_mongo_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remember_panel_message(context, query, "mongo_plugin")
    context.user_data["awaiting"] = "mongo_uri"
    await query.message.reply_text(
        "🗄 " + to_small_caps("send the mongodb connection string now") + "\n"
        + to_small_caps("(starts with mongodb:// or mongodb+srv://)") + "\n\n"
        + to_small_caps("it will be tested before anything is switched over — if it fails, nothing changes.")
        + "\n\n/cancel " + to_small_caps("to abort.")
    )


async def cb_adm_mongo_disconnect_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [styled_button("✅ Yes, disconnect", callback_data="adm_mongo_disconnect_do", style="danger"),
         styled_button("❌ Cancel", callback_data="adm_mongo_plugin")],
    ])
    await query.edit_message_text(
        "⚠️ " + to_small_caps("disconnect mongodb?") + "\n\n"
        + to_small_caps("the bot will switch back to saving everything in a local file on this server. your mongodb data itself is not deleted — you can reconnect the same uri again anytime.") ,
        reply_markup=kb,
    )


async def cb_adm_mongo_disconnect_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    disconnect_mongo()
    await log_event(context, "🗄 MongoDB disconnected by admin " + str(update.effective_user.id) + " — reverted to local JSON file.")
    await _render_adm_mongo_plugin(update, context)


SCREEN_RENDERERS["adm_mongo_plugin"] = _render_adm_mongo_plugin
SCREEN_RENDERERS["adm_update_backup"] = _render_adm_update_backup


__all__ = [_n for _n in dir() if not _n.startswith("__")]
