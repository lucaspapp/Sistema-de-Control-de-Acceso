import base64
import json
import os
from pathlib import Path

import cv2
import numpy as np
import paho.mqtt.client as mqtt
from settings import load_local_env

load_local_env()


# ============================================================
# CONFIGURACIÓN MQTT
# ============================================================

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "7777"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "frigate")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

REQUEST_TOPIC = "sistema/edad_genero/request"
RESULT_TOPIC = "sistema/edad_genero/result"


# ============================================================
# RUTAS DE MODELOS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "assets" / "models"

FACE_PROTO = MODEL_DIR / "opencv_face_detector.pbtxt"
FACE_MODEL = MODEL_DIR / "opencv_face_detector_uint8.pb"

AGE_PROTO = MODEL_DIR / "age_deploy.prototxt"
AGE_MODEL = MODEL_DIR / "age_net.caffemodel"

GENDER_PROTO = MODEL_DIR / "gender_deploy.prototxt"
GENDER_MODEL = MODEL_DIR / "gender_net.caffemodel"


# ============================================================
# CONFIGURACIÓN DE MODELOS
# ============================================================

MEAN = (
    78.4263377603,
    87.7689143744,
    114.895847746
)


AGE_LIST = [
    "(0-2)",
    "(4-6)",
    "(8-12)",
    "(15-20)",
    "(25-32)",
    "(38-43)",
    "(48-53)",
    "(60-100)"
]


GENDER_LIST = [
    "Male",
    "Female"
]


# ============================================================
# NORMALIZACIÓN DE EDADES
# ============================================================

def normalize_age(age):

    if age in (
        "(0-2)",
        "(4-6)",
        "(8-12)",
        "(15-20)"
    ):
        return "(15-20)"

    return age


# ============================================================
# INICIO
# ============================================================

print("=" * 60)
print("       SERVICIO EDAD + GÉNERO - PYTHON 3.11")
print("=" * 60)


# ============================================================
# CARGAR MODELOS
# ============================================================

try:

    faceNet = cv2.dnn.readNet(
        str(FACE_MODEL),
        str(FACE_PROTO)
    )

    ageNet = cv2.dnn.readNet(
        str(AGE_MODEL),
        str(AGE_PROTO)
    )

    genderNet = cv2.dnn.readNet(
        str(GENDER_MODEL),
        str(GENDER_PROTO)
    )

    print("[DETECT] Modelos cargados.")

except Exception as e:

    print(
        f"[DETECT] ERROR cargando modelos: {e}"
    )

    raise


# ============================================================
# DETECCIÓN FACIAL
# ============================================================

def highlightFace(frame, conf_threshold=0.5):

    if frame is None or frame.size == 0:
        return []

    h, w = frame.shape[:2]

    blob = cv2.dnn.blobFromImage(
        frame,
        1.0,
        (300, 300),
        [104, 117, 123],
        True,
        False
    )

    faceNet.setInput(blob)

    detections = faceNet.forward()

    boxes = []

    for i in range(detections.shape[2]):

        confidence = float(
            detections[0, 0, i, 2]
        )

        if confidence <= conf_threshold:
            continue

        x1 = int(
            detections[0, 0, i, 3] * w
        )

        y1 = int(
            detections[0, 0, i, 4] * h
        )

        x2 = int(
            detections[0, 0, i, 5] * w
        )

        y2 = int(
            detections[0, 0, i, 6] * h
        )

        # ----------------------------------------------------
        # Mantener coordenadas dentro de la imagen
        # ----------------------------------------------------

        x1 = max(
            0,
            min(x1, w - 1)
        )

        y1 = max(
            0,
            min(y1, h - 1)
        )

        x2 = max(
            0,
            min(x2, w)
        )

        y2 = max(
            0,
            min(y2, h)
        )

        # ----------------------------------------------------
        # Validar tamaño
        # ----------------------------------------------------

        if x2 <= x1:
            continue

        if y2 <= y1:
            continue

        face_width = x2 - x1
        face_height = y2 - y1

        # Evitar detecciones extremadamente pequeñas
        if face_width < 10:
            continue

        if face_height < 10:
            continue

        boxes.append(
            (
                x1,
                y1,
                x2,
                y2,
                confidence
            )
        )

    return boxes


# ============================================================
# DETECCIÓN FACIAL TOLERANTE
# ============================================================

def detectar_mejor_cara(frame):

    if frame is None or frame.size == 0:
        return None

    # --------------------------------------------------------
    # Primer intento:
    # detección normal
    # --------------------------------------------------------

    thresholds = [
        0.50,
        0.40,
        0.30
    ]

    for threshold in thresholds:

        faces = highlightFace(
            frame,
            threshold
        )

        if faces:

            # ------------------------------------------------
            # Elegimos la cara más grande.
            #
            # En nuestro caso normalmente corresponde
            # a la persona que estamos analizando.
            # ------------------------------------------------

            mejor = max(
                faces,
                key=lambda b:
                    (b[2] - b[0]) *
                    (b[3] - b[1])
            )

            print(
                f"[DETECT] Cara encontrada "
                f"threshold={threshold:.2f} "
                f"confidence={mejor[4]:.3f} "
                f"box={mejor[:4]}"
            )

            return mejor

    print(
        "[DETECT] No se encontró una cara "
        "con ninguno de los thresholds."
    )

    return None


# ============================================================
# RECORTE DE PERSONA
# ============================================================

def crop_person(frame, box):

    if not box or len(box) < 4:
        return frame

    try:

        x1, y1, x2, y2 = [
            int(v)
            for v in box[:4]
        ]

    except (TypeError, ValueError):

        return frame

    h, w = frame.shape[:2]

    # --------------------------------------------------------
    # Un poco más de margen que antes.
    # Esto ayuda especialmente cuando el bounding box
    # de Frigate queda justo sobre la persona.
    # --------------------------------------------------------

    px = int(
        (x2 - x1) * 0.15
    )

    py = int(
        (y2 - y1) * 0.15
    )

    x1 = max(
        0,
        x1 - px
    )

    y1 = max(
        0,
        y1 - py
    )

    x2 = min(
        w,
        x2 + px
    )

    y2 = min(
        h,
        y2 + py
    )

    crop = frame[
        y1:y2,
        x1:x2
    ]

    if crop.size:

        return crop

    return frame


# ============================================================
# ANÁLISIS DE EDAD Y GÉNERO
# ============================================================

def analizar(frame, person_box):

    if frame is None or frame.size == 0:

        print(
            "[DETECT] Imagen vacía."
        )

        return None

    # --------------------------------------------------------
    # Recortar la persona según Frigate
    # --------------------------------------------------------

    frame = crop_person(
        frame,
        person_box
    )

    # --------------------------------------------------------
    # Buscar la mejor cara
    # --------------------------------------------------------

    mejor_cara = detectar_mejor_cara(
        frame
    )

    if mejor_cara is None:

        return None

    x1, y1, x2, y2, confidence = mejor_cara

    # --------------------------------------------------------
    # Tamaño de la cara
    # --------------------------------------------------------

    fw = x2 - x1
    fh = y2 - y1

    # --------------------------------------------------------
    # Ampliar la cara antes de enviarla
    # a los modelos de edad/género.
    #
    # Antes era 20%.
    # Ahora usamos 25%.
    # --------------------------------------------------------

    px = int(
        fw * 0.25
    )

    py = int(
        fh * 0.25
    )

    x1 = max(
        0,
        x1 - px
    )

    y1 = max(
        0,
        y1 - py
    )

    x2 = min(
        frame.shape[1],
        x2 + px
    )

    y2 = min(
        frame.shape[0],
        y2 + py
    )

    face = frame[
        y1:y2,
        x1:x2
    ]

    if face.size == 0:

        print(
            "[DETECT] El recorte de cara está vacío."
        )

        return None

    # --------------------------------------------------------
    # Información de diagnóstico
    # --------------------------------------------------------

    face_h, face_w = face.shape[:2]

    print(
        f"[DETECT] Cara para análisis: "
        f"{face_w}x{face_h} px"
    )

    # --------------------------------------------------------
    # Crear blob
    # --------------------------------------------------------

    blob = cv2.dnn.blobFromImage(
        face,
        1.0,
        (227, 227),
        MEAN,
        swapRB=False
    )

    # ========================================================
    # GÉNERO
    # ========================================================

    genderNet.setInput(
        blob
    )

    genderPreds = genderNet.forward()

    genderIndex = int(
        genderPreds[0].argmax()
    )

    gender = GENDER_LIST[
        genderIndex
    ]

    genderConfidence = float(
        genderPreds[0][genderIndex]
    )

    # ========================================================
    # EDAD
    # ========================================================

    ageNet.setInput(
        blob
    )

    agePreds = ageNet.forward()

    ageIndex = int(
        agePreds[0].argmax()
    )

    original_age = AGE_LIST[
        ageIndex
    ]

    age = normalize_age(
        original_age
    )

    ageConfidence = float(
        agePreds[0][ageIndex]
    )

    # --------------------------------------------------------
    # Diagnóstico
    # --------------------------------------------------------

    print(
        f"[DETECT] "
        f"Género={gender} "
        f"conf={genderConfidence:.3f} | "
        f"Edad modelo={original_age} "
        f"conf={ageConfidence:.3f} | "
        f"Edad final={age}"
    )

    # --------------------------------------------------------
    # Resultado
    # --------------------------------------------------------

    return {
        "gender": gender,
        "age": age,
        "original_age": original_age,
        "face_confidence": round(
            confidence,
            4
        ),
        "gender_confidence": round(
            genderConfidence,
            4
        ),
        "age_confidence": round(
            ageConfidence,
            4
        ),
    }


# ============================================================
# MQTT CONNECT
# ============================================================

def on_connect(
    client,
    userdata,
    flags,
    reason_code,
    properties=None
):

    if reason_code == 0:

        client.subscribe(
            REQUEST_TOPIC
        )

        print(
            f"[DETECT] MQTT conectado "
            f"{MQTT_HOST}:{MQTT_PORT}"
        )

        print(
            f"[DETECT] Escuchando: "
            f"{REQUEST_TOPIC}"
        )

    else:

        print(
            f"[DETECT] Error MQTT: "
            f"{reason_code}"
        )


# ============================================================
# MQTT MESSAGE
# ============================================================

def on_message(
    client,
    userdata,
    msg
):

    try:

        # ----------------------------------------------------
        # Leer JSON
        # ----------------------------------------------------

        request = json.loads(
            msg.payload.decode(
                "utf-8"
            )
        )

        tracking_id = request.get(
            "tracking_id"
        )

        image_b64 = request.get(
            "image"
        )

        if not tracking_id:

            print(
                "[DETECT] Solicitud sin tracking_id."
            )

            return

        if not image_b64:

            print(
                f"[DETECT] "
                f"[{tracking_id}] "
                f"Solicitud sin imagen."
            )

            return

        # ----------------------------------------------------
        # Decodificar imagen
        # ----------------------------------------------------

        try:

            image_bytes = base64.b64decode(
                image_b64
            )

        except Exception as e:

            print(
                f"[DETECT] "
                f"[{tracking_id}] "
                f"Error decodificando base64: {e}"
            )

            return

        frame = cv2.imdecode(
            np.frombuffer(
                image_bytes,
                np.uint8
            ),
            cv2.IMREAD_COLOR
        )

        # ----------------------------------------------------
        # Información de diagnóstico
        # ----------------------------------------------------

        print(
            f"\n[DETECT] "
            f"[{tracking_id}] "
            f"imagen="
            f"{frame.shape if frame is not None else None} "
            f"box="
            f"{request.get('box')}"
        )

        if frame is None:

            print(
                f"[DETECT] "
                f"[{tracking_id}] "
                f"No se pudo decodificar la imagen."
            )

            result = {
                "gender": None,
                "age": None,
                "original_age": None,
                "status": "INVALID_IMAGE",
                "tracking_id": tracking_id,
            }

            client.publish(
                RESULT_TOPIC,
                json.dumps(
                    result,
                    ensure_ascii=False
                ),
                qos=0
            )

            return

        # ----------------------------------------------------
        # Analizar
        # ----------------------------------------------------

        result = analizar(
            frame,
            request.get("box")
        )

        # ----------------------------------------------------
        # Si no se encontró cara
        # ----------------------------------------------------

        if result is None:

            result = {
                "gender": None,
                "age": None,
                "original_age": None,
                "status": "NO_FACE",
            }

            print(
                f"[DETECT] "
                f"[{tracking_id}] "
                f"NO_FACE"
            )

        else:

            result["status"] = "OK"

        # ----------------------------------------------------
        # Agregar tracking_id
        # ----------------------------------------------------

        result["tracking_id"] = tracking_id

        # ----------------------------------------------------
        # Enviar resultado a sistema.py
        # ----------------------------------------------------

        client.publish(
            RESULT_TOPIC,
            json.dumps(
                result,
                ensure_ascii=False
            ),
            qos=0
        )

        # ----------------------------------------------------
        # Mostrar resultado
        # ----------------------------------------------------

        print(
            f"[DETECT] "
            f"[{tracking_id}] "
            f"género={result['gender']} "
            f"edad={result['age']} "
            f"status={result['status']}"
        )

    except Exception as e:

        print(
            f"[DETECT] Error: {e}"
        )


# ============================================================
# CONFIGURAR MQTT
# ============================================================

client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2
)

client.username_pw_set(
    MQTT_USERNAME,
    MQTT_PASSWORD
)

client.on_connect = on_connect
client.on_message = on_message


# ============================================================
# CONECTAR
# ============================================================

print(
    f"[DETECT] Conectando a MQTT "
    f"{MQTT_HOST}:{MQTT_PORT}..."
)

client.connect(
    MQTT_HOST,
    MQTT_PORT,
    60
)


# ============================================================
# EJECUCIÓN
# ============================================================

try:

    client.loop_forever()

except KeyboardInterrupt:

    print(
        "\n[DETECT] Detenido."
    )

finally:

    client.disconnect()
