import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import qrcode
from PIL import Image, ImageTk, ImageDraw
import os


# ==================== Rendering helpers ====================

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(rgb[0]))),
        max(0, min(255, int(rgb[1]))),
        max(0, min(255, int(rgb[2]))),
    )


def _interpolate(c1, c2, t):
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex((r1 + (r2 - r1) * t,
                        g1 + (g2 - g1) * t,
                        b1 + (b2 - b1) * t))


def _draw_module(draw, x, y, s, color, style):
    if style == "square":
        draw.rectangle([x, y, x + s - 1, y + s - 1], fill=color)
    elif style == "rounded":
        r = max(1, int(s * 0.35))
        draw.rounded_rectangle([x, y, x + s - 1, y + s - 1], radius=r, fill=color)
    elif style == "circle":
        draw.ellipse([x, y, x + s - 1, y + s - 1], fill=color)
    elif style == "dots":
        pad = max(1, int(s * 0.15))
        draw.ellipse([x + pad, y + pad, x + s - 1 - pad, y + s - 1 - pad], fill=color)
    elif style == "diamond":
        cx, cy = x + s / 2.0, y + s / 2.0
        draw.polygon([(cx, y), (x + s - 1, cy), (cx, y + s - 1), (x, cy)], fill=color)


def _draw_eye(draw, x, y, unit, fg, bg, style):
    s = unit * 7
    if style == "square":
        draw.rectangle([x, y, x + s - 1, y + s - 1], fill=fg)
        draw.rectangle([x + unit, y + unit, x + s - unit - 1, y + s - unit - 1], fill=bg)
        draw.rectangle([x + 2 * unit, y + 2 * unit, x + 5 * unit - 1, y + 5 * unit - 1], fill=fg)
    elif style == "rounded":
        r1 = int(unit * 2.0)
        r2 = int(unit * 1.2)
        r3 = int(unit * 0.6)
        draw.rounded_rectangle([x, y, x + s - 1, y + s - 1], radius=r1, fill=fg)
        draw.rounded_rectangle([x + unit, y + unit, x + s - unit - 1, y + s - unit - 1], radius=r2, fill=bg)
        draw.rounded_rectangle([x + 2 * unit, y + 2 * unit, x + 5 * unit - 1, y + 5 * unit - 1], radius=r3, fill=fg)
    elif style == "circle":
        draw.ellipse([x, y, x + s - 1, y + s - 1], fill=fg)
        draw.ellipse([x + unit, y + unit, x + s - unit - 1, y + s - unit - 1], fill=bg)
        draw.ellipse([x + 2 * unit, y + 2 * unit, x + 5 * unit - 1, y + 5 * unit - 1], fill=fg)


def render_qr(matrix, box_size, border, fg, bg,
              module_style="square", eye_style="square", gradient_end=None,
              supersample=3):
    """Рендерит QR-матрицу с выбранным стилем. Supersample → сглаживание."""
    size = len(matrix)
    big_box = box_size * supersample
    dim = (size + 2 * border) * box_size
    big_dim = (size + 2 * border) * big_box

    img = Image.new("RGB", (big_dim, big_dim), bg)
    draw = ImageDraw.Draw(img)

    eyes = [(0, 0), (0, size - 7), (size - 7, 0)]
    eye_cells = set()
    for r0, c0 in eyes:
        for r in range(r0, r0 + 7):
            for c in range(c0, c0 + 7):
                eye_cells.add((r, c))

    denom = max(1, 2 * (size - 1))

    # Обычные модули
    for r in range(size):
        row = matrix[r]
        for c in range(size):
            if not row[c] or (r, c) in eye_cells:
                continue
            color = fg
            if gradient_end:
                color = _interpolate(fg, gradient_end, (r + c) / denom)
            _draw_module(draw,
                         (c + border) * big_box,
                         (r + border) * big_box,
                         big_box, color, module_style)

    # «Глаза» (finder patterns)
    for r0, c0 in eyes:
        eye_fg = fg
        if gradient_end:
            eye_fg = _interpolate(fg, gradient_end,
                                  ((r0 + 3) + (c0 + 3)) / denom)
        _draw_eye(draw,
                  (c0 + border) * big_box,
                  (r0 + border) * big_box,
                  big_box, eye_fg, bg, eye_style)

    if supersample > 1:
        img = img.resize((dim, dim), Image.LANCZOS)
    return img


# ==================== Дизайн-пресеты ====================

PRESETS = {
    "Classic":   {"fg": "#000000", "bg": "#ffffff", "grad": None,
                  "module": "square",  "eye": "square"},
    "Neon":      {"fg": "#00fff7", "bg": "#0a0a0a", "grad": "#ff00ea",
                  "module": "dots",    "eye": "circle"},
    "Ocean":     {"fg": "#0077be", "bg": "#e6f7ff", "grad": "#00bcd4",
                  "module": "rounded", "eye": "rounded"},
    "Sunset":    {"fg": "#ff5722", "bg": "#fff8e1", "grad": "#ffc107",
                  "module": "diamond", "eye": "rounded"},
    "Mint":      {"fg": "#1b5e20", "bg": "#f1f8e9", "grad": "#4caf50",
                  "module": "circle",  "eye": "circle"},
    "Elegant":   {"fg": "#212121", "bg": "#fafafa", "grad": "#616161",
                  "module": "rounded", "eye": "square"},
    "Cyberpunk": {"fg": "#ff006e", "bg": "#0d0221", "grad": "#8338ec",
                  "module": "rounded", "eye": "circle"},
}


# ==================== Приложение ====================

class QRStudio:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Studio")
        self.root.geometry("1120x820")
        self.root.minsize(1060, 780)

        # Палитра
        self.bg = "#1e1e2e"
        self.surface = "#313244"
        self.surface2 = "#45475a"
        self.fg = "#cdd6f4"
        self.subtext = "#a6adc8"
        self.accent = "#89b4fa"
        self.accent_hover = "#b4befe"
        self.success = "#a6e3a1"
        self.root.configure(bg=self.bg)

        # Состояние
        self.qr_image_full = None
        self.qr_image_show = None
        self.history = []
        self.fg_color = "#000000"
        self.bg_color = "#ffffff"
        self.grad_color = "#ff00ea"
        self.logo_path = None
        self.current_data = ""

        self.setup_style()
        self.build_ui()
        self.generate()

    # ---------- Стили ttk ----------
    def setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")

        s.configure("TFrame", background=self.bg)
        s.configure("Card.TFrame", background=self.surface)
        s.configure("TLabel", background=self.bg, foreground=self.fg,
                    font=("Segoe UI", 10))
        s.configure("Card.TLabel", background=self.surface, foreground=self.fg,
                    font=("Segoe UI", 10))
        s.configure("Muted.TLabel", background=self.surface, foreground=self.subtext,
                    font=("Segoe UI", 9))
        s.configure("Title.TLabel", background=self.bg, foreground=self.accent,
                    font=("Segoe UI", 20, "bold"))
        s.configure("Subtitle.TLabel", background=self.bg, foreground=self.subtext,
                    font=("Segoe UI", 10))
        s.configure("Section.TLabel", background=self.surface, foreground=self.accent,
                    font=("Segoe UI", 9, "bold"))

        s.configure("TEntry", fieldbackground=self.surface2, foreground=self.fg,
                    borderwidth=0, insertcolor=self.fg, padding=8)
        s.map("TEntry", fieldbackground=[("focus", "#585b70")])

        s.configure("Accent.TButton", background=self.accent, foreground=self.bg,
                    font=("Segoe UI", 11, "bold"), borderwidth=0, padding=[20, 10])
        s.map("Accent.TButton",
              background=[("active", self.accent_hover), ("pressed", "#74a0e0")])

        s.configure("Success.TButton", background=self.success, foreground=self.bg,
                    font=("Segoe UI", 10, "bold"), borderwidth=0, padding=[15, 10])
        s.map("Success.TButton", background=[("active", "#b8eaa5")])

        s.configure("Secondary.TButton", background=self.surface2, foreground=self.fg,
                    font=("Segoe UI", 10), borderwidth=0, padding=[12, 8])
        s.map("Secondary.TButton", background=[("active", "#585b70")])

        s.configure("TNotebook", background=self.surface, borderwidth=0)
        s.configure("TNotebook.Tab", background=self.surface, foreground=self.subtext,
                    padding=[12, 7], borderwidth=0, font=("Segoe UI", 10))
        s.map("TNotebook.Tab",
              background=[("selected", self.surface2)],
              foreground=[("selected", self.accent)])

        s.configure("TCombobox", fieldbackground=self.surface2, background=self.surface2,
                    foreground=self.fg, arrowcolor=self.fg, borderwidth=0, padding=5)

        s.configure("TCheckbutton", background=self.surface, foreground=self.fg,
                    font=("Segoe UI", 10))
        s.map("TCheckbutton", background=[("active", self.surface)])

    # ---------- UI ----------
    def build_ui(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=28, pady=(22, 12))
        ttk.Label(header, text="◉ QR Studio", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  ·  дизайн-генератор QR-кодов",
                  style="Subtitle.TLabel").pack(side="left", pady=6)

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=28, pady=10)
        main.columnconfigure(0, weight=0, minsize=490)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # --- ЛЕВАЯ колонка ---
        left = ttk.Frame(main, style="Card.TFrame", padding=20)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        self.notebook = ttk.Notebook(left)
        self.notebook.pack(fill="x", pady=(0, 12))
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.update_live())

        self._tab_url()
        self._tab_text()
        self._tab_wifi()
        self._tab_email()
        self._tab_phone()

        # === ДИЗАЙН ===
        ttk.Label(left, text="ДИЗАЙН", style="Section.TLabel").pack(anchor="w", pady=(6, 8))

        # Пресет
        preset_row = ttk.Frame(left, style="Card.TFrame")
        preset_row.pack(fill="x", pady=(0, 8))
        ttk.Label(preset_row, text="Пресет:", style="Card.TLabel").pack(side="left")
        self.preset_var = tk.StringVar(value="Classic")
        preset_cb = ttk.Combobox(preset_row, textvariable=self.preset_var,
                                 values=list(PRESETS.keys()),
                                 state="readonly", width=16)
        preset_cb.pack(side="left", padx=8)
        preset_cb.bind("<<ComboboxSelected>>",
                       lambda e: self.apply_preset(self.preset_var.get()))

        # Стили модулей и «глаз»
        style_row = ttk.Frame(left, style="Card.TFrame")
        style_row.pack(fill="x", pady=(0, 8))
        ttk.Label(style_row, text="Модули:", style="Card.TLabel").pack(side="left")
        self.module_var = tk.StringVar(value="square")
        ttk.Combobox(style_row, textvariable=self.module_var,
                     values=["square", "rounded", "circle", "dots", "diamond"],
                     state="readonly", width=10).pack(side="left", padx=(6, 12))
        ttk.Label(style_row, text="Глаза:", style="Card.TLabel").pack(side="left")
        self.eye_var = tk.StringVar(value="square")
        ttk.Combobox(style_row, textvariable=self.eye_var,
                     values=["square", "rounded", "circle"],
                     state="readonly", width=9).pack(side="left", padx=6)

        # Цвета
        ttk.Label(left, text="ЦВЕТА", style="Section.TLabel").pack(anchor="w", pady=(8, 8))
        cf = ttk.Frame(left, style="Card.TFrame")
        cf.pack(fill="x")

        fg_box = ttk.Frame(cf, style="Card.TFrame")
        fg_box.pack(side="left", padx=(0, 12))
        ttk.Label(fg_box, text="Модули", style="Muted.TLabel").pack(anchor="w")
        self.fg_btn = tk.Button(fg_box, bg=self.fg_color, width=11, height=2,
                                command=self.pick_fg, relief="flat",
                                cursor="hand2", bd=0)
        self.fg_btn.pack(pady=(4, 0))

        bg_box = ttk.Frame(cf, style="Card.TFrame")
        bg_box.pack(side="left", padx=(0, 12))
        ttk.Label(bg_box, text="Фон", style="Muted.TLabel").pack(anchor="w")
        self.bg_btn = tk.Button(bg_box, bg=self.bg_color, width=11, height=2,
                                command=self.pick_bg, relief="flat",
                                cursor="hand2", bd=0)
        self.bg_btn.pack(pady=(4, 0))

        grad_box = ttk.Frame(cf, style="Card.TFrame")
        grad_box.pack(side="left")
        ttk.Label(grad_box, text="Градиент →", style="Muted.TLabel").pack(anchor="w")
        self.grad_btn = tk.Button(grad_box, bg=self.grad_color, width=11, height=2,
                                  command=self.pick_grad, relief="flat",
                                  cursor="hand2", bd=0)
        self.grad_btn.pack(pady=(4, 0))

        # Тумблер градиента
        self.grad_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(left, text="Включить градиентную заливку",
                        variable=self.grad_enabled,
                        command=self.update_live).pack(anchor="w", pady=(10, 0))

        # === НАСТРОЙКИ ===
        ttk.Label(left, text="НАСТРОЙКИ", style="Section.TLabel").pack(anchor="w", pady=(14, 6))

        size_row = ttk.Frame(left, style="Card.TFrame")
        size_row.pack(fill="x", pady=(0, 4))
        ttk.Label(size_row, text="Размер:", style="Card.TLabel").pack(side="left")
        self.size_var = tk.IntVar(value=10)
        tk.Scale(size_row, from_=5, to=20, orient="horizontal",
                 variable=self.size_var, bg=self.surface, fg=self.fg,
                 troughcolor=self.surface2, highlightthickness=0, bd=0,
                 length=250, activebackground=self.accent,
                 command=lambda v: self.update_live()).pack(side="left", padx=8)

        ec_row = ttk.Frame(left, style="Card.TFrame")
        ec_row.pack(fill="x", pady=(0, 4))
        ttk.Label(ec_row, text="Коррекция:", style="Card.TLabel").pack(side="left")
        self.ec_var = tk.StringVar(value="H (30%)")
        ttk.Combobox(ec_row, textvariable=self.ec_var,
                     values=["L (7%)", "M (15%)", "Q (25%)", "H (30%)"],
                     state="readonly", width=12).pack(side="left", padx=8)
        self.ec_var.trace_add("write", lambda *a: self.update_live())

        logo_row = ttk.Frame(left, style="Card.TFrame")
        logo_row.pack(fill="x", pady=(0, 4))
        ttk.Label(logo_row, text="Логотип:", style="Card.TLabel").pack(side="left")
        self.logo_label = ttk.Label(logo_row, text="не выбран", style="Muted.TLabel")
        self.logo_label.pack(side="left", padx=8)
        ttk.Button(logo_row, text="Выбрать", style="Secondary.TButton",
                   command=self.pick_logo).pack(side="left", padx=4)
        ttk.Button(logo_row, text="✕", style="Secondary.TButton", width=3,
                   command=self.clear_logo).pack(side="left")

        ttk.Button(left, text="⚡  Сгенерировать QR", style="Accent.TButton",
                   command=self.generate).pack(fill="x", pady=(14, 0))

        # --- ПРАВАЯ колонка ---
        right = ttk.Frame(main, style="Card.TFrame", padding=20)
        right.grid(row=0, column=1, sticky="nsew")

        ttk.Label(right, text="ПРЕДПРОСМОТР", style="Section.TLabel").pack(anchor="w")

        self.qr_wrap = tk.Frame(right, bg=self.bg, width=360, height=360,
                                highlightthickness=2,
                                highlightbackground=self.surface2, bd=0)
        self.qr_wrap.pack(pady=12)
        self.qr_wrap.pack_propagate(False)
        self.qr_label = tk.Label(self.qr_wrap, bg="#ffffff",
                                 text="Генерация...",
                                 fg="#888888", font=("Segoe UI", 11))
        self.qr_label.pack(fill="both", expand=True, padx=6, pady=6)

        actions = ttk.Frame(right, style="Card.TFrame")
        actions.pack(fill="x", pady=4)
        ttk.Button(actions, text="💾 PNG", style="Success.TButton",
                   command=lambda: self.download("png")).pack(
            side="left", expand=True, fill="x", padx=(0, 4))
        ttk.Button(actions, text="💾 JPG", style="Secondary.TButton",
                   command=lambda: self.download("jpg")).pack(
            side="left", expand=True, fill="x", padx=4)
        ttk.Button(actions, text="📋 Копировать", style="Secondary.TButton",
                   command=self.copy_data).pack(
            side="left", expand=True, fill="x", padx=(4, 0))

        ttk.Label(right, text="ИСТОРИЯ (двойной клик — загрузить)",
                  style="Section.TLabel").pack(anchor="w", pady=(12, 6))

        hist_wrap = tk.Frame(right, bg=self.surface2)
        hist_wrap.pack(fill="both", expand=True)
        self.history_list = tk.Listbox(
            hist_wrap, bg=self.surface2, fg=self.fg,
            selectbackground=self.accent, selectforeground=self.bg,
            borderwidth=0, highlightthickness=0,
            font=("Segoe UI", 9), activestyle="none")
        self.history_list.pack(fill="both", expand=True, padx=6, pady=6)
        self.history_list.bind("<Double-Button-1>", self.load_history)

        self.status = ttk.Label(right, text="Готов к работе", style="Muted.TLabel")
        self.status.pack(anchor="w", pady=(8, 0))

    # ---------- Вкладки ----------
    def _tab_url(self):
        f = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(f, text="🌐 URL")
        ttk.Label(f, text="Адрес сайта:", style="Card.TLabel").pack(anchor="w")
        self.url_entry = ttk.Entry(f, font=("Segoe UI", 11))
        self.url_entry.pack(fill="x", pady=(5, 0), ipady=3)
        self.url_entry.insert(0, "example.com")
        self.url_entry.bind("<Return>", lambda e: self.generate())

    def _tab_text(self):
        f = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(f, text="📝 Текст")
        ttk.Label(f, text="Текст для QR:", style="Card.TLabel").pack(anchor="w")
        self.text_input = tk.Text(f, height=4, bg=self.surface2, fg=self.fg,
                                  insertbackground=self.fg, borderwidth=0,
                                  font=("Segoe UI", 11), padx=8, pady=8)
        self.text_input.pack(fill="x", pady=(5, 0))

    def _tab_wifi(self):
        f = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(f, text="📶 Wi-Fi")
        ttk.Label(f, text="SSID:", style="Card.TLabel").pack(anchor="w")
        self.wifi_ssid = ttk.Entry(f, font=("Segoe UI", 11))
        self.wifi_ssid.pack(fill="x", pady=(5, 6), ipady=3)
        ttk.Label(f, text="Пароль:", style="Card.TLabel").pack(anchor="w")
        self.wifi_pass = ttk.Entry(f, font=("Segoe UI", 11))
        self.wifi_pass.pack(fill="x", pady=(5, 6), ipady=3)
        ttk.Label(f, text="Шифрование:", style="Card.TLabel").pack(anchor="w")
        self.wifi_enc = tk.StringVar(value="WPA")
        ttk.Combobox(f, textvariable=self.wifi_enc,
                     values=["WPA", "WEP", "nopass"],
                     state="readonly").pack(fill="x", pady=(5, 0))

    def _tab_email(self):
        f = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(f, text="✉ Email")
        ttk.Label(f, text="Email:", style="Card.TLabel").pack(anchor="w")
        self.email_to = ttk.Entry(f, font=("Segoe UI", 11))
        self.email_to.pack(fill="x", pady=(5, 6), ipady=3)
        ttk.Label(f, text="Тема:", style="Card.TLabel").pack(anchor="w")
        self.email_subject = ttk.Entry(f, font=("Segoe UI", 11))
        self.email_subject.pack(fill="x", pady=(5, 0), ipady=3)

    def _tab_phone(self):
        f = ttk.Frame(self.notebook, style="Card.TFrame", padding=12)
        self.notebook.add(f, text="📞 Телефон")
        ttk.Label(f, text="Номер телефона:", style="Card.TLabel").pack(anchor="w")
        self.phone_number = ttk.Entry(f, font=("Segoe UI", 11))
        self.phone_number.pack(fill="x", pady=(5, 0), ipady=3)

    # ---------- Цвет / лого ----------
    def pick_fg(self):
        c = colorchooser.askcolor(color=self.fg_color, title="Цвет модулей")[1]
        if c:
            self.fg_color = c
            self.fg_btn.config(bg=c)
            self.update_live()

    def pick_bg(self):
        c = colorchooser.askcolor(color=self.bg_color, title="Цвет фона")[1]
        if c:
            self.bg_color = c
            self.bg_btn.config(bg=c)
            self.update_live()

    def pick_grad(self):
        c = colorchooser.askcolor(color=self.grad_color, title="Конечный цвет градиента")[1]
        if c:
            self.grad_color = c
            self.grad_btn.config(bg=c)
            self.grad_enabled.set(True)
            self.update_live()

    def pick_logo(self):
        p = filedialog.askopenfilename(
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.gif *.bmp")])
        if p:
            self.logo_path = p
            self.logo_label.config(text=os.path.basename(p), foreground=self.fg)
            self.update_live()

    def clear_logo(self):
        self.logo_path = None
        self.logo_label.config(text="не выбран", foreground=self.subtext)
        self.update_live()

    def apply_preset(self, name):
        p = PRESETS[name]
        self.fg_color = p["fg"]
        self.bg_color = p["bg"]
        self.fg_btn.config(bg=self.fg_color)
        self.bg_btn.config(bg=self.bg_color)
        self.module_var.set(p["module"])
        self.eye_var.set(p["eye"])
        if p["grad"]:
            self.grad_color = p["grad"]
            self.grad_btn.config(bg=self.grad_color)
            self.grad_enabled.set(True)
        else:
            self.grad_enabled.set(False)
        self.update_live()

    # ---------- Данные ----------
    def get_current_data(self):
        idx = self.notebook.index(self.notebook.select())
        if idx == 0:
            url = self.url_entry.get().strip()
            if not url:
                return None
            if not (url.startswith("http://") or url.startswith("https://")):
                url = "https://" + url
            return url
        if idx == 1:
            return self.text_input.get("1.0", "end-1c").strip() or None
        if idx == 2:
            ssid = self.wifi_ssid.get().strip()
            if not ssid:
                return None
            return f"WIFI:T:{self.wifi_enc.get()};S:{ssid};P:{self.wifi_pass.get()};;"
        if idx == 3:
            mail = self.email_to.get().strip()
            if not mail:
                return None
            subj = self.email_subject.get().strip()
            return f"mailto:{mail}" + (f"?subject={subj}" if subj else "")
        if idx == 4:
            ph = self.phone_number.get().strip()
            return f"tel:{ph}" if ph else None
        return None

    def update_live(self):
        self.generate(add_history=False)

    # ---------- Генерация ----------
    def generate(self, add_history=True):
        data = self.get_current_data()
        if not data:
            self.qr_label.config(image="", text="Введите данные", fg="#888888")
            self.qr_image_full = None
            self.current_data = ""
            return

        self.current_data = data
        try:
            ec_map = {
                "L (7%)": qrcode.constants.ERROR_CORRECT_L,
                "M (15%)": qrcode.constants.ERROR_CORRECT_M,
                "Q (25%)": qrcode.constants.ERROR_CORRECT_Q,
                "H (30%)": qrcode.constants.ERROR_CORRECT_H,
            }
            qr = qrcode.QRCode(
                version=None,
                box_size=self.size_var.get(),
                border=4,
                error_correction=ec_map[self.ec_var.get()],
            )
            qr.add_data(data)
            qr.make(fit=True)
            matrix = qr.get_matrix()

            gradient_end = self.grad_color if self.grad_enabled.get() else None
            img = render_qr(
                matrix,
                box_size=self.size_var.get(),
                border=4,
                fg=self.fg_color,
                bg=self.bg_color,
                module_style=self.module_var.get(),
                eye_style=self.eye_var.get(),
                gradient_end=gradient_end,
                supersample=3,
            )

            if self.logo_path:
                img = self.embed_logo(img, self.logo_path)

            self.qr_image_full = img
            show = img.resize((320, 320), Image.LANCZOS)
            self.qr_image_show = ImageTk.PhotoImage(show)
            self.qr_label.config(image=self.qr_image_show, text="",
                                 bg=self.bg_color)

            self.status.config(
                text=f"✓ {self.module_var.get()} · {self.eye_var.get()} · "
                     f"{img.size[0]}×{img.size[1]} px · {len(data)} симв.")

            if add_history:
                self.push_history(data)

        except Exception as e:
            self.status.config(text=f"⚠ Ошибка: {str(e)[:60]}")

    def embed_logo(self, qr_img, logo_path):
        try:
            logo = Image.open(logo_path).convert("RGBA")
            size = int(qr_img.size[0] * 0.22)
            logo = logo.resize((size, size), Image.LANCZOS)
            pad = Image.new("RGBA", (size, size), self.bg_color)
            pad.paste(logo, (0, 0), logo)
            pos = ((qr_img.size[0] - size) // 2,
                   (qr_img.size[1] - size) // 2)
            qr_img.paste(pad, pos)
            return qr_img
        except Exception:
            return qr_img

    # ---------- История ----------
    def push_history(self, data):
        self.history = [h for h in self.history if h[1] != data]
        display = data[:70] + ("..." if len(data) > 70 else "")
        self.history.insert(0, (display, data))
        self.history = self.history[:15]
        self.history_list.delete(0, "end")
        for i, (d, _) in enumerate(self.history):
            self.history_list.insert("end", f"{i+1}. {d}")

    def load_history(self, _event):
        sel = self.history_list.curselection()
        if not sel:
            return
        data = self.history[sel[0]][1]

        if data.startswith("WIFI:"):
            parts = dict(p.split(":", 1) for p in data[5:].split(";") if ":" in p)
            self.wifi_ssid.delete(0, "end"); self.wifi_ssid.insert(0, parts.get("S", ""))
            self.wifi_pass.delete(0, "end"); self.wifi_pass.insert(0, parts.get("P", ""))
            self.wifi_enc.set(parts.get("T", "WPA"))
            self.notebook.select(2)
        elif data.startswith("mailto:"):
            addr = data[7:].split("?")[0]
            self.email_to.delete(0, "end"); self.email_to.insert(0, addr)
            self.notebook.select(3)
        elif data.startswith("tel:"):
            self.phone_number.delete(0, "end"); self.phone_number.insert(0, data[4:])
            self.notebook.select(4)
        elif data.startswith("http://") or data.startswith("https://"):
            self.url_entry.delete(0, "end"); self.url_entry.insert(0, data)
            self.notebook.select(0)
        else:
            self.text_input.delete("1.0", "end"); self.text_input.insert("1.0", data)
            self.notebook.select(1)

        self.generate(add_history=False)
        self.status.config(text="↩ Загружено из истории")

    # ---------- Экспорт ----------
    def download(self, fmt):
        if self.qr_image_full is None:
            messagebox.showwarning("Внимание", "Сначала сгенерируйте QR-код!")
            return
        ext = "." + fmt
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{fmt.upper()} изображение", f"*{ext}")],
            initialfile=f"qrcode{ext}")
        if not path:
            return
        try:
            img = self.qr_image_full
            if fmt == "jpg":
                img = img.convert("RGB")
            img.save(path)
            self.status.config(text=f"💾 Сохранено: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")

    def copy_data(self):
        if not self.current_data:
            messagebox.showwarning("Внимание", "Нет данных для копирования")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self.current_data)
        self.status.config(text="📋 Скопировано в буфер")


if __name__ == "__main__":
    root = tk.Tk()
    QRStudio(root)
    root.mainloop()
