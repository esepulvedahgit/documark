# documark

Aplicación web autoalojada para convertir documentos a Markdown usando
[MarkItDown](https://github.com/microsoft/markitdown), construida en Django.
Migración/evolución del MVP Flask original (`/opt/ConvMk-pdf`), ahora con
usuarios, roles, historial de conversiones y una UI moderna (Tailwind + HTMX).

## Características

- Login propio basado en sesiones Django (sin `django.contrib.auth`).
- Roles `admin` y `user`.
- Conversión de `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.csv`, `.json`, `.xml`, `.html`, `.txt`, `.epub`, `.zip` a Markdown.
- **Conversión en background (Celery + Redis)**: la request HTTP nunca espera a que
  termine; el navegador ve el estado en vivo ("procesando" → éxito/fallo) vía polling HTMX.
- Vista previa del Markdown y descarga del `.md`.
- Historial de conversiones (metadatos únicamente, nunca el contenido del documento),
  temporal: cada registro se borra por completo a las 24h.
- **Sin base de datos SQL**: metadatos e historial persisten como archivos cifrados con
  Fernet (Redis solo se usa como cola de tareas / cache de rate-limit, nunca datos de negocio).
- Expiración automática de resultados y limpieza de archivos temporales.
- Rate limiting en login, conversión y descarga.
- Expiración de sesión por inactividad.
- UI con Tailwind CSS y HTMX vía CDN.

## Cómo generar la clave Fernet

```bash
python scripts/generate_fernet_key.py
```

Copia el valor impreso en `.env` como `DOCUMARK_FERNET_KEY=...`. **Nunca la subas a git.**
Si no defines una clave en desarrollo, la app genera una temporal en memoria y
lo advierte en los logs (los datos cifrados se vuelven ilegibles al reiniciar).
En producción (`DOCUMARK_ENV=production`) la app **falla al arrancar** si falta la clave.

## Configurar `.env`

```bash
cp .env.example .env
```

Edita `.env` y define al menos: `DJANGO_SECRET_KEY`, `DOCUMARK_FERNET_KEY`,
`DOCUMARK_INITIAL_ADMIN_PASSWORD`. Ver la tabla completa de variables más abajo.

## Ejecutar con Docker

```bash
docker compose up --build
```

La app queda disponible en:

```text
http://localhost:8000
```

Esto levanta **4 servicios**:

| Servicio | Rol |
|---|---|
| `documark` | Web (Gunicorn) — recibe requests, encola conversiones |
| `celery_worker` | Ejecuta las conversiones en background |
| `celery_beat` | Dispara `cleanup_expired` periódicamente (cada `DOCUMARK_CLEANUP_INTERVAL_SECONDS`) |
| `redis` | Broker de Celery + cache de rate-limiting (sin datos de negocio) |

Al iniciar el servicio `documark` se ejecutan automáticamente (`scripts/entrypoint.sh`,
solo para ese servicio):
1. `create_initial_admin` — crea el admin inicial desde el `.env` si no existe.
2. `cleanup_expired` — limpia archivos temporales/expirados de una sesión anterior.

## Usuario admin inicial

Definido por `DOCUMARK_INITIAL_ADMIN_USERNAME` / `DOCUMARK_INITIAL_ADMIN_PASSWORD`
en `.env` (por defecto `admin` / `ChangeMe123!` — **cámbiala**). Se crea una sola
vez; si ya existe un usuario con ese nombre, no se toca.

## Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta de Django | `change-me` (debes cambiarla) |
| `DJANGO_DEBUG` | Modo debug | `True` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por coma | `localhost,127.0.0.1` |
| `DOCUMARK_ENV` | `development` o `production` | `development` |
| `DOCUMARK_FERNET_KEY` | Clave Fernet para cifrado en reposo | *(vacío en dev, obligatoria en prod)* |
| `DOCUMARK_MAX_UPLOAD_MB` | Tamaño máximo de archivo subido | `50` |
| `DOCUMARK_OUTPUT_TTL_SECONDS` | Cuánto queda descargable el `.md` (luego se borra el archivo, la entrada queda "expirada") | `7200` (2h) |
| `DOCUMARK_HISTORY_RETENTION_SECONDS` | Cuánto se conserva el *registro* del historial antes de borrarse por completo | `86400` (24h) |
| `DOCUMARK_SESSION_IDLE_SECONDS` | Expiración de sesión por inactividad | `1800` |
| `DOCUMARK_INITIAL_ADMIN_USERNAME/PASSWORD/EMAIL` | Admin inicial | `admin` / `ChangeMe123!` / `admin@example.local` |
| `CELERY_BROKER_URL` | Broker de Celery (Redis) | `redis://redis:6379/0` |
| `DOCUMARK_REDIS_CACHE_URL` | Cache de rate-limiting (Redis) | `redis://redis:6379/1` |
| `CELERY_WORKER_CONCURRENCY` | Conversiones simultáneas máximas | `2` |
| `DOCUMARK_CLEANUP_INTERVAL_SECONDS` | Cada cuánto corre `cleanup_expired` (Celery Beat) | `300` |

Ver `.env.example` para las variables adicionales de endurecimiento HTTPS
(`DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SECURE_HSTS_SECONDS`, etc.), a activar
una vez la app esté detrás de TLS.

## Seguridad

- **Contraseñas**: hasheadas con `django.contrib.auth.hashers` (nunca texto plano).
  Validador de fuerza propio (`apps/core/security.py`) exige ≥12 caracteres,
  mayúscula, minúscula, número y símbolo, más los validadores estándar de Django
  que bloquean contraseñas comunes y similares al nombre de usuario.
- **Sesiones**: `SESSION_ENGINE = signed_cookies` (sin base de datos). Expiran
  por inactividad (`DOCUMARK_SESSION_IDLE_SECONDS`) y se revalidan en cada
  request contra el repositorio de usuarios (`AuthContextMiddleware`), así que
  desactivar un usuario surte efecto de inmediato, no solo al vencer la cookie.
- **CSRF**: activo en todos los formularios (`{% csrf_token %}`); HTMX envía el
  token vía header `X-CSRFToken` (`static/js/app.js`).
- **Rate limiting** (`django-ratelimit` sobre `django-redis`, conteo atómico real):
  login 5/min por IP+usuario, conversión 10/hora por usuario, descarga 60/hora
  por usuario. El endpoint de estado (`/convert/status/<id>/`, polling HTMX)
  deliberadamente no tiene límite propio — un polling legítimo de una sola
  conversión larga puede superar 60 req/h por sí solo.
- **Uploads**: validación de extensión, tamaño y tipo MIME básico; nombres de
  archivo saneados + UUID (`apps/core/utils.py`), sin confiar nunca en el
  nombre original; protección anti path-traversal.
- **Headers de seguridad**: `X-Frame-Options: DENY`, `nosniff`,
  `Referrer-Policy: same-origin`; HSTS/SSL-redirect listos para activar en
  producción.
- **Logging**: eventos de login, conversión, descarga y limpieza, sin loguear
  jamás contenido de documentos, contraseñas o claves de cifrado.
- **Timeout de conversión**: documentos grandes/complejos (PDFs sobre todo, un PDF de
  40MB/863 páginas real tarda ~90-100s) ya no bloquean ninguna request HTTP — la
  conversión corre en `celery_worker`, no en Gunicorn. Dentro de esa tarea,
  `MarkItDownService` ejecuta la conversión real en un **subproceso** (`subprocess.Popen`,
  no `multiprocessing`: Celery corre las tareas en procesos *daemon* del pool `prefork`,
  y `multiprocessing.Process` no permite que un proceso daemon tenga hijos —
  `subprocess` no tiene esa restricción) con límite propio
  (`DOCUMARK_CONVERSION_TIMEOUT_SECONDS`, default 240s): si se excede, el proceso se
  mata y la conversión queda como `status="failed"` con mensaje amigable. Celery
  añade además su propio límite (`CELERY_TASK_TIME_LIMIT`), un poco mayor, como
  respaldo por si la tarea se cuelga por otra razón.
- **Recuperación ante fallos del worker**: `CELERY_TASK_ACKS_LATE` hace que, si
  `celery_worker` muere a mitad de una conversión, el mensaje se reentregue a otro
  worker en vez de perderse (probado matando el contenedor a mitad de una conversión
  real). Como red de seguridad adicional, `cleanup_stale_processing` (parte de
  `cleanup_expired`) marca como fallida cualquier conversión que lleve
  "processing" más tiempo del razonable, para que el usuario nunca vea un
  estado "procesando" indefinido.

## Cifrado en reposo

Todos los metadatos persistentes (`storage/secure/users.enc`,
`storage/secure/history.enc`) y los resultados `.md` mientras esperan
descarga (`storage/outputs/*.md.enc`) se cifran con `cryptography.Fernet`
(`apps/core/crypto.py`). El documento original solo existe en texto claro
durante el proceso de conversión y se borra inmediatamente después.

## Almacenamiento sin base de datos

No se usa PostgreSQL, SQLite ni el ORM de Django para datos de negocio.
Usuarios e historial se guardan como JSON cifrado en archivos, con bloqueo de
archivo (`fcntl`) para que varios workers de Gunicorn puedan escribir sin
corromperse. Los servicios (`apps/*/services/`) solo dependen de una interfaz
de repositorio abstracta (`BaseUserRepository`, `BaseHistoryRepository`), no
del almacenamiento concreto.

## Actualizando MarkItDown

MarkItDown publica versiones muy seguido. Para mantenerlo al día sin arriesgar
el resto de la app:

```bash
bash scripts/update_markitdown.sh   # reescribe el pin en requirements-markitdown.txt
docker compose up --build           # reconstruye con la versión nueva
pytest                               # valida que los formatos clave sigan funcionando
```

Todo el uso de la librería está aislado en
`apps/converter/services/markitdown_service.py`: si una versión nueva cambia
su API, solo ese archivo necesita ajustarse.

## Limitaciones

- El almacenamiento por archivos cifrados es apto para pocos usuarios.
- No es ideal para concurrencia alta (el bloqueo de archivo serializa las
  escrituras a cada archivo `.enc`).
- Para producción multiusuario real se recomienda migrar a PostgreSQL (ver abajo).
- Los documentos convertidos expiran (`DOCUMARK_OUTPUT_TTL_SECONDS`, 2h por
  defecto) y dejan de poder descargarse; el *registro* del historial (nombre,
  fecha, estado) se conserva un poco más, hasta `DOCUMARK_HISTORY_RETENTION_SECONDS`
  (24h por defecto), y luego se borra por completo — no queda nada permanente.
- Redis no tiene volumen persistente (a propósito — solo guarda cola/cache, no
  datos de negocio): si Redis se reinicia, las conversiones en cola/en curso en
  ese momento se pierden. `cleanup_stale_processing` detecta esos casos y los
  marca como fallidos en vez de dejarlos "procesando" para siempre; el usuario
  solo necesita volver a intentar la conversión.
- `CELERY_WORKER_CONCURRENCY` limita cuántas conversiones corren a la vez; con
  documentos muy grandes y concurrencia alta, considerar subir recursos del
  host antes que subir este número indiscriminadamente (cada conversión
  cargada — pandas/numpy/onnxruntime vía MarkItDown — usa memoria real).

## Roadmap

- PostgreSQL como backend de repositorios.
- `django.contrib.auth` / Django Admin (opcional, si se justifica).
- OCR de imágenes/escaneos.
- Integración IA/RAG sobre el historial convertido.

## Migrando a PostgreSQL (segunda etapa)

La arquitectura ya está preparada para esto sin tocar vistas ni servicios:

1. Definir modelos Django: `UserProfile` (o adoptar `django.contrib.auth.User`)
   y `ConversionHistory`, con los mismos campos que los dataclasses actuales
   (`apps/accounts/repositories/base.py:User`,
   `apps/converter/repositories/base.py:HistoryEntry`).
2. Implementar `DjangoUserRepository(BaseUserRepository)` y
   `DjangoHistoryRepository(BaseHistoryRepository)` sobre el ORM.
3. Cambiar `settings.DATABASES` a PostgreSQL y añadir `psycopg` a requirements.txt.
4. Generar y aplicar migraciones (`makemigrations` / `migrate`).
5. Cambiar las factorías `get_user_repository()` / `get_history_repository()`
   (en `apps/accounts/repositories/__init__.py` y
   `apps/converter/repositories/__init__.py`) para devolver las nuevas
   implementaciones.
6. Los servicios (`auth_service`, `conversion_service`, etc.) y las vistas no
   cambian: solo conocen la interfaz abstracta.

## Tests

```bash
pytest
```

Cubre cifrado/descifrado, hashing y fuerza de contraseñas, repositorios de
archivo (usuarios e historial), aislamiento/timeout del subproceso de
MarkItDown (con la librería real, no mockeada), y el flujo de conversión en
background (validación, transición de estados, idempotencia ante una
redelivery de Celery). Los tests corren con `CELERY_TASK_ALWAYS_EAGER=True`
(fixture `autouse` en `conftest.py`) — no necesitan un Redis real.

## Flujo de autenticación

`GET /login/` muestra el formulario → `POST /login/` (rate-limited 5/min por
IP+usuario) autentica contra `FileUserRepository` → la sesión guarda
`{user_id, username, role}` → cada request revalida que el usuario siga activo
y refresca la ventana de inactividad → `POST /logout/` limpia la sesión.

## Flujo de conversión

`GET /convert/` muestra el formulario → `POST /convert/` (HTMX, rate-limited
10/hora) → limpieza previa de temporales → valida el archivo → lo guarda con
nombre seguro + UUID → registra un `HistoryEntry` con `status="processing"` →
**encola la conversión en Celery y responde de inmediato** (nunca espera a que
termine) con un fragmento "procesando...".

El navegador hace polling HTMX (`hx-trigger="load delay:2s"`) contra
`GET /convert/status/<id>/` hasta que el estado deja de ser "processing". En
paralelo, `celery_worker` toma la tarea: MarkItDown convierte (en su propio
subproceso con timeout) → se borra el original → el `.md` se cifra en
`storage/outputs/` con fecha de expiración → se actualiza el historial a
`success`/`failed`. La siguiente respuesta de polling ya trae la vista previa +
botón de descarga (o el error), y al no incluir más directivas de polling, el
navegador deja de refrescar solo.

`GET /download/<id>/` (rate-limited 60/hora) verifica dueño/admin y que no haya
expirado, descifra en memoria y sirve el archivo como adjunto.
