import asyncio
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import httpx
import qrcode

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    Document,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

MARZBAN_URL = os.getenv(
    "MARZBAN_URL",
    "https://panell.goat-hs.online",
).rstrip("/")

MARZBAN_USERNAME = os.getenv(
    "MARZBAN_USERNAME",
    "amirhszz",
).strip()

MARZBAN_PASSWORD = os.getenv(
    "MARZBAN_PASSWORD",
    "amirhszz",
).strip()

SUBSCRIPTION_PREFIX = os.getenv(
    "SUBSCRIPTION_PREFIX",
    "https://panell.goat-hs.online/sub",
).rstrip("/")

OWNER_USERNAME = os.getenv(
    "OWNER_USERNAME",
    "amirhszz",
).replace("@", "").lower()

DATA_FILE = Path(
    os.getenv("DATA_FILE", "bot_data.json")
)

BACKUP_DIR = Path(
    os.getenv("BACKUP_DIR", "backups")
)

BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


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

DEFAULT_DATA = {
    "admins": [],
    "created_users": {},
}


def load_data():
    if not DATA_FILE.exists():
        return DEFAULT_DATA.copy()

    try:
        with open(
            DATA_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return DEFAULT_DATA.copy()

        data.setdefault("admins", [])
        data.setdefault("created_users", {})

        return data

    except Exception:
        logger.exception("Could not load data")
        return DEFAULT_DATA.copy()


DATA = load_data()


def save_data():
    temp = DATA_FILE.with_suffix(".tmp")

    with open(
        temp,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            DATA,
            f,
            ensure_ascii=False,
            indent=2,
        )

    temp.replace(DATA_FILE)


# =========================================================
# BOT
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN در Environment Variables تنظیم نشده است."
    )

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# USER HELPERS
# =========================================================

def normalize_username(username: Optional[str]) -> str:
    if not username:
        return ""

    return username.replace("@", "").strip().lower()


def get_username(user) -> str:
    return normalize_username(
        getattr(user, "username", None)
    )


def is_owner(user) -> bool:
    return (
        get_username(user)
        == OWNER_USERNAME
    )


def is_admin(user) -> bool:
    username = get_username(user)

    return (
        is_owner(user)
        or username in [
            normalize_username(x)
            for x in DATA.get("admins", [])
        ]
    )


def owner_keyboard():
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="➕ ساخت کانفیگ",
            callback_data="create_config",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="👥 مدیریت ادمین‌ها",
            callback_data="manage_admins",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📋 کانفیگ‌ها",
            callback_data="my_configs",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="💾 بک‌آپ",
            callback_data="backup_menu",
        )
    )

    return builder.as_markup()


def admin_keyboard():
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="➕ ساخت کانفیگ",
            callback_data="create_config",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📋 کانفیگ‌های من",
            callback_data="my_configs",
        )
    )

    return builder.as_markup()


# =========================================================
# MARZBAN API
# =========================================================

async def get_marzban_token() -> str:
    url = (
        f"{MARZBAN_URL}/api/admin/token"
    )

    data = {
        "grant_type": "password",
        "username": MARZBAN_USERNAME,
        "password": MARZBAN_PASSWORD,
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
            "گرفتن توکن Marzban ناموفق بود.\n"
            f"{response.status_code}\n"
            f"{response.text[:2000]}"
        )

    result = response.json()

    token = result.get(
        "access_token"
    )

    if not token:
        raise RuntimeError(
            "access_token از Marzban دریافت نشد."
        )

    return token


async def marzban_request(
    method: str,
    path: str,
    token: str,
    **kwargs,
):
    url = (
        f"{MARZBAN_URL}"
        f"/{path.lstrip('/')}"
    )

    headers = kwargs.pop(
        "headers",
        {},
    )

    headers["Authorization"] = (
        f"Bearer {token}"
    )

    async with httpx.AsyncClient(
        timeout=60,
        follow_redirects=True,
    ) as client:

        return await client.request(
            method,
            url,
            headers=headers,
            **kwargs,
        )


# =========================================================
# SUBSCRIPTION
# =========================================================

def build_subscription_url(
    result: dict,
) -> str:

    original = (
        result.get("subscription_url")
        or ""
    ).strip()

    if not original:
        raise RuntimeError(
            "Marzban لینک Subscription را "
            "برنگرداند."
        )

    # اگر خود API فقط token/path داده باشد
    if not original.startswith(
        ("http://", "https://")
    ):

        token = original.strip(
            "/"
        )

        if token.startswith("sub/"):
            token = token[4:]

        return (
            f"{SUBSCRIPTION_PREFIX}"
            f"/{token}"
        )

    # تلاش برای استخراج /sub/TOKEN
    match = re.search(
        r"/sub/([^/?#]+)",
        original,
    )

    if match:
        token = match.group(1)

        return (
            f"{SUBSCRIPTION_PREFIX}"
            f"/{token}"
        )

    # اگر API خودش لینک /sub/token داده
    # ولی regex نتوانست پیدا کند
    return original


def make_qr_code(
    text: str,
) -> bytes:

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )

    qr.add_data(text)
    qr.make(fit=True)

    image = qr.make_image()

    output = BytesIO()

    image.save(
        output,
        format="PNG",
    )

    return output.getvalue()


# =========================================================
# USER CREATION
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

        token = await get_marzban_token()

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
        # PROTOCOLS
        # =================================================

        proxies = {
            "vless": {
                "id": str(
                    uuid.uuid4()
                )
            },

            "trojan": {
                "password": secrets.token_urlsafe(18)
            },

            "shadowsocks": {
                "password": secrets.token_urlsafe(18),
                "method": "chacha20-ietf-poly1305",
            },
        }

        # =================================================
        # IMPORTANT
        #
        # Empty inbounds = ALL INBOUNDS
        # =================================================

        payload = {
            "username": username,
            "status": "active",
            "expire": expire,
            "data_limit": data_limit,
            "data_limit_reset_strategy": "no_reset",
            "proxies": proxies,
            "inbounds": {},
        }

        logger.info(
            "Creating user: %s",
            username,
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

        subscription_url = (
            build_subscription_url(
                result
            )
        )

        qr_bytes = make_qr_code(
            subscription_url
        )

        creator = get_username(
            message.from_user
        )

        DATA.setdefault(
            "created_users",
            {},
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
        # USER MESSAGE
        # =================================================

        caption = (
            "✅ کانفیگ ساخته شد\n\n"
            f"👤 کاربر: {username}\n"
            f"📦 حجم: {volume} GB\n"
            f"⏳ اعتبار: {days} روز\n\n"
            "🔗 لینک اشتراک:\n"
            f"{subscription_url}"
        )

        qr_file = BufferedInputFile(
            qr_bytes,
            filename=f"{username}.png",
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

            report = (
                "🔔 کانفیگ جدید\n"
                f"👤 @{creator}\n"
                f"📦 {volume}GB\n"
                f"⏳ {days} روز"
            )

            try:
                await bot.send_message(
                    owner_chat_id,
                    report,
                )
            except Exception:
                logger.exception(
                    "Owner report failed"
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
            f"خطا:\n{str(error)[:3000]}",
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    message.from_user
                )
                else admin_keyboard()
            ),
        )


# =========================================================
# DELETE USER
# =========================================================

async def delete_marzban_user(
    username: str,
):

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
            f"Delete failed: "
            f"{response.status_code}\n"
            f"{response.text[:2000]}"
        )


# =========================================================
# START
# =========================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
):

    username = get_username(
        message.from_user
    )

    if is_owner(message.from_user):

        DATA["owner_chat_id"] = (
            message.chat.id
        )

        save_data()

        await message.answer(
            "👑 پنل مالک\n\n"
            "یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=owner_keyboard(),
        )

        return

    if is_admin(message.from_user):

        await message.answer(
            "👤 پنل ادمین\n\n"
            "یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=admin_keyboard(),
        )

        return

    await message.answer(
        "❌ شما اجازه استفاده از ربات را ندارید."
    )


# =========================================================
# MAIN MENU
# =========================================================

@dp.callback_query(
    F.data == "main_menu"
)
async def main_menu(
    callback: CallbackQuery,
):

    await callback.answer()

    if is_owner(
        callback.from_user
    ):

        await callback.message.edit_text(
            "👑 پنل مالک",
            reply_markup=owner_keyboard(),
        )

    elif is_admin(
        callback.from_user
    ):

        await callback.message.edit_text(
            "👤 پنل ادمین",
            reply_markup=admin_keyboard(),
        )


# =========================================================
# CREATE CONFIG
# =========================================================

@dp.callback_query(
    F.data == "create_config"
)
async def create_config_start(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_admin(
        callback.from_user
    ):
        return

    builder = InlineKeyboardBuilder()

    for value in (
        5,
        10,
        20,
    ):

        builder.button(
            text=f"{value} GB",
            callback_data=f"volume:{value}",
        )

    builder.button(
        text="✏️ وارد کردن حجم",
        callback_data="volume:manual",
    )

    builder.adjust(3, 1)

    await callback.message.edit_text(
        "📦 حجم درخواستی را انتخاب کنید:",
        reply_markup=builder.as_markup(),
    )


# =========================================================
# VOLUME
# =========================================================

@dp.callback_query(
    F.data.startswith("volume:")
)
async def volume_selected(
    callback: CallbackQuery,
):

    await callback.answer()

    value = callback.data.split(
        ":",
        1,
    )[1]

    if value == "manual":

        DATA.setdefault(
            "states",
            {},
        )

        DATA["states"][
            str(callback.from_user.id)
        ] = {
            "step": "manual_volume"
        }

        save_data()

        await callback.message.edit_text(
            "📦 حجم درخواستی را وارد کنید:"
        )

        return

    volume = int(value)

    await show_days(
        callback.message,
        volume,
    )


async def show_days(
    message: Message,
    volume: int,
):

    DATA.setdefault(
        "states",
        {},
    )

    # برای callback لازم نیست state را
    # در پیام ذخیره کنیم؛ در هر حالتی
    # حجم فعلی را نگه می‌داریم.
    user_id = (
        message.chat.id
    )

    DATA["states"][
        str(user_id)
    ] = {
        "step": "select_days",
        "volume": volume,
    }

    save_data()

    builder = InlineKeyboardBuilder()

    for value in (
        5,
        10,
        15,
        30,
    ):

        builder.button(
            text=f"{value} روز",
            callback_data=f"days:{value}",
        )

    builder.button(
        text="✏️ وارد کردن روز",
        callback_data="days:manual",
    )

    builder.adjust(2, 2, 1)

    await message.edit_text(
        "⏳ مدت اعتبار را انتخاب کنید:",
        reply_markup=builder.as_markup(),
    )


# =========================================================
# MANUAL VOLUME
# =========================================================

@dp.message(
    F.text,
)
async def text_handler(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    user_id = str(
        message.from_user.id
    )

    state = DATA.get(
        "states",
        {},
    ).get(
        user_id
    )

    if not state:
        return

    text = (
        message.text
        or ""
    ).strip()

    # =====================================================
    # MANUAL VOLUME
    # =====================================================

    if state.get("step") == "manual_volume":

        try:
            volume = int(text)

            if volume <= 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ حجم وارد شده صحیح نیست."
            )

            return

        await show_days(
            message,
            volume,
        )

        return

    # =====================================================
    # MANUAL DAYS
    # =====================================================

    if state.get("step") == "manual_days":

        try:
            days = int(text)

            if days <= 0:
                raise ValueError

        except ValueError:

            await message.answer(
                "❌ تعداد روز وارد شده صحیح نیست."
            )

            return

        volume = int(
            state["volume"]
        )

        DATA["states"].pop(
            user_id,
            None,
        )

        save_data()

        await create_user(
            message,
            volume,
            days,
        )


# =========================================================
# DAYS
# =========================================================

@dp.callback_query(
    F.data.startswith("days:")
)
async def days_selected(
    callback: CallbackQuery,
):

    await callback.answer()

    user_id = str(
        callback.from_user.id
    )

    state = DATA.get(
        "states",
        {},
    ).get(
        user_id
    )

    if not state:
        await callback.message.answer(
            "❌ نشست ساخت کانفیگ منقضی شده است."
        )
        return

    volume = int(
        state["volume"]
    )

    value = callback.data.split(
        ":",
        1,
    )[1]

    if value == "manual":

        DATA["states"][
            user_id
        ] = {
            "step": "manual_days",
            "volume": volume,
        }

        save_data()

        await callback.message.edit_text(
            "⏳ مدت اعتبار درخواستی را وارد کنید:"
        )

        return

    days = int(value)

    DATA["states"].pop(
        user_id,
        None,
    )

    save_data()

    await create_user(
        callback.message,
        volume,
        days,
    )


# =========================================================
# MY CONFIGS
# =========================================================

@dp.callback_query(
    F.data == "my_configs"
)
async def my_configs(
    callback: CallbackQuery,
):

    await callback.answer()

    username = get_username(
        callback.from_user
    )

    users = []

    if is_owner(
        callback.from_user
    ):

        for owner, items in DATA.get(
            "created_users",
            {},
        ).items():

            for user in items:

                users.append(
                    (
                        owner,
                        user,
                    )
                )

    else:

        for user in DATA.get(
            "created_users",
            {},
        ).get(
            username,
            [],
        ):

            users.append(
                (
                    username,
                    user,
                )
            )

    if not users:

        await callback.message.edit_text(
            "📭 کانفیگی پیدا نشد.",
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    callback.from_user
                )
                else admin_keyboard()
            ),
        )

        return

    builder = InlineKeyboardBuilder()

    for owner, user in users:

        if is_owner(
            callback.from_user
        ):

            text = (
                f"👤 {user} "
                f"• @{owner}"
            )

        else:

            text = f"👤 {user}"

        builder.button(
            text=text,
            callback_data=f"config:{user}",
        )

    builder.adjust(1)

    builder.row(
        InlineKeyboardButton(
            text="🔙 بازگشت",
            callback_data="main_menu",
        )
    )

    await callback.message.edit_text(
        "📋 کانفیگ‌ها:",
        reply_markup=builder.as_markup(),
    )


# =========================================================
# CONFIG DETAILS
# =========================================================

@dp.callback_query(
    F.data.startswith("config:")
)
async def config_details(
    callback: CallbackQuery,
):

    await callback.answer()

    username = callback.data.split(
        ":",
        1,
    )[1]

    owner_of_user = None

    for owner, users in DATA.get(
        "created_users",
        {},
    ).items():

        if username in users:
            owner_of_user = owner
            break

    if not owner_of_user:
        await callback.message.answer(
            "❌ کانفیگ پیدا نشد."
        )
        return

    if (
        not is_owner(
            callback.from_user
        )
        and owner_of_user
        != get_username(
            callback.from_user
        )
    ):

        await callback.answer(
            "❌ دسترسی ندارید.",
            show_alert=True,
        )

        return

    builder = InlineKeyboardBuilder()

    builder.button(
        text="🗑 حذف کانفیگ",
        callback_data=f"delete:{username}",
    )

    builder.button(
        text="🔙 بازگشت",
        callback_data="my_configs",
    )

    builder.adjust(1)

    await callback.message.edit_text(
        f"👤 کاربر:\n{username}\n\n"
        "مدیریت کانفیگ:",
        reply_markup=builder.as_markup(),
    )


# =========================================================
# DELETE CONFIRM
# =========================================================

@dp.callback_query(
    F.data.startswith("delete:")
)
async def delete_confirm(
    callback: CallbackQuery,
):

    await callback.answer()

    username = callback.data.split(
        ":",
        1,
    )[1]

    owner_of_user = None

    for owner, users in DATA.get(
        "created_users",
        {},
    ).items():

        if username in users:

            owner_of_user = owner
            break

    if not owner_of_user:
        await callback.message.answer(
            "❌ کانفیگ پیدا نشد."
        )
        return

    if (
        not is_owner(
            callback.from_user
        )
        and owner_of_user
        != get_username(
            callback.from_user
        )
    ):

        await callback.answer(
            "❌ اجازه حذف این کانفیگ را ندارید.",
            show_alert=True,
        )

        return

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ بله، حذف شود",
            callback_data=f"delete_yes:{username}",
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="❌ لغو",
            callback_data=f"config:{username}",
        )
    )

    await callback.message.edit_text(
        f"⚠️ حذف کانفیگ:\n\n"
        f"{username}\n\n"
        "مطمئن هستید؟",
        reply_markup=builder.as_markup(),
    )


# =========================================================
# DELETE
# =========================================================

@dp.callback_query(
    F.data.startswith("delete_yes:")
)
async def delete_user(
    callback: CallbackQuery,
):

    await callback.answer()

    username = callback.data.split(
        ":",
        1,
    )[1]

    owner_of_user = None

    for owner, users in DATA.get(
        "created_users",
        {},
    ).items():

        if username in users:

            owner_of_user = owner
            break

    if not owner_of_user:
        await callback.message.answer(
            "❌ کانفیگ پیدا نشد."
        )
        return

    if (
        not is_owner(
            callback.from_user
        )
        and owner_of_user
        != get_username(
            callback.from_user
        )
    ):

        await callback.answer(
            "❌ اجازه حذف این کانفیگ را ندارید.",
            show_alert=True,
        )

        return

    try:

        await delete_marzban_user(
            username
        )

        DATA[
            "created_users"
        ][owner_of_user].remove(
            username
        )

        if not DATA[
            "created_users"
        ][owner_of_user]:

            del DATA[
                "created_users"
            ][owner_of_user]

        save_data()

        await callback.message.edit_text(
            "✅ کانفیگ حذف شد.",
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    callback.from_user
                )
                else admin_keyboard()
            ),
        )

    except Exception as e:

        await callback.message.edit_text(
            "❌ حذف کانفیگ انجام نشد.\n\n"
            f"{str(e)[:2000]}"
        )


# =========================================================
# ADMIN MANAGEMENT
# =========================================================

@dp.callback_query(
    F.data == "manage_admins"
)
async def manage_admins(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    builder = InlineKeyboardBuilder()

    builder.button(
        text="➕ اضافه کردن ادمین",
        callback_data="admin_add",
    )

    builder.button(
        text="🗑 حذف ادمین",
        callback_data="admin_remove",
    )

    builder.button(
        text="📋 لیست ادمین‌ها",
        callback_data="admin_list",
    )

    builder.button(
        text="🔙 بازگشت",
        callback_data="main_menu",
    )

    builder.adjust(1)

    await callback.message.edit_text(
        "👥 مدیریت ادمین‌ها:",
        reply_markup=builder.as_markup(),
    )


# =========================================================
# ADD ADMIN
# =========================================================

@dp.callback_query(
    F.data == "admin_add"
)
async def admin_add(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    DATA.setdefault(
        "states",
        {},
    )

    DATA["states"][
        str(callback.from_user.id)
    ] = {
        "step": "add_admin"
    }

    save_data()

    await callback.message.edit_text(
        "👤 یوزرنیم ادمین را وارد کنید:"
    )


# =========================================================
# REMOVE ADMIN
# =========================================================

@dp.callback_query(
    F.data == "admin_remove"
)
async def admin_remove(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    admins = DATA.get(
        "admins",
        [],
    )

    if not admins:

        await callback.message.edit_text(
            "📭 ادمینی وجود ندارد.",
            reply_markup=owner_keyboard(),
        )

        return

    builder = InlineKeyboardBuilder()

    for admin in admins:

        builder.button(
            text=f"🗑 @{admin}",
            callback_data=f"remove_admin:{admin}",
        )

    builder.button(
        text="🔙 بازگشت",
        callback_data="manage_admins",
    )

    builder.adjust(1)

    await callback.message.edit_text(
        "ادمین مورد نظر را انتخاب کنید:",
        reply_markup=builder.as_markup(),
    )


@dp.callback_query(
    F.data.startswith("remove_admin:")
)
async def remove_admin(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    admin = normalize_username(
        callback.data.split(
            ":",
            1,
        )[1]
    )

    if admin in [
        normalize_username(x)
        for x in DATA.get(
            "admins",
            [],
        )
    ]:

        DATA["admins"] = [
            x
            for x in DATA["admins"]
            if normalize_username(x)
            != admin
        ]

        save_data()

    await callback.message.edit_text(
        f"✅ @{admin} حذف شد.",
        reply_markup=owner_keyboard(),
    )


# =========================================================
# ADMIN LIST
# =========================================================

@dp.callback_query(
    F.data == "admin_list"
)
async def admin_list(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    admins = DATA.get(
        "admins",
        [],
    )

    if not admins:

        text = (
            "📭 هیچ ادمینی وجود ندارد."
        )

    else:

        text = (
            "👥 ادمین‌ها:\n\n"
            + "\n".join(
                f"• @{x}"
                for x in admins
            )
        )

    builder = InlineKeyboardBuilder()

    builder.button(
        text="🔙 بازگشت",
        callback_data="manage_admins",
    )

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
    )


# =========================================================
# BACKUP MENU
# =========================================================

@dp.callback_query(
    F.data == "backup_menu"
)
async def backup_menu(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    builder = InlineKeyboardBuilder()

    builder.button(
        text="📤 دریافت بک‌آپ",
        callback_data="backup_download",
    )

    builder.button(
        text="📥 آپلود بک‌آپ",
        callback_data="backup_upload",
    )

    builder.button(
        text="🔙 بازگشت",
        callback_data="main_menu",
    )

    builder.adjust(1)

    await callback.message.edit_text(
        "💾 مدیریت بک‌آپ:",
        reply_markup=builder.as_markup(),
    )


# =========================================================
# DOWNLOAD BACKUP
# =========================================================

@dp.callback_query(
    F.data == "backup_download"
)
async def backup_download(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    filename = (
        "backup_"
        + datetime.now().strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        + ".json"
    )

    path = (
        BACKUP_DIR
        / filename
    )

    backup = {
        "created_at": datetime.now().isoformat(),
        "admins": DATA.get(
            "admins",
            [],
        ),
        "created_users": DATA.get(
            "created_users",
            {},
        ),
    }

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            backup,
            f,
            ensure_ascii=False,
            indent=2,
        )

    document = BufferedInputFile(
        path.read_bytes(),
        filename=filename,
    )

    await callback.message.answer_document(
        document=document,
        caption="💾 بک‌آپ ربات",
    )


# =========================================================
# UPLOAD BACKUP
# =========================================================

@dp.callback_query(
    F.data == "backup_upload"
)
async def backup_upload(
    callback: CallbackQuery,
):

    await callback.answer()

    if not is_owner(
        callback.from_user
    ):
        return

    DATA.setdefault(
        "states",
        {},
    )

    DATA["states"][
        str(callback.from_user.id)
    ] = {
        "step": "upload_backup"
    }

    save_data()

    await callback.message.edit_text(
        "📥 فایل JSON بک‌آپ را ارسال کنید."
    )


# =========================================================
# DOCUMENT HANDLER
# =========================================================

@dp.message(
    F.document
)
async def document_handler(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    user_id = str(
        message.from_user.id
    )

    state = DATA.get(
        "states",
        {},
    ).get(
        user_id
    )

    if not state:
        return

    if state.get(
        "step"
    ) != "upload_backup":
        return

    document: Document = (
        message.document
    )

    if not document.file_name.lower().endswith(
        ".json"
    ):

        await message.answer(
            "❌ فقط فایل JSON قابل قبول است."
        )

        return

    file = await bot.get_file(
        document.file_id
    )

    buffer = BytesIO()

    await bot.download_file(
        file.file_path,
        buffer,
    )

    buffer.seek(0)

    try:

        backup = json.loads(
            buffer.read().decode(
                "utf-8"
            )
        )

        if not isinstance(
            backup,
            dict,
        ):
            raise ValueError

        admins = backup.get(
            "admins",
            [],
        )

        created_users = backup.get(
            "created_users",
            {},
        )

        if not isinstance(
            admins,
            list,
        ):
            raise ValueError

        if not isinstance(
            created_users,
            dict,
        ):
            raise ValueError

        DATA["admins"] = admins
        DATA[
            "created_users"
        ] = created_users

        DATA["states"].pop(
            user_id,
            None,
        )

        save_data()

        await message.answer(
            "✅ بک‌آپ با موفقیت بازیابی شد.",
            reply_markup=owner_keyboard(),
        )

    except Exception:

        await message.answer(
            "❌ فایل بک‌آپ معتبر نیست."
        )


# =========================================================
# ADD ADMIN TEXT
# =========================================================

async def handle_admin_text(
    message: Message,
    state: dict,
):

    admin = normalize_username(
        message.text
    )

    if not admin:

        await message.answer(
            "❌ یوزرنیم معتبر نیست."
        )

        return

    if admin == OWNER_USERNAME:

        await message.answer(
            "❌ مالک نمی‌تواند به عنوان ادمین اضافه شود."
        )

        return

    if admin not in [
        normalize_username(x)
        for x in DATA.get(
            "admins",
            [],
        )
    ]:

        DATA["admins"].append(
            admin
        )

    DATA["states"].pop(
        str(message.from_user.id),
        None,
    )

    save_data()

    await message.answer(
        f"✅ @{admin} به ادمین‌ها اضافه شد.",
        reply_markup=owner_keyboard(),
    )


# =========================================================
# PATCH TEXT HANDLER FOR ADMIN STATE
# =========================================================

_original_text_handler = text_handler


# =========================================================
# NIGHTLY BACKUP
# =========================================================

async def send_nightly_backup():

    while True:

        now = datetime.now()

        next_midnight = (
            now.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
        )

        if next_midnight <= now:

            from datetime import timedelta

            next_midnight += timedelta(
                days=1
            )

        seconds = (
            next_midnight - now
        ).total_seconds()

        await asyncio.sleep(
            seconds
        )

        try:

            filename = (
                "auto_backup_"
                + datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )
                + ".json"
            )

            path = (
                BACKUP_DIR
                / filename
            )

            backup = {
                "created_at": datetime.now().isoformat(),
                "admins": DATA.get(
                    "admins",
                    [],
                ),
                "created_users": DATA.get(
                    "created_users",
                    {},
                ),
            }

            with open(
                path,
                "w",
                encoding="utf-8",
            ) as f:

                json.dump(
                    backup,
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            owner_chat_id = DATA.get(
                "owner_chat_id"
            )

            if owner_chat_id:

                document = BufferedInputFile(
                    path.read_bytes(),
                    filename=filename,
                )

                await bot.send_document(
                    owner_chat_id,
                    document=document,
                    caption="🌙 بک‌آپ خودکار نیمه‌شب",
                )

        except Exception:

            logger.exception(
                "Nightly backup failed"
            )

        await asyncio.sleep(
            5
        )


# =========================================================
# FIX STATE HANDLER
# =========================================================

@dp.message(F.text)
async def state_router(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    user_id = str(
        message.from_user.id
    )

    state = DATA.get(
        "states",
        {},
    ).get(
        user_id
    )

    if not state:
        return

    step = state.get(
        "step"
    )

    if step == "add_admin":

        await handle_admin_text(
            message,
            state,
        )

        return

    # اگر handler ساخت کانفیگ قبلی
    # این پیام را قبلاً پردازش کرده باشد،
    # اینجا کاری نمی‌کنیم.
    if step in (
        "manual_volume",
        "manual_days",
    ):

        text = (
            message.text
            or ""
        ).strip()

        if step == "manual_volume":

            try:

                volume = int(text)

                if volume <= 0:
                    raise ValueError

            except ValueError:

                await message.answer(
                    "❌ حجم وارد شده صحیح نیست."
                )

                return

            await show_days(
                message,
                volume,
            )

            return

        if step == "manual_days":

            try:

                days = int(text)

                if days <= 0:
                    raise ValueError

            except ValueError:

                await message.answer(
                    "❌ تعداد روز وارد شده صحیح نیست."
                )

                return

            volume = int(
                state["volume"]
            )

            DATA["states"].pop(
                user_id,
                None,
            )

            save_data()

            await create_user(
                message,
                volume,
                days,
            )


# =========================================================
# STARTUP
# =========================================================

async def main():

    logger.info(
        "Bot starting..."
    )

    # تست اتصال به Marzban
    try:

        await get_marzban_token()

        logger.info(
            "Marzban API connection OK"
        )

    except Exception as e:

        logger.error(
            "Marzban API test failed: %s",
            e,
        )

    asyncio.create_task(
        send_nightly_backup()
    )

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        pass
