import os
import json
import time
import uuid
import secrets
import logging
import asyncio
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
    temp_file = Path(
        "bot_data.tmp.json"
    )

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
# MARZBAN TOKEN
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

    if subscription_url.startswith("/"):

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
# QR CODE
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

    raw = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )

    return raw.encode(
        "utf-8"
    )


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
# SEND BACKUP TO OWNER
# =========================================================

async def send_backup_to_owner(
    automatic=False
):

    owner_chat_id = DATA.get(
        "owner_chat_id"
    )

    if not owner_chat_id:

        logger.warning(
            "Owner chat_id is not saved."
        )

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
            "⏰ ساعت ۰۰:۰۰\n"
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

        logger.info(
            "Backup sent to owner."
        )

        return True

    except Exception as e:

        logger.error(
            f"Backup send failed: {e}"
        )

        return False


# =========================================================
# AUTOMATIC BACKUP
# =========================================================

async def automatic_backup():

    logger.info(
        "Running automatic backup..."
    )

    await send_backup_to_owner(
        automatic=True
    )


def start_scheduler():

    scheduler = (
        AsyncIOScheduler(
            timezone=TEHRAN
        )
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
        "Automatic backup scheduler started."
    )

    logger.info(
        "Next backup will run at 00:00 Tehran time."
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
            "سلام امیر 👋\n\n"
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
        "📦 مدیریت بک‌آپ\n\n"
        "یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=(
            backup_keyboard()
        ),
    )


# =========================================================
# DOWNLOAD BACKUP
# =========================================================

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

    try:

        filename, backup_bytes = (
            create_backup_file()
        )

        document = BufferedInputFile(
            backup_bytes,
            filename=filename,
        )

        await message.answer_document(
            document=document,
            caption=(
                "📥 بک‌آپ آماده شد."
            ),
        )

    except Exception as e:

        logger.error(
            f"Backup creation error: {e}"
        )

        await message.answer(
            "❌ ساخت بک‌آپ انجام نشد."
        )


# =========================================================
# UPLOAD BACKUP
# =========================================================

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
        "📤 آپلود بک‌آپ\n\n"
        "فایل JSON بک‌آپ را ارسال کنید.",
        reply_markup=cancel_keyboard(),
    )


# =========================================================
# DOCUMENT HANDLER
# =========================================================

@dp.message(
    F.document
)
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

    document = message.document

    if not document.file_name.lower().endswith(
        ".json"
    ):

        await message.answer(
            "❌ فقط فایل JSON بک‌آپ قابل قبول است."
        )

        return

    try:

        file = await bot.get_file(
            document.file_id
        )

        buffer = BytesIO()

        await bot.download_file(
            file.file_path,
            buffer,
        )

        buffer.seek(0)

        raw = buffer.read()

        backup = json.loads(
            raw.decode(
                "utf-8"
            )
        )

        if not isinstance(
            backup,
            dict
        ):

            raise ValueError(
                "ساختار فایل صحیح نیست."
            )

        backup_data = backup.get(
            "data"
        )

        if not isinstance(
            backup_data,
            dict
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

        # ---------------------------------------------
        # قبل از Restore یک بک‌آپ از وضعیت فعلی
        # در یک فایل محلی نگه می‌داریم.
        # ---------------------------------------------

        current_backup = (
            create_backup_bytes()
        )

        with open(
            "bot_data.before_restore.json",
            "wb",
        ) as f:

            f.write(
                current_backup
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

        logger.info(
            "Backup restored successfully."
        )

    except Exception as e:

        logger.exception(
            "Backup restore failed."
        )

        await message.answer(
            "❌ بازیابی بک‌آپ انجام نشد.\n\n"
            f"خطا: {str(e)[:1500]}",
            reply_markup=(
                owner_keyboard()
            ),
        )


# =========================================================
# CREATE START
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

        await message.answer(
            "⛔️ دسترسی ندارید."
        )

        return

    USER_STATE[
        message.from_user.id
    ] = {
        "step": "volume"
    }

    await message.answer(
        "➕ ساخت کانفیگ\n\n"
        "📦 حجم درخواستی را انتخاب کنید "
        "یا عدد حجم را وارد کنید:",
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


# =========================================================
# ADD ADMIN
# =========================================================

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
        "➕ افزودن ادمین\n\n"
        "Username ادمین را وارد کنید:",
        reply_markup=(
            cancel_keyboard()
        ),
    )


# =========================================================
# REMOVE ADMIN
# =========================================================

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

    if username not in DATA[
        "admins"
    ]:

        await message.answer(
            "❌ این ادمین پیدا نشد.",
            reply_markup=(
                admin_management_keyboard()
            ),
        )

        return

    DATA["admins"].pop(
        username,
        None,
    )

    save_data()

    await message.answer(
        f"✅ ادمین @{username} حذف شد.",
        reply_markup=(
            admin_management_keyboard()
        ),
    )


# =========================================================
# LIST ADMINS
# =========================================================

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

    if not DATA[
        "admins"
    ]:

        text += (
            "هیچ ادمینی ثبت نشده."
        )

    else:

        for username in DATA[
            "admins"
        ]:

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

        users_list = data.get(
            "users",
            [],
        )

        total = data.get(
            "total",
            len(users_list),
        )

        active = sum(
            1
            for user in users_list
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
        "🗑 کانفیگ‌های من\n\n"
        "کانفیگ موردنظر را انتخاب کنید:",
        reply_markup=(
            remove_user_keyboard(
                users
            )
        ),
    )


# =========================================================
# DELETE USER
# =========================================================

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
            "⛔️ این کانفیگ متعلق به شما نیست.",
            reply_markup=(
                admin_keyboard()
            ),
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
# TEXT STATE HANDLER
# =========================================================

@dp.message(F.text)
async def text_handler(
    message: Message
):

    if not can_create(
        message.from_user
    ):
        return

    user_id = (
        message.from_user.id
    )

    state = USER_STATE.get(
        user_id
    )

    if not state:
        return

    text = (
        message.text
        or ""
    ).strip()

    # =====================================================
    # ADD ADMIN
    # =====================================================

    if state.get(
        "step"
    ) == "add_admin":

        if not is_owner(
            message.from_user
        ):
            return

        username = (
            text
            .lstrip("@")
            .strip()
            .lower()
        )

        if not username:

            await message.answer(
                "❌ Username نامعتبر است."
            )

            return

        if username == (
            OWNER_USERNAME.lower()
        ):

            await message.answer(
                "❌ مالک را نمی‌توان "
                "به‌عنوان ادمین اضافه کرد."
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
            "✅ ادمین اضافه شد.\n\n"
            f"👤 @{username}",
            reply_markup=(
                owner_keyboard()
            ),
        )

        return

    # =====================================================
    # VOLUME
    # =====================================================

    if state.get(
        "step"
    ) == "volume":

        clean_text = (
            text
            .replace("GB", "")
            .replace("gb", "")
            .strip()
        )

        try:

            volume = int(
                clean_text
            )

            if volume <= 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ حجم نامعتبر است.\n\n"
                "📦 حجم درخواستی را "
                "انتخاب کنید یا عدد حجم "
                "را وارد کنید:",
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
            "انتخاب کنید یا تعداد "
            "روز را وارد کنید:",
            reply_markup=(
                days_keyboard()
            ),
        )

        return

    # =====================================================
    # DAYS
    # =====================================================

    if state.get(
        "step"
    ) == "days":

        clean_text = (
            text
            .replace("روز", "")
            .strip()
        )

        try:

            days = int(
                clean_text
            )

            if days <= 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ مدت اعتبار نامعتبر است.\n\n"
                "⏳ مدت اعتبار را "
                "انتخاب کنید یا تعداد "
                "روز را وارد کنید:",
                reply_markup=(
                    days_keyboard()
                ),
            )

            return

        volume = state[
            "volume"
        ]

        USER_STATE.pop(
            user_id,
            None,
        )

        await create_user(
            message,
            volume,
            days,
        )

        return


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

        proxy_uuid = str(
            uuid.uuid4()
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

        volume_text = (
            f"{volume} GB"
        )

        payload = {

            "username":
                username,

            "proxies": {
                "vless": {
                    "id":
                        proxy_uuid
                }
            },

            "inbounds": {},

            "expire":
                expire,

            "data_limit":
                data_limit,

            "data_limit_reset_strategy":
                "no_reset",

            "status":
                "active",
        }

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
                f"{response.text[:2000]}"
            )

        result = response.json()

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

        qr_bytes = make_qr_code(
            subscription_url
        )

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

        caption = (
            "✅ کانفیگ ساخته شد\n\n"
            f"👤 نام کاربری:\n"
            f"{username}\n\n"
            f"📦 حجم:\n"
            f"{volume_text}\n\n"
            f"⏳ اعتبار:\n"
            f"{days} روز\n\n"
            "🔗 لینک اشتراک:\n"
            f"{subscription_url}"
        )

        qr_file = BufferedInputFile(
            qr_bytes,
            filename=(
                f"{username}"
                "_subscription.png"
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
                f"📦 حجم: {volume_text}\n"
                f"⏳ اعتبار: {days} روز"
            )

            try:

                await bot.send_message(
                    chat_id=
                        owner_chat_id,
                    text=
                        owner_report,
                )

            except Exception as report_error:

                logger.error(
                    "Owner report failed: "
                    f"{report_error}"
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
            f"{str(error)[:2500]}",
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

    logger.info(
        "Owner chat id: "
        f"{DATA.get('owner_chat_id')}"
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


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
