from handlers_start import *


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # update.message is None for edited messages/channel posts, which this
    # handler also matches against — guard before touching update.message.
    if update.message is None:
        return
    user_obj = update.effective_user
    if is_blocked(user_obj.id) and not is_admin(user_obj.id):
        return  # blocked users get silence, not an error

    # Maintenance is a hard global lock for non-admins: no reply-keyboard
    # action, support flow, reel parsing, auto-reply or media flow can run.
    if BOT_DATA["settings"].get("maintenance") and not is_admin(user_obj.id):
        await send_maintenance_notice(context, update.effective_chat.id)
        return

    # An admin replying to a forwarded ticket message routes straight back
    # to that user, bypassing everything else below.
    if update.message.reply_to_message and is_admin(user_obj.id):
        support_uid = BOT_DATA.get("support_msg_map", {}).get(str(update.message.reply_to_message.message_id))
        if support_uid:
            # Prefix the reply with a quote of the user's original problem
            # so it's clear which issue this is about.
            reply_rid = BOT_DATA.get("support_admin_msg_map", {}).get(
                str(update.message.reply_to_message.message_id)
            )
            problem_text = None
            if reply_rid:
                problem_text = BOT_DATA.get("support_requests", {}).get(reply_rid, {}).get("text")
            try:
                if problem_text:
                    tag = (
                        "<blockquote>"
                        + f"«{html.escape(problem_text[:300])}»" + "\n\n"
                        + to_title_small_caps("Admin's Reply") + " ↩️"
                        + "</blockquote>"
                    )
                    await context.bot.send_message(chat_id=int(support_uid), text=tag, parse_mode="HTML")
                await context.bot.copy_message(
                    chat_id=int(support_uid),
                    from_chat_id=update.effective_chat.id,
                    message_id=update.message.message_id,
                )
                await update.message.reply_text("✅ " + to_title_small_caps("Reply sent to user."))
            except Exception:
                await update.message.reply_text(
                    "⚠️ " + to_title_small_caps("Couldn't deliver reply — the user may have blocked the bot.")
                )
            return
        tid = BOT_DATA["ticket_msg_map"].get(str(update.message.reply_to_message.message_id))
        if tid:
            await handle_admin_ticket_reply(update, context, tid)
            return

    touch_user(update)
    user_id = user_obj.id
    uid = str(user_id)

    # While a user has an open ticket, every message auto-forwards into it.
    open_tid = BOT_DATA["users"].get(uid, {}).get("open_ticket_id")
    if open_tid and str(open_tid) in BOT_DATA["tickets"] and BOT_DATA["tickets"][str(open_tid)]["status"] == "open":
        await forward_to_ticket(update, context, open_tid)
        return

    text = update.message.text or ""

    # Group safety: never answer normal group conversation. The bot only
    # reacts to an actual Instagram URL (with or without @BotUsername).
    # Private chats retain the normal helpful invalid-link feedback.
    if not _is_private_chat(update) and text:
        if not INSTAGRAM_URL_RE.search(text):
            return

    # Non-text media outside an active ticket/awaiting-input flow has
    # nothing to do here.
    if not text and not context.user_data.get("awaiting"):
        return

    # Nothing below runs until the disclaimer + force-join gate clears.
    if not await require_gate(update, context):
        return

    # Persistent reply-keyboard routing. Each branch below deletes the
    # user's own tapped-button message and replaces the same panel in
    # place, so repeat taps leave only the latest copy behind.
    # RKB_ADMINPANEL is excluded — cmd_admin() replies to this exact
    # message first, then deletes it itself.
    user_lang = BOT_DATA["users"].get(uid, {}).get("lang")
    rkb_action = _rkb_action_for_text(text, user_lang)
    if rkb_action in {"download", "usage", "gift", "language", "developer", "howto", "support"}:
        await delete_incoming(update)
        # Tapping a bottom-keyboard button cancels any pending text-input
        # state (e.g. Support's "awaiting": "support_message") so a later
        # unrelated message doesn't get routed into the old flow. Branches
        # that need their own awaiting state set it again right after this.
        context.user_data.pop("awaiting", None)
    if text == RKB_DOWNLOAD:
        # Now a fully admin-editable menu (text/image/buttons) via
        # Menu & UI → "download", instead of a hardcoded string — same
        # single-slot panel behavior as every other reply-keyboard screen.
        sent = await render_menu(context, update.effective_chat.id, "download")
        await track_and_refresh_panel(context, update.effective_chat.id, "rkb_latest", sent)
        return
    if rkb_action == "usage":
        await show_usage_screen(update, context)
        return
    if rkb_action == "gift":
        await show_gift_menu(update, context)
        return
    if rkb_action == "language":
        await cmd_language(update, context)
        return
    if rkb_action == "developer":
        await show_developer_button(update, context)
        return
    if rkb_action == "howto":
        # Same treatment as Download Reel above — admin-editable via
        # Menu & UI → "howto".
        sent = await render_menu(context, update.effective_chat.id, "howto")
        await track_and_refresh_panel(context, update.effective_chat.id, "rkb_latest", sent)
        return
    if rkb_action == "support":
        await support_button_entry(update, context)
        return
    if rkb_action == "admin" and is_admin(user_id):
        await cmd_admin(update, context)
        return

    awaiting = context.user_data.get("awaiting")

    if awaiting == "premium_emoji_capture" and is_admin(user_id):
        await handle_premium_emoji_capture(update, context)
        return

    # PDF #3 / #11 — user-facing text-collection flows (copyright report,
    # support message) run regardless of admin status, before the
    # admin-only dispatcher below.
    if awaiting in (
        "support_message", "copyright_report_link", "copyright_report_details",
        "ticket_new", "gift_stars_custom_amount", "gift_upi_amount",
    ):
        await handle_user_awaiting_input(update, context, awaiting)
        return

    if awaiting and is_admin(user_id):
        await handle_admin_text_input(update, context, awaiting)
        return

    if not check_rate_limit(user_id):
        await update.message.reply_text("⏳ " + to_small_caps("slow down, too many requests too fast."))
        return

    match = INSTAGRAM_URL_RE.search(text)
    if match and not is_admin(user_id) and not check_daily_limit(uid):
        limit = BOT_DATA["settings"].get("daily_limit", 20)
        kb = InlineKeyboardMarkup([[styled_button(to_small_caps("🚀 upgrade for more"), callback_data="gift_menu", style="success")]])
        await update.message.reply_text(
            "🚫 " + to_small_caps(f"daily limit reached ({limit}/{limit}). try again tomorrow or upgrade."),
            reply_markup=kb,
        )
        return

    if not match:
        # Never spam groups for ordinary conversation. Auto-replies and the
        # invalid-link message are intentionally private-chat only.
        if not _is_private_chat(update):
            return
        low = text.lower()
        for phrase, reply in BOT_DATA["settings"].get("auto_replies", {}).items():
            if phrase in low:
                await update.message.reply_text(reply)
                return
        await update.message.reply_text(USER_ERR_WRONG_FORMAT)
        return

    # Maintenance is already enforced at the top of handle_text().

    # (disclaimer + force-join already verified by require_gate() above —
    # no need to re-check either one here)

    url = match.group(1)

    # Anti-misuse monitoring: every reel link a user pastes is logged and,
    # by default, forwarded live to admin DMs (+ logger group) with a
    # one-tap ban button — this is a check-only feed, no automatic action.
    if not is_admin(user_id):
        await log_user_activity(context, update, url)

    if is_link_blocked(url) and not is_admin(user_id):
        await update.message.reply_text("🚫 " + to_small_caps("this link/domain has been blocked by admin."))
        return

    status_msg = await update.message.reply_text(STR["processing"])

    # Live progress, fed by yt-dlp's progress_hooks from the worker thread.
    _progress = {"pct": 0, "stage": "fetching"}

    def _progress_hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            _progress["pct"] = int(done / total * 100) if total else 0
            _progress["stage"] = "fetching"
        elif d.get("status") == "finished":
            _progress["pct"] = 100
            _progress["stage"] = "optimizing"

    async def _animate_status():
        try:
            while True:
                await asyncio.sleep(2)
                pct = _progress["pct"]
                filled = pct // 10
                bar = "▓" * filled + "░" * (10 - filled)
                stage_label = to_small_caps(_progress["stage"])
                try:
                    await status_msg.edit_text(
                        to_small_caps("⏳ processing your reel...") + f"\n📥 {stage_label}\n{bar} {pct}%"
                    )
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass

    anim_task = asyncio.create_task(_animate_status())
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_video")
    except Exception:
        pass

    out_template = os.path.join(DOWNLOAD_DIR, f"%(id)s_{int(time.time())}.%(ext)s")

    def build_ydl_opts(use_merge: bool) -> dict:
        # The no-merge path requires a format with both video and audio
        # already muxed together, format_sort prefers mp4/h264/aac (plays
        # cleanly everywhere), and merged audio is re-encoded to AAC so an
        # odd opus/vorbis track from IG doesn't end up silent in Telegram.
        opts = {
            "format": (
                "bestvideo*+bestaudio/best"
                if use_merge
                else "best[vcodec!=none][acodec!=none]/best"
            ),
            "format_sort": ["res", "ext:mp4:m4a", "vcodec:h264", "acodec:aac"],
            "outtmpl": out_template,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [_progress_hook],
        }
        if use_merge:
            opts["merge_output_format"] = "mp4"
            opts["postprocessor_args"] = {
                "ffmpeg_merger": ["-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart"]
            }
            if FFMPEG_PATH:
                opts["ffmpeg_location"] = FFMPEG_PATH
        return opts

    def run_download(use_merge: bool):
        opts = build_ydl_opts(use_merge)
        try:
            info = _ytdlp_extract_with_retry(opts, url, download=True)
        except Exception as first_error:
            # Instagram occasionally exposes only one extractor-visible stream
            # for a reel. Retry once with yt-dlp's broadest format selector
            # instead of failing solely because our quality preference was too
            # strict. The real exception still reaches logs if this also fails.
            log.warning("Preferred Instagram format failed; retrying with plain best: %s", first_error)
            opts = {
                "format": "best/bestvideo+bestaudio",
                "outtmpl": out_template,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [_progress_hook],
            }
            if FFMPEG_PATH:
                opts["ffmpeg_location"] = FFMPEG_PATH
            info = _ytdlp_extract_with_retry(opts, url, download=True)
        with yt_dlp.YoutubeDL(opts) as ydl:
            fp = ydl.prepare_filename(info)
        stem = fp.rsplit(".", 1)[0]
        for candidate in (fp, stem + ".mp4", stem + ".webm", stem + ".mkv"):
            if os.path.exists(candidate):
                fp = candidate
                break
        ig_caption = (info.get("description") or "").strip()
        uploader = (info.get("uploader") or info.get("uploader_id") or "").strip()
        return fp, ig_caption, uploader

    file_path = None
    try:
        try:
            # run_download() is a blocking yt-dlp call, so it runs in a
            # thread — otherwise it would freeze the event loop for
            # everyone during every download.
            file_path, ig_caption, ig_uploader = await asyncio.to_thread(run_download, FFMPEG_AVAILABLE)
        except Exception as e:
            # Self-heal: if a merge was attempted and ffmpeg turned out to be
            # the problem, retry once with a no-merge (progressive) format.
            if "ffmpeg" in str(e).lower():
                log.warning("Merge failed (ffmpeg issue), retrying with progressive format.")
                file_path, ig_caption, ig_uploader = await asyncio.to_thread(run_download, False)
            else:
                raise

        # Telegram bots can't upload files over 50MB — check upfront and
        # give a clear message instead of a raw exception mid-upload.
        MAX_UPLOAD_BYTES = 50 * 1024 * 1024
        file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0
        if file_size > MAX_UPLOAD_BYTES:
            anim_task.cancel()
            mb = file_size / (1024 * 1024)
            await status_msg.edit_text(
                "❌ " + to_small_caps(f"this reel is too large to send ({mb:.1f}mb, limit 50mb). try a shorter reel.")
            )
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        uid = str(update.effective_user.id)
        lang = BOT_DATA["users"].get(uid, {}).get("lang")
        menu = BOT_DATA["menus"]["reel_result"]
        translation = menu.get("translations", {}).get(lang) if (lang and lang != "en") else None  # "en" is the default language, never a translation override
        base_caption = (translation or {}).get("text") or menu.get("text", "")
        # The delivered reel gets a purpose-built action row.  The old
        # Caption callback is intentionally removed: short captions use
        # Telegram's native CopyTextButton, while long captions fall back
        # to a callback that sends the complete caption for normal copy.
        parse_mode = menu.get("parse_mode") or None
        kb = None

        # Native Telegram blockquote with the reel's caption, HTML only.
        if parse_mode == "HTML":
            import html as _html
            # Keep the caption visibly quoted under the reel.  Telegram's
            # native copy button can copy up to 256 characters; longer
            # captions get a callback fallback below so nothing is lost.
            preview = ig_caption[:700] + ("…" if len(ig_caption) > 700 else "")
            bq = (
                "<blockquote expandable>"
                f"📋 {_html.escape(preview) or '(none)'}"
                "</blockquote>"
            )
            result_caption = f"{base_caption}\n\n{bq}"
        else:
            result_caption = base_caption

        # Compact reel controls: Caption + Audio stay together on the first
        # row, while the full-width Remove Buttons control sits underneath.
        # Labels use the bot's small-caps font so the controls match the rest
        # of the user-facing UI.
        if ig_caption:
            if len(ig_caption) <= 256:
                try:
                    copy_btn = InlineKeyboardButton(
                        to_small_caps("Caption"),
                        copy_text=CopyTextButton(text=ig_caption),
                        **({"style": "primary"} if SUPPORTS_BUTTON_STYLE else {}),
                    )
                except TypeError:
                    copy_btn = InlineKeyboardButton(
                        to_small_caps("Caption"),
                        copy_text=CopyTextButton(text=ig_caption),
                    )
            else:
                copy_btn = styled_button(
                    to_small_caps("Caption"),
                    callback_data="copy_caption", style="primary"
                )
        else:
            copy_btn = None

        top_row = []
        if copy_btn is not None:
            top_row.append(copy_btn)
        top_row.append(styled_button(
            to_small_caps("🎵 Audio"), callback_data="get_audio", style="primary"
        ))
        kb_rows = [top_row, [styled_button(
            to_small_caps("❌ Remove Buttons"),
            callback_data="remove_reel", style="danger"
        )]]
        kb = InlineKeyboardMarkup(kb_rows)

        anim_task.cancel()
        protect = bool(BOT_DATA["settings"].get("lock_all_content", False))
        # Send as a document when the admin forces it, or the file is close
        # to the 50MB cap (documents preserve quality better near the limit).
        threshold = BOT_DATA["settings"].get("document_mode_threshold_mb", 45) * 1024 * 1024
        as_document = BOT_DATA["settings"].get("send_as_document", False) or file_size > threshold
        # Tell the user the reel is ready immediately before delivering the
        # actual media. Keep this as a separate, clean message.
        try:
            await status_msg.edit_text(to_small_caps("Your reel is ready"))
        except Exception:
            pass

        with open(file_path, "rb") as vid:
            if as_document:
                sent = await update.message.reply_document(
                    document=vid, caption=result_caption, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )
            else:
                sent = await update.message.reply_video(
                    video=vid, caption=result_caption, parse_mode=parse_mode, reply_markup=kb, protect_content=protect
                )

        # The original Instagram link is only needed during processing. Once
        # the reel has been delivered successfully, remove that incoming link
        # from the user's chat, matching the chat-cleanup behavior used by
        # the admin input flows.
        await delete_incoming(update)

        # Cache the real Instagram caption + source URL so the Copy Caption
        # fallback, Audio button, and Remove button under THIS specific video
        # can use them, keyed
        # to this exact message. The video file itself is deleted right
        # after sending (see finally: below), so Audio re-downloads
        # audio-only from the cached URL rather than needing the video kept
        # around on disk.
        _caption_cache[(sent.chat_id, sent.message_id)] = {
            "caption": ig_caption,
            "url": url,
            "uploader": ig_uploader,
            "title": (ig_caption.splitlines()[0] if ig_caption else ig_uploader or "Instagram Audio"),
        }
        if len(_caption_cache) > CAPTION_CACHE_MAX:
            _caption_cache.pop(next(iter(_caption_cache)))

        track_sent_message(sent.chat_id, sent.message_id)
        bump_usage(uid)
        BOT_DATA["metrics"]["reels_downloaded"] = BOT_DATA["metrics"].get("reels_downloaded", 0) + 1
        BOT_DATA["users"].setdefault(uid, {})["reels_count"] = BOT_DATA["users"].get(uid, {}).get("reels_count", 0) + 1
        await instagram_monitor_success(context, user_id)
        save_data()
        await log_event(
            context,
            f"📥 New download — user {user_id} (@{user_obj.username or 'no username'}) — {url}",
        )
        await send_reel_delivered_card(
            context,
            user_name=user_obj.full_name or (f"@{user_obj.username}" if user_obj.username else str(user_id)),
            user_id=user_id,
            reel_number=BOT_DATA["metrics"]["reels_downloaded"],
            original_reel_url=url,
            username=user_obj.username,
        )

        seconds = menu.get("auto_delete_seconds")
        if seconds is None:
            seconds = BOT_DATA["settings"].get("global_auto_delete_seconds", 0)
        await schedule_delete(context, sent.chat_id, sent.message_id, seconds)
        await status_msg.delete()
    except Exception as e:  # noqa: BLE001
        anim_task.cancel()
        log.exception("Download failed")
        # Technical details stay in logs/admin activity only. Never expose
        # yt-dlp/Instagram/ffmpeg exceptions to the end user.
        if "no video formats found" in str(e).lower():
            log_error("ytdlp_no_formats", f"url={url} err={e} — yt-dlp may need updating (pip install -U yt-dlp)")
        log_error("download", f"url={url} err={e}")
        await instagram_monitor_failure(context, user_id, e)
        try:
            await status_msg.edit_text(USER_ERR_NOT_AVAILABLE, parse_mode="HTML")
        except Exception:
            try:
                await update.message.reply_text(USER_ERR_NOT_AVAILABLE, parse_mode="HTML")
            except Exception:
                pass
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


async def cb_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = (query.message.chat_id, query.message.message_id)
    entry = _caption_cache.get(key)
    caption = entry.get("caption") if entry else None
    if not caption:
        await query.message.reply_text("ℹ️ " + to_small_caps("no caption found for this post (or cache expired)."))
        return
    # Telegram message limit is 4096 chars — split if needed.
    for i in range(0, len(caption), 4000):
        await query.message.reply_text(caption[i:i + 4000])
    uid = str(query.from_user.id)
    u = BOT_DATA["users"].setdefault(uid, {})
    u["caption_count"] = u.get("caption_count", 0) + 1
    BOT_DATA["metrics"]["caption_gets"] = BOT_DATA["metrics"].get("caption_gets", 0) + 1
    save_data()


async def cb_copy_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback for captions longer than Telegram's 256-char native
    CopyTextButton limit. Sends the complete caption so the user can use
    Telegram's normal copy action without truncation."""
    query = update.callback_query
    await query.answer()
    key = (query.message.chat_id, query.message.message_id)
    entry = _caption_cache.get(key)
    caption = entry.get("caption") if entry else None
    if not caption:
        await query.message.reply_text("ℹ️ " + to_small_caps("caption cache expired."))
        return
    for i in range(0, len(caption), 4000):
        await query.message.reply_text(caption[i:i + 4000])
    uid = str(query.from_user.id)
    u = BOT_DATA["users"].setdefault(uid, {})
    u["caption_count"] = u.get("caption_count", 0) + 1
    BOT_DATA["metrics"]["caption_gets"] = BOT_DATA["metrics"].get("caption_gets", 0) + 1
    save_data()


async def cb_remove_reel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove only the caption and buttons; never delete the reel itself."""
    query = update.callback_query
    await query.answer(to_small_caps("Removed"))
    key = (query.message.chat_id, query.message.message_id)
    _caption_cache.pop(key, None)

    # The media message must remain untouched. Telegram lets us edit the
    # caption/reply markup of the delivered media message independently.
    try:
        await query.message.edit_caption(caption=None, reply_markup=None)
        return
    except Exception:
        pass
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def cb_get_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🎵 Audio button under a delivered reel. The video file is already
    deleted by the time this is tapped, so this re-downloads the source and
    runs ffmpeg directly to strip the audio track — bypassing yt-dlp's
    FFmpegExtractAudio postprocessor, which needs ffprobe and isn't
    available on hosts that only carry the portable ffmpeg binary."""
    query = update.callback_query
    await query.answer()
    key = (query.message.chat_id, query.message.message_id)
    entry = _caption_cache.get(key)
    url = entry.get("url") if entry else None
    if not url:
        await query.message.reply_text("ℹ️ " + to_small_caps("couldn't find the source link for this post (cache expired)."))
        return

    status_msg = await query.message.reply_text("🎵 " + to_small_caps("extracting audio..."))

    # Ask yt-dlp for an audio-only format first, falling back toward
    # muxed/video formats only if a post genuinely has no separate audio
    # track. Instagram's reported acodec metadata isn't reliable, so
    # instead of trusting it we download a candidate and ask ffmpeg itself
    # whether the file actually has an audio stream, trying the next
    # candidate if not.
    def probe_has_audio(path: str) -> bool:
        try:
            result = subprocess.run(
                [FFMPEG_PATH, "-i", path], capture_output=True, text=True, timeout=30
            )
            return bool(re.search(r"Stream #\d+:\d+.*Audio:", result.stderr))
        except Exception:
            return False

    def build_source_opts(fmt: str):
        opts = {
            "format": fmt,
            "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s_audiosrc_" + str(int(time.time())) + "_%(format_id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
        }
        if FFMPEG_PATH:
            opts["ffmpeg_location"] = FFMPEG_PATH
        return opts

    def download_format(fmt: str):
        opts = build_source_opts(fmt)
        info = _ytdlp_extract_with_retry(opts, url, download=True)
        with yt_dlp.YoutubeDL(opts) as ydl:
            fp = ydl.prepare_filename(info)
        return fp if os.path.exists(fp) else None

    def run_source_download():
        # Try, in order: a dedicated audio-only stream; the best muxed
        # (video+audio) stream; then whatever "best" resolves to as a last
        # resort. Each candidate is verified against the real file, not
        # metadata, before we commit to it — failed candidates are cleaned
        # up immediately so we don't leave stray video-only files behind.
        candidates = ["bestaudio", "best[acodec!=none][vcodec!=none]", "best"]
        tried_paths = []
        for fmt in candidates:
            try:
                fp = download_format(fmt)
            except Exception as e:
                log.warning("audio-source download failed for format %r: %s", fmt, e)
                continue
            if not fp:
                continue
            tried_paths.append(fp)
            if probe_has_audio(fp):
                # Clean up any earlier failed attempts before returning.
                for p in tried_paths[:-1]:
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                return fp
        # Nothing worked — clean up every attempt and report clearly.
        for p in tried_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        if tried_paths:
            raise RuntimeError("this post doesn't seem to have an audio track (checked multiple formats).")
        return None

    def extract_audio_ffmpeg(src_path: str) -> str:
        """Direct ffmpeg call — no ffprobe involved."""
        mp3_path = os.path.splitext(src_path)[0] + ".mp3"
        cmd = [
            FFMPEG_PATH, "-y", "-i", src_path,
            "-vn", "-acodec", "libmp3lame", "-q:a", "2",
            mp3_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode != 0 or not os.path.exists(mp3_path):
            raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr[-500:]}")
        return mp3_path

    source_path = None
    audio_path = None
    try:
        if not FFMPEG_AVAILABLE:
            # Audio extraction (muxing out just the audio track) genuinely
            # needs ffmpeg, unlike plain video download — no safe fallback.
            await status_msg.edit_text(
                "❌ " + to_small_caps("audio extraction needs ffmpeg, which isn't available on this server.")
            )
            return
        source_path = await asyncio.to_thread(run_source_download)
        if not source_path:
            await status_msg.edit_text(USER_ERR_AUDIO_NOT_AVAILABLE, parse_mode="HTML")
            return
        audio_path = await asyncio.to_thread(extract_audio_ffmpeg, source_path)
        if not audio_path or not os.path.exists(audio_path):
            await status_msg.edit_text(USER_ERR_AUDIO_NOT_AVAILABLE, parse_mode="HTML")
            return
        protect = bool(BOT_DATA["settings"].get("lock_all_content", False))
        # Give Telegram a clean, human-readable filename/title instead of the
        # temporary yt-dlp filename full of ids and timestamps.
        audio_title = _safe_filename((entry or {}).get("uploader") or (entry or {}).get("title") or "Instagram Audio")
        filename = _safe_filename((entry or {}).get("title") or audio_title) + ".mp3"
        with open(audio_path, "rb") as aud:
            await query.message.reply_audio(
                audio=aud, protect_content=protect, filename=filename,
                title=audio_title, performer="Instagram"
            )
        uid = str(query.from_user.id)
        u = BOT_DATA["users"].setdefault(uid, {})
        u["audio_count"] = u.get("audio_count", 0) + 1
        BOT_DATA["metrics"]["audio_gets"] = BOT_DATA["metrics"].get("audio_gets", 0) + 1
        save_data()
        await status_msg.delete()
    except Exception as e:
        # Full technical error is useful for debugging, but must never be
        # shown to users. Keep it in the server/admin log only.
        log.exception("Audio extraction failed for %s", url)
        log_error("audio", f"url={url} err={e}")
        try:
            await status_msg.edit_text(USER_ERR_AUDIO_NOT_AVAILABLE, parse_mode="HTML")
        except Exception:
            try:
                await query.message.reply_text(USER_ERR_AUDIO_NOT_AVAILABLE, parse_mode="HTML")
            except Exception:
                pass
    finally:
        for p in (source_path, audio_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


async def cb_check_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ok = await is_force_join_ok(context, update.effective_user.id)
    if ok:
        await query.answer(to_small_caps("✅ verified!"), show_alert=True)
        try:
            await query.message.delete()
        except Exception:
            pass
        # Both gates are clear now — land the user in the start menu (this
        # covers the onboarding path; if they were already past onboarding
        # and just got re-blocked later, show_post_onboarding is a no-op
        # past the language-picker/reply-keyboard first-run bits and just
        # re-renders start, which is fine here).
        uid = str(update.effective_user.id)
        await show_post_onboarding(context, query.message.chat_id, uid)
    else:
        await query.answer(to_small_caps("❌ still not joined."), show_alert=True)


async def cb_download_another(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔗 " + to_small_caps("paste your next instagram reel link."))


# ----------------------------------------------------------------------------
# v11 — OWNER-ONLY Instagram Download Failure Monitor
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
