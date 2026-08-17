import os
import json
import time
import uuid
import secrets
import logging
from pathlib import Path
from io import BytesIO

import httpx
import qrcode

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

MARZBAN_URL = "https://panell.goat-hs.online"

MARZBAN_USERNAME = "amirhszz"
MARZBAN_PASSWORD = "amirhszz"

OWNER_USERNAME = "amirhszz"

DATA_FILE = Path("bot_data.json")


# =========================================================
# BOT
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN در Railway Variables تنظیم نشده است."
    )

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

def load_data():

    if not DATA_FILE.exists():
        return {
            "admins": {},
            "created_users": {},
            "owner_chat_id": None,
        }

    try:
        with open(
            DATA_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        data.setdefault("admins", {})
        data.setdefault("created_users", {})
        data.setdefault("owner_chat_id", None)

        return data

    except Exception:
        return {
            "admins": {},
            "created_users": {},
            "owner_chat_id": None,
        }


DATA = load_data()


def save_data():

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            DATA,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# STATE
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

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ ساخت کانفیگ",
                    callback_data="create",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 کاربران",
                    callback_data="users",
                ),
                InlineKeyboardButton(
                    text="📊 آمار",
                    callback_data="stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👤 مدیریت ادمین‌ها",
                    callback_data="admins",
                )
            ],
        ]
    )


def admin_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ ساخت کانفیگ",
                    callback_data="create",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 کانفیگ‌های من",
                    callback_data="my_users",
                )
            ],
        ]
    )


def back_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="back",
                )
            ]
        ]
    )


# =========================================================
# MARZBAN AUTH
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
            "ورود به Marzban ناموفق بود:\n"
            f"HTTP {response.status_code}\n"
            f"{response.text[:1500]}"
        )

    result = response.json()

    token = result.get(
        "access_token"
    )

    if not token:

        raise RuntimeError(
            "Marzban access_token برنگرداند."
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

    url = f"{MARZBAN_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
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

    # اگر Marzban لینک کامل داده
    if subscription_url.startswith(
        "http://"
    ) or subscription_url.startswith(
        "https://"
    ):

        return subscription_url

    # اگر /sub/... داده
    if subscription_url.startswith("/"):
        return (
            MARZBAN_URL.rstrip("/")
            + subscription_url
        )

    # اگر فقط sub/... داده
    if subscription_url.startswith("sub/"):

        return (
            MARZBAN_URL.rstrip("/")
            + "/"
            + subscription_url
        )

    # حالت fallback
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
        error_correction=qrcode.constants.ERROR_CORRECT_M,
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
# START
# =========================================================

@dp.message(CommandStart())
async def start(
    message: Message
):

    if is_owner(
        message.from_user
    ):

        DATA["owner_chat_id"] = (
            message.chat.id
        )

        save_data()

        await message.answer(
            "👑 پنل مالک\n\n"
            "سلام امیر 👋\n\n"
            "دسترسی کامل فعال است.",
            reply_markup=owner_keyboard(),
        )

        return

    if is_admin(
        message.from_user
    ):

        await message.answer(
            "👤 پنل ادمین\n\n"
            "می‌توانی کانفیگ بسازی "
            "و کانفیگ‌های خودت را حذف کنی.",
            reply_markup=admin_keyboard(),
        )

        return

    await message.answer(
        "⛔️ شما اجازه استفاده از این ربات را ندارید."
    )


# =========================================================
# CREATE
# =========================================================

@dp.callback_query(
    F.data == "create"
)
async def create_menu(
    callback: CallbackQuery
):

    if not can_create(
        callback.from_user
    ):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    USER_STATE[
        callback.from_user.id
    ] = {
        "step": "volume"
    }

    await callback.message.edit_text(
        "➕ ساخت کانفیگ\n\n"
        "📦 حجم درخواستی را وارد کنید:",
        reply_markup=back_keyboard(),
    )


# =========================================================
# TEXT HANDLER
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

    # =====================================================
    # ADD ADMIN
    # =====================================================

    if state.get("step") == "add_admin":

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

        if (
            username
            == OWNER_USERNAME.lower()
        ):

            await message.answer(
                "❌ مالک را نمی‌توان به‌عنوان ادمین اضافه کرد."
            )

            return

        DATA["admins"][username] = {
            "created_at": int(
                time.time()
            )
        }

        DATA[
            "created_users"
        ].setdefault(
            username,
            []
        )

        save_data()

        USER_STATE.pop(
            user_id,
            None
        )

        await message.answer(
            "✅ ادمین اضافه شد.\n\n"
            f"👤 @{username}",
            reply_markup=owner_keyboard(),
        )

        return

    # =====================================================
    # VOLUME
    # =====================================================

    if state.get("step") == "volume":

        try:

            volume = int(text)

            if volume < 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ حجم باید به‌صورت عدد وارد شود.\n\n"
                "📦 حجم درخواستی را وارد کنید:"
            )

            return

        USER_STATE[user_id] = {
            "step": "days",
            "volume": volume,
        }

        await message.answer(
            "⏳ مدت اعتبار را به روز وارد کنید:"
        )

        return

    # =====================================================
    # DAYS
    # =====================================================

    if state.get("step") == "days":

        try:

            days = int(text)

            if days <= 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ مدت اعتبار باید عددی بیشتر از صفر باشد.\n\n"
                "⏳ مدت اعتبار را به روز وارد کنید:"
            )

            return

        volume = state[
            "volume"
        ]

        USER_STATE.pop(
            user_id,
            None
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

        # -------------------------------------------------
        # Marzban نیاز به Proxy معتبر دارد.
        # ALL مقدار معتبر برای proxies نیست.
        #
        # VLESS به عنوان Proxy پایه استفاده می‌شود.
        # Inboundها توسط Marzban مدیریت می‌شوند.
        # -------------------------------------------------

        proxy_uuid = str(
            uuid.uuid4()
        )

        proxies = {
            "vless": {
                "id": proxy_uuid
            }
        }

        # -------------------------------------------------
        # USERNAME
        # -------------------------------------------------

        username = (
            "u_"
            + secrets.token_hex(4)
        )

        # -------------------------------------------------
        # EXPIRE
        # -------------------------------------------------

        expire = int(
            time.time()
            + days * 86400
        )

        # -------------------------------------------------
        # DATA LIMIT
        # -------------------------------------------------

        if volume == 0:

            data_limit = 0

        else:

            data_limit = (
                volume
                * 1024
                * 1024
                * 1024
            )

        # -------------------------------------------------
        # PAYLOAD
        # -------------------------------------------------

        payload = {
            "username": username,
            "proxies": proxies,
            "inbounds": {},
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
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
                "Create user failed:\n"
                f"HTTP {response.status_code}\n"
                f"{response.text[:2000]}"
            )

        result = response.json()

        # -------------------------------------------------
        # REAL SUBSCRIPTION URL
        # -------------------------------------------------

        subscription_url = (
            result.get(
                "subscription_url"
            )
            or ""
        )

        if not subscription_url:

            # بعض نسخه‌ها ممکن است subscription_url
            # را داخل اطلاعات کاربر داشته باشند.
            subscription_url = (
                result.get(
                    "subscription"
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
                "Marzban لینک Subscription را در پاسخ ساخت User برنگرداند."
            )

        # -------------------------------------------------
        # QR
        # -------------------------------------------------

        qr_bytes = make_qr_code(
            subscription_url
        )

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        creator = get_username(
            message.from_user
        )

        DATA[
            "created_users"
        ].setdefault(
            creator,
            []
        )

        DATA[
            "created_users"
        ][creator].append(
            username
        )

        save_data()

        # -------------------------------------------------
        # MESSAGE
        # -------------------------------------------------

        volume_text = (
            "نامحدود"
            if volume == 0
            else f"{volume} GB"
        )

        result_text = (
            "✅ کانفیگ ساخته شد\n\n"
            f"👤 نام کاربری:\n"
            f"`{username}`\n\n"
            f"📦 حجم:\n"
            f"{volume_text}\n\n"
            f"⏳ اعتبار:\n"
            f"{days} روز\n\n"
            "🔗 لینک اشتراک:\n"
            f"`{subscription_url}`"
        )

        await progress.delete()

        await message.answer(
            result_text,
            parse_mode="Markdown",
        )

        # -------------------------------------------------
        # SEND REAL QR
        # -------------------------------------------------

        qr_file = BufferedInputFile(
            qr_bytes,
            filename=(
                f"{username}_subscription.png"
            ),
        )

        await message.answer_photo(
            photo=qr_file,
            caption=(
                "📱 QR Code اشتراک\n\n"
                f"`{username}`"
            ),
            parse_mode="Markdown",
        )

        # -------------------------------------------------
        # NOTIFY OWNER WHEN ADMIN CREATES
        # -------------------------------------------------

        if (
            not is_owner(
                message.from_user
            )
            and DATA.get(
                "owner_chat_id"
            )
        ):

            owner_text = (
                "🔔 کانفیگ جدید ساخته شد\n\n"
                f"👤 توسط:\n"
                f"@{creator}\n\n"
                f"🧾 نام کاربری:\n"
                f"`{username}`\n\n"
                f"📦 حجم:\n"
                f"{volume_text}\n\n"
                f"⏳ اعتبار:\n"
                f"{days} روز\n\n"
                "🔗 لینک اشتراک:\n"
                f"`{subscription_url}`"
            )

            await bot.send_message(
                DATA["owner_chat_id"],
                owner_text,
                parse_mode="Markdown",
            )

            owner_qr = BufferedInputFile(
                qr_bytes,
                filename=(
                    f"{username}_subscription.png"
                ),
            )

            await bot.send_photo(
                DATA["owner_chat_id"],
                owner_qr,
                caption="📱 QR Code اشتراک",
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
            f"`{str(error)[:2500]}`",
            parse_mode="Markdown",
        )


# =========================================================
# ADMINS
# =========================================================

@dp.callback_query(
    F.data == "admins"
)
async def admins_menu(
    callback: CallbackQuery
):

    if not is_owner(
        callback.from_user
    ):
        return

    await callback.answer()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ افزودن ادمین",
                    callback_data="add_admin",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 حذف ادمین",
                    callback_data="remove_admin",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 لیست ادمین‌ها",
                    callback_data="list_admins",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="back",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        "👤 مدیریت ادمین‌ها",
        reply_markup=keyboard,
    )


# =========================================================
# ADD ADMIN
# =========================================================

@dp.callback_query(
    F.data == "add_admin"
)
async def add_admin(
    callback: CallbackQuery
):

    if not is_owner(
        callback.from_user
    ):
        return

    await callback.answer()

    USER_STATE[
        callback.from_user.id
    ] = {
        "step": "add_admin"
    }

    await callback.message.edit_text(
        "➕ افزودن ادمین\n\n"
        "Username ادمین را وارد کنید:",
        reply_markup=back_keyboard(),
    )


# =========================================================
# REMOVE ADMIN
# =========================================================

@dp.callback_query(
    F.data == "remove_admin"
)
async def remove_admin(
    callback: CallbackQuery
):

    if not is_owner(
        callback.from_user
    ):
        return

    await callback.answer()

    if not DATA["admins"]:

        await callback.message.edit_text(
            "👤 هیچ ادمینی ثبت نشده.",
            reply_markup=back_keyboard(),
        )

        return

    buttons = []

    for username in DATA["admins"]:

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 @{username}",
                    callback_data=(
                        f"delete_admin:{username}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 بازگشت",
                callback_data="admins",
            )
        ]
    )

    await callback.message.edit_text(
        "🗑 ادمین موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )


# =========================================================
# DELETE ADMIN
# =========================================================

@dp.callback_query(
    F.data.startswith(
        "delete_admin:"
    )
)
async def delete_admin(
    callback: CallbackQuery
):

    if not is_owner(
        callback.from_user
    ):
        return

    username = (
        callback.data
        .split(":", 1)[1]
        .lower()
    )

    DATA["admins"].pop(
        username,
        None
    )

    save_data()

    await callback.answer(
        "✅ ادمین حذف شد."
    )

    await admins_menu(
        callback
    )


# =========================================================
# LIST ADMINS
# =========================================================

@dp.callback_query(
    F.data == "list_admins"
)
async def list_admins(
    callback: CallbackQuery
):

    if not is_owner(
        callback.from_user
    ):
        return

    await callback.answer()

    text = (
        "👑 مالک:\n"
        f"@{OWNER_USERNAME}\n\n"
        "👤 ادمین‌ها:\n\n"
    )

    if not DATA["admins"]:

        text += "هیچ ادمینی وجود ندارد."

    else:

        for username in DATA["admins"]:

            text += (
                f"• @{username}\n"
            )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
    )


# =========================================================
# MY USERS
# =========================================================

@dp.callback_query(
    F.data == "my_users"
)
async def my_users(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    await callback.answer()

    username = get_username(
        callback.from_user
    )

    users = DATA[
        "created_users"
    ].get(
        username,
        []
    )

    if not users:

        await callback.message.edit_text(
            "🗑 کانفیگ‌های من\n\n"
            "هنوز کانفیگی نساخته‌اید.",
            reply_markup=back_keyboard(),
        )

        return

    buttons = []

    for user in users:

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {user}",
                    callback_data=(
                        f"delete_user:{user}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 بازگشت",
                callback_data="back",
            )
        ]
    )

    await callback.message.edit_text(
        "🗑 کانفیگ‌های من\n\n"
        "کانفیگ موردنظر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )


# =========================================================
# DELETE USER
# =========================================================

@dp.callback_query(
    F.data.startswith(
        "delete_user:"
    )
)
async def delete_user(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    username = (
        callback.data
        .split(":", 1)[1]
    )

    creator = get_username(
        callback.from_user
    )

    owned = DATA[
        "created_users"
    ].get(
        creator,
        []
    )

    if username not in owned:

        await callback.answer(
            "⛔️ این کانفیگ متعلق به شما نیست.",
            show_alert=True,
        )

        return

    await callback.answer()

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

        await callback.message.edit_text(
            "✅ کانفیگ حذف شد.\n\n"
            f"`{username}`",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )

    except Exception as error:

        await callback.message.edit_text(
            "❌ حذف کانفیگ انجام نشد.\n\n"
            f"`{str(error)[:1500]}`",
            parse_mode="Markdown",
        )


# =========================================================
# OWNER USERS
# =========================================================

@dp.callback_query(
    F.data == "users"
)
async def users(
    callback: CallbackQuery
):

    if not is_owner(
        callback.from_user
    ):
        return

    await callback.answer()

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
            []
        )

        total = data.get(
            "total",
            len(users_list)
        )

        if not users_list:

            text = (
                "👥 کاربران\n\n"
                "هیچ کاربری وجود ندارد."
            )

        else:

            text = (
                "👥 کاربران\n\n"
                f"تعداد: {total}\n\n"
            )

            for user in users_list[:40]:

                name = user.get(
                    "username",
                    "-"
                )

                status = user.get(
                    "status",
                    "-"
                )

                text += (
                    f"• `{name}` — "
                    f"{status}\n"
                )

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )

    except Exception as error:

        await callback.message.edit_text(
            "❌ دریافت کاربران ناموفق بود.\n\n"
            f"`{str(error)[:1500]}`",
            parse_mode="Markdown",
        )


# =========================================================
# STATS
# =========================================================

@dp.callback_query(
    F.data == "stats"
)
async def stats(
    callback: CallbackQuery
):

    if not is_owner(
        callback.from_user
    ):
        return

    await callback.answer()

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
            []
        )

        total = data.get(
            "total",
            len(users_list)
        )

        active = sum(
            1
            for user in users_list
            if user.get(
                "status"
            ) == "active"
        )

        await callback.message.edit_text(
            "📊 آمار\n\n"
            f"👥 کل کاربران: {total}\n"
            f"🟢 فعال: {active}\n"
            f"🔴 غیرفعال: {total - active}\n"
            f"👤 ادمین‌ها: {len(DATA['admins'])}",
            reply_markup=back_keyboard(),
        )

    except Exception as error:

        await callback.message.edit_text(
            "❌ دریافت آمار ناموفق بود.\n\n"
            f"`{str(error)[:1500]}`",
            parse_mode="Markdown",
        )


# =========================================================
# BACK
# =========================================================

@dp.callback_query(
    F.data == "back"
)
async def back(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):
        return

    USER_STATE.pop(
        callback.from_user.id,
        None,
    )

    await callback.answer()

    if is_owner(
        callback.from_user
    ):

        await callback.message.edit_text(
            "👑 پنل مالک",
            reply_markup=owner_keyboard(),
        )

    else:

        await callback.message.edit_text(
            "👤 پنل ادمین",
            reply_markup=admin_keyboard(),
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

    try:

        await dp.start_polling(
            bot,
            allowed_updates=(
                dp.resolve_used_update_types()
            ),
        )

    finally:

        await bot.session.close()


if __name__ == "__main__":

    import asyncio

    asyncio.run(main())
