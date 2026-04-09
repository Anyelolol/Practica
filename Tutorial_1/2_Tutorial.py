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

ventana = tk.Tk()
ventana.geometry("1115x620")
ventana.resizable(False, False)
ventana.title("Análisis de patrones")


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
        messagebox.showinfo(message="Cámara desactivada")
        camara_activada = False


def iniciar():
    global capture, ImagenCamara
    if capture is not None:
        if boton_iniciar_visible:
            LRecorteScale.place(x=50, y=10)
            LUmbralScale.place(x=435, y=10)
            SGray.place(x=435, y=25, width=300)

            LUmbralTexto.place(x=430, y=315)
            BCapturar.place(x=535, y=340, width=100, height=23)

            LGuardar.place(x=430, y=365)
            BGuardar.place(x=430, y=390, width=100, height=23)
            EntradaNombre.place(x=535, y=392, width=80)
            RadioMacho.place(x=610, y=390)
            RadioHembra.place(x=675, y=390)

            LComparar.place(x=430, y=415)
            BComparar.place(x=535, y=440, width=100, height=23)
        else:
            LRecorteScale.place_forget()

            LUmbralScale.place_forget()
            SGray.place_forget()

            LUmbralTexto.place_forget()
            BCapturar.place_forget()

            LGuardar.place_forget()
            BGuardar.place_forget()
            EntradaNombre.place_forget()
            RadioMacho.place_forget()
            RadioHembra.place_forget()

            LComparar.place_forget()
            BComparar.place_forget()

        ret, frame = capture.read()
        if ret == True:
            frame = imutils.resize(frame, width=311, height=241)
            ImagenCamara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(ImagenCamara)
            img = ImageTk.PhotoImage(image=im)
            LImagenCamara.configure(image=img)
            LImagenCamara.image = img
            valorUmbral = int(SGray.get())
            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            img_mask = cv2.inRange(gray_frame, valorUmbral, 255)
            img_mask_pil = Image.fromarray(img_mask)
            img_mask_photo = ImageTk.PhotoImage(image=img_mask_pil)
            LImagenCamara2.configure(image=img_mask_photo)
            LImagenCamara2.image = img_mask_photo

            LImagenCamara.after(10, iniciar)
        else:
            LImagenCamara.image = ""
            capture.release()
            messagebox.showerror(message="No se pudo capturar ningún fotograma")

def capturar():
    global valor, captura
    camara = capture
    return_value, image = camara.read()
    frame = imutils.resize(image, width=311, height=241)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(rgb)
    img = ImageTk.PhotoImage(image=im)
    LImagenCamara.configure(image=img)
    LImagenCamara.image = img
    captura = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    valor = 2


def click_mouse(event):
    global ix, iy, drawing
    drawing = True
    ix, iy = event.x, event.y
    Coordenadas['text'] = f'x = {event.x}, y = {event.y}'


def mover_mouse(event):
    global fx, fy
    if drawing:
        fx, fy = event.x, event.y
        Coordenadas['text'] = f'x = {event.x}, y = {event.y}'


def soltar_mouse(event):
    global Roi_1, drawing, fx, fy, frame_actual, ImgRec, ImgRecGray
    global zoom_original, CapturaG, CapturaRGB, modo_zoom

    drawing = False
    fx, fy = event.x, event.y

    if frame_actual is None or CapturaG is None or CapturaRGB is None:
        return

    label_w = LImagenRecorte.winfo_width()
    label_h = LImagenRecorte.winfo_height()

    img_w_display = LImagenRecorte.image.width()
    img_h_display = LImagenRecorte.image.height()

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
        return

    scale_x = frame_actual.shape[1] / img_w_display
    scale_y = frame_actual.shape[0] / img_h_display

    x1 = int(x1 * scale_x)
    x2 = int(x2 * scale_x)
    y1 = int(y1 * scale_y)
    y2 = int(y2 * scale_y)

    ImgRecGray = frame_actual[y1:y2, x1:x2]
    ImgRec = CapturaRGB[y1:y2, x1:x2]

    if ImgRecGray.size == 0:
        return

    ImG = Image.fromarray(ImgRecGray)
    ImgG = ImageTk.PhotoImage(image=ImG)
    GImagenROI.configure(image=ImgG)
    GImagenROI.image = ImgG

    if ImgRec.size != 0:
        Im = Image.fromarray(ImgRec)
        ImRec = ImageTk.PhotoImage(image=Im)
        LImagenROI.config(image=ImRec)
        LImagenROI.image = ImRec

        zoom_original = ImgRec.copy()
        modo_zoom = "color"
        actualizar_zoom()


def actualizar_zoom():
    global zoom_original, modo_zoom, mascara_rgb_actual, thresh1, ImgRec
    if modo_zoom == "color" and ImgRec is not None:
        imagen_a_mostrar = ImgRec
    elif modo_zoom == "mascara_rgb" and mascara_rgb_actual is not None:
        imagen_a_mostrar = mascara_rgb_actual
    elif modo_zoom == "umbral" and thresh1 is not None:
        imagen_a_mostrar = thresh1
    else:
        return
    if imagen_a_mostrar is None or imagen_a_mostrar.size == 0:
        return
    height, width = imagen_a_mostrar.shape[:2]
    new_height = int(height * 2.5)
    new_width = int(width * 2.5)
    if len(imagen_a_mostrar.shape) == 3:
        zoomed = cv2.resize(imagen_a_mostrar, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        if zoomed.shape[2] == 3:
            zoomed_rgb = zoomed
        else:
            zoomed_rgb = cv2.cvtColor(zoomed, cv2.COLOR_BGR2RGB)
    else:
        zoomed = cv2.resize(imagen_a_mostrar, (new_width, new_height), interpolation=cv2.INTER_LINEAR)
        zoomed_rgb = cv2.cvtColor(zoomed, cv2.COLOR_GRAY2RGB)
    zoomed_pil = Image.fromarray(zoomed_rgb)
    zoomed_pil.thumbnail((950, 200), Image.Resampling.LANCZOS)
    zoomed_tk = ImageTk.PhotoImage(image=zoomed_pil)
    LImagenZoom.config(image=zoomed_tk)
    LImagenZoom.image = zoomed_tk


def resetear_vista():
    global modo_zoom
    modo_zoom = "color"
    actualizar_zoom()


def guardar_patron():
    global imagen_para_comparar
    nombre = EntradaNombre.get()
    tipo = VariableTipo.get()

    if imagen_para_comparar is None:
        messagebox.showwarning("Advertencia", "No hay imagen para guardar")
        return

    filename = f"{nombre}_{tipo.lower()}.png"
    path = os.path.join(CARPETA_PATRONES, filename)

    try:
        imagen_para_comparar.save(path)

        messagebox.showinfo("Guardado", f"Patrón guardado: {filename}")
    except Exception as e:
        messagebox.showerror("Error", f"Error al guardar: {e}")

def umbralizar(val=None):
    global imagen_para_comparar
    recortada = ImagenCamara

    if recortada is not None:
        valorUmbral = int(SGray.get())
        img_mask = cv2.inRange(recortada, valorUmbral, 255)

        img_aux = 255 - img_mask
        img_mask = Image.fromarray(img_mask)
        imagen_para_comparar = img_mask
        img_mask = ImageTk.PhotoImage(image=img_mask)
        LImagenUmbral.configure(image=img_mask)
        LImagenUmbral.image = img_mask


def comparar_patrones():
    global imagen_para_comparar

    if imagen_para_comparar is None:
        messagebox.showwarning("Advertencia", "No hay imagen para comparar")
        return

    archivos = os.listdir(CARPETA_PATRONES)
    if not archivos:
        messagebox.showerror("Error", "No hay patrones guardados en la carpeta.")
        return

    resultados = []

    img_actual_np = np.array(imagen_para_comparar)
    _, thresh_actual = cv2.threshold(img_actual_np, 127, 255, cv2.THRESH_BINARY)

    for archivo in archivos:
        if archivo.endswith(".png"):
            path = os.path.join(CARPETA_PATRONES, archivo)
            plantilla = cv2.imread(path, 0)

            if plantilla is None:
                continue

            try:
                _, thresh_plantilla = cv2.threshold(plantilla, 127, 255, cv2.THRESH_BINARY)
                score = cv2.matchShapes(thresh_actual, thresh_plantilla, cv2.CONTOURS_MATCH_I2, 0)

                resultados.append((archivo, score))
            except Exception as e:
                print(f"Error comparando {archivo}: {e}")

    resultados.sort(key=lambda x: x[1])

    ComparacionCaja.config(state="normal")
    ComparacionCaja.delete(1.0, tk.END)

    encabezado = f"{'Nombre':<25} {'Diferencia':<25}\n"
    ComparacionCaja.insert(tk.END, encabezado)

    for nombre, score in resultados:
        nombre_mostrar = os.path.splitext(nombre)[0].replace("_", " ")
        texto = f"{nombre_mostrar:<25} {score:.5f}\n"
        ComparacionCaja.insert(tk.END, texto)

    ComparacionCaja.config(state="disabled")

    if resultados:
        mejor_match = resultados[0][0]
        path_mejor = os.path.join(CARPETA_PATRONES, mejor_match)
        try:
            im_mejor = Image.open(path_mejor)
            img_mejor = ImageTk.PhotoImage(image=im_mejor)
            LImagenPatron.configure(image=img_mejor)
            LImagenPatron.image = img_mejor
        except Exception as e:
            print(f"Error cargando mejor imagen: {e}")


# Imagenes
LImagenCamara = tk.Label(ventana, background="gray")
LImagenCamara.place(x=50, y=70, width=311, height=241)

LImagenCamara2 = tk.Label(ventana, background="gray")
LImagenCamara2.place(x=50, y=330, width=311, height=241)


LImagenUmbral = tk.Label(ventana, background="gray")
LImagenUmbral.place(x=430, y=70, width=311, height=241)

LImagenPatron = tk.Label(ventana, background="gray")
LImagenPatron.place(x=770, y=70, width=311, height=241)

LImagenRecorte = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenRecorte.place(x=335, y=100, width=300, height=200)

GImagenROI = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
GImagenROI.place(x=690, y=100, width=300, height=200)

LImagenROI = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenROI.config(state="disabled")

Coordenadas = tk.Label(ventana, text="", bg="#1e1e1e", fg="white")
Coordenadas.place(x=440, y=305)


LImagenZoom = tk.Label(ventana, background="#2e2e2e", borderwidth=2)
LImagenZoom.place(x=335, y=365, width=300, height=200)

# Labels
LRecorteScale = tk.Label(ventana, text="Paso 2: Deslizadores para seleccionar las coordenadas del recorte.")
LUmbralScale = tk.Label(ventana, text="Paso 3: Deslizador para seleccionar la magnitud del umbral.")
LPatron = tk.Label(ventana, text="Imagen del patron mas similar.")
LPatron.place(x=770, y=45)
LIniciarCamara = tk.Label(ventana, text="Paso 1: Boton para iniciar la camara.")
LIniciarCamara.place(x=105, y=355)
LUmbralTexto = tk.Label(ventana, text="Paso 4: Boton para umbralizar la imagen seleccionada.")
LGuardar = tk.Label(ventana, text="Paso 5: Guardar patron con un nombre y tipo.")
LComparar = tk.Label(ventana, text="Paso 6: Boton para compararla con los patrones guardados.")
LComparacion = tk.Label(ventana,
                        text="Comparacion de la imagen seleccionada con los patrones \nguardados, el numero menor es la mayor semejanza.")
LComparacion.place(x=770, y=315)

# Botones
BCamara = tk.Button(ventana, text="Iniciar Camara", command=iniciar_camara)
BCamara.place(x=150, y=375, width=100, height=23)
BCapturar = tk.Button(ventana, text="Umbralizar", command=capturar)
BComparar = tk.Button(ventana, text="Comparar", command=comparar_patrones)
BGuardar = tk.Button(ventana, text="Guardar patron", command=guardar_patron)


SGray = tk.Scale(ventana, from_=0, to=255, orient='horizontal', command=umbralizar)
SGray.set(127)

# TextBox
ComparacionCaja = tk.Text(ventana, state="disabled")
ComparacionCaja.place(x=770, y=350, width=311, height=241)

# Entradas
EntradaNombre = tk.Entry(ventana)
EntradaNombre.insert(0, "Nombre")
VariableTipo = tk.StringVar(value="Macho")
RadioMacho = tk.Radiobutton(ventana, text="Macho", variable=VariableTipo, value="Macho")
RadioHembra = tk.Radiobutton(ventana, text="Hembra", variable=VariableTipo, value="Hembra")

ventana.mainloop()
