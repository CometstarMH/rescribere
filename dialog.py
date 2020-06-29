from tkinter import *
from tkinter import ttk
import os

class ClampedDoubleVar(DoubleVar):
    def __init__(self, minvalue = None, maxvalue = None, master=None, value=None, name=None):
        super().__init__(master, value, name)
        self.minvalue = minvalue
        self.maxvalue = maxvalue
    def set(self, value):
        if self.minvalue is not None and value < self.minvalue: value = self.minvalue
        if self.maxvalue is not None and value > self.maxvalue: value = self.maxvalue
        super().set(value)

class ProgressBarDialog(Toplevel):
    def __init__(self, parent, title = None, maxvalue = None):
        '''Initialize a dialog with a progress bar.
        Arguments:
            parent -- a parent window (the application window)
            title -- the dialog title
        '''
        if not parent:
            parent = tkinter._default_root

        self.status_text = StringVar()
        self.status_text.set("Please wait...")
        if maxvalue is None: maxvalue = 100
        self.progress_value = ClampedDoubleVar(0, maxvalue, None, 0)
        self.done = False

        Toplevel.__init__(self, parent)
        
        self.withdraw() # remain invisible for now
        # If the master is not viewable, don't
        # make the child transient, or else it
        # would be opened withdrawn
        if parent.winfo_viewable():
            self.transient(parent)

        if title:
            self.title(title)

        self.parent = parent
        self.result = None

        body = Frame(self)
        self.initial_focus = self.body(body)
        body.pack(padx=5, pady=5)

        if not self.initial_focus:
            self.initial_focus = self

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.resizable(False, False)
        #self.overrideredirect(1)

        if self.parent is not None:
            self.geometry("+%d+%d" % (parent.winfo_rootx()+50,
                                      parent.winfo_rooty()+50))
    
    def show(self):
        self.deiconify() # become visible now

        self.initial_focus.focus_set()

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()
        self.wait_window(self)
        
    def body(self, master):
        w = Label(master, textvariable=self.status_text, justify=LEFT)
        w.grid(row=0, padx=5, sticky=W)

        progress = ttk.Progressbar(master, variable=self.progress_value, maximum=self.progress_value.maxvalue, orient=HORIZONTAL, length=200, mode='determinate')
        progress.grid(column=0, row=1, sticky=(E, W))

        return None
    
    def cancel(self, event=None):
        # put focus back to the parent window
        if self.done:
            if self.parent is not None:
                self.parent.focus_set()
            self.destroy()
