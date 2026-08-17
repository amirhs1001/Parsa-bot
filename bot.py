import os
import json
import time
import uuid
import secrets
import logging
from pathlib import Path

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

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

MARZBAN_URL = "https://panell.goat-hs.online"

MARZBAN_USERNAME = "amirhszz"
MARZBAN_PASSWORD = "amirhszz"

# مالک فعلی ربات
OWNER_USERNAME = "amirhszz"

DATA_FILE = Path("bot_data.json")


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

        return data

    except Exception:
        return {
            "admins": {},
            "created_users": {},
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
                "ورود به Marzban ناموفق بود:\n"
                f"{response.status_code}\n"
                f"{response.text[:1000]}"
            )

        result = response.json()

        token = result.get(
            "access_token"
        )

        if not token:

            raise RuntimeError(
                "Marzban توکن ورود را برنگرداند."
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
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    if is_owner(message.from_user):

        await message.answer(
            "👑 پنل مالک\n\n"
            "سلام امیر 👋\n"
            "دسترسی کامل فعال است.",
            reply_markup=owner_keyboard(),
        )

        return

    if is_admin(message.from_user):

        await message.answer(
            "👤 پنل ادمین\n\n"
            "شما فقط می‌توانید کانفیگ بسازید "
            "و کانفیگ‌های خودتان را حذف کنید.",
            reply_markup=admin_keyboard(),
        )

        return

    await message.answer(
        "⛔️ شما اجازه استفاده از ربات را ندارید."
    )


# =========================================================
# CREATE MENU
# =========================================================

@dp.callback_query(F.data == "create")
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
        "پروتکل: `ALL`\n"
        "سرور: `ALL`\n\n"
        "📦 حجم را به GB وارد کن.\n\n"
        "مثال:\n"
        "`100`",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )


# =========================================================
# TEXT INPUT
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
            .lower()
        )

        if not username:

            await message.answer(
                "❌ Username نامعتبر است."
            )

            return

        if username == OWNER_USERNAME.lower():

            await message.answer(
                "❌ مالک را نمی‌توان ادمین کرد."
            )

            return

        DATA["admins"][username] = {
            "created_at": int(
                time.time()
            )
        }

        DATA["created_users"].setdefault(
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
            f"👤 @{username}\n\n"
            "دسترسی‌ها:\n"
            "• ساخت کانفیگ\n"
            "• حذف کانفیگ‌های خودش",
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
                "❌ حجم باید فقط عدد باشد.\n\n"
                "مثال:\n"
                "`100`",
                parse_mode="Markdown",
            )

            return

        USER_STATE[user_id] = {
            "step": "days",
            "volume": volume,
        }

        await message.answer(
            "⏳ حالا مدت اعتبار را به روز وارد کن.\n\n"
            "مثال:\n"
            "`30`",
            parse_mode="Markdown",
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
                "❌ تعداد روز باید بیشتر از صفر باشد.\n\n"
                "مثال:\n"
                "`30`",
                parse_mode="Markdown",
            )

            return

        volume = state["volume"]

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

    await message.answer(
        "⏳ در حال ساخت کانفیگ...\n\n"
        "لطفاً صبر کن."
    )

    try:

        token = await get_marzban_token()

        # =================================================
        # PROTOCOL = ALL
        #
        # Marzban برای User حداقل یک Proxy معتبر
        # می‌خواهد. بنابراین VLESS را به عنوان Proxy
        # پایه می‌فرستیم.
        #
        # Inboundها در کد هاردکد نشده‌اند.
        # =================================================

        proxy_id = str(
            uuid.uuid4()
        )

        proxies = {
            "vless": {
                "id": proxy_id
            }
        }

        # =================================================
        # USERNAME
        # =================================================

        username = (
            "u_"
            + secrets.token_hex(4)
        )

        # =================================================
        # EXPIRE
        # =================================================

        expire = int(
            time.time()
            + days * 86400
        )

        # =================================================
        # DATA LIMIT
        # =================================================

        if volume == 0:

            data_limit = None

        else:

            data_limit = (
                volume
                * 1024
                * 1024
                * 1024
            )

        # =================================================
        # PAYLOAD
        # =================================================

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
                "Marzban User creation failed:\n"
                f"{response.status_code}\n"
                f"{response.text[:2000]}"
            )

        result = response.json()

        # =================================================
        # SUBSCRIPTION
        # =================================================

        subscription_url = (
            result.get(
                "subscription_url"
            )
            or result.get(
                "subscription"
            )
            or ""
        )

        if not subscription_url:

            subscription_url = (
                f"{MARZBAN_URL}"
                f"/sub/{username}"
            )

        # =================================================
        # SAVE OWNER
        # =================================================

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

        # =================================================
        # RESULT
        # =================================================

        volume_text = (
            "♾ نامحدود"
            if volume == 0
            else f"{volume} GB"
        )

        await message.answer(
            "✅ کانفیگ ساخته شد!\n\n"
            f"👤 Username:\n"
            f"`{username}`\n\n"
            f"🔌 Protocol: `ALL`\n"
            f"🌐 Servers: `ALL`\n"
            f"📦 حجم: {volume_text}\n"
            f"⏳ اعتبار: {days} روز\n\n"
            "🔗 لینک Subscription:\n"
            f"`{subscription_url}`",
            parse_mode="Markdown",
        )

    except Exception as error:

        logger.exception(
            "Create user error"
        )

        await message.answer(
            "❌ ساخت کانفیگ انجام نشد.\n\n"
            "خطا:\n"
            f"`{str(error)[:2000]}`",
            parse_mode="Markdown",
        )


# =========================================================
# ADMINS MENU
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

        await callback.answer(
            "⛔️ فقط مالک.",
            show_alert=True,
        )

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
        "Username تلگرام را وارد کن.\n\n"
        "مثال:\n"
        "`username`",
        parse_mode="Markdown",
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
        "🗑 ادمینی که می‌خواهی حذف شود انتخاب کن:",
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
            "هنوز کانفیگی نساخته‌ای.",
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
        "برای حذف روی کانفیگ بزن:",
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

        token = await get_marzban_token()

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
                f"{response.status_code}\n"
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
            "❌ حذف انجام نشد.\n\n"
            f"`{str(error)[:1000]}`",
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

        token = await get_marzban_token()

        response = await marzban_request(
            "GET",
            "/api/users",
            token,
        )

        if response.status_code != 200:

            raise RuntimeError(
                response.text[:500]
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

            for user in users_list[:30]:

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
            "❌ خطا در دریافت کاربران.\n\n"
            f"`{str(error)[:1000]}`",
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

        token = await get_marzban_token()

        response = await marzban_request(
            "GET",
            "/api/users",
            token,
        )

        if response.status_code != 200:

            raise RuntimeError(
                response.text[:500]
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
            "❌ خطا در دریافت آمار.\n\n"
            f"`{str(error)[:1000]}`",
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

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN در Railway Variables "
            "تنظیم نشده است."
        )

    logger.info(
        "Bot starting..."
    )

    logger.info(
        f"Owner: @{OWNER_USERNAME}"
    )

    bot = Bot(
        token=BOT_TOKEN
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
