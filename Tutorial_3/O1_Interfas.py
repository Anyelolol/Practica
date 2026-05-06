import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.filedialog import asksaveasfilename
from PIL import Image, ImageTk
import cv2
from cv2_enumerate_cameras import enumerate_cameras
import numpy as np
import imutils
import os

import serial
import time
import warnings

CARPETA_PATRONES = "patrones_guardados"
if not os.path.exists(CARPETA_PATRONES):
    os.makedirs(CARPETA_PATRONES)

global img, region, valor
imageToShow = None
captura = None
valor = 0
imagen_para_comparar = None
frame_actual = None
frame_rgb_actual = None
img_mask_actual = None
invertir_colores = False
SerialPort1 = serial.Serial()
warnings.filterwarnings("ignore", category=UserWarning)
menu_visible = True

resultados_match_shapes = []
resultados_iou = []
resultados_template = []

ventana = tk.Tk()
ventana.geometry("1280x720")
ventana.resizable(False, False)
ventana.configure(bg="#1e1e1e")
ventana.title("Analisis de patrones")

drawing = False
ix, iy = -1, -1
fx, fy = -1, -1
ImgRecUmbral = None


def iniciar_camara():
    global ventana_camaras
    ventana_camaras = tk.Toplevel(ventana)

    if (len(enumerate_cameras(cv2.CAP_MSMF)) > 1):
        ventana_camaras.title("Seleccionar camara")
        ventana_camaras.minsize(300, 1)
        ventana_camaras.maxsize(300, 9999)
        ventana_camaras.resizable(False, False)

        ventana_camaras.withdraw()

        LCamaras = tk.Label(ventana_camaras, text="Se detectaron " + str(
            len(enumerate_cameras(cv2.CAP_MSMF))) + " camaras.\nSeleccione una camara para iniciar.")
        LCamaras.pack(padx=5, pady=10)

        FBotones = tk.Frame(ventana_camaras)
        FBotones.pack(fill="y", anchor="e", padx=10, pady=10)

        i = 0
        for camera_info in enumerate_cameras(cv2.CAP_MSMF):
            newButton = tk.Button(FBotones, text=str(camera_info.name), command=lambda n=camera_info.index: camara(n))
            row = i // 2
            column = i % 2
            newButton.grid(row=row, column=column, padx=5, pady=5, sticky="ew")
            i += 1

        ventana_camaras.update_idletasks()

        w = 300
        h = ventana_camaras.winfo_reqheight()
        ws = ventana_camaras.winfo_screenwidth()
        hs = ventana_camaras.winfo_screenheight()
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        ventana_camaras.geometry(f"+{x}+{y}")

        ventana_camaras.deiconify()

        ventana_camaras.transient(ventana)
        ventana_camaras.grab_set()
        ventana.wait_window(ventana_camaras)
    else:
        camara(0)


camara_activada = False
boton_iniciar_visible = False


def camara(n):
    global capture, camara_activada, boton_iniciar_visible

    if ventana_camaras.winfo_exists() == 1:
        ventana_camaras.destroy()

    if not camara_activada:
        try:
            capture = cv2.VideoCapture(n)
            iniciar()
            camara_activada = True
            boton_iniciar_visible = True
        except:
            pass
    else:
        if capture is not None:
            capture.release()
            boton_iniciar_visible = False
        LImagenCamara.configure(image="")
        LImagenUmbralizada.configure(image="")
        LRecorteUmbralizado.configure(image="")
        camara_activada = False


def click_mouse(event):
    global ix, iy, drawing
    drawing = True
    ix, iy = event.x, event.y
    Coordenadas.config(text=f'Inicio: ({event.x}, {event.y})', fg="white")


def mover_mouse(event):
    global fx, fy, drawing
    if drawing:
        fx, fy = event.x, event.y
        Coordenadas.config(text=f'Seleccionando: ({event.x}, {event.y})', fg="yellow")


def soltar_mouse(event):
    global drawing, fx, fy, ImgRecUmbral, frame_actual, frame_rgb_actual, img_mask_actual
    global imagen_para_comparar

    drawing = False
    fx, fy = event.x, event.y

    if frame_actual is None or img_mask_actual is None:
        Coordenadas.config(text="No", fg="red")
        return

    label_w = LImagenUmbralizada.winfo_width()
    label_h = LImagenUmbralizada.winfo_height()

    if label_w <= 1 or label_h <= 1:
        label_w = 300
        label_h = 240

    if LImagenUmbralizada.image is None:
        Coordenadas.config(text="No", fg="red")
        return

    img_w_display = LImagenUmbralizada.image.width()
    img_h_display = LImagenUmbralizada.image.height()

    offset_x = (label_w - img_w_display) // 2
    offset_y = (label_h - img_h_display) // 2

    x1 = ix - offset_x
    y1 = iy - offset_y
    x2 = fx - offset_x
    y2 = fy - offset_y

    x1 = max(0, min(x1, img_w_display))
    x2 = max(0, min(x2, img_w_display))
    y1 = max(0, min(y1, img_h_display))
    y2 = max(0, min(y2, img_h_display))

    x1, x2 = sorted([x1, x2])
    y1, y2 = sorted([y1, y2])

    if x1 == x2 or y1 == y2:
        Coordenadas.config(text="No", fg="yellow")
        return

    scale_x = frame_actual.shape[1] / img_w_display
    scale_y = frame_actual.shape[0] / img_h_display

    x1_img = int(x1 * scale_x)
    x2_img = int(x2 * scale_x)
    y1_img = int(y1 * scale_y)
    y2_img = int(y2 * scale_y)

    ImgRecUmbral = img_mask_actual[y1_img:y2_img, x1_img:x2_img]

    if ImgRecUmbral.size == 0:
        Coordenadas.config(text="Error", fg="red")
        return

    ImgG = Image.fromarray(ImgRecUmbral)
    ImgG_photo = ImageTk.PhotoImage(image=ImgG)
    LRecorteUmbralizado.configure(image=ImgG_photo)
    LRecorteUmbralizado.image = ImgG_photo

    imagen_para_comparar = ImgG

    Coordenadas.config(text=f"x={x1_img}.y={y1_img} -- w={x2_img}.h={y2_img}", fg="white")


def iniciar():
    global capture, frame_actual, frame_rgb_actual, img_mask_actual
    if capture is not None:
        if boton_iniciar_visible:
            SGray.place(x=920, y=35, width=300, height=70)
            BGuardar.place(x=1140, y=230, width=65, height=35)
            lenombre.place(x=930, y=230, width=50, height=35)
            EntradaNombre.place(x=990, y=230, width=100, height=35)
            RadioMacho.place(x=1090, y=225)
            RadioHembra.place(x=1090, y=250)
            BComparar.place(x=1210, y=230, width=65, height=35)
            BInvertir.place(x=1225, y=75, width=50, height=35)
        else:
            SGray.place_forget()
            BGuardar.place_forget()
            EntradaNombre.place_forget()
            RadioMacho.place_forget()
            RadioHembra.place_forget()
            BComparar.place_forget()
            BInvertir.place_forget()

        ret, frame = capture.read()
        if ret == True:
            frame = imutils.resize(frame, width=300, height=220)

            frame_rgb_actual = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_actual = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            im = Image.fromarray(frame_rgb_actual)
            img = ImageTk.PhotoImage(image=im)
            LImagenCamara.configure(image=img)
            LImagenCamara.image = img

            valorUmbral = int(SGray.get())
            img_mask = cv2.inRange(frame_actual, valorUmbral, 255)
            img_mask_actual = img_mask.copy()
            img_mask_pil = Image.fromarray(img_mask)
            img_mask_photo = ImageTk.PhotoImage(image=img_mask_pil)
            LImagenUmbralizada.configure(image=img_mask_photo)
            LImagenUmbralizada.image = img_mask_photo

            LImagenCamara.after(10, iniciar)
        else:
            LImagenCamara.image = ""
            capture.release()


def umbralizar(val=None):
    global frame_actual, img_mask_actual, ImgRecUmbral

    if frame_actual is not None:
        valorUmbral = int(SGray.get())
        img_mask = cv2.inRange(frame_actual, valorUmbral, 255)
        img_mask_actual = img_mask.copy()

        img_mask_pil = Image.fromarray(img_mask)
        img_mask_photo = ImageTk.PhotoImage(image=img_mask_pil)
        LImagenUmbralizada.configure(image=img_mask_photo)
        LImagenUmbralizada.image = img_mask_photo


def guardar_patron():
    global imagen_para_comparar
    nombre = EntradaNombre.get()
    tipo = VariableTipo.get()

    if imagen_para_comparar is not None:
        filename = f"{nombre}_{tipo.lower()}.png"
        path = os.path.join(CARPETA_PATRONES, filename)
        imagen_para_comparar.save(path)


def toggle_invertir():
    global invertir_colores
    invertir_colores = not invertir_colores
    if invertir_colores:
        BInvertir.config(text="Inv", bg="#4a4a4a")
    else:
        BInvertir.config(text="Normal", bg="#2e2e2e")


def invertir_imagen_binaria(img_bin):
    return 1 - img_bin

def centrar_imagen(img):
    coords = np.column_stack(np.where(img > 0))

    if coords.size == 0:
        return img

    y, x = coords.mean(axis=0).astype(int)

    h, w = img.shape
    shiftx = w // 2 - x
    shifty = h // 2 - y

    M = np.float32([[1, 0, shiftx], [0, 1, shifty]])
    return cv2.warpAffine(img, M, (w, h))

def comparar_con_match_shapes(img_actual_bin, contorno_actual, archivos):
    resultados = []
    for archivo in archivos:
        if not archivo.endswith(".png"):
            continue
        path = os.path.join(CARPETA_PATRONES, archivo)
        plantilla = cv2.imread(path, 0)
        if plantilla is None:
            continue

        _, thresh_plantilla = cv2.threshold(plantilla, 127, 255, cv2.THRESH_BINARY)
        img_patron_bin = (thresh_plantilla == 0).astype(np.uint8)

        kernel = np.ones((3, 3), np.uint8)
        img_patron_bin = cv2.morphologyEx(img_patron_bin, cv2.MORPH_CLOSE, kernel)

        img_patron_resized = cv2.resize(img_patron_bin, (img_actual_bin.shape[1], img_actual_bin.shape[0]))

        contornos_patron, _ = cv2.findContours((img_patron_resized * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contornos_patron:
            continue

        contorno_patron = max(contornos_patron, key=cv2.contourArea)
        score_raw = cv2.matchShapes(contorno_actual, contorno_patron, cv2.CONTOURS_MATCH_I2, 0)
        score = 1 / (1 + score_raw)
        resultados.append((archivo, score))

    # No ordenar, mantener el orden original de la carpeta
    return resultados

def comparar_con_iou(img_actual_bin, archivos):
    resultados = []
    for archivo in archivos:
        if not archivo.endswith(".png"):
            continue
        path = os.path.join(CARPETA_PATRONES, archivo)
        plantilla = cv2.imread(path, 0)
        if plantilla is None:
            continue

        _, thresh_plantilla = cv2.threshold(plantilla, 127, 255, cv2.THRESH_BINARY)
        img_patron_bin = (thresh_plantilla == 0).astype(np.uint8)

        kernel = np.ones((3, 3), np.uint8)
        img_patron_bin = cv2.morphologyEx(img_patron_bin, cv2.MORPH_CLOSE, kernel)

        img_patron_resized = cv2.resize(img_patron_bin, (img_actual_bin.shape[1], img_actual_bin.shape[0]))

        interseccion = np.logical_and(img_actual_bin, img_patron_resized).sum()
        union = np.logical_or(img_actual_bin, img_patron_resized).sum()
        score = interseccion / union if union != 0 else 0
        resultados.append((archivo, score))

    # No ordenar, mantener el orden original de la carpeta
    return resultados

def comparar_con_template_matching(img_actual_gris, archivos):
    resultados = []

    def resize_con_padding(img, target_shape):
        h, w = img.shape
        th, tw = target_shape

        scale = min(tw / w, th / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        img_resized = cv2.resize(img, (new_w, new_h))

        result = np.zeros((th, tw), dtype=np.uint8)

        y_offset = (th - new_h) // 2
        x_offset = (tw - new_w) // 2

        result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = img_resized

        return result

    _, img_bin = cv2.threshold(img_actual_gris, 127, 255, cv2.THRESH_BINARY)
    img_edges = cv2.Canny(img_bin, 50, 150)

    for archivo in archivos:
        if not archivo.endswith(".png"):
            continue

        path = os.path.join(CARPETA_PATRONES, archivo)
        plantilla = cv2.imread(path, 0)

        if plantilla is None:
            continue

        _, plantilla_bin = cv2.threshold(plantilla, 127, 255, cv2.THRESH_BINARY)
        plantilla_edges = cv2.Canny(plantilla_bin, 50, 150)

        plantilla_edges = resize_con_padding(
            plantilla_edges,
            img_edges.shape
        )

        result = cv2.matchTemplate(
            img_edges,
            plantilla_edges,
            cv2.TM_CCOEFF_NORMED
        )

        score = np.max(result)
        score = (score + 1) / 2

        # --- Penalización por área ---
        area_actual = np.sum(img_bin > 0)
        area_patron = np.sum(plantilla_bin > 0)

        if max(area_actual, area_patron) > 0:
            ratio_area = min(area_actual, area_patron) / max(area_actual, area_patron)
        else:
            ratio_area = 0

        score = score * ratio_area

        resultados.append((archivo, score))

    return resultados

def mostrar_resultados_en_cajas(resultados_m, resultados_h, resultados_t):
    # Caja MatchShapes (M)
    ComparacionCajaM.config(state="normal")
    ComparacionCajaM.delete(1.0, tk.END)
    ComparacionCajaM.insert(tk.END, "MATCH SHAPES\n")
    ComparacionCajaM.insert(tk.END, f"{'Nombre':<25} {'Similitud':<15}\n")
    for nombre, score in resultados_m[:10]:
        nombre_mostrar = os.path.splitext(nombre)[0].replace("_", " ")
        ComparacionCajaM.insert(tk.END, f"{nombre_mostrar:<25} {score:.4f}\n")
    ComparacionCajaM.config(state="disabled")

    # Caja IoU (Momentos HU)
    ComparacionCajaH.config(state="normal")
    ComparacionCajaH.delete(1.0, tk.END)
    ComparacionCajaH.insert(tk.END, "MOMENTOS HU\n")
    ComparacionCajaH.insert(tk.END, f"{'Nombre':<25} {'Similitud':<15}\n")
    for nombre, score in resultados_h[:10]:
        nombre_mostrar = os.path.splitext(nombre)[0].replace("_", " ")
        ComparacionCajaH.insert(tk.END, f"{nombre_mostrar:<25} {score:.4f}\n")
    ComparacionCajaH.config(state="disabled")

    # Caja Template Matching (T)
    ComparacionCajaT.config(state="normal")
    ComparacionCajaT.delete(1.0, tk.END)
    ComparacionCajaT.insert(tk.END, "MATCH TEMPLATE\n")
    ComparacionCajaT.insert(tk.END, f"{'Nombre':<25} {'Similitud':<15}\n")
    for nombre, score in resultados_t[:10]:
        nombre_mostrar = os.path.splitext(nombre)[0].replace("_", " ")
        ComparacionCajaT.insert(tk.END, f"{nombre_mostrar:<25} {score:.4f}\n")
    ComparacionCajaT.config(state="disabled")

def mostrar_mejores_imagenes(resultados_m, resultados_h, resultados_t):
    if resultados_m:
        # Encontrar el de mayor score en match shapes
        mejor_m = max(resultados_m, key=lambda x: x[1])
        archivo_m = mejor_m[0]
        score_m = mejor_m[1]
        path_m = os.path.join(CARPETA_PATRONES, archivo_m)
        img_m = cv2.imread(path_m, cv2.IMREAD_GRAYSCALE)
        if img_m is not None:
            im_m = Image.fromarray(img_m)
            img_tk_m = ImageTk.PhotoImage(im_m)
            LImagenPatron1.configure(image=img_tk_m)
            LImagenPatron1.image = img_tk_m

    if resultados_h:
        # Encontrar el de mayor score en momentos hu
        mejor_h = max(resultados_h, key=lambda x: x[1])
        archivo_h = mejor_h[0]
        score_h = mejor_h[1]
        path_h = os.path.join(CARPETA_PATRONES, archivo_h)
        img_h = cv2.imread(path_h, cv2.IMREAD_GRAYSCALE)
        if img_h is not None:
            im_h = Image.fromarray(img_h)
            img_tk_h = ImageTk.PhotoImage(im_h)
            LImagenPatron2.configure(image=img_tk_h)
            LImagenPatron2.image = img_tk_h

    if resultados_t:
        # Encontrar el de mayor score en template matching
        mejor_t = max(resultados_t, key=lambda x: x[1])
        archivo_t = mejor_t[0]
        score_t = mejor_t[1]
        path_t = os.path.join(CARPETA_PATRONES, archivo_t)
        img_t = cv2.imread(path_t, cv2.IMREAD_GRAYSCALE)
        if img_t is not None:
            im_t = Image.fromarray(img_t)
            img_tk_t = ImageTk.PhotoImage(im_t)
            LImagenPatron3.configure(image=img_tk_t)
            LImagenPatron3.image = img_tk_t


def comparar_patrones():
    global imagen_para_comparar
    global resultados_match_shapes, resultados_iou, resultados_template

    if imagen_para_comparar is None:
        print("No hay imagen para comparar")
        return

    archivos = [a for a in os.listdir(CARPETA_PATRONES) if a.endswith(".png")]

    if not archivos:
        print("No hay patrones guardados")
        return

    img_actual_np = np.array(imagen_para_comparar)

    if len(img_actual_np.shape) == 3:
        img_actual_np = cv2.cvtColor(img_actual_np, cv2.COLOR_RGB2GRAY)

    _, thresh_actual = cv2.threshold(img_actual_np, 127, 255, cv2.THRESH_BINARY)
    img_actual_bin = (thresh_actual == 255).astype(np.uint8)

    if invertir_colores:
        img_actual_bin = invertir_imagen_binaria(img_actual_bin)

    kernel = np.ones((3, 3), np.uint8)
    img_actual_bin = cv2.morphologyEx(img_actual_bin, cv2.MORPH_CLOSE, kernel)

    img_actual_gris = (img_actual_bin * 255).astype(np.uint8)

    contornos_actual, _ = cv2.findContours(
        img_actual_gris,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contornos_actual:
        print("No se encontraron contornos")
        return

    contorno_actual = max(contornos_actual, key=cv2.contourArea)

    resultados_match_shapes = comparar_con_match_shapes(
        img_actual_bin, contorno_actual, archivos
    )

    resultados_iou = comparar_con_iou(
        img_actual_bin, archivos
    )

    resultados_template = comparar_con_template_matching(
        img_actual_gris, archivos
    )

    resultados_match_shapes = sorted(resultados_match_shapes, key=lambda x: x[1])
    resultados_iou = sorted(resultados_iou, key=lambda x: x[1], reverse=True)
    resultados_template = sorted(resultados_template, key=lambda x: x[1], reverse=True)

    if resultados_match_shapes:
        nombre, valor = resultados_match_shapes[0]
        LTextoPatron1.config(text=f"Match Shape: {nombre} | {valor*100:.1f}%")

    if resultados_iou:
        nombre, valor = resultados_iou[0]
        LTextoPatron2.config(text=f"Momentos HU: {nombre} | {valor*100:.1f}%")

    if resultados_template:
        nombre, valor = resultados_template[0]
        LTextoPatron3.config(text=f"Match Template: {nombre} | {valor*100:.1f}%")

    mostrar_resultados_en_cajas(
        resultados_match_shapes,
        resultados_iou,
        resultados_template
    )

    mostrar_mejores_imagenes(
        resultados_match_shapes,
        resultados_iou,
        resultados_template
    )


def manchasG():
    global imagen_para_comparar  # Usar la imagen recortada

    # Verificar si existe la imagen recortada
    if imagen_para_comparar is None:
        CajaManchas.configure(state="normal")
        CajaManchas.delete(1.0, tk.END)
        CajaManchas.insert(1.0, "No hay imagen recortada para analizar")
        CajaManchas.configure(state="disabled")
        return

    # Convertir la imagen recortada a numpy array si es necesario
    if hasattr(imagen_para_comparar, 'convert'):
        # Es una imagen PIL
        import numpy as np
        img_array = np.array(imagen_para_comparar)
    else:
        img_array = imagen_para_comparar

    # Asegurar que sea binaria (0 y 255)
    if len(img_array.shape) == 3:
        # Convertir a escala de grises si es RGB
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

    # Umbralizar para asegurar que sea binaria
    _, thresh1 = cv2.threshold(img_array, 127, 255, cv2.THRESH_BINARY)

    # INVERTIR la imagen para que las manchas (negras) se vuelvan blancas
    thresh1_invertida = cv2.bitwise_not(thresh1)

    total_pixeles = thresh1_invertida.size
    pixeles_blancos = cv2.countNonZero(thresh1_invertida)  # Estos son las manchas (eran negras)
    pixeles_negros = total_pixeles - pixeles_blancos

    porcentaje_manchas = (pixeles_blancos / total_pixeles) * 100
    porcentaje_sin_manchas = (pixeles_negros / total_pixeles) * 100

    # Detectar contornos en la imagen invertida (manchas ahora son blancas)
    contornos = cv2.findContours(thresh1_invertida, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
    numero_manchas = len(contornos)

    Cadena = (f"Área con manchas: {round(porcentaje_manchas, 2)}%\n"
              f"Área sin manchas: {round(porcentaje_sin_manchas, 2)}%\n"
              f"Número de manchas: {numero_manchas}")

    CajaManchas.configure(state="normal")
    CajaManchas.delete(1.0, tk.END)
    CajaManchas.insert(1.0, Cadena)
    CajaManchas.configure(state="disabled")


def click_guardar():
    filepath = asksaveasfilename(
        title="Guardando...",
        defaultextension="txt",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    if not filepath:
        return
    with open(filepath, "w") as output_file:
        text = TextEnviar.get(1.0, tk.END)
        output_file.write(text)

def leer_respuesta():
    ventana.after(1000, _leer_y_mostrar)

def _leer_y_mostrar():
    if SerialPort1.is_open:
        data = SerialPort1.read_all()
        if data:
            texto = data.decode(errors="ignore").strip()
            TextRecibidos.insert(tk.END, texto + "\n")
            TextRecibidos.see(tk.END)

def click_pcplc():
    SerialPort1.write(b"Run pcplc\r")
    leer_respuesta()


def click_a():
    SerialPort1.write(b"a\r")
    leer_respuesta()


def click_ttsib():
    SerialPort1.write(b"Run ppnb\r")
    leer_respuesta()


def click_coff():
    SerialPort1.write(b"coff\r")
    leer_respuesta()


def click_move():
    SerialPort1.write(b"move 0\r")
    leer_respuesta()


def click_open():
    SerialPort1.write(b"open\r")
    leer_respuesta()

def click_close():
    SerialPort1.write(b"close\r")
    leer_respuesta()


def toggle_conectar():
    if not SerialPort1.is_open:
        try:
            SerialPort1.port = CCOM.get()
            SerialPort1.baudrate = 9600
            SerialPort1.bytesize = serial.EIGHTBITS
            SerialPort1.parity = serial.PARITY_NONE
            SerialPort1.stopbits = serial.STOPBITS_ONE
            SerialPort1.timeout = 1
            SerialPort1.xonxoff = False
            SerialPort1.rtscts = False
            SerialPort1.dsrdtr = False
            SerialPort1.open()
            TextoEstado.config(text="CONECTADO")
            BConectar.config(text="Desconectar", bg="#8B0000", fg="white")
        except Exception as e:
            messagebox.showerror("Error", str(e))
    else:
        SerialPort1.close()
        TextoEstado.config(text="DESCONECTADO")
        BConectar.config(text="Conectar", bg="#2e2e2e", fg="white")

def click_desconectar():
    if SerialPort1.is_open:
        SerialPort1.close()
        TextoEstado.config(text="Desconectado")
        messagebox.showinfo(message="Puerto Desconectado")


def click_enviar():
    try:
        msj = TextEnviar.get(1.0, tk.END)
        lista = msj.split("\n")

        for x in lista:
            if x.strip() == "":
                continue
            SerialPort1.write(x.encode() + b"\r")
            time.sleep(1 + int(CNUM.get()))
            data = SerialPort1.read_all()
            if data:
                texto = data.decode(errors="ignore").strip()
                TextRecibidos.insert(tk.END, texto + "\n" )
                TextRecibidos.see(tk.END)

    except Exception as e:
        messagebox.showerror("Error", str(e))


def mostrar_panel(panel_seleccionado):
    # Comprobamos si el panel que apretamos ya está visible
    esta_visible = panel_seleccionado.winfo_ismapped()

    # 1. Ocultamos TODOS los frames para limpiar la pantalla
    frame_metodos.place_forget()
    frame_metodo.place_forget()

    # 2. Si el panel NO estaba visible, lo mostramos en su posición
    if not esta_visible:
        panel_seleccionado.place(x=820, y=275, width=460, height=390)


def ver_detalle_metodo(metodo):
    global fotos_miniaturas
    fotos_miniaturas = {}

    # Mostrar frame
    frame_metodos.place_forget()
    frame_Imetodo.place_forget()
    frame_metodo.place(x=820, y=275, width=460, height=390)

    # Limpiar
    for w in frame_metodo.winfo_children():
        w.destroy()

    # Scroll
    canvas = tk.Canvas(frame_metodo, bg="#1e3e1e", highlightthickness=0)
    scrollbar = tk.Scrollbar(frame_metodo, orient="vertical", command=canvas.yview)
    contenedor = tk.Frame(canvas, bg="#1e3e1e")

    contenedor.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=contenedor, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Elegir resultados y orden
    datos = {
        "shapes": (resultados_match_shapes, True),
        "hu": (resultados_iou, True),
        "template": (resultados_template, True)
    }

    if metodo not in datos:
        return

    resultados, invertir = datos[metodo]
    resultados = sorted(resultados, key=lambda x: x[1], reverse=invertir)

    # Mostrar
    for nombre, valor in resultados:

        fila = tk.Frame(contenedor, bg="#2e2e2e")
        fila.pack(fill="x", padx=5, pady=4, ipady=10)

        # Imagen
        try:
            img = Image.open(os.path.join(CARPETA_PATRONES, nombre)).convert("RGB")
            img.thumbnail((80, 80))
            foto = ImageTk.PhotoImage(img)
            fotos_miniaturas[nombre] = foto

            tk.Label(fila, image=foto, bg="#2e2e2e").pack(side="left", padx=5)
        except:
            tk.Label(fila, text="No Img", bg="#2e2e2e", fg="gray").pack(side="left", padx=5)

        base = os.path.splitext(nombre)[0]
        nombre_simple, tipo = base.rsplit("_", 1) if "_" in base else (base, "?")

        texto_valor = f"{valor*100:.1f}%"

        texto = f"{nombre_simple}\nTipo: {tipo}\n{texto_valor}"

        tk.Label(fila, text=texto, bg="#2e2e2e", fg="white",
                 font=("Arial", 10), justify="left", anchor="w").pack(side="left", padx=10)

LImagenCamara = tk.Label(ventana, background="#1e1e2e", text="Camara")
LImagenCamara.place(x=5, y=35, width=300, height=220)

LImagenUmbralizada = tk.Label(ventana, background="#1e1e2e", cursor="crosshair", text="Imagen Umbralizada")
LImagenUmbralizada.place(x=310, y=35, width=300, height=220)

LImagenUmbralizada.bind("<ButtonPress-1>", click_mouse)
LImagenUmbralizada.bind("<B1-Motion>", mover_mouse)
LImagenUmbralizada.bind("<ButtonRelease-1>", soltar_mouse)

LRecorteUmbralizado = tk.Label(ventana, background="#1e1e2e", text="Recorte")
LRecorteUmbralizado.place(x=615, y=35, width=300, height=220)


frame_metodos = tk.Frame(ventana, bg="#3e3e3e")
frame_metodo = tk.Frame(ventana, bg="#1e3e1e")
frame_Imetodo = tk.Frame(ventana, bg="#1e1e3e")

LTextoPatron1 = tk.Label(frame_metodos, bg="#1e1e1e", fg="white", text="Mach Shape", font=("Arial", 9))
LTextoPatron1.place(x=0, y=0, width=455, height=20)

LImagenPatron1 = tk.Label(frame_metodos, bg="#1e1e2e", text="Match Shapes")
LImagenPatron1.place(x=0, y=25, width=150, height=100)

ComparacionCajaM = tk.Text(frame_metodos, state="disabled", wrap=tk.WORD, bg="#2e2e2e", fg="white")
ComparacionCajaM.place(x=155, y=25, width=300, height=100)

BSsh = tk.Button(frame_metodos, text="Ver",
                 command=lambda: ver_detalle_metodo("shapes"))
BSsh.place(x=0, y=95, width=35, height=35)


# --- Bloque Momentos Hu ---
LTextoPatron2 = tk.Label(frame_metodos, bg="#1e1e1e", fg="white", text="Mometos Hu", font=("Arial", 9))
LTextoPatron2.place(x=0, y=130, width=455, height=20)

LImagenPatron2 = tk.Label(frame_metodos, bg="#1e1e2e", text="Momentos HU")
LImagenPatron2.place(x=0, y=155, width=150, height=100)

ComparacionCajaH = tk.Text(frame_metodos, state="disabled", wrap=tk.WORD, bg="#2e2e2e", fg="white")
ComparacionCajaH.place(x=155, y=155, width=300, height=100)

BShu = tk.Button(frame_metodos, text="Ver",
                 command=lambda: ver_detalle_metodo("hu"))
BShu.place(x=0, y=225, width=35, height=35)

# --- Bloque Match Template ---
LTextoPatron3 = tk.Label(frame_metodos, bg="#1e1e1e", fg="white", text="Match Template", font=("Arial", 9))
LTextoPatron3.place(x=0, y=260, width=455, height=20)

LImagenPatron3 = tk.Label(frame_metodos, bg="#1e1e2e", text="Template Matching")
LImagenPatron3.place(x=0, y=285, width=150, height=100)

ComparacionCajaT = tk.Text(frame_metodos, state="disabled", wrap=tk.WORD, bg="#2e2e2e", fg="white")
ComparacionCajaT.place(x=155, y=285, width=300, height=100)

BSte = tk.Button(frame_metodos, text="Ver",
                 command=lambda: ver_detalle_metodo("template"))
BSte.place(x=0, y=355, width=35, height=35)

Bmetodos = tk.Button(ventana, text="Ms", command=lambda: mostrar_panel(frame_metodos), bg="#2e2e2e", fg="white")
Bmetodos.place(x=820, y=675, width=35, height=35)

Bmetodo = tk.Button(ventana, text="Me", command=lambda: mostrar_panel(frame_metodo), bg="#2e2e2e", fg="white")
Bmetodo.place(x=860, y=675, width=35, height=35)

Coordenadas = tk.Label(ventana, text="", bg="#1e1e1e", fg="white")
Coordenadas.place(x=725, y=235, width=160, height=25)

BCamara = tk.Button(ventana, text="On", command=iniciar_camara)
BCamara.place(x=10, y=215, width=35, height=35)
BComparar = tk.Button(ventana, text="Comparar", command=comparar_patrones)
BGuardar = tk.Button(ventana, text="Guardar", command=guardar_patron)
BInvertir = tk.Button(ventana, text="Normal", command=toggle_invertir, bg="#2e2e2e", fg="white")

SGray = tk.Scale(ventana, from_=0, to=255, orient='horizontal', command=umbralizar, label="Umbral", fg="white",
                 bg="#1e1e1e")
SGray.set(127)

BAnalizarManchas = tk.Button(ventana, text="Manchas", command=manchasG,
                              bg="#2e2e2e", fg="white", font=("Arial", 8))
BAnalizarManchas.place(x=1225, y=35, width=50, height=35)

CajaManchas = tk.Text(ventana, state="disabled", bg="#2e2e2e", fg="white")
CajaManchas.place(x=920, y=110, width=355, height=105)

lenombre = tk.Label(ventana, background="#1e1e1e", fg="white", text="Nombre")
EntradaNombre = tk.Entry(ventana, fg="white", bg="#2e2e2e")
EntradaNombre.insert(0, "")
VariableTipo = tk.StringVar(value="Macho")
RadioMacho = tk.Radiobutton(ventana, text="M", bg="#1e1e1e", fg="white", variable=VariableTipo, value="Macho")
RadioHembra = tk.Radiobutton(ventana, text="F", bg="#1e1e1e", fg="white", variable=VariableTipo, value="Hembra")

TextRecibidos = tk.Text(ventana, height=15, width=40, bg="#2e2e2e", fg="white", font=("Courier", 14))
TextRecibidos.place(x=5, y=310, width=805, height=310)

TextEnviar = tk.Text(ventana, fg="white", bg="#2e2e2e", font=("Courier", 14))
TextEnviar.place(x=5, y=625, width=615, height=35)

BEnviar = tk.Button(ventana, text="Enviar", command=click_enviar)
BEnviar.place(x=625, y=625, width=90, height=35)

BGuardarC = tk.Button(ventana, text="Sv", command=click_guardar)
BGuardarC.place(x=720, y=625, width=35, height=35)

BAbort = tk.Button(ventana, text="Abort", command=click_a)
BAbort.place(x=760, y=625, width=50, height=35)

BConectar = tk.Button(ventana, text="Conectar", command=toggle_conectar, bg="#2e2e2e", fg="white")
BConectar.place(x=5, y=270, width=90, height=35)

TextoEstado = tk.Label(ventana, bg="#2e2e2e", fg="white")
TextoEstado.place(x=570, y=270, width=110, height=35)
TextoEstado.config(text="DESCONECTADO")

CCOM = ttk.Combobox(
    state="readonly",
    values=["COM1","COM2","COM3","COM4","COM5","COM6","COM7","COM8","COM9","COM10"]
)
CCOM.set("COM1")
CCOM.place(x=100, y=270, width=60, height=35)

CNUM = ttk.Combobox(
    state="readonly",
    values=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
)
CNUM.set(0)
CNUM.place(x=165, y=270, width=40, height=35)

BPCPLC = tk.Button(ventana, text="Run PCPLC", command=click_pcplc)
BPCPLC.place(x=210, y=270, width=70, height=35)

BPPNB = tk.Button(ventana, text="Run PPNB", command=click_ttsib)
BPPNB.place(x=285, y=270, width=70, height=35)

BCoff = tk.Button(ventana, text="Coff", command=click_coff)
BCoff.place(x=360, y=270, width=50, height=35)

BMove0 = tk.Button(ventana, text="Move O", command=click_move)
BMove0.place(x=415, y=270, width=60, height=35)

BClose = tk.Button(ventana, text="Close", command=click_open)
BClose.place(x=480, y=270, width=40, height=35)

BOpen = tk.Button(ventana, text="Open", command=click_close)
BOpen.place(x=525, y=270, width=40, height=35)


ventana.mainloop()
