# 🎂 Birthday Bot (Discord)

Bot de Discord para **registrar cumpleaños** y **anunciarlos automáticamente** en un canal.

## ✨ Características principales

- ✅ Slash commands completos (`/cumple`, `/cumples`, `/proximoscumples`, `/estadisticas`, etc.)
- ✅ Anuncios automáticos precisos (exactamente a la hora configurada, con timezone)
- ✅ Recordatorio automático un día antes
- ✅ Mensajes en **español neutro** con 12 variantes aleatorias
- ✅ Embeds con colores, avatar del usuario y GIF de cumpleaños (opcional)
- ✅ Persistencia en JSON con **escritura atómica** (segura contra corrupción)
- ✅ **I/O asíncrono** con `aiofiles` (sin bloqueos)
- ✅ **Session HTTP reutilizable** (rendimiento optimizado)
- ✅ Protección anti-spam (no repite anuncios aunque reinicies, con limpieza automática)
- ✅ **Paginación** en `/cumples` (para muchos registros)
- ✅ **Comandos admin** para gestionar cumpleaños de otros usuarios
- ✅ **Limpieza automática** cuando miembros salen del servidor
- ✅ Soporte para fechas **29 de febrero** (con aviso al usuario)
- ✅ Deploy simple con Docker Compose

---

## ✅ Requisitos

- Docker + Docker Compose
- Un bot creado en el **Discord Developer Portal** (con intención `members` habilitada)

---

## 🔧 Variables de entorno

Copia el archivo `.env.example` y crea tu `.env`:

```bash
cp .env.example .env
```

Edita `.env`:

```env
DISCORD_TOKEN=tu_token_aqui
KLIPY_API_KEY=tu_klipy_key_aqui
TIMEZONE=America/Lima
CHECK_HOUR=8
MENTION_EVERYONE=true
SYNC_COMMANDS=0
```

### Explicación de variables

| Variable | Tipo | Descripción |
|----------|------|-------------|
| **DISCORD_TOKEN** | string | Token del bot (obligatorio) |
| **KLIPY_API_KEY** | string | API Key de KLIPY para GIFs (opcional — si está vacío no envía GIFs) |
| **TIMEZONE** | string | Zona horaria (ej: `America/Lima`, `Europe/Madrid`, `America/Argentina/Buenos_Aires`) |
| **CHECK_HOUR** | int | Hora del anuncio diario (0-23) |
| **MENTION_EVERYONE** | bool | `true/false` — Mencionar @everyone en anuncios |
| **SYNC_COMMANDS** | int | **`0` por defecto**. Pon a `1` SOLO cuando agregues/cambies slash commands. Luego vuelve a `0`. |

**ℹ️ Nota sobre SYNC_COMMANDS:**
- Discord limita sincronizaciones a 200 por 24h por aplicación
- Mantener en `0` evita sincronizaciones innecesarias
- Solo cambiar a `1` cuando hagas cambios en los comandos

---

## 🚀 Ejecutar con Docker

### Levantar el bot

```bash
docker compose up -d --build
```

### Ver logs en tiempo real

```bash
docker compose logs -f
```

### Ver logs recientes

```bash
docker compose logs --tail=50
```

### Detener el bot

```bash
docker compose down
```

### Actualizar después de cambios de código

```bash
docker compose down
docker compose up -d --build
```

---

## 💻 Ejecutar en local (sin Docker)

### Requisitos

- Python 3.11+
- pip

### Instalación

```bash
pip install -r requirements.txt
```

### Crear .env

```bash
cp .env.example .env
# Editar .env con tus valores
```

### Ejecutar

```bash
python bot.py
```

---

## 🤖 Comandos disponibles

### Para Usuarios

| Comando | Descripción |
|---------|-------------|
| `/cumple <fecha>` | Guardar o actualizar tu cumpleaños. Ej: `/cumple 15/03` o `/cumple 15/03/1990` |
| `/micumple` | Ver tu cumpleaños guardado |
| `/borrarcumple` | Eliminar tu cumpleaños |
| `/cumples` | Listar todos los cumpleaños del servidor (con paginación) |
| `/proximoscumples` | Ver los 5 próximos cumpleaños |

### Para Administradores

| Comando | Descripción |
|---------|-------------|
| `/setcanal <canal>` | Definir el canal donde se anuncian los cumpleaños |
| `/cumpleadmin <set\|borrar> <usuario> [fecha]` | Gestionar cumpleaños de otros usuarios |
| `/estadisticas` | Total registrados, mes más popular, próximo cumpleaños y distribución mensual |
| `/limpiar` | Eliminar cumpleaños de miembros que ya no están en el servidor |
| `/testcumple` | Simular el anuncio de cumpleaños (solo si hay cumpleaños hoy) |
| `/testrecordatorio` | Simular el recordatorio de mañana (solo si hay cumpleaños mañana) |

**ℹ️ Nota:** Todos los comandos solo funcionan dentro de un servidor (no en DMs).

---

## 🔄 Flujo de anuncios

1. **Exactamente a `CHECK_HOUR:00`** (en la zona horaria configurada), el bot verifica todos los cumpleaños registrados
2. **Si es cumpleaños HOY**: envía anuncio con GIF opcional y mención a @everyone (si está habilitado)
3. **Si es cumpleaños MAÑANA**: envía recordatorio
4. **Anti-spam**: registra la fecha de cada anuncio para no repetir aunque el bot se reinicie; las entradas se limpian automáticamente pasados 2 días

---

## 🛠️ Características técnicas

### Performance & Robustez

- **I/O Asíncrono**: usa `aiofiles` en lugar de `open()` bloqueante
- **Session HTTP Reutilizable**: la conexión con la API de KLIPY se mantiene abierta entre peticiones
- **Escritura Atómica**: usa archivos `.tmp` para evitar corrupción de datos
- **Error Handling**: try/except en todos los puntos críticos con logging completo
- **Guard de DMs**: rechaza comandos en mensajes directos

### Fechas especiales

- **29 de febrero**: aceptado y guardado normalmente. En años no bisiestos el anuncio se envía el 28/02. El usuario recibe un aviso al registrar esta fecha.
- **Limpieza de `last_announcement`**: el registro de anuncios ya enviados se purga automáticamente (entradas con más de 2 días), evitando que el JSON crezca indefinidamente.

### Arquitectura

```
bot.py
├── Configuración (variables de entorno)
├── Persistencia async (load_data / save_data con escritura atómica)
├── Helpers (parse_date, days_until, cleanup_announcements)
├── Discord Client + Session HTTP (aiohttp)
├── Tarea diaria con @tasks.loop(time=...)
├── Handlers de eventos (on_ready, on_member_remove, on_guild_join)
├── 11 Slash commands (usuarios + admin)
└── Paginador (View) para /cumples
```

### Dependencias

```
discord.py==2.4.0      # Bot framework
pytz==2025.1           # Timezone handling
aiohttp==3.10.11       # HTTP async
aiofiles==23.2.1       # File I/O async
```

---

## ⚙️ Personalización

### Cambiar mensajes de cumpleaños o recordatorios

Edita `BIRTHDAY_MESSAGES` y `REMINDER_MESSAGES` en `bot.py`.

### Cambiar colores de los embeds

Edita las constantes `COLOR_*` al inicio de `bot.py`. Formato: `discord.Color(0xRRGGBB)`.

### Cambiar número de próximos cumpleaños en `/proximoscumples`

Busca `[:5]` en la función `slash_upcoming` y cámbialo al número deseado.

### Cambiar tamaño de página en `/cumples`

Busca `PAGE_SIZE = 10` en la función `slash_list_birthdays`.

---

## 🔑 Permisos necesarios del bot

En el canal donde envía mensajes:

- **Send Messages** (obligatorio)
- **Embed Links** (obligatorio)
- **Read Message History** (recomendado)
- **Mention Everyone** (solo si `MENTION_EVERYONE=true`)

---

## 📋 Persistencia

Los cumpleaños se guardan en:

```
/data/birthdays.json
```

En Docker este archivo está montado en un volumen llamado `birthday_data`. La escritura es **atómica** (segura contra corrupción).

---

## 🐛 Troubleshooting

### El bot no aparece en línea

1. Verifica que el token sea correcto en `.env`
2. Verifica que el bot tiene los permisos correctos en el Discord Developer Portal
3. Revisa los logs: `docker compose logs`

### Los comandos no aparecen en Discord

1. Pon `SYNC_COMMANDS=1` en `.env`
2. Reinicia: `docker compose down && docker compose up -d`
3. Una vez aparezcan los comandos, vuelve a `SYNC_COMMANDS=0`

### El anuncio no se envía a la hora exacta

1. Verifica que `TIMEZONE` sea correcta (ej: `America/Lima`, no `UTC-5`)
2. Verifica que `CHECK_HOUR` sea la hora deseada (0–23)

### Error "No se encontró canal válido"

1. Usa `/setcanal #tu-canal` para definir el canal manualmente
2. Verifica que el bot tenga permisos de `Enviar mensajes` y `Incrustar enlaces` en ese canal

### Los cumpleaños guardados desaparecen al reiniciar Docker

1. Verifica que el volumen persiste: `docker volume ls | grep birthday_data`
2. Si no existe, revisa tu `docker-compose.yml` y que el volumen esté declarado

### No se envían GIFs

1. Si no quieres GIFs, deja `KLIPY_API_KEY` vacío en `.env` — el bot funciona igual sin ellos
2. Si quieres GIFs, obtén una key gratuita en https://partner.klipy.com

---

## 📜 Licencia

Este proyecto se distribuye bajo la licencia incluida en el archivo `LICENSE`.
