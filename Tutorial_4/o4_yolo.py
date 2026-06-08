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

FOCAL_LENGTH        = 800   # calibrado empíricamente para webcams típicas
ALTURA_PERSONA_REAL = 1.70  # metros
MODEL_PATH          = "yolo11n-pose.pt"

# Suavizado: cuántos frames consecutivos debe mantenerse un color antes de cambiar
_COLOR_HOLD_FRAMES = 4


def _color_distancia(dist):
    if dist is None:
        return None
    if dist >= 4.0:
        return "#27ae60"   # verde  : ≥ 4 m  (lejos, seguro)
    if dist >= 2.0:
        return "#f39c12"   # naranja: 2-4 m  (precaución)
    return "#e74c3c"       # rojo   : < 2 m  (muy cerca)


def _grosor_distancia(dist):
    if dist is None:
        return 1
    if dist >= 4.0:
        return 2
    if dist >= 2.0:
        return 3
    return 5


class YoloPoseProcessor:
    def __init__(self):
        self._model   = None
        self._activo  = True
        self._listo   = False
        self._lock    = threading.Lock()
        self._last_color: str | None = None

        # Suavizado anti-parpadeo: buffer de los últimos N colores crudos
        self._color_history: list[str | None] = []
        self._stable_color:  str | None = None

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
            print("[YOLO] Modelo cargado")
        except Exception as e:
            print(f"[YOLO] Error: {e}")

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
            self._last_color   = None
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
        """Devuelve un color estable solo si el mismo color aparece en la mayoría
        de los últimos _COLOR_HOLD_FRAMES frames. Evita el parpadeo."""
        self._color_history.append(raw)
        if len(self._color_history) > _COLOR_HOLD_FRAMES:
            self._color_history.pop(0)

        # Contar votos (ignorar None como "sin detección")
        votes: dict[str, int] = {}
        for c in self._color_history:
            if c is not None:
                votes[c] = votes.get(c, 0) + 1

        if not votes:
            self._stable_color = None
            return None

        # Ganador: color con más votos, solo si supera la mitad del buffer
        winner = max(votes, key=lambda c: votes[c])
        if votes[winner] >= max(2, _COLOR_HOLD_FRAMES // 2):
            self._stable_color = winner

        return self._stable_color

    def _estimar_distancia(self, altura_px):
        if altura_px == 0:
            return None
        return round((ALTURA_PERSONA_REAL * FOCAL_LENGTH) / altura_px, 2)

    def _obtener_altura(self, kps, bbox):
        if kps is not None and len(kps) >= 16:
            nariz   = kps[0]
            tobillo = kps[15]
            cn = nariz[2]   if len(nariz)   > 2 else 1.0
            ct = tobillo[2] if len(tobillo) > 2 else 1.0
            if cn > 0.5 and ct > 0.5:
                h = abs(tobillo[1] - nariz[1])
                if h > 20:
                    return h
        x1, y1, x2, y2 = bbox
        return abs(y2 - y1)

    def _analizar(self, frame, results):
        min_dist = None
        for result in results:
            if result.boxes is None:
                continue
            boxes    = result.boxes.xyxy.cpu().numpy()
            kps_xy   = result.keypoints.xy.cpu().numpy()   if result.keypoints else None
            kps_conf = result.keypoints.conf.cpu().numpy() if result.keypoints else None

            for i, bbox in enumerate(boxes):
                kps = None
                if kps_xy is not None and i < len(kps_xy):
                    kps = (np.column_stack([kps_xy[i], kps_conf[i]])
                           if kps_conf is not None else kps_xy[i])

                dist = self._estimar_distancia(self._obtener_altura(kps, bbox))
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