# Kayendar

> Lightweight CalDAV/CardDAV server with a modern, glassmorphism web client for your homelab.
> Servidor CalDAV/CardDAV ligero con un cliente web moderno y de estilo "glassmorphism" para tu homelab.

[![Docker Image](https://img.shields.io/badge/Docker-ghcr.io%2Fsnchz%2Fkayendar-blue)](https://ghcr.io/snchz/kayendar)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 🌐 Choose Language / Elige Idioma
- [🇺🇸 English Version](#english-version)
- [🇪🇸 Versión en Español](#versión-en-español)

---

<a name="english-version"></a>
# 🇺🇸 English Version

Kayendar is a simple, lightweight, and self-hosted CalDAV/CardDAV server designed to sync your calendars and contacts across devices (iOS, Android, Thunderbird, One Calendar) while providing a premium, interactive web interface.

## Features

- 📅 **CalDAV Server** — Full calendar synchronization with iOS, Android (DAVx⁵/OpenSync), Thunderbird, and One Calendar.
- 📇 **CardDAV Server** — Contact synchronization with standard clients.
- 🌐 **Modern SPA Web Client** — Gorgeous glassmorphic user interface supporting month/week views, event creation, and contacts management.
- 📍 **Enhanced Event Metadata** — Full support for event **Locations** and **Reminders (Alarms)** synchronized bidirectionally.
- 🔐 **Secure Authentication** — Basic Authentication for DAV clients and secure session cookies for the web app.
- 💾 **File-Based Storage** — Flat files (`.ics` for events, `.vcf` for contacts) under a simple directory tree. No complex database to configure or backup!
- 🐳 **Docker-Ready** — Extremely lightweight Python container, running without heavy dependencies. Perfect for homelab setups (Caddy, Traefik, Dockge, etc.).

---

## Quick Start

### 1. Docker Compose (Recommended)

Using Docker Compose is the easiest way to deploy Kayendar. Create a `docker-compose.yml` file:

```yaml
services:
  kayendar:
    image: ghcr.io/snchz/kayendar:latest
    # To build the image locally instead:
    # build: .
    container_name: kayendar
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - kayendar_data:/data
    environment:
      KAYENDAR_DATA_DIR: /data
      KAYENDAR_HOST: 0.0.0.0
      KAYENDAR_PORT: 8000
      # IMPORTANT: Change this to a long random string!
      KAYENDAR_SECRET_KEY: "change-me-to-a-long-random-string"
      
      # --- User Auto-Provisioning ---
      # If these variables are set, Kayendar will automatically create
      # this user on startup if the database is empty.
      KAYENDAR_ADMIN_USER: "admin"
      KAYENDAR_ADMIN_PASSWORD: "your-secure-password"
      
      # --- Logging ---
      # Set to "true" to enable verbose CalDAV/CardDAV debug logs.
      KAYENDAR_LOG_DEBUG: "false"
      
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/dav/', method='OPTIONS')"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3

volumes:
  kayendar_data:
    driver: local
```

#### Run the server:
```bash
# Pull the latest image and start
docker compose pull
docker compose up -d
```

Once started, open `http://localhost:8000` in your browser. You can log in using the credentials defined in `KAYENDAR_ADMIN_USER` and `KAYENDAR_ADMIN_PASSWORD`.

### 2. Local Setup (Development)

If you want to run Kayendar directly using Python on your host:

```bash
# Clone the repository
git clone https://github.com/snchz/kayendar
cd kayendar

# Install dependencies
pip install -r requirements-dev.txt

# Option A: Run with auto-provisioning environment variables
export KAYENDAR_ADMIN_USER="admin"
export KAYENDAR_ADMIN_PASSWORD="your-secure-password"
python -m server

# Option B: Or manually create a user first via CLI
python manage.py adduser admin
python -m server
```

---

## User Management

If you prefer to manage users via command line, you can use the CLI tool.

### Using Docker:
```bash
# Add a new user
docker exec -it kayendar python manage.py adduser <username>

# List all registered users
docker exec -it kayendar python manage.py listusers

# Delete a user
docker exec -it kayendar python manage.py deluser <username>
```

### Using Local Python:
```bash
# Add a user
python manage.py adduser <username>

# List users
python manage.py listusers

# Delete a user
python manage.py deluser <username>
```

---

## Client Connection Guide

To sync your client devices with Kayendar, use the following guidelines:

> [!IMPORTANT]
> **Base URL Format:**
> Always use your username in the URL path.
> - **URL:** `http://<your-server-ip>:8000/dav/<username>/`
> - **Note:** Many clients (especially iOS) **require** the trailing slash `/` at the end of the URL.

### 📱 Android (DAVx⁵ / OpenSync)
Since Android does not support CalDAV/CardDAV natively, you must use a sync adapter like **DAVx⁵** (available on F-Droid for free, or Google Play Store).
1. Open DAVx⁵ and tap **Add Account** (`+`).
2. Select **Login with URL and user credentials**.
3. **Base URL:** Enter `http://<your-server-ip>:8000/dav/` (DAVx⁵ supports automatic collection discovery!).
4. Enter your **Username** and **Password**.
5. Once authenticated, select the Calendars and Contacts folders you want to sync, and set your desired synchronization interval.

### 🍏 iOS (iPhone / iPad) & macOS
1. Open **Settings** → **Calendar** (or **Contacts**) → **Accounts** → **Add Account**.
2. Tap **Other** → **Add CalDAV Account** (or **Add CardDAV Account**).
3. Select **Manual** setup.
4. **Server:** `http://<your-server-ip>:8000/dav/<username>/` (Ensure the trailing `/` is present!).
5. **Username:** `<username>`
6. **Password:** `<password>`
7. *Note:* If you are connecting over unencrypted HTTP (local IP), iOS will display a warning that the connection is unencrypted. Select **Continue** or **Save** to proceed anyway.

### 📅 One Calendar
1. Add a new account and choose **CalDAV**.
2. Enter your server URL: `http://<your-server-ip>:8000/dav/<username>/`.
3. Fill in your username and password.
4. > [!IMPORTANT]
   > **Enable HTTP Communication:** By default, One Calendar rejects non-SSL (HTTP) connections. In the account setup/connection settings, you **must enable the option to allow HTTP / insecure connections**, or the sync will fail silently.

### ✉️ Thunderbird
1. Go to Calendar → right-click the calendar list → **New Calendar...**
2. Choose **On the Network**.
3. Username: `<username>`
4. Location: `http://<your-server-ip>:8000/dav/<username>/personal/` (or the specific calendar path).
5. Click **Find Calendars** and enter your password when prompted.

---

## Web Client Features

Kayendar includes a modern, responsive web application out of the box:
- **Month & Week Grid**: Fully interactive views for calendar events.
- **Bidirectional Locations & Reminders**:
  - You can view and edit event **Locations** directly in the web UI.
  - You can configure **Reminders** (Alarms) on the web.
  - The backend safely stores CalDAV `VALARM` components. Editing event titles or descriptions on the web client **will not erase or overwrite** the alarms/locations you configured on your phone.

---

## Troubleshooting & FAQ

### ❌ Docker permission errors / nginx cache failures
* **Symptom:** Logs show `nginx: [emerg] open() "/var/cache/nginx/.../client_temp" failed (13: Permission denied)`.
* **Cause:** An older version of the Docker image used Nginx inside the container, causing conflicts when running under custom non-root users (`user: 1000:1000`).
* **Solution:** The container has been updated to run purely on Python. To fix this:
  1. Run `docker compose pull` to grab the latest Python-only image.
  2. Alternatively, force a local build from source by uncommenting `build: .` in your `docker-compose.yml` and running `docker compose up --build`.

### ❌ Android/iOS XML namespace parsing errors
* **Symptom:** App fails to add the calendar and shows errors like:
  `xml messagewitherrorposition`, `xml dupattributename, 2, 128`, or generic XML validation errors.
* **Cause:** Strict mobile DAV clients reject duplicate XML namespace attributes or invalid element prefix serializations.
* **Solution:** This is fully resolved in the latest server release by globally registering XML namespaces (`DAV:`, `caldav`, etc.) and generating compliant ElementTree structures. Please pull the latest version of the server.

### 🔄 Changes made on the Web App do not sync to my Phone
* **Symptom:** Adding an event on the phone shows up on the web UI, but adding an event on the web UI does not show up on the phone.
* **Cause:** CalDAV clients fetch updates only when the collection's `getctag` (Collection Tag) changes. 
* **Solution:** The server calculates the `getctag` dynamically using the last modification time (`mtime`) of the calendar directory. Whenever you add/edit/delete an event on the web UI, the calendar directory `mtime` updates, triggering the phone client to sync.
* **Tip:** Check the sync interval settings in your mobile client (e.g. DAVx⁵) to ensure it is syncing automatically.

### 🔒 How do I enable HTTPS?
For security, it is highly recommended to run Kayendar behind a reverse proxy (such as Caddy, Nginx, or Traefik) when exposing it outside your local network.
Example Caddy configuration:
```caddy
kayendar.yourdomain.com {
    reverse_proxy localhost:8000
}
```
If running behind HTTPS, make sure to set the environment variable:
`KAYENDAR_SECURE_COOKIES=true`

---

## Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `KAYENDAR_DATA_DIR` | `data` | Directory where calendars, contacts, and users are stored |
| `KAYENDAR_SECRET_KEY` | *(insecure default)* | Key used to sign session cookies for the web client. **Change this!** |
| `KAYENDAR_SECURE_COOKIES` | `false` | Set to `true` when running behind an HTTPS reverse proxy |
| `KAYENDAR_HOST` | `0.0.0.0` | IP address the server binds to |
| `KAYENDAR_PORT` | `8000` | Port the server listens on |
| `KAYENDAR_DEV` | `false` | Enables development auto-reload |
| `KAYENDAR_ADMIN_USER` | `None` | (Optional) Creates an admin user automatically on startup if empty |
| `KAYENDAR_ADMIN_PASSWORD` | `None` | Password for the auto-provisioned admin user |
| `KAYENDAR_LOG_DEBUG` | `false` | Set to `true` to enable verbose CalDAV/CardDAV debug logging |

---

<a name="versión-en-español"></a>
# 🇪🇸 Versión en Español

Kayendar es un servidor CalDAV/CardDAV simple, ligero y autoalojado diseñado para sincronizar tus calendarios y contactos en todos tus dispositivos (iOS, Android, Thunderbird, One Calendar) mientras ofrece una interfaz web interactiva y premium.

## Características

- 📅 **Servidor CalDAV** — Sincronización completa de calendarios con iOS, Android (DAVx⁵/OpenSync), Thunderbird y One Calendar.
- 📇 **Servidor CardDAV** — Sincronización de contactos con clientes estándar.
- 🌐 **Cliente Web SPA Moderno** — Preciosa interfaz de usuario con estilo "glassmorphism" que admite vistas mensuales/semanales, creación de eventos y gestión de contactos.
- 📍 **Metadatos de Eventos Mejorados** — Soporte completo para **Ubicaciones** y **Recordatorios (Alarmas)** de eventos sincronizados bidireccionalmente.
- 🔐 **Autenticación Segura** — Autenticación básica (Basic Auth) para clientes DAV y cookies de sesión seguras para la aplicación web.
- 💾 **Almacenamiento Basado en Archivos** — Archivos planos (`.ics` para eventos, `.vcf` para contactos) bajo un árbol de directorios simple. ¡Sin bases de datos complejas que configurar o respaldar!
- 🐳 **Listo para Docker** — Contenedor Python extremadamente ligero, que se ejecuta sin dependencias pesadas. Perfecto para entornos domésticos (Caddy, Traefik, Dockge, etc.).

---

## Inicio Rápido

### 1. Docker Compose (Recomendado)

Usar Docker Compose es la forma más sencilla de desplegar Kayendar. Crea un archivo `docker-compose.yml`:

```yaml
services:
  kayendar:
    image: ghcr.io/snchz/kayendar:latest
    # Para construir la imagen localmente:
    # build: .
    container_name: kayendar
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - kayendar_data:/data
    environment:
      KAYENDAR_DATA_DIR: /data
      KAYENDAR_HOST: 0.0.0.0
      KAYENDAR_PORT: 8000
      # IMPORTANTE: ¡Cambia esto por una cadena larga y aleatoria!
      KAYENDAR_SECRET_KEY: "change-me-to-a-long-random-string"
      
      # --- Auto-Aprovisionamiento de Usuario ---
      # Si se definen estas variables, Kayendar creará automáticamente
      # este usuario en el primer arranque si la base de datos está vacía.
      KAYENDAR_ADMIN_USER: "admin"
      KAYENDAR_ADMIN_PASSWORD: "tu-contraseña-segura"
      
      # --- Registro de Logs ---
      # Establécelo en "true" para activar los registros de depuración detallados de CalDAV/CardDAV.
      KAYENDAR_LOG_DEBUG: "false"
      
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/dav/', method='OPTIONS')"]
      interval: 30s
      timeout: 5s
      start_period: 10s
      retries: 3

volumes:
  kayendar_data:
    driver: local
```

#### Ejecutar el servidor:
```bash
# Descargar la última versión de la imagen e iniciar
docker compose pull
docker compose up -d
```

Una vez iniciado, abre `http://localhost:8000` en tu navegador. Puedes iniciar sesión con las credenciales definidas en `KAYENDAR_ADMIN_USER` y `KAYENDAR_ADMIN_PASSWORD`.

### 2. Configuración Local (Desarrollo)

Si prefieres ejecutar Kayendar directamente usando Python en tu máquina:

```bash
# Clonar el repositorio
git clone https://github.com/snchz/kayendar
cd kayendar

# Instalar dependencias
pip install -r requirements-dev.txt

# Opción A: Ejecutar con variables de entorno de auto-aprovisionamiento
export KAYENDAR_ADMIN_USER="admin"
export KAYENDAR_ADMIN_PASSWORD="tu-contraseña-segura"
python -m server

# Opción B: O crear manualmente un usuario primero a través de la CLI
python manage.py adduser admin
python -m server
```

---

## Gestión de Usuarios

Si prefieres gestionar usuarios a través de la línea de comandos, puedes usar la herramienta CLI incorporada.

### Usando Docker:
```bash
# Añadir un nuevo usuario
docker exec -it kayendar python manage.py adduser <usuario>

# Listar todos los usuarios registrados
docker exec -it kayendar python manage.py listusers

# Eliminar un usuario
docker exec -it kayendar python manage.py deluser <usuario>
```

### Usando Python Local:
```bash
# Añadir un usuario
python manage.py adduser <usuario>

# Listar usuarios
python manage.py listusers

# Eliminar un usuario
python manage.py deluser <usuario>
```

---

## Guía de Conexión de Clientes

Para sincronizar tus dispositivos con Kayendar, sigue estas pautas:

> [!IMPORTANT]
> **Formato de URL Base:**
> Usa siempre tu nombre de usuario en la ruta de la URL.
> - **URL:** `http://<ip-de-tu-servidor>:8000/dav/<usuario>/`
> - **Nota:** Muchos clientes (especialmente iOS) **requieren** la barra diagonal/slash final `/` al final de la URL.

### 📱 Android (DAVx⁵ / OpenSync)
Dado que Android no admite CalDAV/CardDAV de forma nativa, debes usar un adaptador de sincronización como **DAVx⁵** (disponible de forma gratuita en F-Droid, o en Google Play Store).
1. Abre DAVx⁵ y toca **Añadir cuenta** (`+`).
2. Selecciona **Iniciar sesión con URL y datos de acceso**.
3. **URL base:** Introduce `http://<ip-de-tu-servidor>:8000/dav/` (¡DAVx⁵ admite el descubrimiento automático de colecciones!).
4. Introduce tu **Usuario** y **Contraseña**.
5. Una vez autenticado, selecciona los calendarios y libretas de contactos que deseas sincronizar y define el intervalo de sincronización deseado.

### 🍏 iOS (iPhone / iPad) & macOS
1. Ve a **Ajustes** → **Calendario** (o **Contactos**) → **Cuentas** → **Añadir cuenta**.
2. Toca **Otra** → **Añadir cuenta CalDAV** (o **Añadir cuenta CardDAV**).
3. Selecciona configuración **Manual**.
4. **Servidor:** `http://<ip-de-tu-servidor>:8000/dav/<usuario>/` (¡Asegúrate de que la barra `/` final esté presente!).
5. **Usuario:** `<usuario>`
6. **Contraseña:** `<contraseña>`
7. *Nota:* Si te estás conectando a través de HTTP sin cifrar (IP local), iOS mostrará una advertencia indicando que la conexión no es segura. Selecciona **Continuar** o **Guardar** para proceder de todos modos.

### 📅 One Calendar
1. Añade una nueva cuenta y elige **CalDAV**.
2. Introduce la URL de tu servidor: `http://<ip-de-tu-servidor>:8000/dav/<usuario>/`.
3. Introduce tu usuario y contraseña.
4. > [!IMPORTANT]
   > **Habilitar comunicación HTTP:** Por defecto, One Calendar rechaza conexiones que no sean SSL (HTTP). En la configuración de la cuenta/conexión, **debes habilitar la opción de permitir comunicación HTTP / conexiones inseguras**, o de lo contrario la sincronización fallará en silencio.

### ✉️ Thunderbird
1. Ve a Calendario → clic derecho en la lista de calendarios → **Nuevo calendario...**
2. Elige **En la red**.
3. Usuario: `<usuario>`
4. Ubicación: `http://<ip-de-tu-servidor>:8000/dav/<usuario>/personal/` (o la ruta específica del calendario).
5. Haz clic en **Buscar calendarios** e introduce tu contraseña cuando se te solicite.

---

## Características del Cliente Web

Kayendar incluye una aplicación web moderna y adaptable:
- **Vista de Mes y Semana**: Cuadrículas interactivas para gestionar tus eventos.
- **Ubicaciones y Recordatorios Bidireccionales**:
  - Puedes ver y editar las **Ubicaciones** de los eventos directamente en la web.
  - Puedes configurar **Recordatorios** (Alarmas) desde la web.
  - El backend almacena de forma segura los componentes CalDAV `VALARM`. Editar el título o la descripción de un evento en el cliente web **no borrará ni sobrescribirá** las alarmas o ubicaciones que hayas configurado desde tu teléfono.

---

## Resolución de Problemas y FAQ (Preguntas Frecuentes)

### ❌ Errores de permisos en Docker / Fallos en la caché de nginx
* **Síntoma:** Los logs muestran `nginx: [emerg] open() "/var/cache/nginx/.../client_temp" failed (13: Permission denied)`.
* **Causa:** Una versión anterior de la imagen de Docker utilizaba Nginx dentro del contenedor, lo que provocaba conflictos de permisos al ejecutarse con usuarios no raíz personalizados (`user: 1000:1000`).
* **Solución:** El contenedor se ha actualizado para ejecutarse puramente en Python. Para solucionarlo:
  1. Ejecuta `docker compose pull` para obtener la última imagen basada únicamente en Python.
  2. Alternativamente, fuerza una construcción local desde el código fuente desmarcando la línea `build: .` en tu `docker-compose.yml` y ejecutando `docker compose up --build`.

### ❌ Errores de análisis XML en Android/iOS (Namespaces)
* **Síntoma:** La aplicación no puede añadir el calendario y muestra errores como:
  `xml messagewitherrorposition`, `xml dupattributename, 2, 128`, o errores genéricos de validación XML.
* **Causa:** Los clientes DAV móviles estrictos rechazan atributos XML duplicados o serializaciones de prefijos de elementos no válidos.
* **Solución:** Esto está completamente resuelto en la última versión del servidor registrando globalmente los espacios de nombres XML (`DAV:`, `caldav`, etc.) y generando estructuras de ElementTree totalmente compatibles. Por favor, descarga la última versión del servidor.

### 🔄 Los cambios realizados en la App Web no se sincronizan en mi teléfono
* **Síntoma:** Añadir un evento en el teléfono aparece en la interfaz web, pero añadir un evento en la interfaz web no aparece en el teléfono.
* **Causa:** Los clientes CalDAV solo buscan actualizaciones cuando el `getctag` (Collection Tag) de la colección cambia.
* **Solución:** El servidor calcula el `getctag` dinámicamente utilizando el tiempo de última modificación (`mtime`) del directorio del calendario. Cada vez que añades/editas/eliminas un evento en la web, el `mtime` del directorio se actualiza, indicándole al cliente del teléfono que debe sincronizarse.
* **Consejo:** Verifica los ajustes de intervalo de sincronización en tu cliente móvil (por ejemplo, en DAVx⁵) para asegurarte de que se sincroniza automáticamente.

### 🔒 ¿Cómo habilito HTTPS?
Por seguridad, se recomienda encarecidamente ejecutar Kayendar detrás de un proxy inverso (como Caddy, Nginx o Traefik) cuando se exponga fuera de la red local.
Ejemplo de configuración para Caddy:
```caddy
kayendar.tudominio.com {
    reverse_proxy localhost:8000
}
```
Si se ejecuta bajo HTTPS, asegúrate de establecer la variable de entorno:
`KAYENDAR_SECURE_COOKIES=true`

---

## Referencia de Variables de Entorno

| Variable | Por Defecto | Descripción |
|---|---|---|
| `KAYENDAR_DATA_DIR` | `data` | Directorio donde se guardan calendarios, contactos y usuarios |
| `KAYENDAR_SECRET_KEY` | *(inseguro por defecto)* | Clave para firmar las cookies de sesión web. **¡Cámbiala!** |
| `KAYENDAR_SECURE_COOKIES` | `false` | Establécelo en `true` cuando corra detrás de un proxy HTTPS |
| `KAYENDAR_HOST` | `0.0.0.0` | Dirección IP a la que se enlaza el servidor |
| `KAYENDAR_PORT` | `8000` | Puerto en el que escucha el servidor |
| `KAYENDAR_DEV` | `false` | Habilita el reinicio automático en desarrollo |
| `KAYENDAR_ADMIN_USER` | `None` | (Opcional) Crea un administrador inicial al arrancar si está vacío |
| `KAYENDAR_ADMIN_PASSWORD` | `None` | Contraseña para el administrador inicial auto-aprovisionado |
| `KAYENDAR_LOG_DEBUG` | `false` | Establécelo en `true` para activar el registro de depuración detallado de CalDAV/CardDAV |

---

## Estructura del Proyecto

```
kayendar/
├── server/               # Backend en Python y Cliente Web Estático
│   ├── app.py            # Aplicación FastAPI y Auto-Aprovisionamiento
│   ├── auth.py           # Lógica de Autenticación (PBKDF2 Hashing)
│   ├── storage.py        # Almacenamiento plano de Calendarios y Contactos (ICS/VCF)
│   ├── dav.py            # Endpoints del protocolo CalDAV/CardDAV
│   ├── web.py            # API REST para el cliente web SPA
│   └── static/           # Fuentes de la web SPA (HTML, CSS, JS)
├── manage.py             # Utilidad CLI para gestión de usuarios
├── tests/                # Pruebas Unitarias y E2E
├── Dockerfile            # Imagen Docker basada en Python
└── docker-compose.yml    # Plantilla de Docker Compose
```

---

## Licencia

MIT © [snchz](https://github.com/snchz)