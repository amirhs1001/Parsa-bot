import os
import json
import time
import uuid
import secrets
import asyncio
import logging
from pathlib import Path
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import qrcode

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BufferedInputFile,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

MARZBAN_URL = "https://panell.goat-hs.online"

MARZBAN_USERNAME = "amirhszz"
MARZBAN_PASSWORD = "amirhszz"

OWNER_USERNAME = "amirhszz"

DATA_FILE = Path("bot_data.json")

TEHRAN = ZoneInfo("Asia/Tehran")


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN در Environment Variables تنظیم نشده است."
    )


# =========================================================
# BOT
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# DATA
# =========================================================

def default_data():
    return {
        "admins": {},
        "created_users": {},
        "owner_chat_id": None,
    }


def load_data():
    if not DATA_FILE.exists():
        return default_data()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        data.setdefault("admins", {})
        data.setdefault("created_users", {})
        data.setdefault("owner_chat_id", None)

        return data

    except Exception as e:
        logger.error(f"Data load error: {e}")
        return default_data()


DATA = load_data()


def save_data():
    temp_file = Path("bot_data.tmp.json")

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            DATA,
            f,
            ensure_ascii=False,
            indent=2,
        )

    temp_file.replace(DATA_FILE)


# =========================================================
# USER STATE
# =========================================================

USER_STATE = {}


# =========================================================
# ACCESS
# =========================================================

def get_username(user):
    if not user:
        return ""

    return (
        getattr(user, "username", None)
        or ""
    ).lower()


def is_owner(user):
    return (
        get_username(user)
        == OWNER_USERNAME.lower()
    )


def is_admin(user):
    username = get_username(user)

    if not username:
        return False

    if is_owner(user):
        return True

    return username in DATA["admins"]


def can_create(user):
    return is_owner(user) or is_admin(user)


# =========================================================
# KEYBOARDS
# =========================================================

def owner_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="➕ ساخت کانفیگ"
                )
            ],
            [
                KeyboardButton(
                    text="📦 بک‌آپ"
                ),
                KeyboardButton(
                    text="📊 آمار"
                ),
            ],
            [
                KeyboardButton(
                    text="👤 مدیریت ادمین‌ها"
                )
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="➕ ساخت کانفیگ"
                )
            ],
            [
                KeyboardButton(
                    text="🗑 کانفیگ‌های من"
                )
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="❌ لغو"
                )
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def volume_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="5 GB"),
                KeyboardButton(text="10 GB"),
                KeyboardButton(text="20 GB"),
            ],
            [
                KeyboardButton(
                    text="❌ لغو"
                )
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def days_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="5 روز"),
                KeyboardButton(text="10 روز"),
            ],
            [
                KeyboardButton(text="15 روز"),
                KeyboardButton(text="30 روز"),
            ],
            [
                KeyboardButton(
                    text="❌ لغو"
                )
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def backup_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📤 آپلود بک‌آپ"
                ),
                KeyboardButton(
                    text="📥 دریافت بک‌آپ"
                ),
            ],
            [
                KeyboardButton(
                    text="🔙 بازگشت"
                )
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_management_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="➕ افزودن ادمین"
                ),
                KeyboardButton(
                    text="🗑 حذف ادمین"
                ),
            ],
            [
                KeyboardButton(
                    text="📋 لیست ادمین‌ها"
                )
            ],
            [
                KeyboardButton(
                    text="🔙 بازگشت"
                )
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def remove_admin_keyboard():
    buttons = []

    for username in DATA["admins"]:
        buttons.append(
            [
                KeyboardButton(
                    text=f"🗑 @{username}"
                )
            ]
        )

    buttons.append(
        [
            KeyboardButton(
                text="🔙 بازگشت"
            )
        ]
    )

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )


def remove_user_keyboard(users):
    buttons = []

    for username in users:
        buttons.append(
            [
                KeyboardButton(
                    text=f"🗑 {username}"
                )
            ]
        )

    buttons.append(
        [
            KeyboardButton(
                text="🔙 بازگشت"
            )
        ]
    )

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )


# =========================================================
# MARZBAN LOGIN
# =========================================================

async def get_marzban_token():

    url = (
        f"{MARZBAN_URL}"
        "/api/admin/token"
    )

    data = {
        "grant_type": "password",
        "username": MARZBAN_USERNAME,
        "password": MARZBAN_PASSWORD,
        "scope": "",
        "client_id": "",
        "client_secret": "",
    }

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
    ) as client:

        response = await client.post(
            url,
            data=data,
        )

    if response.status_code != 200:
        raise RuntimeError(
            "ورود به Marzban ناموفق بود.\n"
            f"HTTP {response.status_code}\n"
            f"{response.text[:1500]}"
        )

    result = response.json()

    token = result.get(
        "access_token"
    )

    if not token:
        raise RuntimeError(
            "Marzban توکن دسترسی برنگرداند."
        )

    return token


# =========================================================
# MARZBAN REQUEST
# =========================================================

async def marzban_request(
    method,
    endpoint,
    token,
    **kwargs,
):

    url = (
        f"{MARZBAN_URL}"
        f"{endpoint}"
    )

    headers = {
        "Authorization":
            f"Bearer {token}",
        "Accept":
            "application/json",
    }

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
    ) as client:

        return await client.request(
            method,
            url,
            headers=headers,
            **kwargs,
        )


# =========================================================
# GET INBOUNDS
# =========================================================

async def get_active_inbounds(token):

    response = await marzban_request(
        "GET",
        "/api/inbounds",
        token,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "دریافت Inbound ها ناموفق بود.\n"
            f"HTTP {response.status_code}\n"
            f"{response.text[:2000]}"
        )

    data = response.json()

    if isinstance(data, dict):

        inbounds = (
            data.get("inbounds")
            or data.get("items")
            or data.get("data")
            or []
        )

    elif isinstance(data, list):

        inbounds = data

    else:

        inbounds = []

    return inbounds


# =========================================================
# BUILD INBOUND MAP
# =========================================================

def build_inbound_map(inbounds):

    result = {}

    for inbound in inbounds:

        if not isinstance(
            inbound,
            dict,
        ):
            continue

        tag = (
            inbound.get("tag")
            or inbound.get("name")
        )

        protocol = (
            inbound.get("protocol")
            or inbound.get("type")
        )

        if not tag or not protocol:
            continue

        protocol = str(
            protocol
        ).lower()

        if protocol not in (
            "vless",
            "vmess",
            "trojan",
            "shadowsocks",
        ):
            continue

        result.setdefault(
            protocol,
            [],
        )

        result[protocol].append(
            tag
        )

    return result


# =========================================================
# SUBSCRIPTION URL
# =========================================================

def build_subscription_url(
    subscription_url
):

    if not subscription_url:
        return ""

    subscription_url = str(
        subscription_url
    ).strip()

    if (
        subscription_url.startswith(
            "http://"
        )
        or
        subscription_url.startswith(
            "https://"
        )
    ):
        return subscription_url

    if subscription_url.startswith(
        "/"
    ):
        return (
            MARZBAN_URL.rstrip("/")
            + subscription_url
        )

    return (
        MARZBAN_URL.rstrip("/")
        + "/"
        + subscription_url
    )


# =========================================================
# QR
# =========================================================

def make_qr_code(
    subscription_url
):

    qr = qrcode.QRCode(
        version=None,
        error_correction=(
            qrcode.constants
            .ERROR_CORRECT_M
        ),
        box_size=10,
        border=4,
    )

    qr.add_data(
        subscription_url
    )

    qr.make(
        fit=True
    )

    image = qr.make_image()

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    buffer.seek(0)

    return buffer.getvalue()


# =========================================================
# BACKUP
# =========================================================

def create_backup_bytes():

    data = {
        "backup_version": 1,
        "created_at": datetime.now(
            TEHRAN
        ).isoformat(),
        "data": DATA,
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def create_backup_file():

    timestamp = datetime.now(
        TEHRAN
    ).strftime(
        "%Y-%m-%d_%H-%M"
    )

    filename = (
        f"marzban_bot_backup_"
        f"{timestamp}.json"
    )

    return (
        filename,
        create_backup_bytes(),
    )


# =========================================================
# AUTOMATIC BACKUP
# =========================================================

async def send_backup_to_owner(
    automatic=False
):

    owner_chat_id = DATA.get(
        "owner_chat_id"
    )

    if not owner_chat_id:
        return False

    filename, backup_bytes = (
        create_backup_file()
    )

    file = BufferedInputFile(
        backup_bytes,
        filename=filename,
    )

    if automatic:

        caption = (
            "🌙 بک‌آپ خودکار شبانه\n\n"
            "💾 بک‌آپ ربات آماده شد."
        )

    else:

        caption = (
            "📥 بک‌آپ ربات\n\n"
            "💾 فایل پشتیبان آماده است."
        )

    try:

        await bot.send_document(
            chat_id=owner_chat_id,
            document=file,
            caption=caption,
        )

        return True

    except Exception as e:

        logger.error(
            f"Backup send failed: {e}"
        )

        return False


async def automatic_backup():

    logger.info(
        "Running nightly backup..."
    )

    await send_backup_to_owner(
        automatic=True
    )


def start_scheduler():

    scheduler = AsyncIOScheduler(
        timezone=TEHRAN
    )

    scheduler.add_job(
        automatic_backup,
        "cron",
        hour=0,
        minute=0,
        id="nightly_backup",
        replace_existing=True,
    )

    scheduler.start()

    logger.info(
        "Nightly backup scheduler started."
    )

    return scheduler


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(
    message: Message
):

    if is_owner(
        message.from_user
    ):

        DATA[
            "owner_chat_id"
        ] = message.chat.id

        save_data()

        await message.answer(
            "👑 پنل مالک\n\n"
            "سلام 👋\n\n"
            "دسترسی کامل فعال است.",
            reply_markup=(
                owner_keyboard()
            ),
        )

        return

    if is_admin(
        message.from_user
    ):

        await message.answer(
            "👤 پنل ادمین\n\n"
            "می‌توانید کانفیگ بسازید "
            "و کانفیگ‌های خودتان را حذف کنید.",
            reply_markup=(
                admin_keyboard()
            ),
        )

        return

    await message.answer(
        "⛔️ شما اجازه استفاده "
        "از این ربات را ندارید."
    )


# =========================================================
# CANCEL
# =========================================================

@dp.message(
    F.text == "❌ لغو"
)
async def cancel(
    message: Message
):

    USER_STATE.pop(
        message.from_user.id,
        None,
    )

    if is_owner(
        message.from_user
    ):

        await message.answer(
            "❌ عملیات لغو شد.",
            reply_markup=(
                owner_keyboard()
            ),
        )

    elif is_admin(
        message.from_user
    ):

        await message.answer(
            "❌ عملیات لغو شد.",
            reply_markup=(
                admin_keyboard()
            ),
        )


# =========================================================
# BACKUP MENU
# =========================================================

@dp.message(
    F.text == "📦 بک‌آپ"
)
async def backup_menu(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    await message.answer(
        "📦 مدیریت بک‌آپ",
        reply_markup=(
            backup_keyboard()
        ),
    )


@dp.message(
    F.text == "📥 دریافت بک‌آپ"
)
async def download_backup(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    filename, backup_bytes = (
        create_backup_file()
    )

    document = BufferedInputFile(
        backup_bytes,
        filename=filename,
    )

    await message.answer_document(
        document=document,
        caption="📥 بک‌آپ آماده شد.",
    )


@dp.message(
    F.text == "📤 آپلود بک‌آپ"
)
async def upload_backup_start(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    USER_STATE[
        message.from_user.id
    ] = {
        "step": "upload_backup"
    }

    await message.answer(
        "📤 فایل JSON بک‌آپ را ارسال کنید.",
        reply_markup=cancel_keyboard(),
    )


# =========================================================
# DOCUMENT
# =========================================================

@dp.message(F.document)
async def document_handler(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    state = USER_STATE.get(
        message.from_user.id
    )

    if not state:
        return

    if state.get(
        "step"
    ) != "upload_backup":
        return

    if not message.document.file_name.lower().endswith(
        ".json"
    ):

        await message.answer(
            "❌ فقط فایل JSON قابل قبول است."
        )

        return

    try:

        file = await bot.get_file(
            message.document.file_id
        )

        buffer = BytesIO()

        await bot.download_file(
            file.file_path,
            buffer,
        )

        buffer.seek(0)

        backup = json.loads(
            buffer.read().decode(
                "utf-8"
            )
        )

        backup_data = backup.get(
            "data"
        )

        if not isinstance(
            backup_data,
            dict,
        ):
            raise ValueError(
                "فایل بک‌آپ معتبر نیست."
            )

        backup_data.setdefault(
            "admins",
            {}
        )

        backup_data.setdefault(
            "created_users",
            {}
        )

        backup_data.setdefault(
            "owner_chat_id",
            message.chat.id
        )

        # Backup before restore
        with open(
            "bot_data.before_restore.json",
            "wb",
        ) as f:

            f.write(
                create_backup_bytes()
            )

        DATA.clear()
        DATA.update(
            backup_data
        )

        save_data()

        USER_STATE.pop(
            message.from_user.id,
            None,
        )

        await message.answer(
            "✅ بک‌آپ با موفقیت بازیابی شد.",
            reply_markup=(
                owner_keyboard()
            ),
        )

    except Exception as e:

        logger.exception(
            "Backup restore failed"
        )

        await message.answer(
            "❌ بازیابی بک‌آپ انجام نشد.\n\n"
            f"خطا:\n{str(e)[:1500]}",
            reply_markup=(
                owner_keyboard()
            ),
        )


# =========================================================
# CREATE
# =========================================================

@dp.message(
    F.text == "➕ ساخت کانفیگ"
)
async def create_start(
    message: Message
):

    if not can_create(
        message.from_user
    ):
        return

    USER_STATE[
        message.from_user.id
    ] = {
        "step": "volume"
    }

    await message.answer(
        "➕ ساخت کانفیگ\n\n"
        "📦 حجم درخواستی را انتخاب کنید "
        "یا حجم را وارد کنید:",
        reply_markup=(
            volume_keyboard()
        ),
    )


# =========================================================
# ADMIN MANAGEMENT
# =========================================================

@dp.message(
    F.text == "👤 مدیریت ادمین‌ها"
)
async def admin_management(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    await message.answer(
        "👤 مدیریت ادمین‌ها",
        reply_markup=(
            admin_management_keyboard()
        ),
    )


@dp.message(
    F.text == "➕ افزودن ادمین"
)
async def add_admin_start(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    USER_STATE[
        message.from_user.id
    ] = {
        "step": "add_admin"
    }

    await message.answer(
        "➕ Username ادمین را وارد کنید:",
        reply_markup=cancel_keyboard(),
    )


@dp.message(
    F.text == "🗑 حذف ادمین"
)
async def remove_admin_start(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    if not DATA["admins"]:

        await message.answer(
            "👤 هیچ ادمینی ثبت نشده.",
            reply_markup=(
                admin_management_keyboard()
            ),
        )

        return

    await message.answer(
        "🗑 ادمین موردنظر را انتخاب کنید:",
        reply_markup=(
            remove_admin_keyboard()
        ),
    )


@dp.message(
    F.text.startswith("🗑 @")
)
async def remove_admin_confirm(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    username = (
        message.text
        .replace("🗑 @", "")
        .strip()
        .lower()
    )

    if username not in DATA["admins"]:

        await message.answer(
            "❌ این ادمین پیدا نشد."
        )

        return

    DATA["admins"].pop(
        username,
        None
    )

    save_data()

    await message.answer(
        f"✅ ادمین @{username} حذف شد.",
        reply_markup=(
            admin_management_keyboard()
        ),
    )


@dp.message(
    F.text == "📋 لیست ادمین‌ها"
)
async def list_admins(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    text = (
        "👑 مالک:\n"
        f"@{OWNER_USERNAME}\n\n"
        "👤 ادمین‌ها:\n\n"
    )

    if not DATA["admins"]:

        text += "هیچ ادمینی ثبت نشده."

    else:

        for username in DATA["admins"]:

            text += (
                f"• @{username}\n"
            )

    await message.answer(
        text,
        reply_markup=(
            admin_management_keyboard()
        ),
    )


# =========================================================
# STATS
# =========================================================

@dp.message(
    F.text == "📊 آمار"
)
async def stats(
    message: Message
):

    if not is_owner(
        message.from_user
    ):
        return

    try:

        token = (
            await get_marzban_token()
        )

        response = await marzban_request(
            "GET",
            "/api/users",
            token,
        )

        if response.status_code != 200:
            raise RuntimeError(
                response.text[:1000]
            )

        data = response.json()

        users = data.get(
            "users",
            []
        )

        total = data.get(
            "total",
            len(users)
        )

        active = sum(
            1
            for user in users
            if user.get(
                "status"
            ) == "active"
        )

        await message.answer(
            "📊 آمار\n\n"
            f"👥 کل کاربران: {total}\n"
            f"🟢 فعال: {active}\n"
            f"🔴 غیرفعال: "
            f"{total - active}\n"
            f"👤 ادمین‌ها: "
            f"{len(DATA['admins'])}",
            reply_markup=(
                owner_keyboard()
            ),
        )

    except Exception as error:

        await message.answer(
            "❌ دریافت آمار ناموفق بود.\n\n"
            f"{str(error)[:1500]}",
            reply_markup=(
                owner_keyboard()
            ),
        )


# =========================================================
# MY CONFIGS
# =========================================================

@dp.message(
    F.text == "🗑 کانفیگ‌های من"
)
async def my_users(
    message: Message
):

    if not is_admin(
        message.from_user
    ):
        return

    username = get_username(
        message.from_user
    )

    users = DATA[
        "created_users"
    ].get(
        username,
        [],
    )

    if not users:

        await message.answer(
            "🗑 کانفیگ‌های من\n\n"
            "هنوز کانفیگی نساخته‌اید.",
            reply_markup=(
                admin_keyboard()
            ),
        )

        return

    await message.answer(
        "🗑 کانفیگ موردنظر را انتخاب کنید:",
        reply_markup=(
            remove_user_keyboard(
                users
            )
        ),
    )


@dp.message(
    F.text.startswith("🗑 u_")
)
async def delete_user(
    message: Message
):

    if not is_admin(
        message.from_user
    ):
        return

    username = (
        message.text
        .replace("🗑 ", "")
        .strip()
    )

    creator = get_username(
        message.from_user
    )

    owned = DATA[
        "created_users"
    ].get(
        creator,
        [],
    )

    if username not in owned:

        await message.answer(
            "⛔️ این کانفیگ متعلق به شما نیست."
        )

        return

    try:

        token = (
            await get_marzban_token()
        )

        response = await marzban_request(
            "DELETE",
            f"/api/user/{username}",
            token,
        )

        if response.status_code not in (
            200,
            204,
        ):

            raise RuntimeError(
                f"HTTP {response.status_code}\n"
                f"{response.text[:1000]}"
            )

        owned.remove(
            username
        )

        save_data()

        await message.answer(
            "✅ کانفیگ حذف شد.",
            reply_markup=(
                admin_keyboard()
            ),
        )

    except Exception as error:

        await message.answer(
            "❌ حذف کانفیگ انجام نشد.\n\n"
            f"{str(error)[:1500]}",
            reply_markup=(
                admin_keyboard()
            ),
        )


# =========================================================
# CREATE STATE HANDLER
# =========================================================

@dp.message(F.text)
async def text_handler(
    message: Message
):

    if not can_create(
        message.from_user
    ):
        return

    user_id = message.from_user.id

    state = USER_STATE.get(
        user_id
    )

    if not state:
        return

    text = (
        message.text
        or ""
    ).strip()

    # -----------------------------------------------------
    # ADD ADMIN
    # -----------------------------------------------------

    if state.get(
        "step"
    ) == "add_admin":

        username = (
            text
            .lstrip("@")
            .strip()
            .lower()
        )

        if username == OWNER_USERNAME.lower():

            await message.answer(
                "❌ مالک را نمی‌توان "
                "به‌عنوان ادمین اضافه کرد."
            )

            return

        if not username:

            await message.answer(
                "❌ Username نامعتبر است."
            )

            return

        DATA[
            "admins"
        ][username] = {
            "created_at":
                int(time.time())
        }

        DATA[
            "created_users"
        ].setdefault(
            username,
            [],
        )

        save_data()

        USER_STATE.pop(
            user_id,
            None,
        )

        await message.answer(
            f"✅ ادمین @{username} اضافه شد.",
            reply_markup=(
                owner_keyboard()
            ),
        )

        return

    # -----------------------------------------------------
    # VOLUME
    # -----------------------------------------------------

    if state.get(
        "step"
    ) == "volume":

        clean = (
            text
            .replace("GB", "")
            .replace("gb", "")
            .strip()
        )

        try:

            volume = int(clean)

            if volume <= 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ حجم نامعتبر است.\n\n"
                "📦 حجم درخواستی را "
                "انتخاب کنید یا وارد کنید:",
                reply_markup=(
                    volume_keyboard()
                ),
            )

            return

        USER_STATE[
            user_id
        ] = {
            "step": "days",
            "volume": volume,
        }

        await message.answer(
            "⏳ مدت اعتبار را "
            "انتخاب کنید یا وارد کنید:",
            reply_markup=(
                days_keyboard()
            ),
        )

        return

    # -----------------------------------------------------
    # DAYS
    # -----------------------------------------------------

    if state.get(
        "step"
    ) == "days":

        clean = (
            text
            .replace("روز", "")
            .strip()
        )

        try:

            days = int(clean)

            if days <= 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ مدت اعتبار نامعتبر است.\n\n"
                "⏳ مدت اعتبار را "
                "انتخاب کنید یا وارد کنید:",
                reply_markup=(
                    days_keyboard()
                ),
            )

            return

        volume = state["volume"]

        USER_STATE.pop(
            user_id,
            None,
        )

        await create_user(
            message,
            volume,
            days,
        )


# =========================================================
# CREATE USER
# =========================================================

async def create_user(
    message: Message,
    volume: int,
    days: int,
):

    progress = await message.answer(
        "⏳ در حال ساخت کانفیگ..."
    )

    try:

        token = (
            await get_marzban_token()
        )

        username = (
            "u_"
            + secrets.token_hex(4)
        )

        expire = int(
            time.time()
            + days * 86400
        )

        data_limit = (
            volume
            * 1024
            * 1024
            * 1024
        )

        # =================================================
        # دریافت تمام Inbound ها
        # =================================================

        all_inbounds = (
            await get_active_inbounds(
                token
            )
        )

        inbound_map = (
            build_inbound_map(
                all_inbounds
            )
        )

        if not inbound_map:

            raise RuntimeError(
                "هیچ Inbound فعالی در Marzban پیدا نشد."
            )

        logger.info(
            "Detected protocols: "
            f"{list(inbound_map.keys())}"
        )

        # =================================================
        # PROXIES
        # =================================================

        proxies = {}

        # VLESS
        if "vless" in inbound_map:

            proxies["vless"] = {
                "id": str(
                    uuid.uuid4()
                )
            }

        # VMESS
        if "vmess" in inbound_map:

            proxies["vmess"] = {
                "id": str(
                    uuid.uuid4()
                ),
                "security": "auto"
            }

        # TROJAN
        if "trojan" in inbound_map:

            proxies["trojan"] = {
                "password":
                    secrets.token_urlsafe(16)
            }

        # SHADOWSOCKS
        if "shadowsocks" in inbound_map:

            proxies["shadowsocks"] = {
                "password":
                    secrets.token_urlsafe(16),
                "method":
                    "chacha20-ietf-poly1305"
            }

        if not proxies:

            raise RuntimeError(
                "هیچ پروتکل پشتیبانی‌شده‌ای "
                "در Inbound ها پیدا نشد."
            )

        # =================================================
        # INBOUNDS
        # =================================================

        inbounds = {}

        for protocol, tags in inbound_map.items():

            if protocol in proxies:

                inbounds[
                    protocol
                ] = tags

        # =================================================
        # PAYLOAD
        # =================================================

        payload = {
            "username": username,

            "proxies": proxies,

            "inbounds": inbounds,

            "expire": expire,

            "data_limit": data_limit,

            "data_limit_reset_strategy":
                "no_reset",

            "status": "active",
        }

        logger.info(
            "Creating user %s with protocols %s",
            username,
            list(proxies.keys()),
        )

        response = await marzban_request(
            "POST",
            "/api/user",
            token,
            json=payload,
        )

        if response.status_code not in (
            200,
            201,
        ):

            raise RuntimeError(
                "Create user failed: "
                f"{response.status_code}\n"
                f"{response.text[:3000]}"
            )

        result = response.json()

        # =================================================
        # SUB URL
        # =================================================

        subscription_url = (
            result.get(
                "subscription_url"
            )
            or ""
        )

        subscription_url = (
            build_subscription_url(
                subscription_url
            )
        )

        if not subscription_url:

            raise RuntimeError(
                "Marzban لینک Subscription "
                "واقعی را برنگرداند."
            )

        # =================================================
        # QR
        # =================================================

        qr_bytes = make_qr_code(
            subscription_url
        )

        # =================================================
        # SAVE
        # =================================================

        creator = get_username(
            message.from_user
        )

        DATA[
            "created_users"
        ].setdefault(
            creator,
            [],
        )

        DATA[
            "created_users"
        ][creator].append(
            username
        )

        save_data()

        try:
            await progress.delete()
        except Exception:
            pass

        # =================================================
        # RESULT
        # =================================================

        caption = (
            "✅ کانفیگ ساخته شد\n\n"
            f"👤 نام کاربری:\n"
            f"{username}\n\n"
            f"📦 حجم:\n"
            f"{volume} GB\n\n"
            f"⏳ اعتبار:\n"
            f"{days} روز\n\n"
            "🔗 لینک اشتراک:\n"
            f"{subscription_url}"
        )

        qr_file = BufferedInputFile(
            qr_bytes,
            filename=(
                f"{username}_subscription.png"
            ),
        )

        await message.answer_photo(
            photo=qr_file,
            caption=caption,
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    message.from_user
                )
                else admin_keyboard()
            ),
        )

        # =================================================
        # OWNER REPORT
        # =================================================

        owner_chat_id = DATA.get(
            "owner_chat_id"
        )

        if (
            owner_chat_id
            and not is_owner(
                message.from_user
            )
        ):

            owner_report = (
                "🔔 کانفیگ جدید\n\n"
                f"👤 سازنده: @{creator}\n"
                f"🧾 کاربر: {username}\n"
                f"📦 حجم: {volume} GB\n"
                f"⏳ اعتبار: {days} روز"
            )

            try:

                await bot.send_message(
                    chat_id=owner_chat_id,
                    text=owner_report,
                )

            except Exception as e:

                logger.error(
                    f"Owner report failed: {e}"
                )

    except Exception as error:

        logger.exception(
            "Create user failed"
        )

        try:
            await progress.delete()
        except Exception:
            pass

        await message.answer(
            "❌ ساخت کانفیگ انجام نشد.\n\n"
            "خطا:\n"
            f"{str(error)[:3000]}",
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    message.from_user
                )
                else admin_keyboard()
            ),
        )


# =========================================================
# BACK
# =========================================================

@dp.message(
    F.text == "🔙 بازگشت"
)
async def back(
    message: Message
):

    USER_STATE.pop(
        message.from_user.id,
        None,
    )

    if is_owner(
        message.from_user
    ):

        await message.answer(
            "👑 پنل مالک",
            reply_markup=(
                owner_keyboard()
            ),
        )

    elif is_admin(
        message.from_user
    ):

        await message.answer(
            "👤 پنل ادمین",
            reply_markup=(
                admin_keyboard()
            ),
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info(
        "Telegram bot starting..."
    )

    logger.info(
        f"Owner: @{OWNER_USERNAME}"
    )

    scheduler = start_scheduler()

    try:

        await dp.start_polling(
            bot,
            allowed_updates=(
                dp.resolve_used_update_types()
            ),
        )

    finally:

        scheduler.shutdown(
            wait=False
        )


if __name__ == "__main__":

    asyncio.run(
        main()
    )
