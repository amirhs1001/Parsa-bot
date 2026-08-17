import os
import json
import time
import uuid
import secrets
import logging
import asyncio
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

MARZBAN_URL = "https://panell.goat-hs.online"

MARZBAN_USERNAME = "amirhszz"
MARZBAN_PASSWORD = "amirhszz"

# فعلاً مالک خودت هستی
OWNER_USERNAME = "amirhszz"

# فایل اطلاعات ادمین‌های ربات
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
# BOT
# =========================================================

dp = Dispatcher()


# =========================================================
# LOCAL DATA
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
# ACCESS
# =========================================================

def username_of(user):

    if not user:
        return ""

    return (
        getattr(user, "username", None)
        or ""
    ).lower()


def is_owner(user):

    return (
        username_of(user)
        == OWNER_USERNAME.lower()
    )


def is_admin(user):

    username = username_of(user)

    if not username:
        return False

    if is_owner(user):
        return True

    return username in DATA["admins"]


def can_create(user):

    return is_owner(user) or is_admin(user)


# =========================================================
# MAIN KEYBOARD
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
                f"{response.text[:500]}"
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
        "Authorization": (
            f"Bearer {token}"
        ),
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
# GET INBOUNDS
# =========================================================

async def get_inbounds(token):

    response = await marzban_request(
        "GET",
        "/api/inbounds",
        token,
    )

    if response.status_code != 200:

        raise RuntimeError(
            "دریافت Inboundها ناموفق بود:\n"
            f"{response.status_code}\n"
            f"{response.text[:500]}"
        )

    data = response.json()

    if isinstance(data, list):

        return data

    if isinstance(data, dict):

        return data.get(
            "inbounds",
            []
        )

    return []


# =========================================================
# BUILD PROXIES DYNAMICALLY
# =========================================================

def build_proxies_and_inbounds(
    inbounds
):

    proxies = {}
    inbound_map = {}

    for inbound in inbounds:

        protocol = (
            inbound.get("protocol")
            or ""
        ).lower()

        tag = inbound.get("tag")

        if not protocol or not tag:
            continue

        # ---------------------------------------------
        # VLESS
        # ---------------------------------------------

        if protocol == "vless":

            if "vless" not in proxies:

                proxies["vless"] = {
                    "id": str(
                        uuid.uuid4()
                    )
                }

            inbound_map.setdefault(
                "vless",
                []
            ).append(tag)

        # ---------------------------------------------
        # VMESS
        # ---------------------------------------------

        elif protocol == "vmess":

            if "vmess" not in proxies:

                proxies["vmess"] = {
                    "id": str(
                        uuid.uuid4()
                    )
                }

            inbound_map.setdefault(
                "vmess",
                []
            ).append(tag)

        # ---------------------------------------------
        # TROJAN
        # ---------------------------------------------

        elif protocol == "trojan":

            if "trojan" not in proxies:

                proxies["trojan"] = {
                    "password": secrets.token_urlsafe(
                        18
                    )
                }

            inbound_map.setdefault(
                "trojan",
                []
            ).append(tag)

        # ---------------------------------------------
        # SHADOWSOCKS
        # ---------------------------------------------

        elif protocol in (
            "shadowsocks",
            "shadowsocks2022",
        ):

            if protocol not in proxies:

                method = (
                    "chacha20-ietf-poly1305"
                )

                try:

                    settings = inbound.get(
                        "settings",
                        {}
                    )

                    if isinstance(
                        settings,
                        str
                    ):

                        settings = json.loads(
                            settings
                        )

                    method = (
                        settings
                        .get("method")
                        or method
                    )

                except Exception:
                    pass

                proxies[protocol] = {
                    "password": secrets.token_urlsafe(
                        18
                    ),
                    "method": method,
                }

            inbound_map.setdefault(
                protocol,
                []
            ).append(tag)

    return proxies, inbound_map


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):

    if is_owner(message.from_user):

        await message.answer(
            "👑 پنل مالک\n\n"
            "دسترسی کامل ربات برای شما فعال است.",
            reply_markup=owner_keyboard(),
        )

        return

    if is_admin(message.from_user):

        await message.answer(
            "👤 پنل ادمین\n\n"
            "شما می‌توانید کانفیگ بسازید "
            "و کانفیگ‌های خودتان را حذف کنید.",
            reply_markup=admin_keyboard(),
        )

        return

    await message.answer(
        "⛔️ شما اجازه استفاده از این ربات را ندارید."
    )


# =========================================================
# CREATE
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

    await callback.message.edit_text(
        "📦 ساخت کانفیگ\n\n"
        "حجم را به صورت عدد وارد کن.\n\n"
        "مثال:\n"
        "`100`\n\n"
        "یعنی 100 گیگابایت.",
        parse_mode="Markdown",
        reply_markup=back_keyboard(),
    )

    USER_STATE[
        callback.from_user.id
    ] = {
        "step": "volume"
    }


# =========================================================
# USER STATE
# =========================================================

USER_STATE = {}


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
    # VOLUME
    # =====================================================

    if state["step"] == "volume":

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

        state["volume"] = volume
        state["step"] = "days"

        await message.answer(
            "⏳ حالا مدت اعتبار را به روز وارد کن.\n\n"
            "مثال:\n"
            "`30`\n\n"
            "یعنی 30 روز.",
            parse_mode="Markdown",
        )

        return

    # =====================================================
    # DAYS
    # =====================================================

    if state["step"] == "days":

        try:

            days = int(text)

            if days <= 0:

                raise ValueError

        except ValueError:

            await message.answer(
                "❌ تعداد روز باید یک عدد "
                "بزرگ‌تر از صفر باشد.\n\n"
                "مثال:\n"
                "`30`",
                parse_mode="Markdown",
            )

            return

        volume = state["volume"]

        del USER_STATE[user_id]

        await create_mrzban_user(
            message,
            volume,
            days,
        )


# =========================================================
# CREATE MARZBAN USER
# =========================================================

async def create_mrzban_user(
    message: Message,
    volume: int,
    days: int,
):

    await message.answer(
        "⏳ در حال ساخت کانفیگ...\n\n"
        "در حال دریافت Inboundهای فعلی Marzban..."
    )

    try:

        token = await get_marzban_token()

        # ---------------------------------------------
        # دریافت همه Inboundهای فعلی
        # ---------------------------------------------

        inbounds = await get_inbounds(
            token
        )

        if not inbounds:

            raise RuntimeError(
                "هیچ Inbound فعالی در Marzban پیدا نشد."
            )

        # ---------------------------------------------
        # ساخت Proxyهای لازم
        # ---------------------------------------------

        proxies, inbound_map = (
            build_proxies_and_inbounds(
                inbounds
            )
        )

        if not proxies:

            raise RuntimeError(
                "هیچ پروتکل قابل پشتیبانی "
                "در Inboundهای Marzban پیدا نشد."
            )

        # ---------------------------------------------
        # Username
        # ---------------------------------------------

        username = (
            "u_"
            + secrets.token_hex(4)
        )

        # ---------------------------------------------
        # Expire
        # ---------------------------------------------

        expire = int(
            time.time()
            + days * 24 * 60 * 60
        )

        # ---------------------------------------------
        # Data Limit
        # ---------------------------------------------

        if volume == 0:

            data_limit = None

        else:

            data_limit = (
                volume
                * 1024
                * 1024
                * 1024
            )

        # ---------------------------------------------
        # Payload
        # ---------------------------------------------

        payload = {
            "username": username,
            "proxies": proxies,
            "inbounds": inbound_map,
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "status": "active",
        }

        # ---------------------------------------------
        # CREATE
        # ---------------------------------------------

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
                f"{response.text[:1500]}"
            )

        user = response.json()

        # ---------------------------------------------
        # Subscription
        # ---------------------------------------------

        subscription_url = (
            user.get(
                "subscription_url"
            )
            or user.get(
                "subscription"
            )
            or ""
        )

        if not subscription_url:

            subscription_url = (
                f"{MARZBAN_URL}"
                f"/sub/{username}"
            )

        # ---------------------------------------------
        # Save ownership
        # ---------------------------------------------

        creator = (
            username_of(
                message.from_user
            )
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

        # ---------------------------------------------
        # Result
        # ---------------------------------------------

        protocols = ", ".join(
            proxies.keys()
        )

        await message.answer(
            "✅ کانفیگ با موفقیت ساخته شد!\n\n"
            f"👤 Username:\n"
            f"`{username}`\n\n"
            f"📦 حجم: "
            f"{'نامحدود' if volume == 0 else str(volume) + ' GB'}\n"
            f"⏳ اعتبار: {days} روز\n\n"
            f"🔌 پروتکل‌ها:\n"
            f"`{protocols}`\n\n"
            "🌐 همه Inboundهای فعلی به این کاربر "
            "متصل شدند.\n\n"
            "🔗 Subscription:\n"
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
# ADMIN MANAGEMENT
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
            "⛔️ فقط مالک دسترسی دارد.",
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
        "👤 مدیریت ادمین‌ها\n\n"
        "مالک می‌تواند ادمین‌ها را اضافه یا حذف کند.",
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

        await callback.answer(
            "⛔️ فقط مالک.",
            show_alert=True,
        )

        return

    await callback.answer()

    USER_STATE[
        callback.from_user.id
    ] = {
        "step": "add_admin"
    }

    await callback.message.edit_text(
        "➕ افزودن ادمین\n\n"
        "Username تلگرام ادمین را وارد کن.\n\n"
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

        await callback.answer(
            "⛔️ فقط مالک.",
            show_alert=True,
        )

        return

    await callback.answer()

    if not DATA["admins"]:

        await callback.message.edit_text(
            "👤 هیچ ادمینی وجود ندارد.",
            reply_markup=back_keyboard(),
        )

        return

    buttons = []

    for username in DATA[
        "admins"
    ]:

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
        "🗑 انتخاب ادمین برای حذف:",
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

        await callback.answer(
            "⛔️ فقط مالک.",
            show_alert=True,
        )

        return

    username = (
        callback.data
        .split(":", 1)[1]
        .lower()
    )

    DATA[
        "admins"
    ].pop(
        username,
        None
    )

    save_data()

    await callback.answer(
        "ادمین حذف شد."
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

        await callback.answer(
            "⛔️ فقط مالک.",
            show_alert=True,
        )

        return

    await callback.answer()

    text = (
        "👤 لیست دسترسی‌ها\n\n"
        f"👑 مالک:\n"
        f"@{OWNER_USERNAME}\n\n"
    )

    if DATA["admins"]:

        text += "👤 ادمین‌ها:\n\n"

        for username in DATA[
            "admins"
        ]:

            text += (
                f"• @{username}\n"
            )

    else:

        text += (
            "👤 ادمینی اضافه نشده است."
        )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
    )


# =========================================================
# ADMIN ADD INPUT
# =========================================================

async def process_add_admin(
    message: Message
):

    username = (
        message.text
        or ""
    ).strip().lstrip("@").lower()

    if not username:

        await message.answer(
            "❌ Username معتبر نیست."
        )

        return

    if username == OWNER_USERNAME.lower():

        await message.answer(
            "❌ مالک را نمی‌توان به عنوان ادمین اضافه کرد."
        )

        return

    DATA[
        "admins"
    ][username] = {
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
        message.from_user.id,
        None
    )

    await message.answer(
        "✅ ادمین اضافه شد.\n\n"
        f"👤 @{username}\n\n"
        "دسترسی ادمین:\n"
        "• ساخت کانفیگ\n"
        "• حذف کانفیگ‌های خودش\n"
        "• مشاهده کانفیگ‌های خودش",
        reply_markup=owner_keyboard(),
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

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    username = username_of(
        callback.from_user
    )

    users = DATA[
        "created_users"
    ].get(
        username,
        []
    )

    await callback.answer()

    if not users:

        await callback.message.edit_text(
            "🗑 کانفیگ‌های من\n\n"
            "شما هنوز کانفیگی نساخته‌اید.",
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
        "برای حذف، روی کانفیگ موردنظر بزن:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )


# =========================================================
# DELETE OWN USER
# =========================================================

@dp.callback_query(
    F.data.startswith(
        "delete_user:"
    )
)
async def delete_own_user(
    callback: CallbackQuery
):

    if not is_admin(
        callback.from_user
    ):

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    target = (
        callback.data
        .split(":", 1)[1]
    )

    owner_username = username_of(
        callback.from_user
    )

    owned = DATA[
        "created_users"
    ].get(
        owner_username,
        []
    )

    if target not in owned:

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
            f"/api/user/{target}",
            token,
        )

        if response.status_code not in (
            200,
            204,
        ):

            raise RuntimeError(
                f"{response.status_code}\n"
                f"{response.text[:500]}"
            )

        owned.remove(
            target
        )

        save_data()

        await callback.message.edit_text(
            "✅ کانفیگ حذف شد.\n\n"
            f"👤 `{target}`",
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )

    except Exception as error:

        await callback.message.edit_text(
            "❌ حذف کانفیگ ناموفق بود.\n\n"
            f"`{str(error)[:1000]}`",
            parse_mode="Markdown",
        )


# =========================================================
# USERS - OWNER
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

        await callback.answer(
            "⛔️ فقط مالک.",
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
                f"{response.status_code}"
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
                f"📊 تعداد: {total}\n\n"
            )

            for user in users_list[:30]:

                username = user.get(
                    "username",
                    "-"
                )

                status = user.get(
                    "status",
                    "-"
                )

                text += (
                    f"• `{username}` — "
                    f"{status}\n"
                )

            if total > 30:

                text += (
                    "\n... کاربران بیشتر"
                )

        await callback.message.edit_text(
            text,
            parse_mode="Markdown",
            reply_markup=back_keyboard(),
        )

    except Exception as error:

        await callback.message.edit_text(
            "❌ دریافت کاربران ناموفق بود.\n\n"
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

        await callback.answer(
            "⛔️ فقط مالک.",
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
                f"{response.status_code}"
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
            "📊 آمار پنل\n\n"
            f"👥 کل کاربران: {total}\n"
            f"🟢 فعال: {active}\n"
            f"🔴 غیرفعال: {total - active}\n\n"
            f"👤 ادمین‌های ربات: "
            f"{len(DATA['admins'])}",
            reply_markup=back_keyboard(),
        )

    except Exception as error:

        await callback.message.edit_text(
            "❌ دریافت آمار ناموفق بود.\n\n"
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

        await callback.answer(
            "⛔️ دسترسی ندارید.",
            show_alert=True,
        )

        return

    await callback.answer()

    if is_owner(
        callback.from_user
    ):

        await callback.message.edit_text(
            "👑 پنل مالک\n\n"
            "دسترسی کامل فعال است.",
            reply_markup=owner_keyboard(),
        )

    else:

        await callback.message.edit_text(
            "👤 پنل ادمین\n\n"
            "می‌توانید کانفیگ بسازید "
            "و کانفیگ‌های خودتان را حذف کنید.",
            reply_markup=admin_keyboard(),
        )


# =========================================================
# SPECIAL TEXT ROUTER
# =========================================================

_original_text_handler = text_handler


@dp.message(F.text)
async def admin_and_state_router(
    message: Message
):

    if not is_admin(
        message.from_user
    ):

        return

    user_id = message.from_user.id

    state = USER_STATE.get(
        user_id
    )

    if state:

        if state.get(
            "step"
        ) == "add_admin":

            if not is_owner(
                message.from_user
            ):

                return

            await process_add_admin(
                message
            )

            return

        if state.get(
            "step"
        ) in (
            "volume",
            "days",
        ):

            await _original_text_handler(
                message
            )

            return


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
        "Starting bot..."
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

    asyncio.run(main())
