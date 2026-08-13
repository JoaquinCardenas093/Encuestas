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

Actualizar código (con git): `git pull && docker compose up -d --build`.

---

## Notas / pendientes

- **Firewall Vultr:** en el panel, permití **puerto 80** (y 22 para SSH). Sin eso no
  entra tráfico web.
- **HTTPS (recomendado antes de uso real):** poné un dominio apuntando a la IP y
  agregá TLS. Lo más simple: Caddy como reverse proxy, o `certbot` + nginx. No
  incluido acá para mantenerlo mínimo; se puede sumar después.
- **Export de PPTX:** el endpoint `/api/export-pptx` hoy escribe el archivo en una
  ruta **del servidor** (`~/.aurum` vía volumen), no lo devuelve como descarga al
  navegador. Para uso remoto real conviene cambiarlo a devolver el archivo como
  download. Es cambio de código aparte, no bloquea el deploy.
- **Un solo usuario a la vez:** el modelo de proyecto no está pensado para
  concurrencia multiusuario con aislamiento. Para varios usuarios en paralelo hay
  que revisar el store de proyectos. OK para uso personal / pocos usuarios.
- **RAM:** si LibreOffice falla al renderizar, subí el plan a 4 GB.
