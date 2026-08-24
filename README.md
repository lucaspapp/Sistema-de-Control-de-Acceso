# Sistema de Control de Acceso con Visión Artificial

Proyecto que integra **Frigate**, **MQTT** y Python para registrar el tránsito de personas por zonas de una cámara, estimar rango etario y género, y generar alertas cuando una persona coincide con una referencia local autorizada.

> El reconocimiento facial es una funcionalidad sensible. Debe utilizarse solo con una finalidad legítima, consentimiento o una base legal válida, medidas de seguridad y revisión humana. El repositorio no incluye caras de referencia, grabaciones, credenciales ni datos de producción.

## Qué resuelve

- Consume eventos de detección de personas publicados por Frigate vía MQTT.
- Determina entradas y salidas mediante secuencias de zonas configuradas.
- Solicita un análisis de edad y género a un servicio Python independiente.
- Compara rostros contra referencias locales autorizadas y guarda alertas locales.
- Presenta métricas en un dashboard de escritorio y guarda resúmenes JSON/Excel.

## Arquitectura

```text
Cámara RTSP → Frigate → MQTT ─┬→ detect.py (edad y género)
                              └→ sistema.py → dashboard.py
                                              └→ runtime/ (métricas y alertas)
```

## Estructura

```text
src/access_control/     Código principal de la aplicación
assets/models/          Modelos locales de visión (no versionados)
assets/restricted_faces/ Referencias faciales autorizadas (no versionadas)
config/examples/        Plantillas de configuración sin secretos
runtime/                Datos, alertas y estadísticas generadas (no versionados)
scripts/                Utilidades de arranque
mosquitto/              Configuración del broker local
legacy/                 Prototipos conservados como referencia
```

## Requisitos

- Dos entornos de Python: el de detección usa Python 3.11 y el del sistema/dashboard usa Python 3.14 en esta instalación.
- Docker Desktop con Docker Compose, para Frigate y Mosquitto.
- Una cámara RTSP configurada localmente (opcional para desarrollar la interfaz).
- Los modelos indicados en [`assets/models/README.md`](assets/models/README.md).

## Puesta en marcha

1. Esta copia conserva los dos entornos locales que ya utilizaba el proyecto:

   | Proceso | Entorno local | Versión comprobada |
   | --- | --- | --- |
   | `detect.py` | `analisis-caras/venv` | Python 3.11.9 |
   | `sistema.py` y `dashboard.py` | `analisis-caras/.venv` | Python 3.14.5 |

   El script de arranque los detecta automáticamente. No los subas a GitHub.

   Para una copia nueva del repositorio, creá `.venv-detect` con Python 3.11 y `.venv-system` con una versión compatible; instalá las dependencias de `requirements.txt` en ambos. El script también reconoce esos nombres.

2. Copiá `.env.example` como `.env` y completá las credenciales locales. Este archivo está ignorado por Git.

3. Copiá `config/examples/frigate.yml.example` como `config/config.yml`, adaptá la URL RTSP, las zonas y las credenciales.

4. Incorporá los modelos en `assets/models/`. Si se habilitará el reconocimiento facial, agregá las referencias autorizadas en `assets/restricted_faces/`.

5. Levantá la infraestructura:

   ```powershell
   docker compose up -d
   ```

6. Iniciá los tres procesos con `scripts\start_windows.bat`, o en terminales separadas:

   ```powershell
   python src/access_control/detect.py
   python src/access_control/sistema.py
   python src/access_control/dashboard.py
   ```

## Configuración y datos sensibles

No se deben subir a GitHub: `.env`, `config/config.yml`, bases SQLite, modelos, capturas, grabaciones, imágenes de referencia ni historiales de alertas. El archivo `.gitignore` ya cubre esos casos y hay plantillas públicas para reconstruir la configuración.

Antes de publicar, revocá o cambiá cualquier contraseña de MQTT, RTSP o token que haya sido usado localmente. Si un secreto llegó a estar en un repositorio remoto, cambiarlo es obligatorio: ocultarlo en un commit posterior no elimina el historial.

## Tecnologías

Python · OpenCV · NumPy · Paho MQTT · OpenPyXL · Tkinter · Frigate · Mosquitto · Docker Compose

## Estado

Proyecto demostrativo para portfolio. Las decisiones de despliegue, privacidad, retención de datos y control de acceso deben adaptarse al contexto real de uso.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consultá [LICENSE](LICENSE).
