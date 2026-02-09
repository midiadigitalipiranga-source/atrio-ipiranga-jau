import customtkinter as ctk
from PIL import Image
import math
import os
from recepcao import TelaRecepcao  # Importação do módulo de recepção

# --- PALETA DE CORES ÁTRIO ---
AZUL_PROFUNDO = "#010d1a"
AZUL_HEADER = "#002366"
DOURADO_METÁLICO = "#bf953f"
DOURADO_BRILHO = "#fcf6ba"

BANCO_IGREJAS = {
    "ipiranga123": {
        "nome": "IPIRANGA SEDE JAÚ",
        "logo": "assets/igreja_ipiranga.png",
        "nivel": "admin",
        "botoes_liberados": "todos"
    }
}

class AtrioSistema(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Sistema ÁTRIO - Gestão")
        self.geometry("1150x800")
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=AZUL_PROFUNDO)
        
        self.igreja_atual = None
        self.mostrar_tela_login()

    def limpar_tela(self):
        for widget in self.winfo_children():
            widget.destroy()

    def mostrar_tela_login(self):
        self.limpar_tela()
        frame_login = ctk.CTkFrame(self, fg_color="transparent")
        frame_login.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(frame_login, text="🛡️ ÁTRIO", font=("Arial", 50, "bold"), text_color=DOURADO_METÁLICO).pack(pady=20)
        
        self.entry_senha = ctk.CTkEntry(frame_login, placeholder_text="SENHA DA IGREJA", 
                                        show="*", width=300, height=45, justify="center",
                                        border_color=DOURADO_METÁLICO)
        self.entry_senha.pack(pady=10)
        
        ctk.CTkButton(frame_login, text="ACESSAR ÁTRIO", fg_color=DOURADO_METÁLICO, 
                       text_color="black", font=("Arial", 14, "bold"),
                       hover_color=DOURADO_BRILHO, height=45, 
                       command=self.verificar_acesso).pack(pady=20)

    def verificar_acesso(self):
        senha = self.entry_senha.get()
        if senha in BANCO_IGREJAS:
            self.igreja_atual = BANCO_IGREJAS[senha]
            self.mostrar_home()
        else:
            self.entry_senha.configure(border_color="red")

    def mostrar_home(self):
        self.limpar_tela()

        # --- HEADER ---
        header = ctk.CTkFrame(self, fg_color=AZUL_HEADER, corner_radius=15, height=90, border_width=1, border_color="white")
        header.pack(fill="x", padx=30, pady=20)
        header.pack_propagate(False)

        ctk.CTkLabel(header, text=self.igreja_atual["nome"], font=("Arial", 26, "bold"), text_color="white").place(relx=0.5, rely=0.35, anchor="center")
        ctk.CTkLabel(header, text="PAINEL ADMINISTRATIVO", font=("Arial", 14), text_color=DOURADO_BRILHO).place(relx=0.5, rely=0.7, anchor="center")

        if os.path.exists(self.igreja_atual["logo"]):
            img_raw = Image.open(self.igreja_atual["logo"])
            img_igreja = ctk.CTkImage(light_image=img_raw, dark_image=img_raw, size=(70, 70))
            ctk.CTkLabel(header, image=img_igreja, text="").pack(side="right", padx=20)

        # --- ÁREA CENTRAL ---
        area_central = ctk.CTkFrame(self, fg_color="transparent")
        area_central.pack(expand=True, fill="both")

        if os.path.exists("assets/atrio_logo.png"):
            img_atrio_raw = Image.open("assets/atrio_logo.png")
            img_atrio = ctk.CTkImage(light_image=img_atrio_raw, dark_image=img_atrio_raw, size=(280, 280))
            ctk.CTkLabel(area_central, image=img_atrio, text="").place(relx=0.5, rely=0.5, anchor="center")

        # --- BOTÕES CIRCULARES ---
        todos_botoes = ["RECEPÇÃO", "TESOURARIA", "PASTORAL", "EVENTOS", "CONFIG", "ASSISTÊNCIA", "MÍDIA", "SECRETARIA"]
        raio_x, raio_y = 380, 250

        for i, nome in enumerate(todos_botoes):
            angulo = math.radians((i * 360 / 8) - 90)
            x = 0.5 + (raio_x * math.cos(angulo)) / 1150
            y = 0.5 + (raio_y * math.sin(angulo)) / 800

            btn = ctk.CTkButton(area_central, text=nome, font=("Arial", 13, "bold"),
                                text_color="black", fg_color=DOURADO_METÁLICO,
                                hover_color=DOURADO_BRILHO, height=50, width=150, 
                                corner_radius=25, border_width=2, border_color="white",
                                command=lambda n=nome: self.abrir_modulo(n))
            btn.place(relx=x, rely=y, anchor="center")

    def abrir_modulo(self, nome):
        if nome == "RECEPÇÃO":
            self.limpar_tela()
            TelaRecepcao(self, self.mostrar_home)

if __name__ == "__main__":
    app = AtrioSistema()
    app.mainloop()