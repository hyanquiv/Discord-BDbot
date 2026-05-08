import os
import json
import random
import aiohttp
import discord
import pytz

from datetime import datetime, timedelta
from discord import app_commands
from discord.ext import tasks


# ── Config ───────────────────────────────────────────────────────────────────
TOKEN = os.environ["DISCORD_TOKEN"]
DATA_FILE = os.environ.get("DATA_FILE", "/data/birthdays.json")
TIMEZONE = os.environ.get("TIMEZONE", "America/Lima")
CHECK_HOUR = int(os.environ.get("CHECK_HOUR", "8"))
KLIPY_KEY = os.environ.get("KLIPY_API_KEY", "")


# ── Mensajes aleatorios ───────────────────────────────────────────────────────
BIRTHDAY_MESSAGES = [
    "🎂 ¡Hoy es el cumpleaños de {usuario}! ¡Que la rompas! 🥳",
    "🎉 ¡Feliz cumple {usuario}! Que este año venga cargado de cosas buenas 🙌",
    "🥳 ¡{usuario} está de cumpleaños hoy! Alguien tráele una torta 🎂",
    "🎈 ¡Ojo que hoy cumple {usuario}! Mándenle un saludo 👇",
    "🎊 El universo decidió que hoy nació {usuario}. ¡Buena decisión, universo! 🌟",
    "🍰 ¡{usuario} cumple un año más de experiencia! Happy birthday 🎉",
    "🥂 ¡Brindemos por {usuario} que hoy está de cumple! 🎂🎊",
    "🎸 ¡{usuario} cumple hoy! Que sea un día épico 🔥",
    "✨ Hoy el servidor celebra a {usuario}. ¡Feliz cumple! 🎂",
    "🎁 ¡Alguien dijo cumpleaños? Feliz cumple {usuario}! 🥳🎉",
]

REMINDER_MESSAGES = [
    "🔔 Mañana es el cumpleaños de {usuario}. ¡Preparen los saludos! 🎂",
    "📅 Ojo que mañana {usuario} cumple años. No se olviden 😉",
    "⏰ Recordatorio: mañana es el cumple de {usuario}. A cargar las pilas 🎉",
    "🗓️ Mañana {usuario} está de cumple. ¡Ya van avisados! 🥳",
    "🎈 Pre-aviso: mañana cumple {usuario}. Vayan pensando el saludo 👀",
]


# ── Client ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True


class BirthdayBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands sincronizados globalmente")


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
        data["guilds"][gid] = {"channel_id": None, "birthdays": {}}

    return data["guilds"][gid]


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
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:

                if resp.status != 200:
                    print(f"⚠️  KLIPY HTTP {resp.status}")
                    return None

                result = await resp.json()
                items = result.get("data", {}).get("data", [])

                if not items:
                    print("⚠️  KLIPY: No devolvió gifs")
                    return None

                item = random.choice(items)

                gif_url = item.get("file", {}).get("hd", {}).get("gif", {}).get("url")
                if not gif_url:
                    print("⚠️  KLIPY: respuesta sin URL válida")
                    return None

                return gif_url

    except Exception as e:
        print(f"⚠️  KLIPY error: {e}")
        return None


# ── Helper: enviar aviso de cumpleaños ───────────────────────────────────────
async def send_birthday_message(channel: discord.TextChannel, member: discord.Member):
    try:
        gif_url = await fetch_birthday_gif()
        mensaje = random.choice(BIRTHDAY_MESSAGES).format(usuario=member.mention)

        embed = discord.Embed(
            description=mensaje,
            color=discord.Color(0xff6eb4)
        )
        embed.set_footer(text="🎂 Birthday Bot")

        if gif_url:
            embed.set_image(url=gif_url)

        await channel.send("@everyone", embed=embed)

        print(f"✅ Mensaje enviado en #{channel.name} para {member}")

    except Exception as e:
        print("❌ ERROR enviando mensaje de cumpleaños:", e)
        await channel.send(f"@everyone 🎂 Feliz cumple {member.mention} (fallback)")


# ── Tarea diaria ─────────────────────────────────────────────────────────────
@tasks.loop(hours=1)
async def check_birthdays():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    if now.hour != CHECK_HOUR:
        return

    data = load_data()
    today = (now.month, now.day)

    tomorrow_dt = now + timedelta(days=1)
    tmrw = (tomorrow_dt.month, tomorrow_dt.day)

    for guild in client.guilds:
        gdata = get_guild_data(data, guild.id)
        channel_id = gdata.get("channel_id")

        channel = (
            guild.get_channel(int(channel_id)) if channel_id
            else next(
                (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
                None
            )
        )

        if not channel:
            continue

        for user_id, info in gdata.get("birthdays", {}).items():
            bday = datetime.strptime(info["date"], "%d/%m/%Y")
            bday_md = (bday.month, bday.day)

            member = guild.get_member(int(user_id))
            if not member:
                continue

            if bday_md == today:
                await send_birthday_message(channel, member)

            elif bday_md == tmrw:
                mensaje = random.choice(REMINDER_MESSAGES).format(usuario=member.mention)
                await channel.send(mensaje)


@check_birthdays.before_loop
async def before_check():
    await client.wait_until_ready()


# ── /setcanal ────────────────────────────────────────────────────────────────
@client.tree.command(
    name="setcanal",
    description="[Admin] Define el canal donde se anuncian los cumpleaños"
)
@app_commands.describe(canal="Canal de texto donde el bot mandará los avisos")
@app_commands.default_permissions(administrator=True)
async def slash_set_channel(interaction: discord.Interaction, canal: discord.TextChannel):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)

    gdata["channel_id"] = str(canal.id)
    save_data(data)

    await interaction.response.send_message(
        f"✅ Canal de cumpleaños configurado: {canal.mention}",
        ephemeral=True
    )


# ── /cumple ──────────────────────────────────────────────────────────────────
@client.tree.command(name="cumple", description="Guarda o actualiza tu fecha de cumpleaños")
@app_commands.describe(fecha="Tu cumpleaños en formato DD/MM o DD/MM/AAAA → ej: 15/03")
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
            "❌ Formato inválido. Usá `DD/MM` o `DD/MM/AAAA`. Ej: `/cumple 15/03`",
            ephemeral=True
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

    await interaction.response.send_message(
        f"🎂 Cumpleaños {action}: **{normalized}** para {interaction.user.mention}",
        ephemeral=True
    )


# ── /micumple ────────────────────────────────────────────────────────────────
@client.tree.command(name="micumple", description="Muestra tu cumpleaños guardado")
async def slash_my_birthday(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)

    user_id = str(interaction.user.id)

    if user_id not in gdata["birthdays"]:
        await interaction.response.send_message(
            "No tenés ningún cumpleaños guardado. Usá `/cumple DD/MM`.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"🎂 Tu cumpleaños guardado es: **{gdata['birthdays'][user_id]['date']}**",
        ephemeral=True
    )


# ── /borrarcumple ────────────────────────────────────────────────────────────
@client.tree.command(name="borrarcumple", description="Elimina tu cumpleaños guardado")
async def slash_delete_birthday(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)

    user_id = str(interaction.user.id)

    if user_id not in gdata["birthdays"]:
        await interaction.response.send_message(
            "No tenés ningún cumpleaños guardado.",
            ephemeral=True
        )
        return

    del gdata["birthdays"][user_id]
    save_data(data)

    await interaction.response.send_message(
        "🗑️ Tu cumpleaños fue eliminado.",
        ephemeral=True
    )


# ── /cumples ─────────────────────────────────────────────────────────────────
@client.tree.command(name="cumples", description="Lista todos los cumpleaños del servidor")
async def slash_list_birthdays(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)

    birthdays = gdata.get("birthdays", {})
    if not birthdays:
        await interaction.response.send_message(
            "📭 No hay cumpleaños guardados todavía.",
            ephemeral=True
        )
        return

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_md = (now.month, now.day)

    entries = sorted(
        birthdays.items(),
        key=lambda x: datetime.strptime(x[1]["date"], "%d/%m/%Y").strftime("%m%d")
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
        color=discord.Color(0xff6eb4)
    )
    embed.set_footer(text=f"Total: {len(entries)} cumpleaños guardados")

    await interaction.response.send_message(embed=embed)


# ── /proximoscumples ─────────────────────────────────────────────────────────
@client.tree.command(
    name="proximoscumples",
    description="Muestra los próximos 5 cumpleaños del servidor"
)
async def slash_upcoming(interaction: discord.Interaction):
    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)

    birthdays = gdata.get("birthdays", {})
    if not birthdays:
        await interaction.response.send_message(
            "📭 No hay cumpleaños guardados todavía.",
            ephemeral=True
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
        key=lambda x: days_until(x[1]["date"])
    )[:5]

    lines = []

    for uid, info in upcoming:
        member = interaction.guild.get_member(int(uid))
        name = member.display_name if member else info.get("name", f"Usuario {uid}")

        days = days_until(info["date"])

        if days == 0:
            label = "¡**HOY** 🎉!"
        elif days == 1:
            label = "**mañana** 🔔"
        else:
            label = f"en **{days} días**"

        lines.append(f"🎂 **{name}** — {info['date']} ({label})")

    embed = discord.Embed(
        title="📅 Próximos cumpleaños",
        description="\n".join(lines),
        color=discord.Color(0xffa500)
    )

    await interaction.response.send_message(embed=embed)


# ── /testcumple (admin) ──────────────────────────────────────────────────────
@client.tree.command(
    name="testcumple",
    description="[Admin] Simula el aviso de cumpleaños para hoy"
)
@app_commands.default_permissions(administrator=True)
async def slash_test_birthday(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    data = load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    birthdays = gdata.get("birthdays", {})

    today_md = (now.month, now.day)
    found = False

    channel_id = gdata.get("channel_id")
    channel = interaction.guild.get_channel(int(channel_id)) if channel_id else interaction.channel

    for user_id, info in birthdays.items():
        bday = datetime.strptime(info["date"], "%d/%m/%Y")

        if (bday.month, bday.day) == today_md:
            member = interaction.guild.get_member(int(user_id))
            if member:
                await send_birthday_message(channel, member)
                found = True

    msg = (
        "✅ Mensajes enviados."
        if found
        else "📭 No hay cumpleaños hoy. Guardá el tuyo con `/cumple` usando la fecha de hoy y probá de nuevo."
    )

    await interaction.followup.send(msg, ephemeral=True)


# ── Eventos ──────────────────────────────────────────────────────────────────
@client.event
async def on_ready():
    print(f"✅ Conectado como {client.user} (ID: {client.user.id})")
    print(f"⏰ Chequeo diario a las {CHECK_HOUR}:00 ({TIMEZONE})")
    print(f"🎬 KLIPY GIFs: {'activado' if KLIPY_KEY else 'desactivado (sin API key)'}")

    check_birthdays.start()


@client.event
async def on_error(event, *args, **kwargs):
    print("❌ ERROR EVENT:", event, args, kwargs)


client.run(TOKEN)