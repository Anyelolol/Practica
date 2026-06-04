import threading
import tkinter as tk
import numpy as np
import cv2

# YOLO se importa lazy para no romper el servidor si no está instalado
_yolo_disponible = False
try:
    from ultralytics import YOLO as _YOLO
    _yolo_disponible = True
except ImportError:
    pass

FOCAL_LENGTH        = 600
ALTURA_PERSONA_REAL = 1.70
MODEL_PATH          = "yolo11n-pose.pt"


class YoloPoseProcessor:
    """
    Procesa frames numpy (BGR o RGB) con YOLO Pose.
    Thread-safe: el modelo se carga en un hilo aparte para no bloquear la UI.
    """

    def __init__(self):
        self._model   = None
        self._activo  = False          # el usuario lo activa con toggle()
        self._listo   = False          # True cuando el modelo ya cargó
        self._lock    = threading.Lock()

        # Carga el modelo en background
        threading.Thread(target=self._cargar_modelo, daemon=True).start()

    # ── Carga ────────────────────────────────────────────────────────────────

    def _cargar_modelo(self):
        if not _yolo_disponible:
            print("[YOLO] ultralytics no instalado — pip install ultralytics")
            return
        try:
            model = _YOLO(MODEL_PATH)
            with self._lock:
                self._model = model
                self._listo = True
            print("[YOLO] Modelo cargado ✓")
        except Exception as e:
            print(f"[YOLO] Error cargando modelo: {e}")

    # ── API pública ───────────────────────────────────────────────────────────

    @property
    def activo(self):
        return self._activo

    @property
    def listo(self):
        return self._listo

    def toggle(self):
        self._activo = not self._activo
        estado = "ACTIVADO" if self._activo else "DESACTIVADO"
        print(f"[YOLO] {estado}")
        return self._activo

    def procesar(self, frame: np.ndarray, es_bgr: bool = True) -> np.ndarray:
        """
        Recibe un frame numpy (BGR por defecto) y devuelve el mismo frame
        con las anotaciones YOLO dibujadas (mismo formato de entrada).
        Si YOLO no está activo o el modelo no cargó, devuelve el frame sin cambios.
        """
        if not self._activo or not self._listo:
            return frame

        with self._lock:
            model = self._model

        if model is None:
            return frame

        # YOLO espera BGR
        bgr = frame if es_bgr else cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        try:
            results = model(bgr, conf=0.5, verbose=False)
            bgr = self._dibujar(bgr, results)
        except Exception as e:
            print(f"[YOLO] Error en inferencia: {e}")
            return frame

        return bgr if es_bgr else cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # ── Dibujo ────────────────────────────────────────────────────────────────

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

    def _dibujar(self, frame, results):
        personas = 0
        for result in results:
            if result.boxes is None:
                continue
            boxes    = result.boxes.xyxy.cpu().numpy()
            kps_xy   = result.keypoints.xy.cpu().numpy()   if result.keypoints else None
            kps_conf = result.keypoints.conf.cpu().numpy() if result.keypoints else None

            for i, bbox in enumerate(boxes):
                personas += 1

                kps = None
                if kps_xy is not None and i < len(kps_xy):
                    kps = (np.column_stack([kps_xy[i], kps_conf[i]])
                           if kps_conf is not None else kps_xy[i])

                dist = self._estimar_distancia(self._obtener_altura(kps, bbox))
                x1, y1, x2, y2 = map(int, bbox)

                if dist is None:    color = (128, 128, 128)
                elif dist < 1.5:    color = (0,   0,   255)
                elif dist < 3.0:    color = (0,   165, 255)
                elif dist < 5.0:    color = (0,   255, 255)
                else:               color = (0,   255,   0)

                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                txt = f"P{personas}: {dist}m" if dist else f"P{personas}"
                (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                cv2.rectangle(frame, (x1, y1 - th - 10), (x1 + tw + 6, y1), color, -1)
                cv2.putText(frame, txt, (x1 + 3, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

                if kps is not None:
                    for idx in [0, 5, 6, 11, 12, 15, 16]:
                        if idx < len(kps):
                            kp = kps[idx]
                            c  = kp[2] if len(kp) > 2 else 1.0
                            if c > 0.5:
                                cv2.circle(frame, (int(kp[0]), int(kp[1])), 5, color, -1)

        return frame


# ── Botón helper (igual que make_audio_button) ────────────────────────────────

def make_yolo_button(parent: tk.Misc, processor: YoloPoseProcessor,
                     x: int, y: int,
                     width: int = 37, height: int = 37) -> tk.Button:
    """Crea un botón toggle para activar/desactivar YOLO en la ventana dada."""

    def _toggle():
        activo = processor.toggle()
        if activo:
            btn.config(bg="#8e44ad", text="🤖")
        else:
            btn.config(bg="#2e2e2e", text="🤖")

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