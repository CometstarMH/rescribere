from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import doc
import threading

class SyncVariable():
    def __init__(self):
        self._value = None
        self._lock = threading.Lock()
    def get(self):
        temp = None
        with self._lock:
            temp = self._value
        return temp
    def set(self, value):
        with self._lock:
            self._value = value


class App(ttk.Frame):
    # content = ttk.Frame(root, padding=(3,3,12,12))
    def __init__(self, root, master, **kwargs):
        super().__init__(master, **kwargs)
        self.f = None
        self.root = master
        self.pack() # defaults to side = "top"
        
        self.grid(column=0, row=0, sticky=(N, S, E, W))
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=3)
        self.columnconfigure(2, weight=3)
        self.columnconfigure(3, weight=1)
        self.columnconfigure(4, weight=1)
        self.rowconfigure(1, weight=1)

        # Instance "Variables"
        self.onevar = BooleanVar()
        self.twovar = BooleanVar()
        self.threevar = BooleanVar()
        self.read_status = StringVar()
        self.status_sync_var = SyncVariable()

        # Initialize widgets
        self.init_widget()

        # Initialize Instance "Variables" 
        self.onevar.set(True)
        self.twovar.set(False)
        self.threevar.set(True)
        self.read_status.set('')
    
    def init_widget(self):
        menubar = Menu(self)
        self.root['menu'] = menubar
        menu_file = Menu(menubar)
        menubar.add_cascade(menu=menu_file, label='File')
        menu_file.add_command(label='New', command=None)
        menu_file.add_command(label='Open...', command=self.open_file)
        menu_file.add_separator()
        menu_file.add_command(label='Exit', command=None)
        menu_edit = Menu(menubar)
        menubar.add_cascade(menu=menu_edit, label='Edit')

        frame = ttk.Frame(self, borderwidth=5, relief="sunken", width=200, height=100)
        namelbl = ttk.Label(self, textvariable=self.read_status)
        name = ttk.Entry(self)

        one = ttk.Checkbutton(self, text="One", variable=self.onevar, onvalue=True)
        two = ttk.Checkbutton(self, text="Two", variable=self.twovar, onvalue=True)
        three = ttk.Checkbutton(self, text="Three", variable=self.threevar, onvalue=True)
        ok = ttk.Button(self, text="Okay")
        cancel = ttk.Button(self, text="Cancel")

        frame.grid(column=0, row=0, columnspan=3, rowspan=2, sticky=(N, S, E, W))
        namelbl.grid(column=3, row=0, columnspan=2, sticky=(N, W), padx=5)
        name.grid(column=3, row=1, columnspan=2, sticky=(N, E, W), pady=5, padx=5)
        one.grid(column=0, row=3)
        two.grid(column=1, row=3)
        three.grid(column=2, row=3)
        ok.grid(column=3, row=3)
        cancel.grid(column=4, row=3)
    
    def open_file(self):
        filename = filedialog.askopenfilename(filetypes=[('PDF Documents', '*.pdf'), ('All Files', '*.*'), ])
        if filename != '':
            if self.f is not None:
                try: f.close() 
                except: pass
            f = open(filename, 'rb')
            x = threading.Thread(target=self.thread_open_pdf, args=(f,))
            x.start()
            self.poll_status_open_pdf()
            print(pdfdoc)

    def thread_open_pdf(self, f):
        pdfdoc = doc.PdfDocument(f, progress_cb=lambda status, **kwargs: self.status_sync_var.set(status))
    
    def poll_status_open_pdf(self):
        status = self.status_sync_var.get()
        self.read_status.set(status)
        self.master.after(50, self.poll_status_open_pdf)

    

root = Tk()
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
# turn off tear off menus
root.option_add('*tearOff', FALSE)
# Left, Top, Right, Bottom
appframe = App(root, root, padding=(12,12,12,12))

root.geometry('1024x768-60+60')
root.mainloop()