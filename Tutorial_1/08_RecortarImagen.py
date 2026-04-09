import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk
import imutils
import cv2

ventana = tk.Tk()
ventana.title("RFoto")
ventana.resizable(0,0)
ventana.geometry("1070x450")

def camara():
    global captura
    captura = cv2.VideoCapture(0)
    iniciar()

def iniciar():
    global captura
    if captura is not None:
        ret, frame = captura.read()
        if ret == True:
            frame = imutils.resize(frame, width=311)
            frame = imutils.resize(frame, width=241)
            imagen_camara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(imagen_camara)
            img = ImageTk.PhotoImage(image=im)
            LImagen.configure(image= img)
            LImagen.image = img
            LImagen.after(1,iniciar)
        else:
            LImagen.image = ""
            captura.release()

def Capturar():
    global captura, imagen_camara
    camara = captura
    return_value, image = camara.read()
    frame = imutils.resize(image, width=301)
    frame = imutils.resize(frame, width=221)
    imagen_camara = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    im = Image.fromarray(imagen_camara)
    img = ImageTk.PhotoImage(image= im)
    LImagenROI.config(image= img)
    LImagenROI.image = img

def mostrar_coordenadas(event):
    coords['text']=f'x={event.x} y={event.y}'

def recortar():
    global ImgRec, imagen_camara
    vx1= int(x1.get())
    vy1= int(y1.get())
    vx2= int(x2.get())
    vy2= int(y2.get())
    
    x_1, x_2 = sorted([vx1, vx2])
    y_1, y_2 = sorted([vy1, vy2])

    ImgRec = imagen_camara[y_1:y_2, x_1:x_2]

    Im = Image.fromarray(ImgRec)
    ImRec = ImageTk.PhotoImage(image= Im)
    LImagenRec.configure(image = ImRec)
    LImagenRec.image = ImRec

BCamara = tk.Button(ventana, text="On", command= camara)
BCamara.place(x=80, y=330, width=90, height=23)
BCapturar = tk.Button(ventana, text="Capturar", command=Capturar)
BCapturar.place(x=220, y=330, width=91, height=23)
BRec = tk.Button(ventana, text="Recorar", command=recortar)
BRec.place(x=840, y=400, width=80, height=23)


LImagen = tk.Label(ventana, background="white")
LImagen.place(x=50, y=50, width=300, height=240)
LImagenROI = tk.Label(ventana, background="white")
LImagenROI.place(x=390, y=50, width=300, height=240)
LImagenRec = tk.Label(ventana, background="white")
LImagenRec.place(x=730, y=50, width=300, height=240)

LImagenROI.bind('<Button-1>',mostrar_coordenadas)

coordsTitulo = tk.Label(ventana, text="Coords")
coordsTitulo.place(x=505, y=310)
coords = tk.Label(ventana, text="")
coords.place(x=495, y=330)

lx1 = tk.Label(ventana, text="x1")
lx1.place(x=790, y=330)
ly1 = tk.Label(ventana, text="y1")
ly1.place(x=890, y=330)

lx2 = tk.Label(ventana, text="x2")
lx2.place(x=790, y=360)
ly2 = tk.Label(ventana, text="y2")
ly2.place(x=890, y=360)

x1 = tk.Spinbox(ventana, from_= 0, to= 298)
x1.place(x=810, y=330, width= 42, height= 22)
y1 = tk.Spinbox(ventana, from_= 0, to= 239)
y1.place(x=910, y=330, width= 42, height= 22)

x2= tk.Spinbox(ventana, from_= 0, to= 298)
x2.place(x=810, y=360, width= 42, height= 22)
y2 = tk.Spinbox(ventana, from_= 0, to= 239,)
y2.place(x=910, y=360, width= 42, height= 22)

ventana.mainloop()
