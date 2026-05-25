import customtkinter as ctk
from .gui import MainWindow


class App:
    def __init__(self):
        ctk.set_appearance_mode("System")
        try:
            ctk.set_default_color_theme("blue")
        except Exception:
            pass
        self.root = ctk.CTk()
        self.root.title("Internet Archive Downloader")
        self.root.geometry("900x600")
        self.root.minsize(700, 500)
        self.window = MainWindow(self.root)

    def run(self):
        self.root.mainloop()
