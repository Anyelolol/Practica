import tkinter as tk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import cv2
from cv2_enumerate_cameras import enumerate_cameras
import numpy as np
import imutils
import os

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
        label_w = 311
        label_h = 241

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

    Coordenadas.config(text=f"{x1_img}.{y1_img} -- {x2_img}.{y2_img}", fg="white")


def iniciar():
    global capture, frame_actual, frame_rgb_actual, img_mask_actual
    if capture is not None:
        if boton_iniciar_visible:
            SGray.place(x=440, y=305, width=190, height=55)
            BGuardar.place(x=875, y=320, width=65, height=35)
            lenombre.place(x=640, y=320, width=50, height=35)
            EntradaNombre.place(x=700, y=320, width=120, height=35)
            RadioMacho.place(x=830, y=315)
            RadioHembra.place(x=830, y=340)
            BComparar.place(x=5, y=340, width=100, height=35)
            BInvertir.place(x=110, y=340, width=50, height=35)
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
            frame = imutils.resize(frame, width=311, height=241)

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

    # --- Imagen actual ---
    _, img_bin = cv2.threshold(img_actual_gris, 127, 255, cv2.THRESH_BINARY)
    img_edges = cv2.Canny(img_bin, 50, 150)

    for archivo in archivos:
        if not archivo.endswith(".png"):
            continue

        path = os.path.join(CARPETA_PATRONES, archivo)
        plantilla = cv2.imread(path, 0)

        if plantilla is None:
            continue

        # --- Plantilla ---
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
            nombre_m = os.path.splitext(archivo_m)[0].replace("_", " ")
            LTextoPatron1.config(text=f"MatchShapes: {nombre_m} ({score_m:.4f})")

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
            nombre_h = os.path.splitext(archivo_h)[0].replace("_", " ")
            LTextoPatron2.config(text=f"Momentos Hu: {nombre_h} ({score_h:.4f})")

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
            nombre_t = os.path.splitext(archivo_t)[0].replace("_", " ")
            LTextoPatron3.config(text=f"Template: {nombre_t} ({score_t:.4f})")


def comparar_patrones():
    global imagen_para_comparar

    if imagen_para_comparar is None:
        return

    archivos = os.listdir(CARPETA_PATRONES)
    if not archivos:
        return

    # Preparar imagen actual
    img_actual_np = np.array(imagen_para_comparar)
    _, thresh_actual = cv2.threshold(img_actual_np, 127, 255, cv2.THRESH_BINARY)
    img_actual_bin = (thresh_actual == 255).astype(np.uint8)

    # Aplicar inversion solo a la imagen recortada si el modo esta activado
    if invertir_colores:
        img_actual_bin = invertir_imagen_binaria(img_actual_bin)

    kernel = np.ones((3, 3), np.uint8)
    img_actual_bin = cv2.morphologyEx(img_actual_bin, cv2.MORPH_CLOSE, kernel)

    img_actual_gris = (img_actual_bin * 255).astype(np.uint8)

    contornos_actual, _ = cv2.findContours((img_actual_bin * 255), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos_actual:
        return

    contorno_actual = max(contornos_actual, key=cv2.contourArea)

    # Filtrar solo archivos de imagen y mantener orden original
    archivos_img = [a for a in archivos if a.endswith(".png")]

    resultados_match_shapes = comparar_con_match_shapes(img_actual_bin, contorno_actual, archivos_img)
    resultados_iou = comparar_con_iou(img_actual_bin, archivos_img)
    resultados_template = comparar_con_template_matching(img_actual_gris, archivos_img)

    mostrar_resultados_en_cajas(resultados_match_shapes, resultados_iou, resultados_template)
    mostrar_mejores_imagenes(resultados_match_shapes, resultados_iou, resultados_template)


# UI Elements
LImagenCamara = tk.Label(ventana, background="#1e1e2e", text="Camara")
LImagenCamara.place(x=5, y=65, width=311, height=241)

LImagenUmbralizada = tk.Label(ventana, background="#1e1e2e", cursor="crosshair", text="Imagen Umbralizada")
LImagenUmbralizada.place(x=320, y=65, width=311, height=241)

LImagenUmbralizada.bind("<ButtonPress-1>", click_mouse)
LImagenUmbralizada.bind("<B1-Motion>", mover_mouse)
LImagenUmbralizada.bind("<ButtonRelease-1>", soltar_mouse)

LRecorteUmbralizado = tk.Label(ventana, background="#1e1e2e", text="Recorte")
LRecorteUmbralizado.place(x=635, y=65, width=311, height=241)

LImagenPatron1 = tk.Label(ventana, bg="#1e1e2e", text="Match Shapes")
LImagenPatron1.place(x=955, y=5, width=311, height=200)

LImagenPatron2 = tk.Label(ventana, bg="#1e1e2e", text="Momentos HU")
LImagenPatron2.place(x=955, y=245, width=311, height=200)

LImagenPatron3 = tk.Label(ventana, bg="#1e1e2e", text="Template Matching")
LImagenPatron3.place(x=955, y=490, width=311, height=200)

LTextoPatron1 = tk.Label(ventana, bg="#1e1e1e", fg="white", text="Esperando...", font=("Arial", 9))
LTextoPatron1.place(x=955, y=205, width=311, height=40)

LTextoPatron2 = tk.Label(ventana, bg="#1e1e1e", fg="white", text="Esperando...", font=("Arial", 9))
LTextoPatron2.place(x=955, y=445, width=311, height=40)

LTextoPatron3 = tk.Label(ventana, bg="#1e1e1e", fg="white", text="Esperando...", font=("Arial", 9))
LTextoPatron3.place(x=955, y=680, width=311, height=40)

Coordenadas = tk.Label(ventana, text="recortar", bg="#1e1e1e", fg="white")
Coordenadas.place(x=325, y=310, width=90, height=25)

BCamara = tk.Button(ventana, text="On", command=iniciar_camara)
BCamara.place(x=280, y=270, width=35, height=35)
BComparar = tk.Button(ventana, text="Comparar", command=comparar_patrones)
BGuardar = tk.Button(ventana, text="Guardar", command=guardar_patron)
BInvertir = tk.Button(ventana, text="Normal", command=toggle_invertir, bg="#2e2e2e", fg="white")

SGray = tk.Scale(ventana, from_=0, to=255, orient='horizontal', command=umbralizar, label="Umbral", fg="white",
                 bg="#1e1e1e")
SGray.set(127)

# Tres cajas de texto para los resultados de cada metodo
ComparacionCajaM = tk.Text(ventana, state="disabled", wrap=tk.WORD, height=15, width=40, bg="#2e2e2e", fg="white")
ComparacionCajaM.place(x=5, y=390, width=311, height=300)

ComparacionCajaH = tk.Text(ventana, state="disabled", wrap=tk.WORD, height=15, width=40, bg="#2e2e2e", fg="white")
ComparacionCajaH.place(x=320, y=390, width=311, height=300)

ComparacionCajaT = tk.Text(ventana, state="disabled", wrap=tk.WORD, height=15, width=40, bg="#2e2e2e", fg="white")
ComparacionCajaT.place(x=635, y=390, width=311, height=300)

lenombre = tk.Label(ventana, background="#1e1e1e", fg="white", text="Nombre")
EntradaNombre = tk.Entry(ventana, fg="white", bg="#2e2e2e")
EntradaNombre.insert(0, "")
VariableTipo = tk.StringVar(value="Macho")
RadioMacho = tk.Radiobutton(ventana, text="M", bg="#1e1e1e", fg="white", variable=VariableTipo, value="Macho")
RadioHembra = tk.Radiobutton(ventana, text="F", bg="#1e1e1e", fg="white", variable=VariableTipo, value="Hembra")

ventana.mainloop()
