import asyncio
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

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


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

MARZBAN_URL = os.getenv(
    "MARZBAN_URL",
    "https://parsa.goat-hs.online"
).rstrip("/")

MARZBAN_USERNAME = os.getenv(
    "MARZBAN_USERNAME",
    "amirhszz"
).strip()

MARZBAN_PASSWORD = os.getenv(
    "MARZBAN_PASSWORD",
    ""
).strip()


# =========================================================
# OWNERS
# =========================================================

OWNER_USERNAMES = [
    "amirhszz",
    "parsa9599",
]


SUB_URL = "https://parsa.goat-hs.online/sub"

DATA_FILE = Path("bot_data.json")
BACKUP_DIR = Path("backups")

BACKUP_DIR.mkdir(exist_ok=True)


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

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN در Environment Variables تنظیم نشده است."
    )

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# DATABASE
# =========================================================

DEFAULT_DATA = {
    "admins": [],
    "users": {},
    "states": {},
    "owner_chat_ids": {},
}


def load_data():

    if not DATA_FILE.exists():

        return {
            "admins": [],
            "users": {},
            "states": {},
            "owner_chat_ids": {},
        }

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            data = json.load(f)

        for key, value in DEFAULT_DATA.items():

            if key not in data:
                data[key] = value

        # سازگاری با نسخه قدیمی
        if (
            "owner_chat_id" in data
            and data.get("owner_chat_id")
        ):

            old_id = data["owner_chat_id"]

            data.setdefault(
                "owner_chat_ids",
                {},
            )

            data["owner_chat_ids"][
                "amirhszz"
            ] = old_id

            del data["owner_chat_id"]

        return data

    except Exception:

        logger.exception(
            "Database load failed"
        )

        return {
            "admins": [],
            "users": {},
            "states": {},
            "owner_chat_ids": {},
        }


DATA = load_data()


def save_data():

    tmp = Path("bot_data.tmp")

    with open(
        tmp,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            DATA,
            f,
            ensure_ascii=False,
            indent=2,
        )

    tmp.replace(DATA_FILE)


# =========================================================
# HELPERS
# =========================================================

def clean_username(username):

    if not username:
        return ""

    return (
        username
        .replace("@", "")
        .strip()
        .lower()
    )


def get_username(user):

    return clean_username(
        getattr(
            user,
            "username",
            None,
        )
    )


def is_owner(user):

    username = get_username(user)

    return username in [
        clean_username(x)
        for x in OWNER_USERNAMES
    ]


def is_admin(user):

    username = get_username(user)

    admins = [
        clean_username(x)
        for x in DATA.get(
            "admins",
            [],
        )
    ]

    return (
        is_owner(user)
        or username in admins
    )


def set_state(
    user_id,
    state,
):

    DATA["states"][
        str(user_id)
    ] = state

    save_data()


def get_state(user_id):

    return DATA.get(
        "states",
        {},
    ).get(
        str(user_id)
    )


def clear_state(user_id):

    DATA.get(
        "states",
        {},
    ).pop(
        str(user_id),
        None,
    )

    save_data()


# =========================================================
# KEYBOARDS
# =========================================================

def owner_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="➕ ساخت کانفیگ"
                ),
            ],
            [
                KeyboardButton(
                    text="📋 کانفیگ‌های من"
                ),
                KeyboardButton(
                    text="👥 مدیریت ادمین‌ها"
                ),
            ],
            [
                KeyboardButton(
                    text="💾 بک‌آپ"
                ),
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
                ),
            ],
            [
                KeyboardButton(
                    text="📋 کانفیگ‌های من"
                ),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def volume_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="5 GB"
                ),
                KeyboardButton(
                    text="10 GB"
                ),
                KeyboardButton(
                    text="20 GB"
                ),
            ],
            [
                KeyboardButton(
                    text="🔙 بازگشت"
                ),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def days_keyboard():

    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="5 روز"
                ),
                KeyboardButton(
                    text="10 روز"
                ),
            ],
            [
                KeyboardButton(
                    text="15 روز"
                ),
                KeyboardButton(
                    text="30 روز"
                ),
            ],
            [
                KeyboardButton(
                    text="🔙 بازگشت"
                ),
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
                    text="➕ اضافه کردن ادمین"
                ),
            ],
            [
                KeyboardButton(
                    text="🗑 حذف ادمین"
                ),
                KeyboardButton(
                    text="📋 لیست ادمین‌ها"
                ),
            ],
            [
                KeyboardButton(
                    text="🔙 بازگشت"
                ),
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
                    text="📤 دریافت بک‌آپ"
                ),
                KeyboardButton(
                    text="📥 آپلود بک‌آپ"
                ),
            ],
            [
                KeyboardButton(
                    text="🔙 بازگشت"
                ),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


# =========================================================
# MARZBAN API
# =========================================================

async def get_marzban_token():

    url = (
        f"{MARZBAN_URL}"
        "/api/admin/token"
    )

    payload = {
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
            data=payload,
        )

    if response.status_code != 200:

        raise RuntimeError(
            "Marzban Token Error\n"
            f"HTTP {response.status_code}\n"
            f"{response.text[:2000]}"
        )

    result = response.json()

    token = result.get(
        "access_token"
    )

    if not token:

        raise RuntimeError(
            "access_token دریافت نشد."
        )

    return token


async def marzban_request(
    method,
    endpoint,
    token,
    **kwargs,
):

    url = (
        f"{MARZBAN_URL}"
        f"/{endpoint.lstrip('/')}"
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
# CREATE USER
# =========================================================

async def create_marzban_user(
    volume,
    days,
):

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

    proxies = {
        "vless": {
            "id": str(
                uuid.uuid4()
            ),
        },

        "trojan": {
            "password": secrets.token_urlsafe(
                24
            ),
        },

        "shadowsocks": {
            "method":
                "chacha20-ietf-poly1305",
            "password":
                secrets.token_urlsafe(
                    24
                ),
        },
    }

    payload = {
        "username": username,
        "status": "active",
        "expire": expire,
        "data_limit": data_limit,
        "data_limit_reset_strategy": "no_reset",
        "proxies": proxies,

        # خالی یعنی همه Inbound ها
        "inbounds": {},
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
            f"{response.text[:3000]}"
        )

    return response.json(), username


# =========================================================
# SUBSCRIPTION
# =========================================================

def get_subscription_link(result):

    value = (
        result.get(
            "subscription_url"
        )
        or result.get(
            "sub_link"
        )
        or result.get(
            "subscription"
        )
        or ""
    )

    value = str(
        value
    ).strip()

    if not value:

        raise RuntimeError(
            "لینک Subscription توسط Marzban برگردانده نشد."
        )

    if (
        value.startswith(
            "http://"
        )
        or value.startswith(
            "https://"
        )
    ):

        if "/sub/" in value:

            token = (
                value
                .split(
                    "/sub/",
                    1,
                )[1]
                .split(
                    "?",
                    1,
                )[0]
                .strip("/")
            )

            return (
                f"{SUB_URL}/{token}"
            )

        return value

    value = value.strip("/")

    if value.startswith(
        "sub/"
    ):

        value = value[4:]

    return (
        f"{SUB_URL}/{value}"
    )


# =========================================================
# QR
# =========================================================

def create_qr(text):

    qr = qrcode.QRCode(
        version=None,
        error_correction=(
            qrcode.constants
            .ERROR_CORRECT_M
        ),
        box_size=10,
        border=4,
    )

    qr.add_data(text)

    qr.make(
        fit=True
    )

    image = qr.make_image()

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


# =========================================================
# START
# =========================================================

@dp.message(
    CommandStart()
)
async def start(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):

        await message.answer(
            "❌ شما اجازه استفاده از این ربات را ندارید."
        )

        return

    username = get_username(
        message.from_user
    )

    if is_owner(
        message.from_user
    ):

        DATA.setdefault(
            "owner_chat_ids",
            {},
        )

        DATA["owner_chat_ids"][
            username
        ] = message.chat.id

        save_data()

        await message.answer(
            "👑 پنل مالک\n\n"
            "یکی از گزینه‌های پایین را انتخاب کنید.",
            reply_markup=owner_keyboard(),
        )

    else:

        await message.answer(
            "👤 پنل ادمین\n\n"
            "یکی از گزینه‌های پایین را انتخاب کنید.",
            reply_markup=admin_keyboard(),
        )


# =========================================================
# BACK
# =========================================================

@dp.message(
    F.text == "🔙 بازگشت"
)
async def back(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    clear_state(
        message.from_user.id
    )

    if is_owner(
        message.from_user
    ):

        await message.answer(
            "👑 پنل مالک",
            reply_markup=owner_keyboard(),
        )

    else:

        await message.answer(
            "👤 پنل ادمین",
            reply_markup=admin_keyboard(),
        )


# =========================================================
# CREATE
# =========================================================

@dp.message(
    F.text == "➕ ساخت کانفیگ"
)
async def create_start(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    set_state(
        message.from_user.id,
        {
            "step": "volume"
        },
    )

    await message.answer(
        "📦 حجم درخواستی را انتخاب کنید یا عدد دلخواه را مستقیم وارد کنید:",
        reply_markup=volume_keyboard(),
    )


@dp.message(
    F.text.in_(
        [
            "5 GB",
            "10 GB",
            "20 GB",
        ]
    )
)
async def volume_select(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    state = get_state(
        message.from_user.id
    )

    if (
        not state
        or state.get("step")
        != "volume"
    ):
        return

    volume = int(
        message.text.split()[0]
    )

    set_state(
        message.from_user.id,
        {
            "step": "days",
            "volume": volume,
        },
    )

    await message.answer(
        "⏳ مدت اعتبار را انتخاب کنید یا عدد دلخواه را مستقیم وارد کنید:",
        reply_markup=days_keyboard(),
    )


@dp.message(
    F.text.in_(
        [
            "5 روز",
            "10 روز",
            "15 روز",
            "30 روز",
        ]
    )
)
async def days_select(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    state = get_state(
        message.from_user.id
    )

    if (
        not state
        or state.get("step")
        != "days"
    ):
        return

    days = int(
        message.text.split()[0]
    )

    volume = state.get(
        "volume"
    )

    clear_state(
        message.from_user.id
    )

    await build_config(
        message,
        volume,
        days,
    )


# =========================================================
# DIRECT NUMBER
# =========================================================

@dp.message(
    F.text.regexp(r"^\d+$")
)
async def numeric_input(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    state = get_state(
        message.from_user.id
    )

    if not state:
        return

    value = int(
        message.text
    )

    if value <= 0:

        await message.answer(
            "❌ عدد باید بیشتر از صفر باشد."
        )

        return

    if state.get(
        "step"
    ) == "volume":

        set_state(
            message.from_user.id,
            {
                "step": "days",
                "volume": value,
            },
        )

        await message.answer(
            "⏳ مدت اعتبار را انتخاب کنید یا عدد دلخواه را مستقیم وارد کنید:",
            reply_markup=days_keyboard(),
        )

        return

    if state.get(
        "step"
    ) == "days":

        volume = state.get(
            "volume"
        )

        clear_state(
            message.from_user.id
        )

        await build_config(
            message,
            volume,
            value,
        )


# =========================================================
# BUILD CONFIG
# =========================================================

async def build_config(
    message,
    volume,
    days,
):

    status_message = await message.answer(
        "⏳ در حال ساخت کانفیگ..."
    )

    try:

        result, username = (
            await create_marzban_user(
                volume,
                days,
            )
        )

        subscription = (
            get_subscription_link(
                result
            )
        )

        qr = create_qr(
            subscription
        )

        creator = get_username(
            message.from_user
        )

        DATA["users"].setdefault(
            creator,
            [],
        )

        DATA["users"][
            creator
        ].append(
            username
        )

        save_data()

        try:
            await status_message.delete()
        except Exception:
            pass

        caption = (
            "✅ کانفیگ ساخته شد\n\n"
            f"👤 کاربر: {username}\n"
            f"📦 حجم: {volume} GB\n"
            f"⏳ اعتبار: {days} روز\n\n"
            "🔗 لینک اشتراک:\n"
            f"{subscription}"
        )

        photo = BufferedInputFile(
            qr,
            filename=f"{username}.png",
        )

        await message.answer_photo(
            photo=photo,
            caption=caption,
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    message.from_user
                )
                else admin_keyboard()
            ),
        )

        # گزارش مختصر برای تمام مالک‌ها
        report = (
            "🔔 کانفیگ جدید\n"
            f"👤 @{creator}\n"
            f"📦 {volume}GB\n"
            f"⏳ {days} روز"
        )

        for owner_username, chat_id in (
            DATA.get(
                "owner_chat_ids",
                {},
            ).items()
        ):

            if (
                owner_username
                == creator
            ):
                continue

            try:

                await bot.send_message(
                    chat_id,
                    report,
                )

            except Exception:

                logger.exception(
                    "Owner report failed for %s",
                    owner_username,
                )

    except Exception as e:

        logger.exception(
            "Config creation failed"
        )

        try:
            await status_message.delete()
        except Exception:
            pass

        await message.answer(
            "❌ ساخت کانفیگ انجام نشد.\n\n"
            f"خطا:\n{str(e)[:3000]}",
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    message.from_user
                )
                else admin_keyboard()
            ),
        )


# =========================================================
# MY CONFIGS
# =========================================================

@dp.message(
    F.text == "📋 کانفیگ‌های من"
)
async def configs(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    username = get_username(
        message.from_user
    )

    if is_owner(
        message.from_user
    ):

        all_users = []

        for owner, users in DATA.get(
            "users",
            {},
        ).items():

            for user in users:

                all_users.append(
                    (
                        owner,
                        user,
                    )
                )

        if not all_users:

            await message.answer(
                "📭 هیچ کانفیگی ساخته نشده است.",
                reply_markup=owner_keyboard(),
            )

            return

        text = "📋 کانفیگ‌ها:\n\n"

        for owner, user in all_users:

            text += (
                f"👤 {user}\n"
                f"سازنده: @{owner}\n\n"
            )

    else:

        users = DATA.get(
            "users",
            {},
        ).get(
            username,
            [],
        )

        if not users:

            await message.answer(
                "📭 هنوز کانفیگی نساخته‌اید.",
                reply_markup=admin_keyboard(),
            )

            return

        text = (
            "📋 کانفیگ‌های شما:\n\n"
        )

        for user in users:

            text += (
                f"👤 {user}\n"
            )

        text += (
            "\nبرای حذف یک کانفیگ:\n"
            "حذف username"
        )

    await message.answer(
        text,
        reply_markup=(
            owner_keyboard()
            if is_owner(
                message.from_user
            )
            else admin_keyboard()
        ),
    )


# =========================================================
# ADMIN MANAGEMENT
# =========================================================

@dp.message(
    F.text == "👥 مدیریت ادمین‌ها"
)
async def admin_management(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    await message.answer(
        "👥 مدیریت ادمین‌ها:",
        reply_markup=admin_management_keyboard(),
    )


@dp.message(
    F.text == "➕ اضافه کردن ادمین"
)
async def add_admin_start(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    set_state(
        message.from_user.id,
        {
            "step": "add_admin"
        },
    )

    await message.answer(
        "👤 Username ادمین را ارسال کنید."
    )


@dp.message(
    F.text == "🗑 حذف ادمین"
)
async def remove_admin_start(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    admins = DATA.get(
        "admins",
        [],
    )

    if not admins:

        await message.answer(
            "📭 هیچ ادمینی وجود ندارد.",
            reply_markup=admin_management_keyboard(),
        )

        return

    text = (
        "👥 ادمین‌های فعلی:\n\n"
        + "\n".join(
            f"• @{x}"
            for x in admins
        )
        + "\n\n"
        "Username ادمینی که می‌خواهید حذف شود را ارسال کنید."
    )

    set_state(
        message.from_user.id,
        {
            "step": "remove_admin"
        },
    )

    await message.answer(
        text,
        reply_markup=admin_management_keyboard(),
    )


@dp.message(
    F.text == "📋 لیست ادمین‌ها"
)
async def admin_list(
    message: Message,
):

    if not is_owner(
        message.from_user
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
            "👥 لیست ادمین‌ها:\n\n"
            + "\n".join(
                f"• @{x}"
                for x in admins
            )
        )

    await message.answer(
        text,
        reply_markup=admin_management_keyboard(),
    )


# =========================================================
# DELETE CONFIG
# =========================================================

@dp.message(
    F.text.regexp(
        r"^حذف\s+.+$"
    )
)
async def delete_command(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    username = (
        message.text
        .split(
            None,
            1,
        )[1]
        .strip()
    )

    await delete_user_by_name(
        message,
        username,
    )


async def delete_user_by_name(
    message,
    username,
):

    username = username.strip()

    creator = get_username(
        message.from_user
    )

    owner_of_user = None

    for owner, users in DATA.get(
        "users",
        {},
    ).items():

        if username in users:

            owner_of_user = owner
            break

    if not owner_of_user:

        await message.answer(
            "❌ این کانفیگ پیدا نشد."
        )

        return

    if (
        not is_owner(
            message.from_user
        )
        and owner_of_user
        != creator
    ):

        await message.answer(
            "❌ شما فقط می‌توانید کانفیگ‌های خودتان را حذف کنید."
        )

        return

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
                f"{response.text[:2000]}"
            )

        DATA["users"][
            owner_of_user
        ].remove(
            username
        )

        if not DATA["users"][
            owner_of_user
        ]:

            del DATA["users"][
                owner_of_user
            ]

        save_data()

        await message.answer(
            "✅ کانفیگ حذف شد.",
            reply_markup=(
                owner_keyboard()
                if is_owner(
                    message.from_user
                )
                else admin_keyboard()
            ),
        )

    except Exception as e:

        await message.answer(
            "❌ حذف کانفیگ انجام نشد.\n\n"
            f"{str(e)[:2000]}"
        )


# =========================================================
# BACKUP
# =========================================================

@dp.message(
    F.text == "💾 بک‌آپ"
)
async def backup_menu(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    await message.answer(
        "💾 مدیریت بک‌آپ:",
        reply_markup=backup_keyboard(),
    )


def create_backup_file(
    prefix="backup",
):

    filename = (
        f"{prefix}_"
        f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        ".json"
    )

    path = (
        BACKUP_DIR
        / filename
    )

    backup = {
        "created_at":
            datetime.now().isoformat(),

        "admins":
            DATA.get(
                "admins",
                [],
            ),

        "users":
            DATA.get(
                "users",
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

    return path


@dp.message(
    F.text == "📤 دریافت بک‌آپ"
)
async def download_backup(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    path = create_backup_file()

    document = BufferedInputFile(
        path.read_bytes(),
        filename=path.name,
    )

    await message.answer_document(
        document=document,
        caption="💾 بک‌آپ ربات",
        reply_markup=backup_keyboard(),
    )


@dp.message(
    F.text == "📥 آپلود بک‌آپ"
)
async def upload_backup_start(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    set_state(
        message.from_user.id,
        {
            "step": "upload_backup"
        },
    )

    await message.answer(
        "📥 فایل JSON بک‌آپ را ارسال کنید.",
        reply_markup=backup_keyboard(),
    )


@dp.message(
    F.document
)
async def backup_document(
    message: Message,
):

    if not is_owner(
        message.from_user
    ):
        return

    state = get_state(
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
            "❌ فقط فایل JSON قابل قبول است."
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

        data = json.loads(
            buffer.read().decode(
                "utf-8"
            )
        )

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError

        admins = data.get(
            "admins",
            [],
        )

        users = data.get(
            "users",
            {},
        )

        if not isinstance(
            admins,
            list,
        ):

            raise ValueError

        if not isinstance(
            users,
            dict,
        ):

            raise ValueError

        DATA["admins"] = admins
        DATA["users"] = users

        clear_state(
            message.from_user.id
        )

        save_data()

        await message.answer(
            "✅ بک‌آپ با موفقیت بازیابی شد.",
            reply_markup=owner_keyboard(),
        )

    except Exception:

        logger.exception(
            "Backup restore failed"
        )

        await message.answer(
            "❌ فایل بک‌آپ معتبر نیست."
        )


# =========================================================
# ADMIN TEXT STATES
# =========================================================

@dp.message(F.text)
async def text_states(
    message: Message,
):

    if not is_admin(
        message.from_user
    ):
        return

    state = get_state(
        message.from_user.id
    )

    if not state:
        return

    step = state.get(
        "step"
    )

    text = (
        message.text or ""
    ).strip()

    if step == "add_admin":

        username = clean_username(
            text
        )

        if not username:

            await message.answer(
                "❌ Username معتبر نیست."
            )

            return

        if username in [
            clean_username(x)
            for x in OWNER_USERNAMES
        ]:

            await message.answer(
                "❌ این کاربر مالک است و نیازی به اضافه شدن به ادمین‌ها ندارد."
            )

            return

        admins = [
            clean_username(x)
            for x in DATA.get(
                "admins",
                [],
            )
        ]

        if username in admins:

            clear_state(
                message.from_user.id
            )

            await message.answer(
                "⚠️ این کاربر از قبل ادمین است.",
                reply_markup=admin_management_keyboard(),
            )

            return

        DATA["admins"].append(
            username
        )

        clear_state(
            message.from_user.id
        )

        save_data()

        await message.answer(
            f"✅ @{username} اضافه شد.",
            reply_markup=admin_management_keyboard(),
        )

        return

    if step == "remove_admin":

        username = clean_username(
            text
        )

        admins = DATA.get(
            "admins",
            [],
        )

        found = None

        for admin in admins:

            if (
                clean_username(admin)
                == username
            ):

                found = admin
                break

        if not found:

            await message.answer(
                "❌ این Username در لیست ادمین‌ها نیست."
            )

            return

        DATA["admins"].remove(
            found
        )

        clear_state(
            message.from_user.id
        )

        save_data()

        await message.answer(
            f"✅ @{username} حذف شد.",
            reply_markup=admin_management_keyboard(),
        )

        return


# =========================================================
# NIGHTLY BACKUP
# =========================================================

async def nightly_backup():

    while True:

        now = datetime.now()

        tomorrow = (
            now
            + timedelta(days=1)
        ).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        seconds = (
            tomorrow - now
        ).total_seconds()

        await asyncio.sleep(
            seconds
        )

        try:

            path = create_backup_file(
                prefix="auto_backup"
            )

            owner_chats = DATA.get(
                "owner_chat_ids",
                {},
            )

            for owner_username, chat_id in (
                owner_chats.items()
            ):

                try:

                    document = BufferedInputFile(
                        path.read_bytes(),
                        filename=path.name,
                    )

                    await bot.send_document(
                        chat_id,
                        document=document,
                        caption="🌙 بک‌آپ خودکار شبانه",
                    )

                except Exception:

                    logger.exception(
                        "Nightly backup failed for %s",
                        owner_username,
                    )

        except Exception:

            logger.exception(
                "Nightly backup creation failed"
            )

        await asyncio.sleep(5)


# =========================================================
# MAIN
# =========================================================

async def main():

    logger.info(
        "Bot starting..."
    )

    try:

        await get_marzban_token()

        logger.info(
            "Marzban API connection OK"
        )

    except Exception as e:

        logger.error(
            "Marzban connection failed: %s",
            e,
        )

    asyncio.create_task(
        nightly_backup()
    )

    await dp.start_polling(
        bot
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        pass
