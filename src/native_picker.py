"""One isolated Tk event loop per Windows native file/folder dialog."""
import json
import sys
import tkinter as tk
from tkinter import filedialog


def select(kind):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        if kind == "queue":
            path = filedialog.askopenfilename(parent=root, title="Selecionar planilha da campanha",
                                              filetypes=[("Planilhas Excel", "*.xlsx")])
            return [path] if path else []
        if kind == "photos":
            return list(filedialog.askopenfilenames(parent=root, title="Adicionar fotos da campanha",
                                                    filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp")]))
        if kind == "folder":
            path = filedialog.askdirectory(parent=root, title="Selecionar pasta", mustexist=True)
            return [path] if path else []
        raise ValueError("Seletor inválido.")
    finally:
        root.destroy()


if __name__ == "__main__":
    print(json.dumps(select(sys.argv[1]), ensure_ascii=True))
