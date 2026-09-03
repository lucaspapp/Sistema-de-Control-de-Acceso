# GoldenJack · Control de acceso por reconocimiento facial

Aplicación local para detectar personas en cámaras configuradas en Frigate y generar alertas cuando se reconoce a un perfil restringido. El sistema permite administrar desde una web dos tipos de perfiles: **prohibidos** y **autoexcluidos**.

> El reconocimiento facial requiere una finalidad legítima, autorización, medidas de seguridad y revisión humana. No se deben versionar ni compartir imágenes de referencia, grabaciones, credenciales o bases de datos de producción.

## Qué hace

- Frigate detecta objetos `person` en las cámaras RTSP y publica los eventos mediante MQTT.
- `sistema.py` recibe cada tracking, solicita una captura a Frigate y recorta la persona detectada.
- OpenCV detecta el rostro y lo compara con las referencias de perfiles activos.
- Si hay coincidencia, se guarda una alerta y una captura local.
- El panel web permite iniciar sesión, crear y eliminar perfiles, consultar el historial y ver la cámara y la última alerta.
- Las fotos cargadas se validan antes de guardarse: deben contener un rostro claro y detectable.
- El panel consulta alertas cada 1,5 segundos y se actualiza automáticamente cuando se registra una nueva.

## Arquitectura

```text
Cámara RTSP
   │
   ▼
Frigate ── eventos MQTT ──► sistema.py ──► SQLite + capturas
   │                              │                 │
   └── snapshots / vista web ─────┘                 ▼
                                           webapp.py (Flask)
                                                │
                                                ▼
                                        Panel en http://localhost:8080
```

## Componentes

| Componente | Responsabilidad |
| --- | --- |
| `docker-compose.yml` | Ejecuta Frigate y Mosquitto. |
| `config/config.yml` | Configuración local de Frigate, cámaras y MQTT. |
| `src/access_control/sistema.py` | Escucha eventos MQTT y dispara el reconocimiento. |
| `src/access_control/face.py` | Detecta rostros, genera embeddings y compara referencias. |
| `src/access_control/webapp.py` | Panel web y API de última alerta. |
| `src/access_control/prohibited_store.py` | Persistencia SQLite, perfiles y alertas. |
| `runtime/access_control/` | Base SQLite, fotos de perfiles y capturas generadas. No se versiona. |

## Requisitos

- Windows con Docker Desktop y Docker Compose.
- Python 3.11 o superior. El proyecto incluye `scripts/start_windows.bat`, que busca `analisis-caras/.venv` y, como alternativa, `.venv-system`.
- Una o más cámaras RTSP configuradas en Frigate.
- Los modelos de OpenCV indicados en [assets/models/README.md](assets/models/README.md).

## Instalación

1. Creá el entorno e instalá las dependencias:

   ```powershell
   py -m venv .venv-system
   .\.venv-system\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Copiá `.env.example` a `.env` y completá la conexión local con Frigate y MQTT. Usá una clave larga y aleatoria para `WEB_SECRET_KEY`.

3. Copiá [config/examples/frigate.yml.example](config/examples/frigate.yml.example) como `config/config.yml`. Configurá las direcciones RTSP, las dimensiones reales del stream y las credenciales locales.

4. Incorporá en `assets/models/` los dos modelos necesarios para reconocimiento facial:

   - `face_detection_yunet_2023mar.onnx`
   - `face_recognition_sface_2021dec.onnx`

5. Iniciá Frigate y Mosquitto:

   ```powershell
   docker compose up -d
   ```

6. Iniciá el monitor y el panel:

   ```powershell
   .\.venv-system\Scripts\python.exe src\access_control\sistema.py
   .\.venv-system\Scripts\python.exe src\access_control\webapp.py
   ```

   También se pueden abrir ambos procesos con:

   ```powershell
   scripts\start_windows.bat
   ```

7. Abrí `http://localhost:8080`. Si todavía no hay usuarios, registrá la primera cuenta desde el panel.

## Uso del panel

1. Iniciá sesión.
2. En **Prohibidos** o **Autoexcluidos**, seleccioná **Agregar**.
3. Completá los datos y subí una foto frontal, bien iluminada y sin filtros. En prohibidos, también se requiere quién informó el caso y el motivo.
4. El perfil queda disponible para reconocimiento en un máximo de 30 segundos, sin reiniciar el monitor.
5. Cuando Frigate detecte una persona y el rostro coincida, el sistema guarda la captura y el panel muestra la alerta más reciente automáticamente.

La foto de referencia debe contener un rostro suficientemente grande, de frente y nítido. Si no supera la detección, el panel no guardará el perfil y explicará el motivo.

## Datos locales y seguridad

Los siguientes datos son locales y están ignorados por Git:

- `.env` y `config/config.yml`
- `runtime/` (SQLite, imágenes de referencia y capturas de alertas)
- `media/`, modelos de visión y datos de Mosquitto

Antes de compartir el proyecto, verificá que no haya contraseñas RTSP/MQTT, secretos de sesión, fotos de referencia ni bases SQLite en archivos versionados. Si una credencial se expuso, debe reemplazarse; ocultarla en un commit posterior no elimina el historial.

## Solución de problemas

| Problema | Revisión recomendada |
| --- | --- |
| No aparece ninguna cámara | Verificá que Frigate esté en ejecución y que `FRIGATE_URL` apunte a `http://127.0.0.1:5000`. |
| El monitor no recibe eventos | Confirmá MQTT en `config/config.yml`, Mosquitto en el puerto 7777 y que Frigate detecte `person`. |
| La foto es rechazada | Usá una imagen JPG, PNG o WEBP con una cara frontal, nítida y bien iluminada. |
| El perfil no genera alerta | Esperá hasta 30 segundos tras el alta y revisá que la cara en cámara tenga tamaño, luz y enfoque suficientes. |
| El panel no refleja cambios | Reiniciá `webapp.py` después de actualizar código; las nuevas alertas se refrescan solas. |

## Licencia

Ver [LICENSE](LICENSE).
