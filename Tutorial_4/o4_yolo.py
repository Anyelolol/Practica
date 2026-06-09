import threading
import tkinter as tk
import numpy as np
import cv2

_yolo_disponible = False
try:
    from ultralytics import YOLO as _YOLO

    _yolo_disponible = True
except ImportError:
    pass

# CALIBRACIÓN: Ajusta este valor según tu webcam.
# Si a 1 metro de distancia la persona mide H píxeles en pantalla, usa: FOCAL_LENGTH = H / 1.70
FOCAL_LENGTH = 550
ALTURA_PERSONA_REAL = 0.55  # metros
MODEL_PATH = "yolo11n-pose.pt"

# Suavizado: cuántos frames consecutivos debe mantenerse un color antes de cambiar
_COLOR_HOLD_FRAMES = 4


def _color_distancia(dist):
    if dist is None:
        return None
    if dist >= 6.5:
        return "#27ae60"  # Verde  : ≥ 6.5 m (Distancia segura)
    if dist >= 1.0:
        return "#f39c12"  # Naranja: 1.0 m a 6.5 m (Precaución)
    return "#e74c3c"  # Rojo   : < 1.0 m (Peligro / Muy cerca)


def _grosor_distancia(dist):
    if dist is None:
        return 1
    if dist >= 6.5:
        return 1  # Verde: Margen de 1 píxel
    if dist >= 1.0:
        return 3  # Naranja: Margen de 3 píxeles
    return 5  # Rojo: Margen de 5 píxeles


class YoloPoseProcessor:
    def __init__(self):
        self._model = None
        self._activo = True
        self._listo = False
        self._lock = threading.Lock()
        self._last_color: str | None = None

        # Suavizado anti-parpadeo: buffer de los últimos N colores crudos
        self._color_history: list[str | None] = []
        self._stable_color: str | None = None

        threading.Thread(target=self._cargar_modelo, daemon=True).start()

    def _cargar_modelo(self):
        if not _yolo_disponible:
            print("[YOLO] ultralytics no instalado")
            return
        try:
            model = _YOLO(MODEL_PATH)
            with self._lock:
                self._model = model
                self._listo = True
            print("[YOLO] Modelo cargado con éxito")
        except Exception as e:
            print(f"[YOLO] Error al cargar el modelo: {e}")

    @property
    def activo(self):
        return self._activo

    @property
    def listo(self):
        return self._listo

    @property
    def last_color(self):
        return self._last_color

    def toggle(self):
        self._activo = not self._activo
        if not self._activo:
            self._last_color = None
            self._stable_color = None
            self._color_history.clear()
        return self._activo

    def procesar(self, frame: np.ndarray, es_bgr: bool = True) -> np.ndarray:
        if not self._activo or not self._listo:
            self._last_color = None
            return frame

        with self._lock:
            model = self._model
        if model is None:
            return frame

        bgr = frame if es_bgr else cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        try:
            results = model(bgr, conf=0.5, verbose=False)
            bgr, raw_color = self._analizar(bgr, results)
            self._last_color = self._smooth_color(raw_color)
        except Exception as e:
            print(f"[YOLO] Error inferencia: {e}")
            self._last_color = None
            return frame

        return bgr if es_bgr else cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    def _smooth_color(self, raw: str | None) -> str | None:
        """Devuelve un color estable reduciendo el parpadeo espurio."""
        self._color_history.append(raw)
        if len(self._color_history) > _COLOR_HOLD_FRAMES:
            self._color_history.pop(0)

        votes: dict[str, int] = {}
        for c in self._color_history:
            if c is not None:
                votes[c] = votes.get(c, 0) + 1

        if not votes:
            self._stable_color = None
            return None

        winner = max(votes, key=lambda c: votes[c])
        if votes[winner] >= max(2, _COLOR_HOLD_FRAMES // 2):
            self._stable_color = winner

        return self._stable_color

    def _estimar_distancia(self, altura_px):
        if altura_px <= 0:
            return None
        dist = round((ALTURA_PERSONA_REAL * FOCAL_LENGTH) / altura_px, 2)

        # LOG EN CONSOLA: Te servirá para calibrar tu FOCAL_LENGTH exacta en tiempo real
        print(f"[YOLO Debug] Altura: {altura_px}px -> Distancia Estimada: {dist}m")
        return dist

    def _obtener_altura(self, bbox):
        """Calcula la altura usando estrictamente el Bounding Box para evitar saltos"""
        x1, y1, x2, y2 = bbox
        return max(1, int(abs(y2 - y1)))

    def _analizar(self, frame, results):
        min_dist = None
        for result in results:
            if result.boxes is None:
                continue
            boxes = result.boxes.xyxy.cpu().numpy()

            for bbox in boxes:
                # Obtenemos la altura directa de la caja de predicción
                altura_px = self._obtener_altura(bbox)
                dist = self._estimar_distancia(altura_px)

                if dist is not None:
                    if min_dist is None or dist < min_dist:
                        min_dist = dist

        color_hex = _color_distancia(min_dist)
        return frame, color_hex


def make_yolo_button(parent: tk.Misc, processor: YoloPoseProcessor,
                     x: int, y: int,
                     width: int = 37, height: int = 37) -> tk.Button:
    def _toggle():
        activo = processor.toggle()
        btn.config(bg="#8e44ad" if activo else "#2e2e2e")

    btn = tk.Button(
        parent,
        text="🤖",
        bg="#2e2e2e",
        fg="white",
        font=("Arial", 16, "bold"),
        relief="flat",
        cursor="hand2",
        command=_toggle,
    )
    btn.place(x=x, y=y, width=width, height=height)
    return btn