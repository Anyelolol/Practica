from tkinter import *
import numpy as np

def cbosu(x,y):
    ensu.config(state="normal")
    ensu.delete(0, END)
    ensu.insert(0,f"{int(x)+int(y)}")
    ensu.config(state="disabled")
    bosu.config(background="white")

def cbore(x,y):
    enre.config(state="normal")
    enre.delete(0, END)
    enre.insert(0,f"{int(x)-int(y)}")
    enre.config(state="disabled")
    bore.config(background="white")

def cbomu(x,y):
    enmu.config(state="normal")
    enmu.delete(0, END)
    enmu.insert(0,f"{int(x)*int(y)}")
    enmu.config(state="disabled")
    bomu.config(background="white")

def cbodi(x,y):
    endi.config(state="normal")
    endi.delete(0, END)
    endi.insert(0,f"{int(x)/int(y)}")
    endi.config(state="disabled")
    bodi.config(background="white")

ventana = Tk()
ventana.title("Calculadora Tk")
ventana.geometry("400x190")
ventana.resizable(width=0, height=0)
#1
txv1 = Label(ventana,text="nm1")
txv1.grid(row=0, column=0, padx=5, pady=5)
env1 = Entry(ventana)
env1.grid(row=0, column=1, padx=5, pady=5)
#2
txv2 = Label(ventana,text="nm2")
txv2.grid(row=0, column=3, padx=5, pady=5)
env2 = Entry(ventana)
env2.grid(row=0, column=4, padx=5, pady=5)
#su
ensu = Entry(ventana, state="readonly")
ensu.grid(row=1, column=1, padx=5, pady=5)

bosu = Button(ventana, text="Sum", width=8, height=1, command=lambda: cbosu(env1.get(), env2.get()))
bosu.grid(row=1, column=0, padx=5, pady=5)
#re
enre = Entry(ventana, state="disabled")
enre.grid(row=2, column=1, padx=5, pady=5)

bore = Button(ventana, text="Res", width=8, height=1, command=lambda: cbore(env1.get(), env2.get()))
bore.grid(row=2, column=0, padx=5, pady=5)
#mu
enmu = Entry(ventana, state="disabled")
enmu.grid(row=3, column=1, padx=5, pady=5)

bomu = Button(ventana, text="Mul", width=8, height=1, command=lambda: cbomu(env1.get(), env2.get()))
bomu.grid(row=3, column=0, padx=5, pady=5)
#di
endi = Entry(ventana, state="disabled")
endi.grid(row=4, column=1, padx=5, pady=5)

bodi = Button(ventana, text="Div", width=8, height=1, command=lambda: cbodi(env1.get(), env2.get()))
bodi.grid(row=4, column=0, padx=5, pady=5)
ventana.mainloop()