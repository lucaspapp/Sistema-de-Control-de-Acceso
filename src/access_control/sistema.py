"""Monitor de personas prohibidas para GoldenJack, sin conteos ni analítica."""

import json
import os
import threading
import time

import paho.mqtt.client as mqtt

from face import FaceAnalyzer, guardar_historial_prohibido, obtener_snapshot, recortar_persona
from prohibited_store import initialize, record_alert
from settings import load_local_env

load_local_env()
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "7777"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "frigate")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = "frigate/events"
SAMPLE_INTERVAL = 0.75
TRACKING_STALE_SECONDS = 8

face: FaceAnalyzer | None = None
tracks: dict[str, dict] = {}
lock = threading.RLock()


def monitor_tracking(tracking_id: str) -> None:
    """Analiza muestras mientras Frigate mantenga el tracking de la persona."""
    assert face is not None
    try:
        while True:
            with lock:
                track = tracks.get(tracking_id)
                if track is None:
                    return
                if track["ended"] or time.monotonic() - track["last_seen"] > TRACKING_STALE_SECONDS:
                    return
                event_id, camera, box = track["event_id"], track["camera"], track.get("box")

            image = obtener_snapshot(event_id, camera)
            if image is not None:
                person = recortar_persona(image, box)
                result = face.analizar_tracking(tracking_id, person)
                if result and result.get("status") == "MATCH" and result.get("confirmed"):
                    name, score = result["name"], result.get("score", 0.0)
                    image_path = guardar_historial_prohibido(person, tracking_id, name, score)
                    record_alert(name, camera, score, image_path)
                    print(f"[ALERTA] PROHIBIDO: {name} | cámara={camera} | score={score:.3f}")
                    return
            time.sleep(SAMPLE_INTERVAL)
    except Exception as error:
        print(f"[FACE] Error en tracking {tracking_id}: {error}")
    finally:
        face.olvidar_tracking(tracking_id)
        with lock:
            tracks.pop(tracking_id, None)


def process_event(event: dict) -> None:
    event_type = event.get("type")
    after, before = event.get("after") or {}, event.get("before") or {}
    data = after or before
    if data.get("label") != "person":
        return
    tracking_id = data.get("id")
    if not tracking_id:
        return

    with lock:
        if event_type == "end":
            if tracking_id in tracks:
                tracks[tracking_id]["ended"] = True
            return
        if event_type not in {"new", "update"}:
            return
        if tracking_id in tracks:
            tracks[tracking_id].update(camera=data.get("camera", "unknown"), box=data.get("box"),
                                       last_seen=time.monotonic(), ended=False)
            return
        tracks[tracking_id] = {"event_id": tracking_id, "camera": data.get("camera", "unknown"),
                               "box": data.get("box"), "last_seen": time.monotonic(), "ended": False}
        threading.Thread(target=monitor_tracking, args=(tracking_id,), daemon=True).start()
        print(f"[FACE] Analizando tracking {tracking_id} en cámara {data.get('camera', 'unknown')}")


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code != 0:
        print(f"[MQTT] Error de conexión: {reason_code}")
        return
    client.subscribe(MQTT_TOPIC)
    print(f"[MQTT] Escuchando {MQTT_TOPIC} en {MQTT_HOST}:{MQTT_PORT}")


def on_message(client, userdata, message):
    try:
        process_event(json.loads(message.payload.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"[MQTT] Evento inválido: {error}")


def main():
    global face
    initialize()
    face = FaceAnalyzer()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect, client.on_message = on_connect, on_message
    print("[GOLDENJACK] Monitor de prohibidos iniciado. Sin conteos ni análisis demográfico.")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("[GOLDENJACK] Monitor detenido.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
