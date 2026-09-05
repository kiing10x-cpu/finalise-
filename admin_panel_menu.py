from admin_panel_core import *


# ---- Menu & UI (#1, #2, #4, #7 controls) -------------------------------------

MENU_DISPLAY_NAMES = {
    # v10 — short labels requested for the Menu & UI list, so a button
    # name never gets cut off / hard to read on a phone screen. Anything
    # not in this map falls back to its raw id (title-cased) below.
    "start": "Start",
    "disclaimer": "Disclaimer",
    "download": "Downld",
    "howto": "HTU",
    "gift": "Gift",
    "language": "Language",
    "developer": "Developer",
    "support": "Support",
    "admin": "Admin",
    "help_user": "Help User",
    "reel_result": "Reel Result",
    "maintenance": "Maintenance",
    "bot_live": "Bot Live",
    "help_admin": "Help Admin",
}


async def _render_adm_menu_ui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # 2-per-row grid, a single ✅ badge when the menu has an image set, and
    # short display names so nothing overflows on a phone screen.
    menu_ids = list(BOT_DATA["menus"])

    def _label(mid):
        has_image = bool(BOT_DATA["menus"][mid].get("image_file_id"))
        name = MENU_DISPLAY_NAMES.get(mid, mid.replace("_", " ").title())
        return f"{name} ✅" if has_image else name

    rows = [[styled_button("🖼️ Set Welcome Image", callback_data="adm_menu_img:start")]]
    for i in range(0, len(menu_ids), 2):
        pair = menu_ids[i:i + 2]
        rows.append([styled_button(_label(mid), callback_data=f"adm_menu_edit:{mid}") for mid in pair])
    rows.append(back_row())
    rows.append(home_row())
    text = (
        to_deco(to_title_small_caps("Menu & UI")) + "\n\n"
        + to_small_caps("tap a menu below to edit its text, image or buttons.") + "\n"
        + to_small_caps("✅ next to a menu means it already has an image set.")
    )
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def cb_adm_menu_ui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _render_adm_menu_ui(update, context)


def _build_menu_edit_screen(menu_id: str):
    """Single source of truth for the 'editing menu X' screen — used both
    when first opening it and when refreshing it in place after a save
    (e.g. right after an image upload), so the two never drift apart."""
    menu = BOT_DATA["menus"][menu_id]
    parse_mode_label = menu.get("parse_mode") or "OFF (Raw Text)"
    override = menu.get("auto_delete_seconds")
    override_label = f"{override}s" if override is not None else "Uses Global"
    has_image = bool(menu.get("image_file_id"))
    image_status = "✅ " + to_title_small_caps("Set") if has_image else "❌ " + to_title_small_caps("Not Set")
    image_btn_label = ("🖼️ Change Image" if has_image else "🖼️ Set Image")

    rows = [
        [styled_button("✏️ Edit Text", callback_data=f"adm_menu_txt:{menu_id}"),
         styled_button("🅰️ Style Text", callback_data=f"adm_menu_style:{menu_id}")],
        [styled_button(f"🔤 Parse Mode: {parse_mode_label}", callback_data=f"adm_menu_parsemode:{menu_id}"),
         styled_button("🔘 Manage Buttons", callback_data=f"adm_menu_btns:{menu_id}")],
    ]
    if has_image:
        rows.append([
            styled_button(image_btn_label, callback_data=f"adm_menu_img:{menu_id}"),
            styled_button("🗑️ Remove Image", callback_data=f"adm_menu_rmimg:{menu_id}"),
        ])
    else:
        rows.append([styled_button(image_btn_label, callback_data=f"adm_menu_img:{menu_id}")])
    rows.append([
        styled_button(f"⏱ Auto-Delete: {override_label}", callback_data=f"adm_menu_autodel:{menu_id}"),
        styled_button("🌐 Translations", callback_data=f"adm_menu_trans:{menu_id}"),
    ])
    rows.append([styled_button("🔙 Back", callback_data="adm_menu_ui")])

    # v10 — the header now names the menu with its short display name (not
    # a generic "Editing Menu" title with the id buried below), and a
    # quoted preview of the CURRENT text is shown right under the status
    # lines — so it's confirmed at a glance which menu this is and what's
    # already set for it, without needing to tap "Edit Text" first.
    display_name = MENU_DISPLAY_NAMES.get(menu_id, menu_id.replace("_", " ").title())
    current_text = menu.get("text") or ""
    preview = html.escape(re.sub(r"<[^>]+>", "", current_text)).strip()
    if len(preview) > 200:
        preview = preview[:200].rstrip() + "…"
    text = (
        to_deco(to_title_small_caps(f"Editing Menu: {display_name}")) + "\n\n"
        + f"<b>ID:</b> <code>{html.escape(menu_id)}</code>\n"
        + f"<b>Image:</b> {image_status}\n"
        + f"<b>Parse Mode:</b> {html.escape(parse_mode_label)}\n"
        + f"<b>Auto-Delete:</b> {html.escape(override_label)}\n\n"
        + "<b>" + to_title_small_caps("Currently Set") + ":</b>\n"
        + f"<blockquote>{preview or to_small_caps('(empty)')}</blockquote>\n\n"
        + to_small_caps("choose what you'd like to change below")
    )
    return text, InlineKeyboardMarkup(rows)


async def cb_adm_menu_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    text, kb = _build_menu_edit_screen(menu_id)
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


async def cb_adm_menu_trans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    langs = BOT_DATA["settings"].get("languages", [])
    if not langs:
        await query.message.reply_text(
            to_small_caps("first add at least one language via settings & admins → 🌐 manage languages.")
        )
        return
    rows = []
    have = BOT_DATA["menus"][menu_id].get("translations", {})
    for code in langs:
        mark = "✅" if code in have else "➕"
        rows.append([styled_button(f"{mark} {LANG_NAMES.get(code, code)}", callback_data=f"adm_menu_trans_edit:{menu_id}:{code}")])
    rows.append([styled_button("🔙 Back", callback_data=f"adm_menu_edit:{menu_id}")])
    await query.edit_message_text(f"🌐 Translations for {menu_id}", reply_markup=InlineKeyboardMarkup(rows))


async def cb_adm_menu_trans_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, menu_id, code = query.data.split(":", 2)
    context.user_data["awaiting"] = f"menu_trans_text:{menu_id}:{code}"
    await query.message.reply_text(
        to_small_caps(f"send the {LANG_NAMES.get(code, code)} translation text for '{menu_id}'") + "\n"
        + to_small_caps("(buttons stay the same as the base menu — they are not translated.)")
    )


async def cb_adm_menu_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    context.user_data["awaiting"] = f"menu_text:{menu_id}"
    await query.message.reply_text(
        to_small_caps("send the new text — it will be saved exactly as sent, with no auto-reformatting.")
    )


async def cb_adm_menu_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    context.user_data["awaiting"] = f"menu_style_source:{menu_id}"
    await query.message.reply_text(to_small_caps("send plain text and a preview of every available style will be shown."))


async def cb_adm_menu_parsemode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    cycle = [None, "HTML", "MarkdownV2"]
    current = BOT_DATA["menus"][menu_id].get("parse_mode")
    nxt = cycle[(cycle.index(current) + 1) % len(cycle)] if current in cycle else None
    BOT_DATA["menus"][menu_id]["parse_mode"] = nxt
    save_data()
    await cb_adm_menu_edit(update, context)


async def cb_adm_menu_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    context.user_data["awaiting"] = f"menu_image:{menu_id}"
    # Remember this exact "editing menu" screen so that once the photo is
    # received, we can flip its 🖼️ status straight to ✅ Set in place,
    # instead of leaving the admin to guess whether it actually saved.
    remember_panel_message(context, query, f"menu_edit:{menu_id}")
    await query.message.reply_text(to_small_caps("send a photo (image only, not a video)."))


async def cb_adm_menu_rmimg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    BOT_DATA["menus"][menu_id]["image_file_id"] = None
    save_data()
    await query.message.reply_text(to_small_caps("✅ image removed — this is now a text-only menu."))
    await cb_adm_menu_edit(update, context)


async def cb_adm_menu_autodel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    context.user_data["awaiting"] = f"menu_autodel:{menu_id}"
    await query.message.reply_text(
        to_small_caps("send the auto-delete time in seconds for this menu (0 = never, or type 'global' to use the global default).")
    )


def _menu_btns_keyboard(menu_id: str) -> InlineKeyboardMarkup:
    buttons = BOT_DATA["menus"][menu_id]["buttons"]
    rows = []
    for i, b in enumerate(buttons):
        rows.append([
            styled_button(f"{i}: {_short_btn_label(b['label'])}", callback_data="noop"),
            styled_button("✏️", callback_data=f"adm_btn_edit:{menu_id}:{i}"),
            styled_button("🅰️", callback_data=f"adm_btn_style:{menu_id}:{i}"),
            styled_button("❌", callback_data=f"adm_btn_del:{menu_id}:{i}"),
        ])
    rows.append([styled_button("➕ Add Button", callback_data=f"adm_btn_add:{menu_id}")])
    rows.append([styled_button("🔙 Back", callback_data=f"adm_menu_edit:{menu_id}")])
    return InlineKeyboardMarkup(rows)


async def cb_adm_menu_btns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    text = to_deco(to_title_small_caps(f"Buttons: {menu_id}"))
    await query.edit_message_text(text, reply_markup=_menu_btns_keyboard(menu_id))


async def cb_noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


async def cb_adm_btn_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, menu_id, idx = query.data.split(":", 2)
    idx = int(idx)
    if 0 <= idx < len(BOT_DATA["menus"][menu_id]["buttons"]):
        BOT_DATA["menus"][menu_id]["buttons"].pop(idx)
        save_data()
    await cb_adm_menu_btns_by_id(update, context, menu_id)


async def cb_adm_btn_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, menu_id, idx = query.data.split(":", 2)
    label = BOT_DATA["menus"][menu_id]["buttons"][int(idx)]["label"]
    context.user_data["style_source_text"] = label
    context.user_data["style_target"] = f"button_label:{menu_id}:{idx}"
    await send_style_preview(context, query.message.chat_id, label)


async def cb_adm_menu_btns_by_id(update, context, menu_id):
    """Helper to redraw the buttons list after a delete/edit, without a fresh query.data."""
    text = to_deco(to_title_small_caps(f"Buttons: {menu_id}"))
    await update.callback_query.edit_message_text(text, reply_markup=_menu_btns_keyboard(menu_id))


async def cb_adm_btn_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit-in-place: pre-fills the same label/type/value/row flow used by
    Add Button with the button's current values, so the admin can just send
    '-' at any step to keep it as-is instead of deleting + re-adding."""
    query = update.callback_query
    await query.answer()
    _, menu_id, idx = query.data.split(":", 2)
    idx = int(idx)
    buttons = BOT_DATA["menus"][menu_id]["buttons"]
    if not (0 <= idx < len(buttons)):
        await query.message.reply_text(to_small_caps("that button no longer exists — refresh the list."))
        return
    existing = dict(buttons[idx])
    context.user_data["btn_flow"] = {"menu_id": menu_id, "data": dict(existing), "edit_idx": idx}
    context.user_data["awaiting"] = "btn_step_label"
    await query.message.reply_text(
        to_small_caps(f"editing button {idx}. current label: {existing.get('label')}") + "\n"
        + to_small_caps("send the new label, or send - to keep it as-is.")
    )


async def cb_adm_btn_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    menu_id = query.data.split(":", 1)[1]
    context.user_data["btn_flow"] = {"menu_id": menu_id, "data": {}}
    context.user_data["awaiting"] = "btn_step_label"
    await query.message.reply_text(to_small_caps("send the new button's label (emoji are welcome)."))


async def cb_btn_type_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, btype = query.data.split(":", 1)
    flow = context.user_data.get("btn_flow")
    if not flow:
        await query.message.reply_text(to_small_caps("session expired — please try again via /admin."))
        return
    if btype == "keep":
        # Edit flow only — type & value stay as they already are in flow["data"].
        context.user_data["awaiting"] = "btn_step_value"
        cur_val = flow["data"].get("value", "")
        await query.message.reply_text(
            to_small_caps(f"current value: {cur_val}") + "\n" + to_small_caps("send a new value, or send - to keep it.")
        )
        return
    flow["data"]["type"] = btype
    context.user_data["awaiting"] = "btn_step_value"
    prompts = {
        "menu": to_small_caps("which menu_id should this open? (e.g. start, help_user)"),
        "url": to_small_caps("send the url (must start with https://)."),
        "callback": to_small_caps("send the internal action's callback_data (e.g. adm_stats)."),
        "toggle": to_small_caps("send the settings key to toggle (e.g. maintenance)."),
    }
    await query.message.reply_text(prompts.get(btype, to_small_caps("send the value:")))


__all__ = [_n for _n in dir() if not _n.startswith("__")]
