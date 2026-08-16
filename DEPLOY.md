# Deploy en Vultr (Docker)

App = frontend (React/Vite estático) + backend (FastAPI) que necesita **LibreOffice**
y **poppler** para renderizar slides. Por eso corre en un VPS (no serverless).

Arquitectura en el servidor:

```
Internet :80
   │
   ▼
nginx (contenedor "web")  ── sirve el build del frontend
   │  proxy /api/*
   ▼
uvicorn/FastAPI (contenedor "backend")  ── LibreOffice + poppler
   │
   ▼
volumen "aurum_data" montado en /data  ── uploads, cache, training (~/.aurum)
```

Todo el estado persistente vive bajo `~/.aurum`; en el contenedor `HOME=/data`,
así que el volumen `aurum_data` lo preserva entre reinicios.

---

## 1. Crear el servidor en Vultr

- **Deploy New Server** → **Cloud Compute** (shared vCPU alcanza).
- OS: **Ubuntu 24.04 LTS**.
- Plan: **2 GB RAM mínimo** (LibreOffice headless necesita RAM; 1 GB puede quedar corto).
- Agregá tu SSH key.
- Anotá la IP pública.

## 2. Instalar Docker en el servidor

SSH al server (`ssh root@TU_IP`) y:

```bash
apt-get update && apt-get install -y ca-certificates curl git
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Verificá: `docker --version` y `docker compose version`.

## 3. Subir el código

Opción A — git (recomendado). Pushear este repo a GitHub/GitLab, luego en el server:

```bash
git clone TU_REPO_URL /opt/aurum
cd /opt/aurum
```

Opción B — sin git, copiar desde tu Mac:

```bash
rsync -av --exclude node_modules --exclude .venv --exclude dist \
  "/Users/joaquincardenas/Desktop/Proyecto Aurum/Proyecto encuestas/" root@TU_IP:/opt/aurum/
```

## 4. Configurar la API key

En el server, dentro de `/opt/aurum`:

```bash
cp .env.example .env
nano .env    # pegá tu REACT_APP_ANTHROPIC_API_KEY real
```

`.env` está gitignoreado — nunca se sube al repo.

## 5. Build + run

```bash
cd /opt/aurum
docker compose up -d --build
```

Primer build tarda (baja LibreOffice). Verificá:

```bash
docker compose ps
curl http://localhost/api/health     # -> {"status":"ok"}
```

Abrí `http://TU_IP` en el navegador.

## 6. Operación

```bash
docker compose logs -f            # ver logs
docker compose logs -f backend    # solo backend
docker compose restart            # reiniciar
docker compose down               # frenar (el volumen aurum_data queda)
docker compose up -d --build      # redeploy tras cambios de código
```

Actualizar código a mano (con git): `git pull && docker compose up -d --build`.
Para que esto pase solo en cada push, ver la sección siguiente.

---

## 7. Auto-deploy en cada push a `main` (opcional)

Un webhook en el VPS recibe el push de GitHub, valida la firma HMAC y corre el
deploy. Archivos ya en el repo: `deploy/deploy.sh`, `deploy/hooks.json`,
`deploy/webhook.service`.

```
git push main → GitHub webhook → VPS:9000/hooks/deploy-aurum
  → valida firma → git reset --hard origin/main → docker compose up -d --build
```

### 7.1 Instalar el webhook y preparar los archivos (en el VPS)

```bash
apt-get update && apt-get install -y webhook
chmod +x /opt/aurum/deploy/deploy.sh
```

### 7.2 Crear el secret (elegí una cadena larga y aleatoria)

Generá un secret y guardalo en un archivo **fuera del repo**:

```bash
SECRET=$(openssl rand -hex 32)
echo "GITHUB_WEBHOOK_SECRET=$SECRET" > /etc/aurum-webhook.env
chmod 600 /etc/aurum-webhook.env
echo "Tu secret (copialo para GitHub): $SECRET"
```

Anotá el secret impreso — lo pegás en GitHub en el paso 7.4.

### 7.3 Activar el servicio systemd

```bash
cp /opt/aurum/deploy/webhook.service /etc/systemd/system/aurum-webhook.service
systemctl daemon-reload
systemctl enable --now aurum-webhook
systemctl status aurum-webhook --no-pager     # debe decir "active (running)"
```

Abrí el **puerto 9000** en el firewall de Vultr (panel → Firewall), o con ufw:
`ufw allow 9000/tcp`.

### 7.4 Configurar el webhook en GitHub

En el repo → **Settings → Webhooks → Add webhook**:

- **Payload URL:** `http://TU_IP:9000/hooks/deploy-aurum`
- **Content type:** `application/json`
- **Secret:** el que imprimió el paso 7.2
- **Which events:** "Just the push event"
- **Active:** ✓

Guardá. GitHub manda un ping; en "Recent Deliveries" tenés que ver respuesta
`200`.

### 7.5 Probar

Hacé un cambio, `git push`. En el VPS:

```bash
tail -f /var/log/aurum-deploy.log      # ves el deploy corriendo
```

En ~1-2 min la nueva versión queda arriba. Si algo falla, revisá también
`journalctl -u aurum-webhook -f`.

Nota: el deploy hace `git reset --hard origin/main` (descarta cambios locales del
server). `.env` y `/etc/aurum-webhook.env` no se tocan porque están fuera del repo.

---

## Notas / pendientes

- **Firewall Vultr:** en el panel, permití **puerto 80** (y 22 para SSH). Sin eso no
  entra tráfico web.
- **HTTPS (recomendado antes de uso real):** poné un dominio apuntando a la IP y
  agregá TLS. Lo más simple: Caddy como reverse proxy, o `certbot` + nginx. No
  incluido acá para mantenerlo mínimo; se puede sumar después.
- **Export de PPTX:** ✅ resuelto — se descarga en el navegador (`FileResponse`).
- **Aislamiento multiusuario:** ✅ por sesión de navegador (header `X-Session-Id`).
  Uploads/recents/proyectos quedan aislados por navegador; sin login. Para cuentas
  reales con contraseña haría falta auth (proyecto aparte).
- **crypto.randomUUID:** en `http://IP` (sin HTTPS) el navegador no expone
  `crypto.randomUUID`; el frontend ya tiene fallback. Con HTTPS anda nativo.
- **RAM:** si LibreOffice falla al renderizar, subí el plan a 4 GB.
