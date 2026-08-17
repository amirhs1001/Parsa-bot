import os
import asyncio
import logging
import secrets
import time

import httpx

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

MARZBAN_URL = "https://panell.goat-hs.online"

MARZBAN_USERNAME = "amirhszz"
MARZBAN_PASSWORD = "amirhszz"

OWNER_USERNAME = "parsa9599"


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# BOT
# =========================================================

dp = Dispatcher()


# =========================================================
# OWNER CHECK
# =========================================================

def is_owner(user) -> bool:
    if user is None:
        return False

    username = getattr(user, "username", None)

    if not username:
        return False

    return username.lower() == OWNER_USERNAME.lower()


# =========================================================
# MAIN KEYBOARD
# =========================================================

def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ ساخت کاربر",
                    callback_data="create_user",
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
        ]
    )


# =========================================================
# VOLUME KEYBOARD
# =========================================================

def volume_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="10 GB",
                    callback_data="volume:10",
                ),
                InlineKeyboardButton(
                    text="20 GB",
                    callback_data="volume:20",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="30 GB",
                    callback_data="volume:30",
                ),
                InlineKeyboardButton(
                    text="50 GB",
                    callback_data="volume:50",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="100 GB",
                    callback_data="volume:100",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="♾ نامحدود",
                    callback_data="volume:0",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="back",
                )
            ],
        ]
    )


# =========================================================
# DAYS KEYBOARD
# =========================================================

def days_keyboard(volume):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="7 روز",
                    callback_data=f"days:{volume}:7",
                ),
                InlineKeyboardButton(
                    text="15 روز",
                    callback_data=f"days:{volume}:15",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="30 روز",
                    callback_data=f"days:{volume}:30",
                ),
                InlineKeyboardButton(
                    text="60 روز",
                    callback_data=f"days:{volume}:60",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="90 روز",
                    callback_data=f"days:{volume}:90",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="create_user",
                )
            ],
        ]
    )


# =========================================================
# MARZBAN TOKEN
# =========================================================

async def get_marzban_token():

    url = f"{MARZBAN_URL}/api/admin/token"

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
                f"Marzban login failed: "
                f"{response.status_code} "
                f"{response.text[:500]}"
            )

        result = response.json()

        token = result.get("access_token")

        if not token:

            raise RuntimeError(
                "Marzban did not return access_token."
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

        response = await client.request(
            method,
            url,
            headers=headers,
            **kwargs,
        )

        return response


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    if not is_owner(message.from_user):

        await message.answer(
            "⛔️ دسترسی ندارید."
        )

        return

    await message.answer(
        "👑 پنل مدیریت\n\n"
        "سلام! به ربات مدیریت Marzban خوش آمدی.\n\n"
        "از منوی زیر انتخاب کن:",
        reply_markup=main_keyboard(),
    )


# =========================================================
# CREATE USER
# =========================================================

@dp.callback_query(F.data == "create_user")
async def create_user(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    await callback.message.edit_text(
        "📦 انتخاب حجم\n\n"
        "حجم موردنظر را انتخاب کن:",
        reply_markup=volume_keyboard(),
    )


# =========================================================
# SELECT VOLUME
# =========================================================

@dp.callback_query(F.data.startswith("volume:"))
async def select_volume(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    volume = int(
        callback.data.split(":")[1]
    )

    if volume == 0:
        volume_text = "♾ نامحدود"
    else:
        volume_text = f"{volume} GB"

    await callback.message.edit_text(
        f"📦 حجم انتخابی: {volume_text}\n\n"
        "⏳ مدت اعتبار را انتخاب کن:",
        reply_markup=days_keyboard(volume),
    )


# =========================================================
# SELECT DAYS + CREATE USER
# =========================================================

@dp.callback_query(F.data.startswith("days:"))
async def select_days(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    parts = callback.data.split(":")

    volume = int(parts[1])
    days = int(parts[2])

    await callback.message.edit_text(
        "⏳ در حال ساخت کاربر...\n\n"
        "لطفاً چند ثانیه صبر کن.",
    )

    try:

        # -------------------------------------------------
        # LOGIN
        # -------------------------------------------------

        token = await get_marzban_token()

        # -------------------------------------------------
        # GET INBOUNDS
        # -------------------------------------------------

        response = await marzban_request(
            "GET",
            "/api/inbounds",
            token,
        )

        if response.status_code != 200:

            raise RuntimeError(
                f"Could not get inbounds: "
                f"{response.status_code}"
            )

        inbounds_data = response.json()

        # -------------------------------------------------
        # BUILD INBOUND MAP
        # -------------------------------------------------

        inbound_map = {}

        if isinstance(inbounds_data, list):

            for inbound in inbounds_data:

                tag = inbound.get("tag")

                if tag:
                    inbound_map[tag] = []

        elif isinstance(inbounds_data, dict):

            inbounds = inbounds_data.get(
                "inbounds",
                [],
            )

            for inbound in inbounds:

                tag = inbound.get("tag")

                if tag:
                    inbound_map[tag] = []

        # -------------------------------------------------
        # USERNAME
        # -------------------------------------------------

        username = (
            "u_"
            + secrets.token_hex(4)
        )

        # -------------------------------------------------
        # EXPIRATION
        # -------------------------------------------------

        expire = int(
            time.time()
            + (days * 24 * 60 * 60)
        )

        # -------------------------------------------------
        # DATA LIMIT
        # -------------------------------------------------

        if volume == 0:

            data_limit = None

        else:

            data_limit = (
                volume
                * 1024
                * 1024
                * 1024
            )

        # -------------------------------------------------
        # USER PAYLOAD
        # -------------------------------------------------

        payload = {
            "username": username,
            "proxies": {},
            "inbounds": inbound_map,
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
        }

        # -------------------------------------------------
        # CREATE USER
        # -------------------------------------------------

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
                f"Create user failed: "
                f"{response.status_code}\n"
                f"{response.text[:1000]}"
            )

        user = response.json()

        # -------------------------------------------------
        # SUBSCRIPTION URL
        # -------------------------------------------------

        subscription_url = (
            user.get("subscription_url")
            or user.get("subscription")
            or user.get("sub_url")
            or ""
        )

        if not subscription_url:

            subscription_url = (
                f"{MARZBAN_URL}/sub/{username}"
            )

        # -------------------------------------------------
        # DISPLAY
        # -------------------------------------------------

        if volume == 0:

            volume_text = "♾ نامحدود"

        else:

            volume_text = f"{volume} GB"

        result_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 منوی اصلی",
                        callback_data="back",
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            "✅ کاربر ساخته شد!\n\n"
            f"👤 نام کاربری:\n"
            f"`{username}`\n\n"
            f"📦 حجم: {volume_text}\n"
            f"⏳ اعتبار: {days} روز\n\n"
            "🔗 لینک اشتراک:\n"
            f"`{subscription_url}`",
            parse_mode="Markdown",
            reply_markup=result_keyboard,
        )

    except Exception as error:

        logger.exception(
            "Create user error"
        )

        await callback.message.edit_text(
            "❌ ساخت کاربر انجام نشد.\n\n"
            "خطا:\n"
            f"`{str(error)[:1500]}`",
            parse_mode="Markdown",
        )


# =========================================================
# USERS
# =========================================================

@dp.callback_query(F.data == "users")
async def users(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    try:

        token = await get_marzban_token()

        response = await marzban_request(
            "GET",
            "/api/users",
            token,
        )

        if response.status_code != 200:

            raise RuntimeError(
                f"Get users failed: "
                f"{response.status_code}"
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

        if not users_list:

            text = (
                "👥 کاربران\n\n"
                "هیچ کاربری وجود ندارد."
            )

        else:

            text = (
                "👥 کاربران\n\n"
                f"📊 تعداد: {total}\n\n"
            )

            for user in users_list[:30]:

                username = user.get(
                    "username",
                    "-",
                )

                status = user.get(
                    "status",
                    "-",
                )

                text += (
                    f"• `{username}` — {status}\n"
                )

            if total > 30:

                text += (
                    "\n... و کاربران بیشتر"
                )

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 بازگشت",
                            callback_data="back",
                        )
                    ]
                ]
            ),
        )

    except Exception as error:

        logger.exception(
            "Users error"
        )

        await callback.message.edit_text(
            "❌ دریافت کاربران ناموفق بود.\n\n"
            f"`{str(error)[:1000]}`",
            parse_mode="Markdown",
        )


# =========================================================
# STATS
# =========================================================

@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    try:

        token = await get_marzban_token()

        response = await marzban_request(
            "GET",
            "/api/users",
            token,
        )

        if response.status_code != 200:

            raise RuntimeError(
                f"Get stats failed: "
                f"{response.status_code}"
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
            if user.get("status") == "active"
        )

        inactive = total - active

        await callback.message.edit_text(
            "📊 آمار پنل\n\n"
            f"👥 کل کاربران: {total}\n"
            f"🟢 فعال: {active}\n"
            f"🔴 غیرفعال: {inactive}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 بازگشت",
                            callback_data="back",
                        )
                    ]
                ]
            ),
        )

    except Exception as error:

        logger.exception(
            "Stats error"
        )

        await callback.message.edit_text(
            "❌ دریافت آمار ناموفق بود.\n\n"
            f"`{str(error)[:1000]}`",
            parse_mode="Markdown",
        )


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    await callback.message.edit_text(
        "👑 پنل مدیریت\n\n"
        "یکی از گزینه‌ها را انتخاب کن:",
        reply_markup=main_keyboard(),
    )


# =========================================================
# MAIN
# =========================================================

async def main():

    if not BOT_TOKEN:

        logger.error(
            "BOT_TOKEN is missing."
        )

        raise RuntimeError(
            "BOT_TOKEN در Railway Variables "
            "تنظیم نشده است."
        )

    logger.info(
        "Starting Telegram bot..."
    )

    bot = Bot(
        token=BOT_TOKEN,
    )

    try:

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )

    finally:

        await bot.session.close()


if __name__ == "__main__":

    asyncio.run(main())
