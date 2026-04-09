from tkinter import *

my_window = Tk()
my_window.resizable(width=False, height=False)
my_window.title("MausKeramientaMisteriosa")

def mostrar_coordenadas(event):
    my_label['text']=f'x={event.x} y={event.y}'


my_canvas = Canvas(my_window,width=400,height=400, background="white")
my_label = Label(bd=4, relief="solid", font="Arial 22 bold", bg="white", fg="black")
my_canvas.bind('<Button-1>',mostrar_coordenadas)
my_label.grid(row=0, column=0)
my_canvas.grid(row=1, column=0)

my_window.mainloop()