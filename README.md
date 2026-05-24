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
- ✅ Protección anti-spam (no repite anuncios aunque reinicies)
- ✅ **Paginación** en `/cumples` (para muchos registros)
- ✅ **Comandos admin** para gestionar cumpleaños de otros usuarios
- ✅ **Limpieza automática** cuando miembros salen del servidor
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
| **KLIPY_API_KEY** | string | API Key de KLIPY para GIFs (opcional - si está vacío no envía GIFs) |
| **TIMEZONE** | string | Zona horaria (ej: `America/Lima`, `Europe/Madrid`, `America/Argentina/Buenos_Aires`) |
| **CHECK_HOUR** | int | Hora del anuncio diario (0-23) |
| **MENTION_EVERYONE** | bool | `true/false` - Mencionar @everyone en anuncios |
| **SYNC_COMMANDS** | int | **`0` por defecto**. Pon a `1` SOLO cuando agregues/cambies slash commands para sincronizar con Discord. Luego vuelve a `0`. |

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

### Ver logs del último contenedor

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

## 🔄 Flujo de anuncios

1. **Cada 30 minutos**, el bot verifica si es la hora configurada (`CHECK_HOUR`)
2. **Exactamente a `CHECK_HOUR:00`** (con precisión de timezone), verifica todos los cumpleaños
3. **Si es cumpleaños HOY**: Envía anuncio con GIF opcional
4. **Si es cumpleaños MAÑANA**: Envía recordatorio
5. **Anti-spam**: Registra las fechas de anuncios para no repetir aunque reinicie

---

## 🛠️ Características técnicas

### Performance & Robustez

- **I/O Asíncrono**: Usa `aiofiles` en lugar de `open()` bloqueante
- **Session HTTP Reutilizable**: La conexión con la API de KLIPY se mantiene abierta
- **Escritura Atómica**: Usa archivos `.tmp` para evitar corrupción de datos
- **Error Handling**: Try/except en todos los puntos críticos
- **Logging Detallado**: Rastreo de todos los eventos importantes
- **Guard de DMs**: Rechaza comandos en mensajes directos

### Arquitectura

```
bot.py
├── Persistencia (load_data/save_data async)
├── Discord Client + Session HTTP
├── Tarea diaria con @tasks.loop(time=...)
├── Handlers de eventos
├── 10 Slash commands (usuarios + admin)
└── Paginación automática en /cumples
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

### Cambiar mensajes

Edita `BIRTHDAY_MESSAGES` y `REMINDER_MESSAGES` en `bot.py` (líneas 46-68)

### Cambiar colores

Edita las constantes `COLOR_*` en `bot.py` (líneas 41-45)

Formato: `discord.Color(0xRRGGBB)`

### Cambiar número de cumpleaños en `/proximoscumples`

En `bot.py` línea ~526, cambia `[:5]` a la cantidad que desees

### Cambiar tamaño de página en `/cumples`

En `bot.py` línea ~500, cambia `PAGE_SIZE = 10` al número deseado

---

## 🐛 Troubleshooting

### El bot no aparece en línea

**Solución:**
1. Verifica que el token sea correcto en `.env`
2. Verifica que el bot tiene los permisos correctos en Discord Developer Portal
3. Revisa los logs: `docker compose logs`

### Los comandos no aparecen

**Solución:**
1. Pon `SYNC_COMMANDS=1` en `.env`
2. Reinicia el bot: `docker compose down && docker compose up -d`
3. Una vez aparezcan, vuelve a `SYNC_COMMANDS=0`

### El anuncio no se envía a la hora exacta

**Solución:**
1. Verifica que `TIMEZONE` sea correcta (ej: `America/Lima`, no `UTC`)
2. Verifica que `CHECK_HOUR` sea la hora deseada (0-23)
3. El bot se sincroniza exactamente a `:00` minutos

### Error "No se encontró canal válido"

**Solución:**
1. Usa `/setcanal #tu-canal` para definir el canal
2. Verifica que el bot tenga permisos de `Enviar mensajes` y `Incrustar enlaces`

### Los cumpleaños guardados desaparecen

**Solución:**
1. Esto ocurre cuando el volumen Docker no persiste
2. Verifica que el volumen existe: `docker volume ls | grep birthday_data`
3. Si no existe, reinicia: `docker compose down && docker compose up -d`

### Error de "KLIPY"

**Solución:**
1. Si no quieres GIFs, deja `KLIPY_API_KEY` vacío en `.env`
2. Si quieres GIFs, obtén una key gratuita en https://partner.klipy.com

---

## 📞 Soporte

Si encuentras bugs o tienes sugerencias:
- Abre un issue en GitHub
- Revisa los logs con `docker compose logs`

---

## 📄 Licencia

---

## 🤖 Comandos disponibles

### Para Usuarios

| Comando | Uso |
|---------|-----|
| `/cumple` | Guardar o actualizar tu cumpleaños. Ej: `/cumple 15/03` o `/cumple 15/03/1990` |
| `/micumple` | Ver tu cumpleaños guardado |
| `/borrarcumple` | Eliminar tu cumpleaños |
| `/cumples` | Listar todos los cumpleaños del servidor (con paginación si hay muchos) |
| `/proximoscumples` | Ver los 5 próximos cumpleaños |

### Para Administradores

| Comando | Uso |
|---------|-----|
| `/setcanal` | Definir el canal donde se anuncian los cumpleaños |
| `/cumpleadmin` | Gestionar cumpleaños de otros usuarios (set/borrar) |
| `/estadisticas` | Ver estadísticas: total registrados, mes más popular, próximo cumpleaños |
| `/limpiar` | Eliminar cumpleaños de miembros que ya no están en el servidor |
| `/testcumple` | Probar el anuncio de cumpleaños (solo si hay cumpleaños hoy) |

**ℹ️ Nota:** Todos los comandos solo funcionan dentro de un servidor (no en DMs).

---

## 📋 Persistencia

Los cumpleaños se guardan en:

```
/data/birthdays.json
```

En Docker esto está montado en un volumen llamado `birthday_data`. La escritura es **atómica** (segura contra corrupción de datos).

---

## 🔑 Permisos necesarios del bot

En el canal donde manda mensajes:

- **Send Messages** (obligatorio)
- **Embed Links** (obligatorio)
- **Read Message History** (recomendado)
- **Mention Everyone** (solo si `MENTION_EVERYONE=true`)

---

## 🧠 Notas importantes

- **Scheduling preciso**: El bot usa `@tasks.loop(time=...)` para ejecutar exactamente a `CHECK_HOUR:00` en tu timezone
- **Sistema anti-spam**: No repite anuncios aunque reinicies el bot (guarda la fecha de último anuncio)
- **Sin bloqueos**: Todas las operaciones de archivo y red son asincrónicas
- **Seguridad de datos**: La escritura es atómica (usa archivos `.tmp` para evitar corrupción)
- **Limpiar automáticamente**: Cuando alguien sale del servidor, su cumpleaños se elimina automáticamente

---

## 📜 Licencia

Este proyecto se distribuye bajo la licencia incluida en el archivo `LICENSE`.
