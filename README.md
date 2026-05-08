# 🎂 Birthday Bot — Discord

Bot de Discord que recuerda cumpleaños en tu servidor. Cada usuario puede guardar **una sola fecha**. A la hora configurada, el bot menciona al usuario y a `@everyone`.

---

## Comandos

| Comando | Descripción |
|---------|-------------|
| `!cumple DD/MM` | Guarda tu cumpleaños (ej: `!cumple 15/03`) |
| `!cumple DD/MM/AAAA` | Con año (ej: `!cumple 15/03/1995`) |
| `!micumple` | Muestra tu cumpleaños guardado |
| `!borrarcumple` | Elimina tu cumpleaños |
| `!cumples` | Lista todos los cumpleaños del servidor |
| `!testcumple` | (Solo admin) Prueba el mensaje de hoy |
| `!ayuda` | Muestra esta ayuda |

---

## 1. Crear el bot en Discord Developer Portal

1. Ir a https://discord.com/developers/applications
2. **New Application** → ponle un nombre
3. Tab **Bot** → **Add Bot**
4. Copiar el **Token** (lo necesitás después)
5. En **Privileged Gateway Intents** activar:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
6. Tab **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Mention Everyone`, `Read Message History`
7. Copiar la URL generada y usarla para invitar el bot a tu servidor

---

## 2. Configurar el proyecto

```bash
git clone https://github.com/TU_USUARIO/birthday-bot.git
cd birthday-bot

cp .env.example .env
nano .env          # Pegar tu DISCORD_TOKEN aquí
```

Variables opcionales en `docker-compose.yml`:
- `TIMEZONE` — zona horaria (default: `America/Lima`)
- `CHECK_HOUR` — hora de envío del mensaje (default: `8` = 8am)

---

## 3. Desplegar en Oracle Cloud Free Tier

### 3.1 Crear la instancia

1. Entrar a https://cloud.oracle.com
2. **Compute → Instances → Create Instance**
3. Shape recomendado (gratuito): **VM.Standard.A1.Flex** (ARM, 1 OCPU, 6 GB RAM)
   - O `VM.Standard.E2.1.Micro` (AMD x86) — también gratuito
4. Imagen: **Ubuntu 22.04**
5. Agregar tu clave SSH pública
6. Crear la instancia y anotar la IP pública

### 3.2 Abrir puerto en el firewall de Oracle

En **Networking → Virtual Cloud Networks → tu VCN → Security Lists → Ingress Rules**,
no necesitás abrir puertos para el bot (solo hace conexiones salientes a Discord).

### 3.3 Conectarse a la instancia

```bash
ssh ubuntu@<IP_PUBLICA>
```

### 3.4 Instalar Docker en la instancia

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Instalar Docker Compose
sudo apt install -y docker-compose-plugin
docker compose version   # verificar
```

### 3.5 Subir el proyecto (opción A — GitHub)

```bash
git clone https://github.com/TU_USUARIO/birthday-bot.git
cd birthday-bot
cp .env.example .env
nano .env   # pegar tu token
```

### 3.5 Subir el proyecto (opción B — SCP directo)

Desde tu máquina local:
```bash
scp -r ./birthday-bot ubuntu@<IP_PUBLICA>:~/birthday-bot
```

Luego en la instancia:
```bash
cd ~/birthday-bot
cp .env.example .env && nano .env
```

### 3.6 Arrancar el bot

```bash
docker compose up -d --build

# Ver logs en tiempo real
docker compose logs -f

# Detener
docker compose down
```

---

## 4. Comandos útiles de operación

```bash
# Estado del contenedor
docker compose ps

# Reiniciar
docker compose restart

# Ver datos guardados
docker compose exec birthday-bot cat /data/birthdays.json

# Actualizar el bot (después de un git pull)
git pull
docker compose up -d --build
```

---

## 5. Persistencia de datos

Los cumpleaños se guardan en un volumen Docker (`birthday_data`).
Los datos **sobreviven** reinicios y actualizaciones del contenedor.

Para hacer backup:
```bash
docker compose exec birthday-bot cat /data/birthdays.json > backup.json
```

---

## Estructura del proyecto

```
birthday-bot/
├── bot.py              # Código del bot
├── requirements.txt    # Dependencias Python
├── Dockerfile          # Imagen Docker
├── docker-compose.yml  # Orquestación
├── .env.example        # Template de variables
├── .gitignore          # Excluye .env y datos
└── README.md
```
