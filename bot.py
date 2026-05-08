import os
import json
import random
import logging
from datetime import datetime, timedelta

import aiohttp
import discord
import pytz
from discord import app_commands
from discord.ext import tasks


# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("birthday-bot")


# ── Config ───────────────────────────────────────────────────────────────────
TOKEN = os.environ["DISCORD_TOKEN"]
DATA_FILE = os.environ.get("DATA_FILE", "/data/birthdays.json")
TIMEZONE = os.environ.get("TIMEZONE", "America/Lima")
CHECK_HOUR = int(os.environ.get("CHECK_HOUR", "8"))
KLIPY_KEY = os.environ.get("KLIPY_API_KEY", "")
MENTION_EVERYONE = os.environ.get("MENTION_EVERYONE", "true").lower() == "true"


# ── Colores ──────────────────────────────────────────────────────────────────
COLOR_BIRTHDAY = discord.Color(0xFF6EB4)  # rosado
COLOR_REMINDER = discord.Color(0xFFC107)  # amarillo
COLOR_LIST = discord.Color(0x4CAF50)  # verde
COLOR_UPCOMING = discord.Color(0x2196F3)  # azul
COLOR_ERROR = discord.Color(0xF44336)  # rojo


# ── Mensajes aleatorios (Español neutro) ─────────────────────────────────────
BIRTHDAY_MESSAGES = [
    "🎉 ¡Hoy celebramos el cumpleaños de {usuario}! ¡Que tengas un día increíble! 🎂",
    "🥳 ¡Feliz cumpleaños {usuario}! Que este nuevo año esté lleno de salud y éxitos ✨",
    "🎂 ¡Atención! Hoy es el cumpleaños de {usuario}. ¡A felicitar! 🎊",
    "🎁 ¡{usuario} cumple años hoy! Que la pases genial y recibas muchos regalos 🎉",
    "🎈 ¡Un año más para {usuario}! Que tengas un cumpleaños excelente 🥳",
    "🍰 ¡Feliz cumpleaños {usuario}! Que nunca falte la torta y las buenas noticias 🎂",
    "🎊 ¡Hoy es un día especial! {usuario} está de cumpleaños. ¡Muchas felicidades! ✨",
    "🥂 ¡Brindemos por {usuario}! Que tengas un gran día y un año aún mejor 🎉",
    "🎶 ¡Feliz cumpleaños {usuario}! Que tu día esté lleno de alegría y buenos momentos 🎂",
    "🌟 Hoy el servidor está de fiesta: {usuario} cumple años. ¡Felicidades! 🎉",
    "🎂 ¡Feliz cumpleaños {usuario}! Que todos tus objetivos se cumplan este año 💪✨",
    "🎁 ¡Hoy celebramos a {usuario}! Que tu día sea tan genial como tú 🥳",
]

REMINDER_MESSAGES = [
    "🔔 Recordatorio: mañana es el cumpleaños de {usuario}. ¡No se olviden de felicitar! 🎂",
    "📅 Atención: mañana {usuario} cumple años. ¡Prepárense para celebrarlo! 🎉",
    "⏰ Mañana es el cumpleaños de {usuario}. ¡Dejen listo el saludo! 🥳",
    "🎈 Aviso importante: mañana {usuario} está de cumpleaños. ¡A celebrar! 🎊",
    "🎁 Mañana es el cumpleaños de {usuario}. ¡Que no se les pase! 🎂",
]


# ── Discord Client ───────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True


class BirthdayBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        log.info("Slash commands sincronizados globalmente")


client = BirthdayBot()


# ── Persistencia ─────────────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_data(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_guild_data(data: dict, guild_id: int) -> dict:
    gid = str(guild_id)

    if "guilds" not in data:
        data["guilds"] = {}

    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "channel_id": None,
            "birthdays": {},
            "last_announcement": {},
        }

    if "last_announcement" not in data["guilds"][gid]:
        data["guilds"][gid]["last_announcement"] = {}

    return data["guilds"][gid]


# ── Anti-spam ────────────────────────────────────────────────────────────────
def already_announced(gdata: dict, user_id: str, kind: str, date_key: str) -> bool:
    key = f"{kind}:{user_id}"
    return gdata.get("last_announcement", {}).get(key) == date_key


def mark_announced(gdata: dict, user_id: str, kind: str, date_key: str):
    key = f"{kind}:{user_id}"
    gdata["last_announcement"][key] = date_key


# ── Canal válido ─────────────────────────────────────────────────────────────
def find_valid_channel(guild: discord.Guild, channel_id: str | None):
    if channel_id:
        ch = guild.get_channel(int(channel_id))
        if ch and isinstance(ch, discord.TextChannel):
            perms = ch.permissions_for(guild.me)
            if perms.send_messages and perms.embed_links:
                return ch

    for c in guild.text_channels:
        perms = c.permissions_for(guild.me)
        if perms.send_messages and perms.embed_links:
            return c

    return None


# ── KLIPY GIF ────────────────────────────────────────────────────────────────
async def fetch_birthday_gif() -> str | None:
    if not KLIPY_KEY:
        return None

    try:
        url = f"https://api.klipy.com/api/v1/{KLIPY_KEY}/gifs/search"
        params = {"q": "happy birthday", "limit": 20}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status != 200:
                    log.warning("KLIPY HTTP %s", resp.status)
                    return None

                result = await resp.json()
                items = result.get("data", {}).get("data", [])
                if not items:
                    return None

                item = random.choice(items)
                return item.get("file", {}).get("hd", {}).get("gif", {}).get("url")

    except Exception as e:
        log.warning("KLIPY error: %s", e)
        return None


# ── Mensajes ────────────────────────────────────────────────────────────────
async def send_birthday_message(channel: discord.TextChannel, member: discord.Member):
    gif_url = await fetch_birthday_gif()
    mensaje = random.choice(BIRTHDAY_MESSAGES).format(usuario=member.mention)

    embed = discord.Embed(
        title="🎂 ¡Feliz cumpleaños!",
        description=mensaje,
        color=COLOR_BIRTHDAY,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="🎉 Birthday Bot")
    embed.set_thumbnail(url=member.display_avatar.url)

    if gif_url:
        embed.set_image(url=gif_url)

    mention = "@everyone" if MENTION_EVERYONE else None
    await channel.send(content=mention, embed=embed)


async def send_reminder_message(channel: discord.TextChannel, member: discord.Member):
    mensaje = random.choice(REMINDER_MESSAGES).format(usuario=member.mention)

    embed = discord.Embed(
        title="🔔 Recordatorio",
        description=mensaje,
        color=COLOR_REMINDER,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="📅 Birthday Bot")
    embed.set_thumbnail(url=member.display_avatar.url)

    await channel.send(embed=embed)


# ── Tarea diaria ─────────────────────────────────────────────────────────────
@tasks.loop(minutes=30)
async def check_birthdays():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    if now.hour != CHECK_HOUR:
        return

    data = load_data()

    today_key = now.strftime("%Y-%m-%d")
    tomorrow_dt = now + timedelta(days=1)
    tomorrow_key = tomorrow_dt.strftime("%Y-%m-%d")

    today_md = (now.month, now.day)
    tmrw_md = (tomorrow_dt.month, tomorrow_dt.day)

    for guild in client.guilds:
        gdata = get_guild_data(data, guild.id)
        channel = find_valid_channel(guild, gdata.get("channel_id"))

        if not channel:
            log.warning("No se encontró canal válido en %s", guild.name)
            continue

        birthdays = gdata.get("birthdays", {})

        for user_id, info in birthdays.items():
            member = guild.get_member(int(user_id))
            if not member:
                continue

            bday = datetime.strptime(info["date"], "%d/%m/%Y")
            bday_md = (bday.month, bday.day)

            # HOY
            if bday_md == today_md:
                if already_announced(gdata, user_id, "birthday", today_key):
                    continue

                await send_birthday_message(channel, member)
                mark_announced(gdata, user_id, "birthday", today_key)
                save_data(data)
                log.info("Cumple enviado para %s en %s", member, guild.name)

            # MAÑANA
            elif bday_md == tmrw_md:
                if already_announced(gdata, user_id, "reminder", tomorrow_key):
                    continue

                await send_reminder_message(channel, member)
                mark_announced(gdata, user_id, "reminder", tomorrow_key)
                save_data(data)
                log.info("Recordatorio enviado para %s en %s", member, guild.name)


@check_birthdays.before_loop
async def before_check():
    await client.wait_until_ready()


# ── Slash Commands ──────────────────────────────────────────────────────────
@client.tree.command(
    name="setcanal",
    description="[Admin] Define el canal donde se anuncian los cumpleaños",
)
@app_commands.describe(canal="Canal de texto donde el bot mandará los avisos")
@app_commands.default_permissions(administrator=True)
async def slash_set_channel(interaction: discord.Interaction, canal: discord.TextChannel):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    gdata["channel_id"] = str(canal.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ Canal configurado: {canal.mention}",
        ephemeral=True,
    )


@client.tree.command(name="cumple", description="Guarda o actualiza tu fecha de cumpleaños")
@app_commands.describe(fecha="Formato: DD/MM o DD/MM/AAAA → Ej: 15/03")
async def slash_set_birthday(interaction: discord.Interaction, fecha: str):
    parsed = None
    for fmt in ("%d/%m/%Y", "%d/%m"):
        try:
            parsed = datetime.strptime(fecha.strip(), fmt)
            break
        except ValueError:
            continue

    if not parsed:
        await interaction.response.send_message(
            "❌ Formato inválido. Usa `DD/MM` o `DD/MM/AAAA`. Ej: `/cumple 15/03`",
            ephemeral=True,
        )
        return

    year = parsed.year if parsed.year != 1900 else 2000
    normalized = parsed.replace(year=year).strftime("%d/%m/%Y")

    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    user_id = str(interaction.user.id)

    action = "actualizado 🔄" if user_id in gdata["birthdays"] else "guardado ✅"
    gdata["birthdays"][user_id] = {"date": normalized, "name": str(interaction.user)}
    save_data(data)

    embed = discord.Embed(
        title="🎂 Cumpleaños guardado",
        description=f"{interaction.user.mention}, tu cumpleaños fue {action}:\n📅 **{normalized}**",
        color=COLOR_BIRTHDAY,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="micumple", description="Muestra tu cumpleaños guardado")
async def slash_my_birthday(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)

    user_id = str(interaction.user.id)
    if user_id not in gdata["birthdays"]:
        await interaction.response.send_message(
            "📭 No tienes ningún cumpleaños guardado. Usa `/cumple DD/MM`.",
            ephemeral=True,
        )
        return

    date = gdata["birthdays"][user_id]["date"]
    embed = discord.Embed(
        title="🎂 Tu cumpleaños",
        description=f"📅 Fecha guardada: **{date}**",
        color=COLOR_BIRTHDAY,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="borrarcumple", description="Elimina tu cumpleaños guardado")
async def slash_delete_birthday(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    user_id = str(interaction.user.id)

    if user_id not in gdata["birthdays"]:
        await interaction.response.send_message(
            "📭 No tienes ningún cumpleaños guardado.",
            ephemeral=True,
        )
        return

    del gdata["birthdays"][user_id]
    save_data(data)

    embed = discord.Embed(
        title="🗑️ Cumpleaños eliminado",
        description="Tu cumpleaños fue eliminado correctamente.",
        color=COLOR_ERROR,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="cumples", description="Lista todos los cumpleaños del servidor")
async def slash_list_birthdays(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    birthdays = gdata.get("birthdays", {})

    if not birthdays:
        await interaction.response.send_message(
            "📭 No hay cumpleaños guardados todavía.",
            ephemeral=True,
        )
        return

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_md = (now.month, now.day)

    entries = sorted(
        birthdays.items(),
        key=lambda x: datetime.strptime(x[1]["date"], "%d/%m/%Y").strftime("%m%d"),
    )

    lines = []
    for uid, info in entries:
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else info.get("name", f"Usuario {uid}")

        bday = datetime.strptime(info["date"], "%d/%m/%Y")
        emoji = "🎉" if (bday.month, bday.day) == today_md else "🎂"
        lines.append(f"{emoji} **{name}** — {info['date']}")

    embed = discord.Embed(
        title="🎉 Cumpleaños del servidor",
        description="\n".join(lines),
        color=COLOR_LIST,
    )
    embed.set_footer(text=f"Total: {len(entries)} cumpleaños registrados")

    await interaction.response.send_message(embed=embed)


@client.tree.command(
    name="proximoscumples",
    description="Muestra los próximos 5 cumpleaños del servidor",
)
async def slash_upcoming(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    birthdays = gdata.get("birthdays", {})

    if not birthdays:
        await interaction.response.send_message(
            "📭 No hay cumpleaños guardados todavía.",
            ephemeral=True,
        )
        return

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)

    def days_until(date_str: str) -> int:
        bday = datetime.strptime(date_str, "%d/%m/%Y")
        next_bday = bday.replace(year=now.year)
        if next_bday.date() < now.date():
            next_bday = next_bday.replace(year=now.year + 1)
        return (next_bday.date() - now.date()).days

    upcoming = sorted(
        birthdays.items(),
        key=lambda x: days_until(x[1]["date"]),
    )[:5]

    lines = []
    for uid, info in upcoming:
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else info.get("name", f"Usuario {uid}")
        days = days_until(info["date"])

        if days == 0:
            label = "HOY 🎉"
        elif days == 1:
            label = "mañana 🔔"
        else:
            label = f"en {days} días"

        lines.append(f"🎂 **{name}** — {info['date']} (**{label}**)")

    embed = discord.Embed(
        title="📅 Próximos cumpleaños",
        description="\n".join(lines),
        color=COLOR_UPCOMING,
    )
    embed.set_footer(text=f"Zona horaria: {TIMEZONE}")

    await interaction.response.send_message(embed=embed)


@client.tree.command(
    name="testcumple",
    description="[Admin] Simula el aviso de cumpleaños para hoy",
)
@app_commands.default_permissions(administrator=True)
async def slash_test_birthday(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_md = (now.month, now.day)

    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    birthdays = gdata.get("birthdays", {})

    channel_id = gdata.get("channel_id")
    channel = interaction.guild.get_channel(int(channel_id)) if channel_id else interaction.channel

    if not channel:
        await interaction.followup.send("❌ No se encontró un canal válido.", ephemeral=True)
        return

    found = False
    for user_id, info in birthdays.items():
        bday = datetime.strptime(info["date"], "%d/%m/%Y")
        if (bday.month, bday.day) == today_md:
            member = interaction.guild.get_member(int(user_id))
            if member:
                await send_birthday_message(channel, member)
                found = True

    await interaction.followup.send(
        "✅ Test completado. Mensaje enviado." if found else "📭 No hay cumpleaños hoy.",
        ephemeral=True,
    )


# ── Eventos ──────────────────────────────────────────────────────────────────
@client.event
async def on_ready():
    log.info("Conectado como %s (ID: %s)", client.user, client.user.id)
    log.info("Chequeo diario a las %s:00 (%s)", CHECK_HOUR, TIMEZONE)
    log.info("KLIPY GIFs: %s", "activado" if KLIPY_KEY else "desactivado")
    log.info("Mention everyone: %s", "SI" if MENTION_EVERYONE else "NO")
    check_birthdays.start()


client.run(TOKEN)
