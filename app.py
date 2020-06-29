from tkinter import *
from tkinter import ttk
from tkinter import filedialog
import doc
import threading
from dialog import ProgressBarDialog
import datetime

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
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.f = None
        self.pack() # defaults to side = "top"
        
        self.grid(column=0, row=0, sticky=(N, S, E, W))
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.columnconfigure(2, weight=0)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        # Instance "Variables"
        self.onevar = BooleanVar()
        self.twovar = BooleanVar()
        self.threevar = BooleanVar()
        self.status_sync_var = SyncVariable()
        self.progress_sync_var = SyncVariable()

        # Initialize widgets
        self.init_widget()

        # Initialize Instance "Variables" 
        self.onevar.set(True)
        self.twovar.set(False)
        self.threevar.set(True)
    
    def init_widget(self):
        menubar = Menu(self)
        root['menu'] = menubar
        menu_file = Menu(menubar)
        menubar.add_cascade(menu=menu_file, label='File')
        menu_file.add_command(label='New', command=None)
        menu_file.add_command(label='Open...', command=self.open_file)
        menu_file.add_separator()
        menu_file.add_command(label='Exit', command=self.close_app)
        menu_edit = Menu(menubar)
        menubar.add_cascade(menu=menu_edit, label='Edit')

        # frame = ttk.Frame(self, borderwidth=5, relief="sunken", width=200, height=100)
        left_frame = ttk.Frame(self)
        left_frame.grid(column=0, row=0, sticky=(N, S, E, W))
        left_frame.columnconfigure(0, weight=1)
        left_frame.columnconfigure(1, weight=0)
        left_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(left_frame)
        self.tree.grid(column=0, row=0, sticky=(N, S, E, W))
        self.tree['columns'] = ('offset', )
        self.tree.heading('#0', text=' Object', anchor=W)
        self.tree.column('offset', width=50, minwidth=50)
        self.tree.heading('offset', text=' Offset', anchor=W)
        tree_scrollbar = ttk.Scrollbar(left_frame, orient=VERTICAL, command=self.tree.yview)
        tree_scrollbar.grid(column=1, row=0, sticky=(N,S))
        self.tree['yscrollcommand'] = tree_scrollbar.set


        namelbl = ttk.Label(self, text='Name')
        name = ttk.Entry(self)

        # one = ttk.Checkbutton(self, text="One", variable=self.onevar, onvalue=True)
        # two = ttk.Checkbutton(self, text="Two", variable=self.twovar, onvalue=True)
        # three = ttk.Checkbutton(self, text="Three", variable=self.threevar, onvalue=True)
        ok = ttk.Button(self, text="Okay")
        cancel = ttk.Button(self, text="Cancel")

        # frame.grid(column=0, row=0, columnspan=3, rowspan=2, sticky=(N, S, E, W))
        # namelbl.grid(column=3, row=0, columnspan=2, sticky=(N, W), padx=5)
        # name.grid(column=3, row=1, columnspan=2, sticky=(N, E, W), pady=5, padx=5)
        ok.grid(column=1, row=1)
        cancel.grid(column=2, row=1)
    
    def open_file(self):
        filename = filedialog.askopenfilename(filetypes=[('PDF Documents', '*.pdf'), ('All Files', '*.*'), ])
        if filename != '':
            if self.f is not None:
                try: f.close() 
                except: pass
            f = open(filename, 'rb')
            x = threading.Thread(target=self.parse_pdf, args=(f,))
            x.start()
            self.loading_dlg = ProgressBarDialog(self, 'Opening PDF...')
            self.poll_wait_parse_pdf()
            self.loading_dlg.show()
            # blocked until loading_dlg is destroyed
            # so pdfdoc is safe to read
            #print(self.pdfdoc)
            self.tree.delete(*self.tree.get_children())
            for offset in self.pdfdoc.offset_obj:
                self.tree.insert('', 'end', text=repr(self.pdfdoc.offset_obj[offset]), values=(offset, ))
    
    def close_app(self):
        root.destroy()

    def parse_pdf(self, f):
        self.pdfdoc = doc.PdfDocument(f, progress_cb=lambda status, **kwargs: (self.status_sync_var.set(status), self.progress_sync_var.set(kwargs['read'] / kwargs['total'] * 100)))
    
    def poll_wait_parse_pdf(self):
        status = self.status_sync_var.get()
        progress = self.progress_sync_var.get()
        if self.loading_dlg is not None: 
            self.loading_dlg.status_text.set(status)
            self.loading_dlg.progress_value.set(progress)
            if status == 'Done':
                self.loading_dlg.done = True
                self.loading_dlg.cancel()
                return
        root.after(50, self.poll_wait_parse_pdf)

    

root = Tk()
root.columnconfigure(0, weight=1)
root.rowconfigure(0, weight=1)
# turn off tear off menus
root.option_add('*tearOff', FALSE)
# Left, Top, Right, Bottom
appframe = App(root, padding=(12,12,12,12))

root.geometry('1024x768-60+60')
root.mainloop()