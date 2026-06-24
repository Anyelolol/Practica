import os
import threading
import cv2

_yolo_disponible = False
try:
    from ultralytics import YOLO as _YOLO
    _yolo_disponible = True
except ImportError:
    pass

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Models", "yolo11n-pose.pt")

# --- umbrales de altura (px) para cada zona ---------------------------------
# Cada zona tiene un umbral distinto para "subir" y para "bajar" (histeresis),
# asi una persona parada justo en el borde no hace parpadear el color.
UMBRAL_NARANJA_SUBE = 70
UMBRAL_NARANJA_BAJA = 55
UMBRAL_ROJO_SUBE    = 170
UMBRAL_ROJO_BAJA    = 150

# Cuantos frames seguidos sin detectar a nadie hay que esperar antes de
# soltar el color (permanencia: no se apaga apenas la persona se pierde un instante).
FRAMES_GRACIA_SIN_DETECCION = 10

# Se manda 1 de cada N frames de camara al modelo; el resto reusa el ultimo
# resultado. Bajar la carga de inferencia es lo que mas ayuda con el delay.
INFERIR_CADA_N_FRAMES = 3

# Tamaño de entrada al modelo. Las camaras ya viajan en baja resolucion,
# no hace falta que YOLO trabaje a 640x640 por dentro.
IMG_SIZE = 320

# Que tan rapido el color "se deja llevar" hacia el nuevo objetivo en cada
# frame (0 a 1). Mas chico = transicion mas suave / lenta.
SUAVIZADO = 0.18

_PANEL_RGB   = (30, 30, 30)     # sin persona detectada (borde apagado)
_VERDE_RGB   = (39, 174, 96)
_NARANJA_RGB = (243, 156, 18)
_ROJO_RGB    = (231, 76, 60)

# nivel -1 = sin persona, 0 = verde, 1 = naranja, 2 = rojo
_ANCLAS = [
    (-1, _PANEL_RGB,   1),
    (0,  _VERDE_RGB,   1),
    (1,  _NARANJA_RGB, 3),
    (2,  _ROJO_RGB,    5),
]


def _rgb_hex(rgb):
    return "#%02x%02x%02x" % rgb


def _interpolar(nivel):
    """Devuelve (color_hex, ancho_borde) interpolando entre las anclas segun
    el nivel continuo actual, para que el cambio de color/ancho sea gradual."""
    if nivel <= _ANCLAS[0][0]:
        _, rgb0, w0 = _ANCLAS[0]
        return _rgb_hex(rgb0), w0
    for (n0, rgb0, w0), (n1, rgb1, w1) in zip(_ANCLAS, _ANCLAS[1:]):
        if n0 <= nivel <= n1:
            t = (nivel - n0) / (n1 - n0)
            rgb = tuple(round(rgb0[k] + (rgb1[k] - rgb0[k]) * t) for k in range(3))
            w = w0 + (w1 - w0) * t
            return _rgb_hex(rgb), w
    _, rgb1, w1 = _ANCLAS[-1]
    return _rgb_hex(rgb1), w1


# ------------------------------------------------------------------------
# El modelo de YOLO se carga UNA sola vez para todo el servidor (pesa
# bastante y antes se cargaba una instancia completa por cada camara
# conectada). Todas las camaras comparten este modelo; el lock evita que
# dos camaras corran inferencia al mismo tiempo y se pisen/saturen la CPU.
# ------------------------------------------------------------------------
_modelo_lock = threading.Lock()
_modelo = None
_modelo_listo = False


def _obtener_modelo():
    global _modelo, _modelo_listo
    if _modelo_listo:
        return _modelo
    with _modelo_lock:
        if not _modelo_listo and _yolo_disponible:
            try:
                _modelo = _YOLO(MODEL_PATH)
                _modelo_listo = True
            except Exception:
                _modelo = None
    return _modelo


threading.Thread(target=_obtener_modelo, daemon=True).start()


class YoloPoseProcessor:
    """
    Una instancia por camara conectada. El modelo pesado se comparte entre
    todas (ver _obtener_modelo); lo que es propio de cada instancia es el
    estado de suavizado/histeresis/permanencia de color de ESA camara.
    """

    def __init__(self):
        self._activo = True
        self._frame_counter = 0
        self._zona_objetivo = -1
        self._frames_sin_deteccion = 0
        self._nivel_actual = -1.0
        self._color_actual = _rgb_hex(_PANEL_RGB)
        self._width_actual = 1.0

    @property
    def activo(self):
        return self._activo

    @property
    def listo(self):
        return _modelo_listo

    @property
    def last_color(self):
        return self._color_actual

    @property
    def last_border_width(self):
        return max(1, round(self._width_actual))

    @property
    def last_level(self):
        """Nivel continuo (-1..2) por si algun consumidor quiere interpolar
        otro color (ej. el tinte de fondo de toda la ventana)."""
        return self._nivel_actual

    def toggle(self):
        self._activo = not self._activo
        if not self._activo:
            self._zona_objetivo = -1
            self._frames_sin_deteccion = 0
            self._nivel_actual = -1.0
            self._color_actual = _rgb_hex(_PANEL_RGB)
            self._width_actual = 1.0
        return self._activo

    def procesar(self, frame, es_bgr=True):
        if not self._activo:
            return frame

        modelo = _obtener_modelo()
        self._frame_counter += 1

        if modelo is not None and self._frame_counter % INFERIR_CADA_N_FRAMES == 0:
            bgr = frame if es_bgr else cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            try:
                with _modelo_lock:
                    results = modelo(bgr, conf=0.5, imgsz=IMG_SIZE, verbose=False)
                altura_px = self._altura_detectada(results)
            except Exception:
                altura_px = None
            self._registrar_deteccion(altura_px)

        self._avanzar_transicion()
        return frame

    def _altura_detectada(self, results):
        max_altura = 0
        detectado = False
        for result in results:
            if result.boxes is None:
                continue
            for bbox in result.boxes.xyxy.cpu().numpy():
                detectado = True
                altura = int(abs(bbox[3] - bbox[1]))
                if altura > max_altura:
                    max_altura = altura
        return max_altura if detectado else None

    def _registrar_deteccion(self, altura_px):
        if altura_px is None:
            self._frames_sin_deteccion += 1
            if self._frames_sin_deteccion >= FRAMES_GRACIA_SIN_DETECCION:
                self._zona_objetivo = -1
            return

        self._frames_sin_deteccion = 0
        zona = self._zona_objetivo if self._zona_objetivo >= 0 else 0

        if zona == 0:
            if altura_px >= UMBRAL_ROJO_SUBE:
                zona = 2
            elif altura_px >= UMBRAL_NARANJA_SUBE:
                zona = 1
        elif zona == 1:
            if altura_px >= UMBRAL_ROJO_SUBE:
                zona = 2
            elif altura_px < UMBRAL_NARANJA_BAJA:
                zona = 0
        elif zona == 2:
            if altura_px < UMBRAL_ROJO_BAJA:
                zona = 1

        self._zona_objetivo = zona

    def _avanzar_transicion(self):
        self._nivel_actual += (self._zona_objetivo - self._nivel_actual) * SUAVIZADO
        if abs(self._zona_objetivo - self._nivel_actual) < 0.01:
            self._nivel_actual = float(self._zona_objetivo)
        self._color_actual, self._width_actual = _interpolar(self._nivel_actual)
