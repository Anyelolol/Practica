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
frame_actual = None  # Frame original en grises
frame_rgb_actual = None  # Frame original en RGB
img_mask_actual = None  # Imagen umbralizada actual

ventana = tk.Tk()
ventana.geometry("1280x720")
ventana.resizable(False, False)
ventana.configure(bg="#1e1e1e")
ventana.title("Análisis de patrones")

# Variables para el recorte con mouse
drawing = False
ix, iy = -1, -1
fx, fy = -1, -1
ImgRecUmbral = None


def iniciar_camara():
    global ventana_camaras
    ventana_camaras = tk.Toplevel(ventana)

    if (len(enumerate_cameras(cv2.CAP_MSMF)) > 1):
        ventana_camaras.title("Seleccionar cámara")
        ventana_camaras.minsize(300, 1)
        ventana_camaras.maxsize(300, 9999)
        ventana_camaras.resizable(False, False)

        ventana_camaras.withdraw()

        LCamaras = tk.Label(ventana_camaras, text="Se detectaron " + str(
            len(enumerate_cameras(cv2.CAP_MSMF))) + " cámaras.\nSeleccione una cámara para iniciar.")
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
        except Exception as e:
            messagebox.showerror(message="Error al inicializar la cámara: " + str(e))
    else:
        if capture is not None:
            capture.release()
            boton_iniciar_visible = False
        LImagenCamara.configure(image="")
        LImagenUmbralizada.configure(image="")
        LRecorteUmbralizado.configure(image="")
        messagebox.showinfo(message="Cámara desactivada")
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

    # Obtener dimensiones del label
    label_w = LImagenUmbralizada.winfo_width()
    label_h = LImagenUmbralizada.winfo_height()

    if label_w <= 1 or label_h <= 1:
        label_w = 311
        label_h = 241

    # Obtener dimensiones de la imagen mostrada
    if LImagenUmbralizada.image is None:
        Coordenadas.config(text="No", fg="red")
        return

    img_w_display = LImagenUmbralizada.image.width()
    img_h_display = LImagenUmbralizada.image.height()

    # Calcular offset para centrado
    offset_x = (label_w - img_w_display) // 2
    offset_y = (label_h - img_h_display) // 2

    # Ajustar coordenadas considerando el offset
    x1 = ix - offset_x
    y1 = iy - offset_y
    x2 = fx - offset_x
    y2 = fy - offset_y

    # Limitar coordenadas al rango de la imagen
    x1 = max(0, min(x1, img_w_display))
    x2 = max(0, min(x2, img_w_display))
    y1 = max(0, min(y1, img_h_display))
    y2 = max(0, min(y2, img_h_display))

    # Ordenar coordenadas
    x1, x2 = sorted([x1, x2])
    y1, y2 = sorted([y1, y2])

    if x1 == x2 or y1 == y2:
        Coordenadas.config(text="No", fg="yellow")
        return

    # Calcular escala entre imagen mostrada y frame real
    scale_x = frame_actual.shape[1] / img_w_display
    scale_y = frame_actual.shape[0] / img_h_display

    # Aplicar escala para obtener coordenadas en el frame original
    x1_img = int(x1 * scale_x)
    x2_img = int(x2 * scale_x)
    y1_img = int(y1 * scale_y)
    y2_img = int(y2 * scale_y)

    # Recortar la imagen umbralizada
    ImgRecUmbral = img_mask_actual[y1_img:y2_img, x1_img:x2_img]

    if ImgRecUmbral.size == 0:
        Coordenadas.config(text="Error", fg="red")
        return

    # Mostrar el recorte umbralizado
    ImgG = Image.fromarray(ImgRecUmbral)
    ImgG_photo = ImageTk.PhotoImage(image=ImgG)
    LRecorteUmbralizado.configure(image=ImgG_photo)
    LRecorteUmbralizado.image = ImgG_photo

    # Guardar imagen umbralizada recortada para comparar
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
            BComparar.place(x=630, y=440, width=100, height=35)
        else:
            SGray.place_forget()
            BGuardar.place_forget()
            EntradaNombre.place_forget()
            RadioMacho.place_forget()
            RadioHembra.place_forget()
            BComparar.place_forget()

        ret, frame = capture.read()
        if ret == True:
            # Redimensionar
            frame = imutils.resize(frame, width=311, height=241)

            # Guardar frames originales para recortes
            frame_rgb_actual = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_actual = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Mostrar imagen original en color
            im = Image.fromarray(frame_rgb_actual)
            img = ImageTk.PhotoImage(image=im)
            LImagenCamara.configure(image=img)
            LImagenCamara.image = img

            # Aplicar umbral y mostrar
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
            messagebox.showerror(message="No se pudo capturar ningún fotograma")


def umbralizar(val=None):
    global frame_actual, img_mask_actual, ImgRecUmbral

    if frame_actual is not None:
        valorUmbral = int(SGray.get())
        img_mask = cv2.inRange(frame_actual, valorUmbral, 255)
        img_mask_actual = img_mask.copy()

        # Actualizar imagen umbralizada principal
        img_mask_pil = Image.fromarray(img_mask)
        img_mask_photo = ImageTk.PhotoImage(image=img_mask_pil)
        LImagenUmbralizada.configure(image=img_mask_photo)
        LImagenUmbralizada.image = img_mask_photo


def guardar_patron():
    global imagen_para_comparar
    nombre = EntradaNombre.get()
    tipo = VariableTipo.get()

    if imagen_para_comparar is None:
        messagebox.showwarning("Advertencia", "No hay imagen para guardar")
        return

    filename = f"{nombre}_{tipo.lower()}.png"
    path = os.path.join(CARPETA_PATRONES, filename)

    imagen_para_comparar.save(path)
    messagebox.showinfo("Guardado", f"Patrón guardado: {filename}")


def cargar_imagen(label_destino):
    archivo = filedialog.askopenfilename( initialdir=CARPETA_PATRONES, title="Seleccionar imagen", filetypes=[("Imagenes", "*.png *.jpg *.jpeg")])

    if archivo:
        try:
            # Cargar la imagen con PIL
            imagen = Image.open(archivo)

            # Redimensionar manteniendo la proporción
            ancho_label = 311
            alto_label = 241

            # Calcular nuevas dimensiones manteniendo aspecto
            ratio = min(ancho_label / imagen.width, alto_label / imagen.height)
            nuevo_ancho = int(imagen.width * ratio)
            nuevo_alto = int(imagen.height * ratio)

            imagen_redimensionada = imagen.resize((nuevo_ancho, nuevo_alto), Image.Resampling.LANCZOS)

            # Crear fondo negro del tamaño del label y centrar la imagen
            fondo = Image.new('RGB', (ancho_label, alto_label), (30, 30, 46))
            x_offset = (ancho_label - nuevo_ancho) // 2
            y_offset = (alto_label - nuevo_alto) // 2
            fondo.paste(imagen_redimensionada, (x_offset, y_offset))

            # Convertir a PhotoImage y mostrar
            img_tk = ImageTk.PhotoImage(fondo)
            label_destino.configure(image=img_tk)
            label_destino.image = img_tk

            messagebox.showinfo("Éxito", f"Lidto{os.path.basename(archivo)}")

        except Exception as e:
            messagebox.showerror("Error", f"No cargo\n{str(e)}")

def comparar_patrones():
    global imagen_para_comparar

    # 🔴 labels (IMPORTANTE)
    labels_img = [LImagenPatron1, LImagenPatron2, LImagenPatron3]
    labels_txt = [LTextoPatron1, LTextoPatron2, LTextoPatron3]

    if imagen_para_comparar is None:
        messagebox.showwarning("Advertencia", "No hay imagen")
        return

    archivos = os.listdir(CARPETA_PATRONES)
    if not archivos:
        messagebox.showerror("Error", "No hay patrones guardados en la carpeta")
        return

    # 🔥 lista de resultados (EL ERROR ESTABA AQUÍ)
    resultados = []

    # 🔥 imagen actual
    img_actual_np = np.array(imagen_para_comparar)
    _, thresh_actual = cv2.threshold(img_actual_np, 127, 255, cv2.THRESH_BINARY)

    img_actual_bin = (thresh_actual == 0).astype(np.uint8)

    kernel = np.ones((3, 3), np.uint8)
    img_actual_bin = cv2.morphologyEx(img_actual_bin, cv2.MORPH_CLOSE, kernel)

    contornos_actual, _ = cv2.findContours(
        (img_actual_bin * 255),
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contornos_actual:
        messagebox.showerror("Error", "No se encontró contorno en imagen actual")
        return

    contorno_actual = max(contornos_actual, key=cv2.contourArea)

    # 🔍 comparar con patrones
    for archivo in archivos:
        if archivo.endswith(".png"):
            path = os.path.join(CARPETA_PATRONES, archivo)
            plantilla = cv2.imread(path, 0)

            if plantilla is None:
                continue

            _, thresh_plantilla = cv2.threshold(plantilla, 127, 255, cv2.THRESH_BINARY)

            img_patron_bin = (thresh_plantilla == 0).astype(np.uint8)
            img_patron_bin = cv2.morphologyEx(img_patron_bin, cv2.MORPH_CLOSE, kernel)

            img_patron_resized = cv2.resize(
                img_patron_bin,
                (img_actual_bin.shape[1], img_actual_bin.shape[0])
            )

            # 🔥 IoU (área negra)
            interseccion = np.logical_and(img_actual_bin, img_patron_resized).sum()
            union = np.logical_or(img_actual_bin, img_patron_resized).sum()
            score_iou = interseccion / union if union != 0 else 0

            contornos_patron, _ = cv2.findContours(
                (img_patron_resized * 255),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )

            if not contornos_patron:
                continue

            contorno_patron = max(contornos_patron, key=cv2.contourArea)

            # 🔥 matchShapes
            score_shape_raw = cv2.matchShapes(
                contorno_actual,
                contorno_patron,
                cv2.CONTOURS_MATCH_I2,
                0
            )

            score_shape = 1 / (1 + score_shape_raw)

            # 🔥 score final
            score_final = (score_shape * 0.4) + (score_iou * 0.6)

            resultados.append((archivo, score_final))

    # 🔄 ordenar
    resultados.sort(key=lambda x: x[1], reverse=True)

    # 📊 mostrar en textbox
    ComparacionCaja.config(state="normal")
    ComparacionCaja.delete(1.0, tk.END)

    encabezado = f"{'Nombre':<25} {'Similitud':<25}\n"
    ComparacionCaja.insert(tk.END, encabezado)

    for nombre, score in resultados:
        nombre_mostrar = os.path.splitext(nombre)[0].replace("_", " ")
        texto = f"{nombre_mostrar:<25} {score:.5f}\n"
        ComparacionCaja.insert(tk.END, texto)

    ComparacionCaja.config(state="disabled")

    # 🖼 mostrar TOP 3
    for i in range(3):

        if i >= len(resultados):
            labels_img[i].configure(image="")
            labels_txt[i].configure(text="Vacío")
            continue

        archivo = resultados[i][0]
        score = resultados[i][1]

        path = os.path.join(CARPETA_PATRONES, archivo)
        img_patron = cv2.imread(path, 0)

        _, thresh_patron = cv2.threshold(img_patron, 127, 255, cv2.THRESH_BINARY)
        img_patron_bin = (thresh_patron == 0).astype(np.uint8)

        contornos_patron, _ = cv2.findContours(
            (img_patron_bin * 255),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        img_color = cv2.cvtColor(img_patron, cv2.COLOR_GRAY2RGB)

        # 🔴 encontrar mejor contorno
        if contornos_patron:
            mejor_contorno = None
            mejor_score = float("inf")

            for cnt in contornos_patron:
                if cv2.contourArea(cnt) < 50:
                    continue

                s = cv2.matchShapes(contorno_actual, cnt, cv2.CONTOURS_MATCH_I2, 0)

                if s < mejor_score:
                    mejor_score = s
                    mejor_contorno = cnt

            if mejor_contorno is not None:
                x, y, w, h = cv2.boundingRect(mejor_contorno)
                cv2.rectangle(img_color, (x, y), (x + w, y + h), (255, 0, 0), 2)

        # mostrar imagen
        im = Image.fromarray(img_color)
        img_tk = ImageTk.PhotoImage(image=im)

        labels_img[i].configure(image=img_tk)
        labels_img[i].image = img_tk

        # mostrar texto debajo
        nombre_limpio = os.path.splitext(archivo)[0].replace("_", " ")
        labels_txt[i].configure(
            text=f"#{i+1} {nombre_limpio}\nSimilitud: {score:.3f}",
            justify="center"
        )

# Imagenes
LImagenCamara = tk.Label(ventana, background="#1e1e2e", text="Cámara")
LImagenCamara.place(x=5, y=65, width=311, height=241)

LImagenUmbralizada = tk.Label(ventana, background="#1e1e2e", cursor="crosshair", text="Imagen Umbralizada")
LImagenUmbralizada.place(x=320, y=65, width=311, height=241)

# Bindings para recorte con mouse
LImagenUmbralizada.bind("<ButtonPress-1>", click_mouse)
LImagenUmbralizada.bind("<B1-Motion>", mover_mouse)
LImagenUmbralizada.bind("<ButtonRelease-1>", soltar_mouse)

LRecorteUmbralizado = tk.Label(ventana, background="#1e1e2e", text="Recorte")
LRecorteUmbralizado.place(x=635, y=65, width=311, height=241)

# IMÁGENES
LImagenPatron1 = tk.Label(ventana, bg="#1e1e2e")
LImagenPatron1.place(x=955, y=5, width=311, height=200)

LImagenPatron2 = tk.Label(ventana, bg="#1e1e2e")
LImagenPatron2.place(x=955, y=245, width=311, height=200)

LImagenPatron3 = tk.Label(ventana, bg="#1e1e2e")
LImagenPatron3.place(x=955, y=490, width=311, height=200)


# TEXTOS (DEBAJO)
LTextoPatron1 = tk.Label(ventana, bg="#1e1e1e", fg="white")
LTextoPatron1.place(x=955, y=205, width=311, height=40)

LTextoPatron2 = tk.Label(ventana, bg="#1e1e1e", fg="white")
LTextoPatron2.place(x=955, y=445, width=311, height=40)

LTextoPatron3 = tk.Label(ventana, bg="#1e1e1e", fg="white")
LTextoPatron3.place(x=955, y=680, width=311, height=40)

Coordenadas = tk.Label(ventana, text="recortar", bg="#1e1e1e", fg="white")
Coordenadas.place(x=325, y=310, width=90, height=25)

# Botones
BCamara = tk.Button(ventana, text="On", command=iniciar_camara)
BCamara.place(x=280, y=270, width=35, height=35)
BComparar = tk.Button(ventana, text="Comparar", command=comparar_patrones)
BGuardar = tk.Button(ventana, text="Guardar", command=guardar_patron)

# Slider
SGray = tk.Scale(ventana, from_=0, to=255, orient='horizontal', command=umbralizar, label="Umbral", fg="white", bg="#1e1e1e")
SGray.set(127)

# TextBox
ComparacionCaja = tk.Text(ventana, state="disabled", wrap=tk.WORD, height=15, width=40)
ComparacionCaja.place(x=5, y=390, width=311, height=300)

# Entradas
lenombre = tk.Label(ventana, background="#1e1e1e", fg="white", text="Nombre")
EntradaNombre = tk.Entry(ventana, fg="white", bg="#2e2e2e")
EntradaNombre.insert(0, "")
VariableTipo = tk.StringVar(value="Macho")
RadioMacho = tk.Radiobutton(ventana, text="M", bg="#1e1e1e", fg="white", variable=VariableTipo, value="Macho")
RadioHembra = tk.Radiobutton(ventana, text="F", bg="#1e1e1e", fg="white", variable=VariableTipo, value="Hembra")

ventana.mainloop()
