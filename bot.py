import os
import json
import random
import logging
import datetime as dt
from datetime import datetime, timedelta
from typing import Literal

import aiofiles
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
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        if os.environ.get("SYNC_COMMANDS") == "1":
            await self.tree.sync()
            log.info("Slash commands sincronizados globalmente")
        else:
            log.info("Slash commands: usando caché (define SYNC_COMMANDS=1 para forzar sync)")
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()


client = BirthdayBot()


# ── Persistencia ─────────────────────────────────────────────────────────────
async def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    async with aiofiles.open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.loads(await f.read())


async def save_data(data: dict):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    try:
        async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        os.replace(tmp, DATA_FILE)
    except Exception as e:
        log.error("Error al guardar datos: %s", e, exc_info=True)
        raise


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

        if not client.session:
            return None
        async with client.session.get(
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
        timestamp=datetime.now(datetime.UTC),
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
        timestamp=datetime.now(datetime.UTC),
    )
    embed.set_footer(text="📅 Birthday Bot")
    embed.set_thumbnail(url=member.display_avatar.url)

    await channel.send(embed=embed)


# ── Tarea diaria ─────────────────────────────────────────────────────────────
@tasks.loop(
    time=dt.time(
        hour=CHECK_HOUR,
        minute=0,
        tzinfo=pytz.timezone(TIMEZONE),
    )
)
async def check_birthdays():
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    try:
        data = await load_data()

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
                    await save_data(data)
                    log.info("Cumple enviado para %s en %s", member, guild.name)

                # MAÑANA
                elif bday_md == tmrw_md:
                    if already_announced(gdata, user_id, "reminder", tomorrow_key):
                        continue

                    await send_reminder_message(channel, member)
                    mark_announced(gdata, user_id, "reminder", tomorrow_key)
                    await save_data(data)
                    log.info("Recordatorio enviado para %s en %s", member, guild.name)
    except Exception as e:
        log.error("check_birthdays falló: %s", e, exc_info=True)


@check_birthdays.before_loop
async def before_check():
    await client.wait_until_ready()


@check_birthdays.error
async def on_check_error(error: Exception):
    log.error("Error en check_birthdays: %s", error, exc_info=True)


class Paginator(discord.ui.View):
    def __init__(self, pages: list[list[str]], color: discord.Color):
        super().__init__(timeout=60)
        self.pages = pages
        self.color = color
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current >= len(self.pages) - 1

    def make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎉 Cumpleaños del servidor",
            description="\n".join(self.pages[self.current]),
            color=self.color,
        )
        embed.set_footer(
            text=f"Página {self.current + 1} de {len(self.pages)}"
        )
        return embed

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


# ── Slash Commands ──────────────────────────────────────────────────────────
@client.tree.command(
    name="setcanal",
    description="[Admin] Define el canal donde se anuncian los cumpleaños",
)
@app_commands.describe(canal="Canal de texto donde el bot mandará los avisos")
@app_commands.default_permissions(administrator=True)
async def slash_set_channel(interaction: discord.Interaction, canal: discord.TextChannel):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
        return
    data = await load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    gdata["channel_id"] = str(canal.id)
    await save_data(data)

    await interaction.response.send_message(
        f"✅ Canal configurado: {canal.mention}",
        ephemeral=True,
    )


@client.tree.command(name="cumple", description="Guarda o actualiza tu fecha de cumpleaños")
@app_commands.describe(fecha="Formato: DD/MM o DD/MM/AAAA → Ej: 15/03")
async def slash_set_birthday(interaction: discord.Interaction, fecha: str):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
        return
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

    data = await load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    user_id = str(interaction.user.id)

    action = "actualizado 🔄" if user_id in gdata["birthdays"] else "guardado ✅"
    gdata["birthdays"][user_id] = {"date": normalized, "name": str(interaction.user)}
    await save_data(data)

    embed = discord.Embed(
        title="🎂 Cumpleaños guardado",
        description=f"{interaction.user.mention}, tu cumpleaños fue {action}:\n📅 **{normalized}**",
        color=COLOR_BIRTHDAY,
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="micumple", description="Muestra tu cumpleaños guardado")
async def slash_my_birthday(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
        return
    data = await load_data()
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
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
        return
    data = await load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    user_id = str(interaction.user.id)

    if user_id not in gdata["birthdays"]:
        await interaction.response.send_message(
            "📭 No tienes ningún cumpleaños guardado.",
            ephemeral=True,
        )
        return

    del gdata["birthdays"][user_id]
    await save_data(data)

    embed = discord.Embed(
        title="🗑️ Cumpleaños eliminado",
        description="Tu cumpleaños fue eliminado correctamente.",
        color=COLOR_ERROR,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@client.tree.command(name="cumples", description="Lista todos los cumpleaños del servidor")
async def slash_list_birthdays(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
        return
    data = await load_data()
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

    PAGE_SIZE = 10
    pages = [lines[i : i + PAGE_SIZE] for i in range(0, len(lines), PAGE_SIZE)]
    view = Paginator(pages, COLOR_LIST)
    embed = view.make_embed()
    embed.set_footer(
        text=f"Total: {len(entries)} cumpleaños · Página 1 de {len(pages)}"
    )
    await interaction.response.send_message(embed=embed, view=view)


@client.tree.command(
    name="proximoscumples",
    description="Muestra los próximos 5 cumpleaños del servidor",
)
async def slash_upcoming(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
        return
    data = await load_data()
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
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Este comando solo funciona dentro de un servidor.",
            ephemeral=True,
        )
        return
    await interaction.response.defer(ephemeral=True)

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    today_md = (now.month, now.day)

    data = await load_data()
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


@client.tree.command(
    name="cumpleadmin",
    description="[Admin] Gestiona el cumpleaños de cualquier miembro",
)
@app_commands.describe(
    accion="'set' para guardar, 'borrar' para eliminar",
    usuario="Miembro del servidor",
    fecha="DD/MM o DD/MM/AAAA (requerido si accion=set)",
)
@app_commands.default_permissions(administrator=True)
async def slash_admin_birthday(
    interaction: discord.Interaction,
    accion: Literal["set", "borrar"],
    usuario: discord.Member,
    fecha: str = "",
):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Solo funciona en servidores.", ephemeral=True
        )
        return

    data = await load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    uid = str(usuario.id)

    if accion == "borrar":
        if uid not in gdata["birthdays"]:
            await interaction.response.send_message(
                f"📭 {usuario.mention} no tiene cumpleaños registrado.",
                ephemeral=True,
            )
            return
        del gdata["birthdays"][uid]
        await save_data(data)
        await interaction.response.send_message(
            f"🗑️ Cumpleaños de {usuario.mention} eliminado.",
            ephemeral=True,
        )

    elif accion == "set":
        if not fecha:
            await interaction.response.send_message(
                "❌ Debes indicar la fecha cuando accion=set. Ej: `15/03`",
                ephemeral=True,
            )
            return
        parsed = None
        for fmt in ("%d/%m/%Y", "%d/%m"):
            try:
                parsed = datetime.strptime(fecha.strip(), fmt)
                break
            except ValueError:
                continue
        if not parsed:
            await interaction.response.send_message(
                "❌ Formato inválido. Usa `DD/MM` o `DD/MM/AAAA`.",
                ephemeral=True,
            )
            return
        year = parsed.year if parsed.year != 1900 else 2000
        normalized = parsed.replace(year=year).strftime("%d/%m/%Y")
        gdata["birthdays"][uid] = {"date": normalized, "name": str(usuario)}
        await save_data(data)
        await interaction.response.send_message(
            f"✅ Cumpleaños de {usuario.mention} guardado: **{normalized}**",
            ephemeral=True,
        )


@client.tree.command(
    name="estadisticas",
    description="Muestra estadísticas de cumpleaños del servidor",
)
async def slash_stats(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Solo funciona en servidores.", ephemeral=True
        )
        return

    data = await load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    birthdays = gdata.get("birthdays", {})

    if not birthdays:
        await interaction.response.send_message(
            "📭 No hay cumpleaños registrados.", ephemeral=True
        )
        return

    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    months = [0] * 12
    for info in birthdays.values():
        try:
            m = datetime.strptime(info["date"], "%d/%m/%Y").month
            months[m - 1] += 1
        except ValueError:
            pass

    mes_top_idx = months.index(max(months))
    nombres_meses = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ]

    def days_until(date_str: str) -> int:
        bday = datetime.strptime(date_str, "%d/%m/%Y")
        next_bday = bday.replace(year=now.year)
        if next_bday.date() < now.date():
            next_bday = next_bday.replace(year=now.year + 1)
        return (next_bday.date() - now.date()).days

    proximo = min(birthdays.items(), key=lambda x: days_until(x[1]["date"]))
    proximo_uid, proximo_info = proximo
    proximo_member = interaction.guild.get_member(int(proximo_uid))
    proximo_name = proximo_member.display_name if proximo_member else proximo_info.get("name", "Desconocido")
    proximo_dias = days_until(proximo_info["date"])

    embed = discord.Embed(
        title="📊 Estadísticas de cumpleaños",
        color=COLOR_LIST,
    )
    embed.add_field(name="Total registrados", value=f"**{len(birthdays)}** miembros", inline=True)
    embed.add_field(
        name="Mes más popular",
        value=f"**{nombres_meses[mes_top_idx]}** ({months[mes_top_idx]} cumpleaños)",
        inline=True,
    )
    if proximo_dias == 0:
        label = "¡HOY! 🎉"
    elif proximo_dias == 1:
        label = "mañana 🔔"
    else:
        label = f"en {proximo_dias} días"
    embed.add_field(
        name="Próximo cumpleaños",
        value=f"**{proximo_name}** — {proximo_info['date']} ({label})",
        inline=False,
    )
    embed.set_footer(text=f"Zona horaria: {TIMEZONE}")
    await interaction.response.send_message(embed=embed)


@client.tree.command(
    name="limpiar",
    description="[Admin] Elimina cumpleaños de miembros que ya no están en el servidor",
)
@app_commands.default_permissions(administrator=True)
async def slash_cleanup(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "❌ Solo funciona en servidores.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    data = await load_data()
    gdata = get_guild_data(data, interaction.guild.id)
    birthdays = gdata.get("birthdays", {})

    to_remove = [
        uid for uid in birthdays
        if not interaction.guild.get_member(int(uid))
    ]

    for uid in to_remove:
        del gdata["birthdays"][uid]

    if to_remove:
        await save_data(data)

    await interaction.followup.send(
        f"🧹 Limpieza completada. Se eliminaron **{len(to_remove)}** registros de miembros que ya no están en el servidor."
        if to_remove
        else "✅ No hay registros huérfanos. Todo está limpio.",
        ephemeral=True,
    )


# ── Eventos ──────────────────────────────────────────────────────────────────
@client.event
async def on_member_remove(member: discord.Member):
    try:
        data = await load_data()
        gdata = get_guild_data(data, member.guild.id)
        uid = str(member.id)
        if uid in gdata["birthdays"]:
            del gdata["birthdays"][uid]
            await save_data(data)
            log.info(
                "Cumpleaños de %s eliminado (salió de %s)",
                member,
                member.guild.name,
            )
    except Exception as e:
        log.error("Error en on_member_remove: %s", e, exc_info=True)


@client.event
async def on_ready():
    log.info("Conectado como %s (ID: %s)", client.user, client.user.id)
    log.info("Chequeo diario a las %02d:00 (%s)", CHECK_HOUR, TIMEZONE)
    log.info("KLIPY GIFs: %s", "activado" if KLIPY_KEY else "desactivado")
    log.info("Mention everyone: %s", "SI" if MENTION_EVERYONE else "NO")
    check_birthdays.start()


client.run(TOKEN)
