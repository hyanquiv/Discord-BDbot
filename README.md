# 🎂 Birthday Bot (Discord)

Bot de Discord para **registrar cumpleaños** y **anunciarlos automáticamente** en un canal.

Incluye:
- Slash commands (`/cumple`, `/cumples`, `/proximoscumples`, etc.)
- Anuncios automáticos diarios
- Recordatorio un día antes
- Mensajes en español neutro
- Embeds con colores, avatar y GIF opcional
- Persistencia en JSON
- Protección anti-spam (no repite anuncios aunque reinicies)
- Deploy simple con Docker

---

## ✅ Requisitos

- Docker + Docker Compose
- Un bot creado en el **Discord Developer Portal**

---

## 🔧 Variables de entorno

Copia el archivo `.env.example` y crea tu `.env`:

```bash
cp .env.example .env
```

Edita `.env`:

```env
DISCORD_TOKEN=tu_token
KLIPY_API_KEY=tu_key_opcional
TIMEZONE=America/Lima
CHECK_HOUR=8
MENTION_EVERYONE=true
```

### Explicación rápida

- **DISCORD_TOKEN**: obligatorio
- **KLIPY_API_KEY**: opcional (si lo dejas vacío, no manda GIF)
- **TIMEZONE**: zona horaria (ej: `America/Lima`)
- **CHECK_HOUR**: hora del anuncio diario (0-23)
- **MENTION_EVERYONE**: `true/false`

---

## 🚀 Ejecutar con Docker

Levantar el bot:

```bash
docker compose up -d --build
```

Ver logs:

```bash
docker compose logs -f
```

Detener:

```bash
docker compose down
```

---

## 🗂️ Persistencia

Los cumpleaños se guardan en:

```
/data/birthdays.json
```

En Docker esto está montado en un volumen llamado `birthday_data`.

---

## 🤖 Comandos disponibles

### Usuarios

- `/cumple DD/MM` o `/cumple DD/MM/AAAA`
- `/micumple`
- `/borrarcumple`
- `/cumples`
- `/proximoscumples`

### Administrador

- `/setcanal #canal`
- `/testcumple`

---

## 🔑 Permisos necesarios del bot

En el canal donde manda mensajes:

- **Send Messages**
- **Embed Links**
- **Read Message History** (recomendado)
- **Mention Everyone** (solo si quieres que use `@everyone`)

---

## 🧠 Notas

- El bot revisa cada 30 minutos, pero solo ejecuta anuncios cuando coincide con `CHECK_HOUR`.
- Tiene sistema anti-spam para evitar duplicados en el mismo día.
- Si no se define un canal con `/setcanal`, el bot intenta usar el primer canal donde tenga permisos.

---

## 📜 Licencia

Este proyecto se distribuye bajo la licencia incluida en `LICENSE`.
