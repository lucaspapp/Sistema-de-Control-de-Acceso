import tkinter as tk
from tkinter import ttk
from pathlib import Path
from PIL import Image, ImageTk
import json
import time


# ============================================================
# CONFIGURACIÓN
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# IMPORTANTE:
# El dashboard lee el estado ACTUAL.
DATOS_FILE = PROJECT_ROOT / "runtime" / "access_control" / "datos" / "estado_actual.json"

HISTORIAL_PROHIBIDOS = PROJECT_ROOT / "runtime" / "access_control" / "historial-prohibidos"

REFRESH_MS = 1000


# ============================================================
# COLORES
# ============================================================

BG = "#0f172a"
CARD = "#1e293b"
CARD_2 = "#334155"

TEXT = "#f8fafc"
TEXT_SECONDARY = "#94a3b8"

GREEN = "#22c55e"
BLUE = "#3b82f6"
PINK = "#ec4899"
ORANGE = "#f59e0b"
RED = "#ef4444"

BORDER = "#475569"


# ============================================================
# VENTANA
# ============================================================

root = tk.Tk()

root.title("Sistema de Control de Acceso")

root.configure(bg=BG)

try:
    root.state("zoomed")
except Exception:
    root.geometry("1200x800")


# ============================================================
# VARIABLES
# ============================================================

last_json_mtime = None
last_photo = None
last_photo_path = None


# ============================================================
# UTILIDADES
# ============================================================

def cargar_datos():

    if not DATOS_FILE.exists():

        print(
            f"[DASHBOARD] No existe el archivo: {DATOS_FILE}"
        )

        return None

    try:

        with open(
            DATOS_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            datos = json.load(f)

        if not isinstance(datos, dict):

            print(
                "[DASHBOARD] estado_actual.json no contiene un objeto JSON."
            )

            return None

        return datos

    except json.JSONDecodeError as e:

        print(
            f"[DASHBOARD] JSON temporalmente incompleto: {e}"
        )

        return None

    except Exception as e:

        print(
            f"[DASHBOARD] Error leyendo estado_actual.json: {e}"
        )

        return None


def buscar_ultima_foto():

    if not HISTORIAL_PROHIBIDOS.exists():
        return None

    try:

        fotos = []

        for extension in ("*.jpg", "*.jpeg", "*.png"):

            fotos.extend(
                HISTORIAL_PROHIBIDOS.rglob(extension)
            )

        if not fotos:
            return None

        fotos.sort(
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        return fotos[0]

    except Exception as e:

        print(
            f"[DASHBOARD] Error buscando fotos: {e}"
        )

        return None


def obtener_valor(datos, clave):

    if not isinstance(datos, dict):
        return 0

    valor = datos.get(clave, 0)

    if valor is None:
        return 0

    return valor


def obtener_edad(datos, edad):

    if not isinstance(datos, dict):
        return 0

    # --------------------------------------------------------
    # Formato:
    #
    # "edades": {
    #     "(15-20)": 2,
    #     "(25-32)": 3
    # }
    # --------------------------------------------------------

    edades_data = datos.get("edades")

    if isinstance(edades_data, dict):

        valor = edades_data.get(edad, 0)

        if valor is not None:
            return valor

    # --------------------------------------------------------
    # Compatibilidad por si están en la raíz
    # --------------------------------------------------------

    valor = datos.get(edad, 0)

    if valor is None:
        return 0

    return valor


# ============================================================
# HEADER
# ============================================================

header = tk.Frame(
    root,
    bg=BG
)

header.pack(
    fill="x",
    padx=30,
    pady=(25, 10)
)


title = tk.Label(
    header,
    text="CONTROL DE ACCESO",
    font=("Segoe UI", 28, "bold"),
    bg=BG,
    fg=TEXT
)

title.pack(anchor="w")


subtitle = tk.Label(
    header,
    text="Estadísticas de entradas y detección de personas prohibidas",
    font=("Segoe UI", 12),
    bg=BG,
    fg=TEXT_SECONDARY
)

subtitle.pack(
    anchor="w",
    pady=(3, 0)
)


# ============================================================
# CONTENEDOR PRINCIPAL
# ============================================================

main = tk.Frame(
    root,
    bg=BG
)

main.pack(
    fill="both",
    expand=True,
    padx=30,
    pady=10
)


# ============================================================
# CONTENEDOR ESTADÍSTICAS
# ============================================================

stats_container = tk.Frame(
    main,
    bg=BG
)

stats_container.pack(
    side="left",
    fill="both",
    expand=True,
    padx=(0, 15)
)


# ============================================================
# FUNCIÓN PARA CREAR TARJETAS
# ============================================================

def crear_card(parent, titulo, color):

    frame = tk.Frame(
        parent,
        bg=CARD,
        highlightbackground=BORDER,
        highlightthickness=1
    )

    frame.pack(
        fill="x",
        pady=6
    )

    label_titulo = tk.Label(
        frame,
        text=titulo,
        font=("Segoe UI", 12),
        bg=CARD,
        fg=TEXT_SECONDARY
    )

    label_titulo.pack(
        anchor="w",
        padx=20,
        pady=(12, 0)
    )

    label_valor = tk.Label(
        frame,
        text="0",
        font=("Segoe UI", 26, "bold"),
        bg=CARD,
        fg=color
    )

    label_valor.pack(
        anchor="w",
        padx=20,
        pady=(0, 12)
    )

    return label_valor


# ============================================================
# TARJETAS PRINCIPALES
# ============================================================

entradas_label = crear_card(
    stats_container,
    "Entradas",
    BLUE
)

hombres_label = crear_card(
    stats_container,
    "Hombres",
    GREEN
)

mujeres_label = crear_card(
    stats_container,
    "Mujeres",
    PINK
)

prohibidos_label = crear_card(
    stats_container,
    "Prohibidos",
    RED
)


# ============================================================
# EDADES
# ============================================================

edades_title = tk.Label(
    stats_container,
    text="EDADES",
    font=("Segoe UI", 14, "bold"),
    bg=BG,
    fg=TEXT
)

edades_title.pack(
    anchor="w",
    pady=(18, 5)
)


edades_frame = tk.Frame(
    stats_container,
    bg=BG
)

edades_frame.pack(
    fill="x"
)


edad_labels = {}

edades = [
    "(15-20)",
    "(25-32)",
    "(38-43)",
    "(48-53)",
    "(60-100)"
]


for edad in edades:

    card = tk.Frame(
        edades_frame,
        bg=CARD,
        highlightbackground=BORDER,
        highlightthickness=1
    )

    card.pack(
        side="left",
        fill="both",
        expand=True,
        padx=3
    )

    label_titulo = tk.Label(
        card,
        text=edad,
        font=("Segoe UI", 10),
        bg=CARD,
        fg=TEXT_SECONDARY
    )

    label_titulo.pack(
        pady=(10, 0)
    )

    label_valor = tk.Label(
        card,
        text="0",
        font=("Segoe UI", 20, "bold"),
        bg=CARD,
        fg=ORANGE
    )

    label_valor.pack(
        pady=(0, 10)
    )

    edad_labels[edad] = label_valor


# ============================================================
# PANEL DE PROHIBIDO
# ============================================================

prohibido_container = tk.Frame(
    main,
    bg=CARD,
    highlightbackground=BORDER,
    highlightthickness=1,
    width=400
)

prohibido_container.pack(
    side="right",
    fill="both",
    padx=(15, 0)
)

prohibido_container.pack_propagate(False)


prohibido_title = tk.Label(
    prohibido_container,
    text="ÚLTIMO PROHIBIDO DETECTADO",
    font=("Segoe UI", 15, "bold"),
    bg=CARD,
    fg=RED
)

prohibido_title.pack(
    pady=(20, 10)
)


photo_frame = tk.Frame(
    prohibido_container,
    bg="#020617"
)

photo_frame.pack(
    fill="both",
    expand=True,
    padx=20,
    pady=10
)


photo_label = tk.Label(
    photo_frame,
    text="No hay detecciones",
    font=("Segoe UI", 12),
    bg="#020617",
    fg=TEXT_SECONDARY
)

photo_label.pack(
    fill="both",
    expand=True
)


photo_info = tk.Label(
    prohibido_container,
    text="",
    font=("Segoe UI", 10),
    bg=CARD,
    fg=TEXT_SECONDARY,
    justify="center"
)

photo_info.pack(
    pady=(5, 20)
)


# ============================================================
# ACTUALIZAR ESTADÍSTICAS
# ============================================================

def actualizar_estadisticas(datos):

    if datos is None:
        return

    entradas_label.config(
        text=str(
            obtener_valor(
                datos,
                "entradas"
            )
        )
    )

    hombres_label.config(
        text=str(
            obtener_valor(
                datos,
                "hombres"
            )
        )
    )

    mujeres_label.config(
        text=str(
            obtener_valor(
                datos,
                "mujeres"
            )
        )
    )

    prohibidos_label.config(
        text=str(
            obtener_valor(
                datos,
                "prohibidos"
            )
        )
    )

    for edad in edades:

        edad_labels[edad].config(
            text=str(
                obtener_edad(
                    datos,
                    edad
                )
            )
        )


# ============================================================
# ACTUALIZAR FOTO
# ============================================================

def actualizar_foto():

    global last_photo
    global last_photo_path

    foto = buscar_ultima_foto()

    if foto is None:

        if last_photo_path is not None:

            photo_label.config(
                image="",
                text="No hay detecciones"
            )

            photo_info.config(
                text=""
            )

            last_photo = None
            last_photo_path = None

        return

    if last_photo_path == foto:
        return

    try:

        image = Image.open(foto)

        image.thumbnail(
            (350, 400),
            Image.Resampling.LANCZOS
        )

        photo = ImageTk.PhotoImage(image)

        photo_label.config(
            image=photo,
            text=""
        )

        last_photo = photo
        last_photo_path = foto

        nombre = foto.stem

        partes = nombre.split("_")

        informacion = ""

        if len(partes) >= 3:

            hora = partes[0]
            nombre_persona = partes[-2]
            score = partes[-1]

            informacion = (
                f"Persona: {nombre_persona}\n"
                f"Hora: {hora}\n"
                f"Score: {score}"
            )

        else:

            informacion = (
                f"Archivo:\n{foto.name}"
            )

        photo_info.config(
            text=informacion
        )

        print(
            f"[DASHBOARD] Nueva foto: {foto}"
        )

    except Exception as e:

        print(
            f"[DASHBOARD] Error mostrando foto: {e}"
        )


# ============================================================
# ACTUALIZACIÓN AUTOMÁTICA
# ============================================================

def actualizar_dashboard():

    global last_json_mtime

    try:

        if DATOS_FILE.exists():

            mtime = DATOS_FILE.stat().st_mtime

            # ------------------------------------------------
            # IMPORTANTE:
            # Leer siempre que cambie el archivo.
            # ------------------------------------------------

            if (
                last_json_mtime is None
                or mtime != last_json_mtime
            ):

                datos = cargar_datos()

                if datos is not None:

                    actualizar_estadisticas(datos)

                    last_json_mtime = mtime

                    print(
                        "[DASHBOARD] estado_actual.json actualizado."
                    )

        else:

            print(
                f"[DASHBOARD] No existe: {DATOS_FILE}"
            )

    except Exception as e:

        print(
            f"[DASHBOARD] Error actualizando datos: {e}"
        )

    actualizar_foto()

    root.after(
        REFRESH_MS,
        actualizar_dashboard
    )


# ============================================================
# FOOTER
# ============================================================

footer = tk.Label(
    root,
    text="Actualización automática cada 1 segundo",
    font=("Segoe UI", 9),
    bg=BG,
    fg=TEXT_SECONDARY
)

footer.pack(
    pady=(0, 15)
)


# ============================================================
# INICIO
# ============================================================

print("=" * 60)
print("             DASHBOARD")
print("=" * 60)

print(
    f"[DASHBOARD] Datos actuales: {DATOS_FILE}"
)

print(
    f"[DASHBOARD] Historial: {HISTORIAL_PROHIBIDOS}"
)

print(
    "[DASHBOARD] Actualización automática: 1 segundo"
)

actualizar_dashboard()


# ============================================================
# CERRAR
# ============================================================

def cerrar():

    global last_photo

    last_photo = None

    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    cerrar
)


# ============================================================
# LOOP TKINTER
# ============================================================

root.mainloop()
