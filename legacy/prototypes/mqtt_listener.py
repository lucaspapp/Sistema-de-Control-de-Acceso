import json
import paho.mqtt.client as mqtt


MQTT_HOST = "127.0.0.1"
MQTT_PORT = 7777
MQTT_TOPIC = "frigate/events"


def on_connect(client, userdata, flags, reason_code, properties=None):
    print(f"MQTT conectado: {reason_code}")

    if reason_code == 0:
        client.subscribe(MQTT_TOPIC)
        print(f"Escuchando: {MQTT_TOPIC}")
    else:
        print(f"Error de conexión MQTT: {reason_code}")


def on_message(client, userdata, msg):
    try:
        event = json.loads(msg.payload.decode("utf-8"))
    except json.JSONDecodeError:
        print("Mensaje MQTT no válido")
        return

    after = event.get("after", {})

    # Solo nos interesan personas
    if after.get("label") != "person":
        return

    tracking_id = after.get("id")
    camera = after.get("camera")
    identity = after.get("sub_label")

    print("\n==============================")
    print("PERSONA DETECTADA")
    print("==============================")

    print(f"Evento:      {event.get('type')}")
    print(f"Tracking ID: {tracking_id}")
    print(f"Cámara:      {camera}")

    if identity:
        print(f"Identidad:   {identity[0]}")
        print(f"Confianza:   {identity[1]}")
    else:
        print("Identidad:   desconocida")

    print(f"Score:       {after.get('score')}")
    print(f"Box:         {after.get('box')}")
    print(f"Snapshot:    {'sí' if after.get('has_snapshot') else 'no'}")


# Crear cliente MQTT
client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)

client.on_connect = on_connect
client.on_message = on_message


print(f"Conectando a {MQTT_HOST}:{MQTT_PORT}...")

try:
    client.connect(MQTT_HOST, MQTT_PORT, 10)
except Exception as e:
    print(f"ERROR conectando a MQTT: {e}")
    raise


print("Iniciando loop MQTT...")

client.loop_forever()