from menus_data import *


BOT_DATA = {}
_mongo_client = None
_mongo_collection = None
_mongo_last_error = None
_mongo_last_checked_at = None   # ISO timestamp of the most recent ping attempt
_rate_state = {}  # in-memory only, not persisted
_caption_cache = {}  # (chat_id, message_id) -> {"caption": str, "url": str}, in-memory only
CAPTION_CACHE_MAX = 500


def _deep_merge_defaults(data: dict) -> dict:
    merged = json.loads(json.dumps(DEFAULT_DATA))
    for k, v in data.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    # ensure any newly-added default menus (and newly-added fields on
    # existing menus, e.g. "translations") exist even in old data files
    for menu_id, menu in DEFAULT_MENUS.items():
        if menu_id not in merged["menus"]:
            merged["menus"][menu_id] = json.loads(json.dumps(menu))
        else:
            for field, default_val in menu.items():
                merged["menus"][menu_id].setdefault(field, json.loads(json.dumps(default_val)))
    return merged


def get_mongo_collection(force: bool = False):
    """Returns the live 'bot_data' collection, or None if MongoDB isn't
    configured/reachable. Caches the connection — pass force=True to make
    it actually re-ping right now (used by /mongodb and the Mongo Plugin
    admin screen so their status is always live, never stale)."""
    global _mongo_client, _mongo_collection, _mongo_last_error, _mongo_last_checked_at
    if not MONGO_URI:
        return None
    if _mongo_collection is not None and not force:
        return _mongo_collection
    try:
        from pymongo import MongoClient

        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        db = client.get_default_database() or client["bot_db"]
        _mongo_client = client
        _mongo_collection = db["bot_data"]
        _mongo_last_error = None
        return _mongo_collection
    except Exception as e:  # noqa: BLE001
        _mongo_last_error = str(e)
        _mongo_collection = None
        return None
    finally:
        _mongo_last_checked_at = datetime.utcnow().isoformat()


def _save_mongo_config(uri: str, connected_at: str) -> None:
    """Persists an admin-panel-set Mongo URI to its own local file so it
    survives a bot restart even without MONGO_URI being set in the
    environment. Never touches bot_data.json / MongoDB itself."""
    try:
        with open(MONGO_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"uri": uri, "connected_at": connected_at}, f)
    except Exception as e:
        log.warning("Could not persist %s: %s", MONGO_CONFIG_FILE, e)


def _clear_mongo_config() -> None:
    try:
        if os.path.exists(MONGO_CONFIG_FILE):
            os.remove(MONGO_CONFIG_FILE)
    except Exception as e:
        log.warning("Could not remove %s: %s", MONGO_CONFIG_FILE, e)


def set_mongo_uri(new_uri: str):
    """🗄 Mongo Plugin — test-connects to a freshly pasted URI and, only on
    success, activates it live (no restart needed) and persists it. On
    success also immediately pushes the bot's current in-memory data into
    the new database, so switching storage never starts the bot on an
    empty slate. Returns (ok: bool, message: str)."""
    global MONGO_URI, MONGO_URI_SOURCE, MONGO_CONNECTED_AT
    global _mongo_client, _mongo_collection, _mongo_last_error, _mongo_last_checked_at
    new_uri = (new_uri or "").strip()
    if not new_uri:
        return False, "Empty URI."
    try:
        from pymongo import MongoClient
    except ImportError:
        return False, "pymongo isn't installed on this server. Run: pip install pymongo"
    try:
        test_client = MongoClient(new_uri, serverSelectionTimeoutMS=5000)
        test_client.admin.command("ping")
        db = test_client.get_default_database() or test_client["bot_db"]
        col = db["bot_data"]
    except Exception as e:  # noqa: BLE001
        return False, str(e)

    MONGO_URI = new_uri
    MONGO_URI_SOURCE = "admin_panel"
    MONGO_CONNECTED_AT = datetime.utcnow().isoformat()
    _mongo_client = test_client
    _mongo_collection = col
    _mongo_last_error = None
    _mongo_last_checked_at = MONGO_CONNECTED_AT
    _save_mongo_config(new_uri, MONGO_CONNECTED_AT)
    try:
        col.update_one({"_id": "bot_data"}, {"$set": BOT_DATA}, upsert=True)
    except Exception as e:  # noqa: BLE001
        return True, f"Connected, but the initial data copy failed: {e}. It will sync on the next save."
    return True, "Connected — this bot's data is now saved to MongoDB."


def disconnect_mongo():
    """Deactivates an admin-panel-set Mongo URI and reverts to the local
    bot_data.json file. Only ever called when MONGO_URI_SOURCE ==
    'admin_panel' — a URI coming from the MONGO_URI env var can't be
    disconnected from inside the bot (it's infra-managed; unset the env
    var and restart instead)."""
    global MONGO_URI, MONGO_URI_SOURCE, MONGO_CONNECTED_AT
    global _mongo_client, _mongo_collection, _mongo_last_error
    MONGO_URI = ""
    MONGO_URI_SOURCE = None
    MONGO_CONNECTED_AT = None
    _mongo_client = None
    _mongo_collection = None
    _mongo_last_error = None
    _clear_mongo_config()
    save_data()  # now falls through to the local JSON file


def get_mongo_status() -> dict:
    """Single source of truth for /mongodb and the 🗄 Mongo Plugin admin
    screen — always re-pings live so the status shown is never stale."""
    col = get_mongo_collection(force=True)
    masked_uri = None
    if MONGO_URI:
        m = re.match(r"^(mongodb(?:\+srv)?://)([^@/]+)@(.+)$", MONGO_URI)
        masked_uri = f"{m.group(1)}***:***@{m.group(3)}" if m else MONGO_URI
    doc_count = None
    if col is not None:
        try:
            doc_count = col.count_documents({})
        except Exception:
            pass
    return {
        "configured": bool(MONGO_URI),
        "connected": col is not None,
        "source": MONGO_URI_SOURCE,
        "masked_uri": masked_uri,
        "connected_at": MONGO_CONNECTED_AT,
        "last_checked_at": _mongo_last_checked_at,
        "last_error": _mongo_last_error,
        "doc_count": doc_count,
    }


def _apply_seed_files_if_present() -> bool:
    """Part of the 📦 Update Backup system (see SEED_SETTINGS_FILE /
    SEED_USERS_FILE and send_update_backup()). Only ever called from
    load_data() in the branch where NO existing data was found (fresh
    Mongo, or no local bot_data.json) — so on a host with persistent
    storage this never runs and never clobbers live data. It exists
    specifically for hosts that wipe the filesystem on every redeploy:
    export the two seed files from the admin panel, commit them into the
    repo next to bot.py with these exact names, push the update — the
    bot then reconstructs its previous settings/menus/users right here,
    automatically, on the very first startup after the deploy."""
    global BOT_DATA
    seed = {}
    if os.path.exists(SEED_SETTINGS_FILE):
        try:
            with open(SEED_SETTINGS_FILE, "r", encoding="utf-8") as f:
                seed.update(json.load(f))
            log.info("Update Backup: found %s — seeding settings/menus from it.", SEED_SETTINGS_FILE)
        except Exception as e:
            log.warning("Update Backup: could not read %s: %s", SEED_SETTINGS_FILE, e)
    if os.path.exists(SEED_USERS_FILE):
        try:
            with open(SEED_USERS_FILE, "r", encoding="utf-8") as f:
                users_payload = json.load(f)
            seed["users"] = users_payload.get("users", users_payload)
            log.info("Update Backup: found %s — seeding users from it.", SEED_USERS_FILE)
        except Exception as e:
            log.warning("Update Backup: could not read %s: %s", SEED_USERS_FILE, e)
    if seed:
        BOT_DATA = _deep_merge_defaults(seed)
        return True
    return False


def _apply_language_pack_migration():
    """Runs once after BOT_DATA is loaded from any source (fresh, local
    JSON, MongoDB, or a restored/seeded backup). Backfills missing menu
    translations and, if the owner has never touched Settings > Languages
    (still the empty default), pre-fills it from language_pack.json so the
    picker isn't empty. Purely additive — never overwrites an existing
    admin-set value — so it's always safe to re-run on every startup."""
    changed = False
    menus = BOT_DATA.get("menus", {})
    before = json.dumps(menus, sort_keys=True)
    _apply_language_pack_to_menus(menus)
    if json.dumps(menus, sort_keys=True) != before:
        changed = True
    settings = BOT_DATA.setdefault("settings", {})
    if not settings.get("languages"):
        pack_langs = [c for c in _load_language_pack().get("languages", {}) if c != "en"]
        if pack_langs:
            settings["languages"] = pack_langs
            changed = True
    if changed:
        save_data()


def load_data():
    global BOT_DATA
    col = get_mongo_collection()

    if col is not None:
        doc = col.find_one({"_id": "bot_data"})
        if doc:
            doc.pop("_id", None)
            BOT_DATA = _deep_merge_defaults(doc)
            log.info("Loaded data from MongoDB.")
        else:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    local = json.load(f)
                BOT_DATA = _deep_merge_defaults(local)
                col.update_one({"_id": "bot_data"}, {"$set": BOT_DATA}, upsert=True)
                log.info("Migrated local JSON data into MongoDB.")
            else:
                BOT_DATA = json.loads(json.dumps(DEFAULT_DATA))
                _apply_seed_files_if_present()
                col.update_one({"_id": "bot_data"}, {"$set": BOT_DATA}, upsert=True)
        _apply_language_pack_migration()
        return

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            BOT_DATA = _deep_merge_defaults(json.load(f))
        log.info("Loaded data from local JSON file.")
    else:
        BOT_DATA = json.loads(json.dumps(DEFAULT_DATA))
        _apply_seed_files_if_present()
        save_data()
    _apply_language_pack_migration()


def save_data():
    col = get_mongo_collection()
    if col is not None:
        col.update_one({"_id": "bot_data"}, {"$set": BOT_DATA}, upsert=True)
        return
    tmp_path = DATA_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(BOT_DATA, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, DATA_FILE)


def get_or_create_backup_key() -> "bytes | None":
    """Local Fernet key used to encrypt backup files. Generated once and
    reused — losing this file means old encrypted backups can never be
    decrypted again, so it's kept next to bot_data.json, never inside the
    BACKUP_DIR (which the /export source-zip explicitly excludes anyway)."""
    if not BACKUP_ENCRYPTION_AVAILABLE:
        return None
    if os.path.exists(BACKUP_KEY_FILE):
        with open(BACKUP_KEY_FILE, "rb") as f:
            return f.read().strip()
    key = Fernet.generate_key()
    with open(BACKUP_KEY_FILE, "wb") as f:
        f.write(key)
    log.warning(
        "Generated a new backup encryption key at %s — this file is the "
        "ONLY way to decrypt existing .enc backups. Keep it safe and never "
        "commit it to git.", BACKUP_KEY_FILE,
    )
    return key


def encrypt_backup_bytes(raw: bytes) -> "tuple[bytes, bool]":
    """Returns (payload, was_encrypted). Falls back to plain bytes if the
    `cryptography` package isn't installed, so backups still work either way."""
    key = get_or_create_backup_key()
    if key is None:
        return raw, False
    return Fernet(key).encrypt(raw), True


def decrypt_backup_bytes(payload: bytes) -> bytes:
    """Reverses encrypt_backup_bytes. Raises InvalidToken if the key doesn't
    match, or ValueError if `cryptography` isn't installed but the payload
    is actually encrypted — callers should catch and show a clear message."""
    key = get_or_create_backup_key()
    if key is None:
        raise ValueError("cryptography package not installed — cannot decrypt.")
    return Fernet(key).decrypt(payload)


def make_backup_snapshot(reason: str = "scheduled") -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    raw = json.dumps(BOT_DATA, ensure_ascii=False, indent=2).encode("utf-8")
    json.loads(raw)  # integrity check before we ever touch disk/encryption
    payload, encrypted = encrypt_backup_bytes(raw)
    ext = "json.enc" if encrypted else "json"
    path = os.path.join(BACKUP_DIR, f"backup_{ts}_{reason}.{ext}")
    with open(path, "wb") as f:
        f.write(payload)
    files = sorted(
        [os.path.join(BACKUP_DIR, x) for x in os.listdir(BACKUP_DIR)], key=os.path.getmtime
    )
    while len(files) > MAX_LOCAL_BACKUPS:
        os.remove(files.pop(0))
    return path


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


__all__ = [_n for _n in dir() if not _n.startswith("__")]
