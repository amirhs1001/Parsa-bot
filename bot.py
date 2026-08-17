import os
import asyncio
import logging
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

BOT_TOKEN = os.getenv("8619194656:AAElQAwRjdodLopUTcPyFSZJaIbxI-9ALYg")

MARZBAN_URL = "https://panell.goat-hs.online"

MARZBAN_USERNAME = "amirhszz"
MARZBAN_PASSWORD = "amirhszz"

OWNER_USERNAME = "parsa9599"

# =========================================================
# BOT
# =========================================================

dp = Dispatcher()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


# =========================================================
# AUTH
# =========================================================

def is_owner(user) -> bool:
    if not user or not user.username:
        return False

    return user.username.lower() == OWNER_USERNAME.lower()


# =========================================================
# MARZBAN API
# =========================================================

async def get_marzban_token():
    """
    گرفتن Access Token از Marzban
    """

    url = f"{MARZBAN_URL}/api/admin/token"

    data = {
        "grant_type": "password",
        "username": MARZBAN_USERNAME,
        "password": MARZBAN_PASSWORD,
        "scope": "",
        "client_id": "",
        "client_secret": "",
    }

    async with httpx.AsyncClient(timeout=30) as client:

        response = await client.post(
            url,
            data=data
        )

        response.raise_for_status()

        result = response.json()

        return result["access_token"]


async def marzban_request(
    method: str,
    endpoint: str,
    token: str,
    **kwargs
):
    """
    درخواست عمومی به API مرزبان
    """

    url = f"{MARZBAN_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with httpx.AsyncClient(timeout=30) as client:

        response = await client.request(
            method,
            url,
            headers=headers,
            **kwargs
        )

        return response


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ ساخت کاربر",
                    callback_data="create_user"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 کاربران",
                    callback_data="users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 آمار",
                    callback_data="stats"
                )
            ],
        ]
    )


def volume_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="10 GB",
                    callback_data="volume:10"
                ),
                InlineKeyboardButton(
                    text="20 GB",
                    callback_data="volume:20"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="30 GB",
                    callback_data="volume:30"
                ),
                InlineKeyboardButton(
                    text="50 GB",
                    callback_data="volume:50"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="100 GB",
                    callback_data="volume:100"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="♾ نامحدود",
                    callback_data="volume:0"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="back"
                )
            ]
        ]
    )


def days_keyboard(volume):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="7 روز",
                    callback_data=f"days:{volume}:7"
                ),
                InlineKeyboardButton(
                    text="15 روز",
                    callback_data=f"days:{volume}:15"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="30 روز",
                    callback_data=f"days:{volume}:30"
                ),
                InlineKeyboardButton(
                    text="60 روز",
                    callback_data=f"days:{volume}:60"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="90 روز",
                    callback_data=f"days:{volume}:90"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت",
                    callback_data="create_user"
                )
            ]
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    if not is_owner(message.from_user):

        await message.answer(
            "⛔️ شما اجازه استفاده از این ربات را ندارید."
        )

        return

    await message.answer(
        "👑 پنل مدیریت\n\n"
        "به ربات مدیریت Marzban خوش آمدید.\n\n"
        "از منوی زیر استفاده کنید:",
        reply_markup=main_keyboard()
    )


# =========================================================
# CREATE USER
# =========================================================

@dp.callback_query(F.data == "create_user")
async def create_user(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید",
            show_alert=True
        )

        return

    await callback.answer()

    await callback.message.edit_text(
        "📦 انتخاب حجم\n\n"
        "حجم کاربر را انتخاب کنید:",
        reply_markup=volume_keyboard()
    )


# =========================================================
# VOLUME
# =========================================================

@dp.callback_query(F.data.startswith("volume:"))
async def select_volume(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید",
            show_alert=True
        )

        return

    await callback.answer()

    volume = int(
        callback.data.split(":")[1]
    )

    if volume == 0:

        text = "♾ حجم نامحدود"

    else:

        text = f"📦 حجم: {volume} GB"

    await callback.message.edit_text(
        f"{text}\n\n"
        "⏳ حالا مدت اعتبار را انتخاب کن:",
        reply_markup=days_keyboard(volume)
    )


# =========================================================
# DAYS
# =========================================================

@dp.callback_query(F.data.startswith("days:"))
async def select_days(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید",
            show_alert=True
        )

        return

    await callback.answer()

    parts = callback.data.split(":")

    volume = int(parts[1])
    days = int(parts[2])

    await callback.message.edit_text(
        "⏳ در حال ساخت کاربر...\n\n"
        "لطفاً چند ثانیه صبر کن."
    )

    try:

        token = await get_marzban_token()

        # -------------------------------------------------
        # گرفتن Inbounds
        # -------------------------------------------------

        response = await marzban_request(
            "GET",
            "/api/inbounds",
            token
        )

        if response.status_code != 200:

            await callback.message.edit_text(
                "❌ خطا در دریافت Inboundهای Marzban\n\n"
                f"HTTP {response.status_code}"
            )

            return

        inbounds_data = response.json()

        # -------------------------------------------------
        # ساخت username
        # -------------------------------------------------

        import secrets

        username = "user_" + secrets.token_hex(4)

        # -------------------------------------------------
        # expire timestamp
        # -------------------------------------------------

        import time

        expire = int(
            time.time() + (days * 24 * 60 * 60)
        )

        # -------------------------------------------------
        # data limit
        # -------------------------------------------------

        if volume == 0:

            data_limit = None

        else:

            data_limit = volume * 1024 * 1024 * 1024

        # -------------------------------------------------
        # Inbound mapping
        # -------------------------------------------------

        inbound_map = {}

        if isinstance(inbounds_data, list):

            for inbound in inbounds_data:

                tag = inbound.get("tag")

                if tag:

                    inbound_map[tag] = []

        elif isinstance(inbounds_data, dict):

            for inbound in inbounds_data.get(
                "inbounds",
                []
            ):

                tag = inbound.get("tag")

                if tag:

                    inbound_map[tag] = []

        # -------------------------------------------------
        # User payload
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
        # Create user
        # -------------------------------------------------

        response = await marzban_request(
            "POST",
            "/api/user",
            token,
            json=payload
        )

        if response.status_code not in (200, 201):

            await callback.message.edit_text(
                "❌ ساخت کاربر ناموفق بود.\n\n"
                f"HTTP: {response.status_code}\n\n"
                f"{response.text[:1000]}"
            )

            return

        user = response.json()

        # -------------------------------------------------
        # Subscription
        # -------------------------------------------------

        subscription_url = (
            user.get("subscription_url")
            or user.get("subscription")
            or ""
        )

        # بعضی نسخه‌های Marzban
        # لینک را با username برمی‌گردانند.

        if not subscription_url:

            subscription_url = (
                f"{MARZBAN_URL}/sub/{username}"
            )

        # -------------------------------------------------
        # Result
        # -------------------------------------------------

        if volume == 0:

            volume_text = "♾ نامحدود"

        else:

            volume_text = f"{volume} GB"

        await callback.message.edit_text(
            "✅ کاربر با موفقیت ساخته شد!\n\n"
            f"👤 Username:\n"
            f"`{username}`\n\n"
            f"📦 حجم: {volume_text}\n"
            f"⏳ مدت: {days} روز\n\n"
            f"🔗 لینک اشتراک:\n"
            f"`{subscription_url}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 منوی اصلی",
                            callback_data="back"
                        )
                    ]
                ]
            )
        )

    except Exception as e:

        logging.exception(
            "Create user error"
        )

        await callback.message.edit_text(
            "❌ خطایی هنگام اتصال به Marzban رخ داد.\n\n"
            f"`{str(e)[:1000]}`",
            parse_mode="Markdown"
        )


# =========================================================
# USERS
# =========================================================

@dp.callback_query(F.data == "users")
async def users(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید",
            show_alert=True
        )

        return

    await callback.answer()

    try:

        token = await get_marzban_token()

        response = await marzban_request(
            "GET",
            "/api/users",
            token
        )

        if response.status_code != 200:

            await callback.message.edit_text(
                "❌ دریافت کاربران ناموفق بود.\n\n"
                f"HTTP {response.status_code}"
            )

            return

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
                "هیچ کاربری پیدا نشد."
            )

        else:

            text = (
                f"👥 کاربران\n\n"
                f"📊 تعداد: {total}\n\n"
            )

            for user in users_list[:20]:

                username = user.get(
                    "username",
                    "-"
                )

                status = user.get(
                    "status",
                    "-"
                )

                text += (
                    f"• `{username}` — {status}\n"
                )

            if total > 20:

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
                            callback_data="back"
                        )
                    ]
                ]
            )
        )

    except Exception as e:

        logging.exception(
            "Users error"
        )

        await callback.message.edit_text(
            "❌ خطا در دریافت کاربران.\n\n"
            f"`{str(e)[:500]}`",
            parse_mode="Markdown"
        )


# =========================================================
# STATS
# =========================================================

@dp.callback_query(F.data == "stats")
async def stats(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید",
            show_alert=True
        )

        return

    await callback.answer()

    try:

        token = await get_marzban_token()

        response = await marzban_request(
            "GET",
            "/api/users",
            token
        )

        if response.status_code != 200:

            await callback.message.edit_text(
                "❌ دریافت آمار ناموفق بود."
            )

            return

        data = response.json()

        total = data.get(
            "total",
            len(data.get("users", []))
        )

        users_list = data.get(
            "users",
            []
        )

        active = 0

        for user in users_list:

            if user.get("status") == "active":

                active += 1

        await callback.message.edit_text(
            "📊 آمار Marzban\n\n"
            f"👥 کل کاربران: {total}\n"
            f"🟢 کاربران فعال: {active}\n"
            f"🔴 غیرفعال: {total - active}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔙 بازگشت",
                            callback_data="back"
                        )
                    ]
                ]
            )
        )

    except Exception as e:

        logging.exception(
            "Stats error"
        )

        await callback.message.edit_text(
            "❌ خطا در دریافت آمار."
        )


# =========================================================
# BACK
# =========================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    if not is_owner(callback.from_user):

        await callback.answer(
            "⛔️ دسترسی ندارید",
            show_alert=True
        )

        return

    await callback.answer()

    await callback.message.edit_text(
        "👑 پنل مدیریت\n\n"
        "یکی از گزینه‌های زیر را انتخاب کن:",
        reply_markup=main_keyboard()
    )


# =========================================================
# START BOT
# =========================================================

async def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN در Environment Variables تنظیم نشده است."
        )

    bot = Bot(
        token=BOT_TOKEN
    )

    try:

        await dp.start_polling(bot)

    finally:

        await bot.session.close()


if __name__ == "__main__":

    asyncio.run(main())
