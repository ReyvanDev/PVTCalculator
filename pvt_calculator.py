"""
PVT Calculator - Petroleum Fluid Properties Analysis
"""

import sys
import subprocess
import math
import csv
import io

# High-DPI scaling configuration for Windows to ensure crisp text
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

def ensure_matplotlib():
    try:
        import matplotlib
    except ImportError:
        print("Installing matplotlib (first-time setup, please wait)...")
        try:
            import pip
        except ImportError:
            print("Error: pip is not available in this Python environment.")
            print("Please install matplotlib manually: pip install matplotlib")
            return
            
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "matplotlib"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("matplotlib installed successfully.")


ensure_matplotlib()

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# ============================================================
#  COLOUR PALETTE  (Quantum Dark Theme)
# ============================================================
BG_PRIMARY   = "#06070a"  # Deep space blue-black
BG_SECONDARY = "#0c0e17"  # Slate card background
BG_TERTIARY  = "#141726"  # Input field / inner panel background
BORDER       = "#20253b"  # Border color
ACCENT       = "#f97316"  # Premium orange primary accent
ACCENT2      = "#fb923c"  # Medium orange secondary accent
ACCENT_LIGHT = "#fed7aa"  # Highlight color for comparison text (light orange)
TEXT_PRIMARY = "#f3f4f6"  # Warm white
TEXT_SEC     = "#9ca3af"  # Slate grey
TEXT_MUTED   = "#5b6175"  # Darker grey for helper text/units
SUCCESS      = "#10b981"  # Emerald green
WARNING      = "#f59e0b"  # Amber orange
DANGER       = "#ef4444"  # Rose red
INFO         = "#3b82f6"  # Bright blue
GLOW_CYAN    = "#fb923c"  # Highlight orange focus ring


# ============================================================
#  CALCULATION ENGINE
# ============================================================

# ---------- OIL ----------

def standing_correlation(API, gasSG, T, P, gor_input=None):
    a = 0.00091 * T - 0.0125 * API
    if gor_input is not None:
        Rs = float(gor_input)
    else:
        Rs = gasSG * ((P / 18.2 + 1.4) * 10 ** (-a)) ** 1.2048
    Pb = 18.2 * ((Rs / gasSG) ** 0.83 * 10 ** a - 1.4)
    oilSG = 141.5 / (API + 131.5)
    F = Rs * math.sqrt(gasSG / oilSG) + 1.25 * T
    Bo = 0.9759 + 0.00012 * F ** 1.2
    return max(14.7, Pb), max(0.0, Rs), Bo


def vasquez_beggs_correlation(API, gasSG, T, P, gor_input=None, sepP=100.0, sepT=80.0):
    gasSGcorr = gasSG * (1 + 5.912e-5 * API * sepT * math.log10(sepP / 114.7))
    if API <= 30:
        C1, C2, C3 = 0.0362, 1.0937, 25.724
    else:
        C1, C2, C3 = 0.0178, 1.187, 23.931
    if gor_input is not None:
        Rs = float(gor_input)
    else:
        Rs = C1 * gasSGcorr * P ** C2 * math.exp(C3 * API / (T + 460))
    Pb = (Rs / (C1 * gasSGcorr * math.exp(C3 * API / (T + 460)))) ** (1 / C2)
    if API <= 30:
        C4, C5, C6 = 4.677e-4, 1.751e-5, -1.811e-8
    else:
        C4, C5, C6 = 4.67e-4, 1.1e-5, 1.337e-9
    Bo = 1 + C4 * Rs + C5 * (T - 60) * (API / gasSGcorr) + C6 * Rs * (T - 60) * (API / gasSGcorr)
    return max(14.7, Pb), max(0.0, Rs), Bo


def petrosky_farshad_correlation(API, gasSG, T, P, oilSG, gor_input=None):
    X = 4.561e-5 * T ** 1.3911 - 7.916e-4 * API ** 1.541
    if gor_input is not None:
        Rs = float(gor_input)
    else:
        Rs = ((P / 112.727 * 10 ** X) ** 0.5657 * gasSG ** 0.8439) ** 1.7326
    Pb = (112.727 * Rs ** 0.577421 / (gasSG ** 0.8439 * 10 ** X)) ** 1.7669
    F = Rs ** 0.3738 * gasSG ** 0.2914 / oilSG ** 0.6265 + 0.24626 * T ** 0.5371
    Bo = 1.0113 + 7.2046e-5 * F ** 3.0936
    return max(14.7, Pb), max(0.0, Rs), Bo


def beggs_robinson_viscosity(API, T, P, Pb, Rs):
    Z = 3.0324 - 0.02023 * API
    Y = 10 ** Z
    X = Y * T ** (-1.163)
    muod = 10 ** X - 1
    A = 10.715 * (Rs + 100) ** (-0.515)
    B = 5.44 * (Rs + 150) ** (-0.338)
    muo = A * muod ** B
    muUnsat = muo
    if P > Pb:
        m = 2.6 * P ** 1.187 * math.exp(-11.513 - 8.98e-5 * P)
        muUnsat = muo * (P / Pb) ** m
    return muod, muo, muUnsat


def calculate_oil_density(oilSG, gasSG, Rs, Bo):
    return (62.4 * oilSG + 0.0136 * Rs * gasSG) / Bo


def calculate_oil_compressibility(API, gasSG, T, P, Rs):
    coAbove = (-1433 + 5 * Rs + 17.2 * T - 1180 * gasSG + 12.61 * API) / (P * 1e5)
    coBelow = coAbove * 1.5
    return coAbove, coBelow


def calculate_undersaturated_bo(Bob, P, Pb, API, gasSG, T, Rs):
    co = (-1433 + 5 * Rs + 17.2 * T - 1180 * gasSG + 12.61 * API) / (1e5 * P)
    return Bob * math.exp(-co * (P - Pb))


# ---------- GAS ----------

def dranchuk_abou_kassem(Pr, Tr):
    A1, A2, A3, A4, A5 = 0.3265, -1.0700, -0.5339, 0.01569, -0.05165
    A6, A7, A8, A9, A10, A11 = 0.5475, -0.7361, 0.1844, 0.1056, 0.6134, 0.7210
    Z = 1.0
    for _ in range(100):
        rhor = 0.27 * Pr / (Z * Tr)
        rhor2 = rhor * rhor
        rhor5 = rhor ** 5
        Zold = Z
        Z = (1
             + (A1 + A2/Tr + A3/Tr**3 + A4/Tr**4 + A5/Tr**5) * rhor
             + (A6 + A7/Tr + A8/Tr**2) * rhor2
             - A9 * (A7/Tr + A8/Tr**2) * rhor5
             + A10 * (1 + A11 * rhor2) * (rhor2 / Tr**3) * math.exp(-A11 * rhor2))
        if abs(Z - Zold) < 1e-8:
            break
    return Z


def hall_yarborough(Pr, Tr):
    t = 1 / Tr
    A = 0.06125 * t * math.exp(-1.2 * (1 - t) ** 2)
    Y = 0.001
    for _ in range(100):
        Y2 = Y * Y
        Y3 = Y2 * Y
        Y4 = Y3 * Y
        omY = 1 - Y
        omY3 = omY ** 3
        exp1 = 2.18 + 2.82 * t
        F = (-A * Pr
             + (Y + Y2 + Y3 - Y4) / omY3
             - (14.76*t - 9.76*t*t + 4.58*t*t*t) * Y2
             + (90.7*t - 242.2*t*t + 42.4*t*t*t) * Y ** exp1)
        dF = ((1 + 4*Y + 4*Y2 - 4*Y3 + Y4) / (1 - Y) ** 4
              - 2 * (14.76*t - 9.76*t*t + 4.58*t*t*t) * Y
              + exp1 * (90.7*t - 242.2*t*t + 42.4*t*t*t) * Y ** (exp1 - 1))
        Ynew = Y - F / dF
        if abs(Ynew - Y) < 1e-10:
            Y = Ynew
            break
        Y = max(0.0001, Ynew)
    return A * Pr / Y


def lee_gonzalez_eakin(T, P, Z, gasSG):
    Tabs = T + 460
    M = 28.967 * gasSG
    rhog = P * M / (Z * 10.73 * Tabs) / 62.4
    K = (9.4 + 0.02 * M) * Tabs ** 1.5 / (209 + 19 * M + Tabs)
    X = 3.5 + 986 / Tabs + 0.01 * M
    Y = 2.4 - 0.2 * X
    return K * math.exp(X * rhog ** Y) / 10000


def calculate_gas_compressibility(P, Z, Pr, Tr, method):
    dP = 1
    if method == "dak":
        Z1 = dranchuk_abou_kassem((P - dP) / P * Pr, Tr)
        Z2 = dranchuk_abou_kassem((P + dP) / P * Pr, Tr)
    else:
        Z1 = hall_yarborough((P - dP) / P * Pr, Tr)
        Z2 = hall_yarborough((P + dP) / P * Pr, Tr)
    dZdP = (Z2 - Z1) / (2 * dP)
    cg = 1 / P - 1 / Z * dZdP
    return cg, cg * P


# ---------- WATER ----------

def calculate_water_bw(T, P, S):
    dVwT = -1.0001e-2 + 1.33391e-4 * T + 5.50654e-7 * T * T
    dVwP = (-1.95301e-9 * P * T - 1.72834e-13 * P * P * T
            - 3.58922e-7 * P - 2.25341e-10 * P * P)
    Bw_pure = (1 + dVwT) * (1 + dVwP)
    corr = 1 + S * (5.1e-8 * P
                    + (5.47e-6 - 1.95e-10 * P) * (T - 60)
                    - (3.23e-8 - 8.5e-13 * P) * (T - 60) ** 2)
    return Bw_pure * corr


def calculate_water_density(salinity, Bw):
    rhoSTC = 62.4 * (1 + salinity / 1e6)
    return rhoSTC / Bw


def calculate_water_viscosity(T, P, S):
    A = (109.574 - 8.40564 * S + 0.313314 * S * S + 8.72213e-3 * S ** 3)
    B = (-1.12166 + 2.63951e-2 * S - 6.79461e-4 * S * S
         - 5.47119e-5 * S ** 3 + 1.55586e-6 * S ** 4)
    muw_pure = A * T ** B
    return muw_pure * (0.9994 + 4.0295e-5 * P + 3.1062e-9 * P * P)


def calculate_rsw(T, P, S):
    A = 8.15839 - 6.12265e-2*T + 1.91663e-4*T*T - 2.1654e-7*T**3
    B = 1.01021e-2 - 7.44241e-5*T + 3.05553e-7*T*T - 2.94883e-10*T**3
    C = -1.0e-7 * (9.02505 - 0.130237*T + 8.53425e-4*T*T
                   - 2.34122e-6*T**3 + 2.37049e-9*T**4)
    Rsw_pure = A + B * P + C * P * P
    Rsw = Rsw_pure * 10 ** (-0.0840655 * S * T ** (-0.285854))
    return max(0.0, Rsw)


def calculate_water_compressibility(T, P, salinity):
    S_gL = salinity / 1000
    return 1 / (7.033 * P + 541.5 * S_gL - 537 * T + 403300)


def calculate_water_content_bukacek(T, P):
    # Bukacek (1959) correlation for natural gas water content (lb/MMscf)
    Tabs = T + 459.67
    log_Pwv = 7.04013 - 1668.21 / Tabs
    Pwv = 10.0 ** log_Pwv
    A = 47484.2 * Pwv
    log_B = -3083.87 / Tabs + 6.69449
    B = 10.0 ** log_B
    W = A / P + B
    return W


# ============================================================
#  GUI  HELPERS (Premium Overhaul)
# ============================================================

def styled_label(parent, text, fg=TEXT_SEC, font_size=9, bold=False, **kw):
    f = ("Segoe UI", font_size, "bold") if bold else ("Segoe UI", font_size)
    bg = parent.cget("bg") if hasattr(parent, "cget") else BG_SECONDARY
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=f, **kw)


def styled_entry(parent, textvariable, width=10):
    e = tk.Entry(parent, textvariable=textvariable, width=width,
                 bg=BG_TERTIARY, fg=TEXT_PRIMARY, insertbackground=GLOW_CYAN,
                 selectbackground=ACCENT, selectforeground=BG_PRIMARY,
                 relief="flat", font=("Segoe UI", 9, "bold"),
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=GLOW_CYAN)
    return e


def styled_combo(parent, textvariable, values, width=28):
    cb = ttk.Combobox(parent, textvariable=textvariable,
                      values=values, width=width,
                      state="readonly", style="Dark.TCombobox",
                      font=("Segoe UI", 9))
    return cb


def result_frame(parent, label, var, unit, highlight=False):
    """A small result box with label / value / unit."""
    card_bg = BG_TERTIARY
    border_col = ACCENT if highlight else BORDER
    
    f = tk.Frame(parent, bg=card_bg,
                 highlightthickness=1,
                 highlightbackground=border_col)
                 
    lbl = tk.Label(f, text=label.upper(), bg=card_bg, fg=TEXT_SEC,
                   font=("Segoe UI", 7, "bold"))
    lbl.pack(pady=(6, 2), padx=6)
    
    val_lbl = tk.Label(f, textvariable=var, bg=card_bg, fg=ACCENT if highlight else ACCENT2,
                       font=("Consolas", 13, "bold"))
    val_lbl.pack(pady=2, padx=6)
    
    unit_lbl = tk.Label(f, text=unit, bg=card_bg, fg=TEXT_MUTED,
                        font=("Segoe UI", 7))
    unit_lbl.pack(pady=(0, 6), padx=6)
    
    return f


def section_label(parent, text):
    bg = parent.cget("bg") if hasattr(parent, "cget") else BG_SECONDARY
    tk.Label(parent, text=text, bg=bg, fg=ACCENT,
             font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 4))


def make_button(parent, text, command, color=ACCENT, width=20):
    btn = tk.Button(parent, text=text, command=command,
                    bg=color, fg=TEXT_PRIMARY if color != SUCCESS and color != WARNING else BG_PRIMARY,
                    activebackground=ACCENT2,
                    activeforeground=TEXT_PRIMARY, relief="flat",
                    font=("Segoe UI", 9, "bold"), cursor="hand2",
                    width=width, bd=0, highlightthickness=0, pady=5)
    
    # Hover maps
    hover_map = {
        ACCENT: "#fa8a3c",
        ACCENT2: "#fdb87b",
        SUCCESS: "#34d399",
        "#1a3a1a": "#235023",
    }
    hover_color = hover_map.get(color, ACCENT2)
    
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_color))
    btn.bind("<Leave>", lambda e: btn.config(bg=color))
    return btn


def form_row(parent, pairs):
    """pairs = list of (label_text, tk.Variable)"""
    bg = parent.cget("bg") if hasattr(parent, "cget") else BG_SECONDARY
    row = tk.Frame(parent, bg=bg)
    row.pack(fill="x", pady=4)
    entries = []
    for col, (lbl, var) in enumerate(pairs):
        col_f = tk.Frame(row, bg=bg)
        col_f.pack(side="left", fill="x", expand=True, padx=(0, 6))
        styled_label(col_f, lbl).pack(anchor="w", pady=(0, 2))
        e = styled_entry(col_f, var, width=12)
        e.pack(fill="x")
        entries.append(e)
    return row, entries


# ============================================================
#  MAIN APPLICATION
# ============================================================

class PVTCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PVT Calculator – Fluid Properties Analysis")
        self.configure(bg=BG_PRIMARY)
        self.geometry("1400x900")
        self.minsize(950, 650)

        self._setup_styles()
        self._build_header()
        self._build_notebook()
        self._build_footer()

        # Run initial calculation after window is drawn
        self.after(100, self._initial_calc)

    # ----------------------------------------------------------
    def _initial_calc(self):
        self._calc_oil()
        self._calc_gas()
        self._calc_water()

    # ----------------------------------------------------------
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Notebook Style
        style.configure("Dark.TNotebook",
                        background=BG_PRIMARY, borderwidth=0)
        style.configure("Dark.TNotebook.Tab",
                        background=BG_SECONDARY, foreground=TEXT_SEC,
                        bordercolor=BORDER, lightcolor=BG_SECONDARY, darkcolor=BG_SECONDARY,
                        padding=(16, 8), font=("Segoe UI", 9, "bold"),
                        borderwidth=0)
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", BG_SECONDARY)],
                  foreground=[("selected", ACCENT)],
                  bordercolor=[("selected", BORDER)])
                  
        # Inner Notebook Style for Reference Tab
        style.configure("Inner.TNotebook",
                        background=BG_PRIMARY, borderwidth=0)
        style.configure("Inner.TNotebook.Tab",
                        background=BG_SECONDARY, foreground=TEXT_SEC,
                        padding=(12, 6), font=("Segoe UI", 8, "bold"),
                        bordercolor=BORDER, lightcolor=BG_SECONDARY, darkcolor=BG_SECONDARY)
        style.map("Inner.TNotebook.Tab",
                  background=[("selected", BG_TERTIARY)],
                  foreground=[("selected", ACCENT)],
                  bordercolor=[("selected", BORDER)])
                  
        # Combobox Style
        style.configure("Dark.TCombobox",
                        fieldbackground=BG_TERTIARY,
                        background=BG_TERTIARY,
                        foreground=TEXT_PRIMARY,
                        selectbackground=ACCENT,
                        selectforeground=TEXT_PRIMARY,
                        bordercolor=BORDER,
                        arrowcolor=TEXT_SEC,
                        lightcolor=BG_TERTIARY,
                        darkcolor=BG_TERTIARY)
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", BG_TERTIARY)],
                  foreground=[("readonly", TEXT_PRIMARY)],
                  bordercolor=[("focus", GLOW_CYAN)])
                  
        # Treeview Style
        style.configure("Dark.Treeview",
                        background=BG_TERTIARY,
                        foreground=TEXT_PRIMARY,
                        fieldbackground=BG_TERTIARY,
                        rowheight=26,
                        font=("Consolas", 9))
        style.configure("Dark.Treeview.Heading",
                        background=BG_SECONDARY,
                        foreground=ACCENT,
                        bordercolor=BORDER,
                        font=("Segoe UI", 8, "bold"))
        style.map("Dark.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BG_PRIMARY)])
                  
        # Scrollbar Layout & Styles
        style.layout("Vertical.Dark.TScrollbar", [
            ("Vertical.Scrollbar.trough", {
                "children": [
                    ("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
                ],
                "sticky": "ns"
            })
        ])
        style.configure("Vertical.Dark.TScrollbar",
                        troughcolor=BG_PRIMARY,
                        background=BORDER,
                        bordercolor=BG_PRIMARY,
                        arrowsize=0)
        style.map("Vertical.Dark.TScrollbar",
                  background=[("active", ACCENT), ("pressed", ACCENT_LIGHT)])
                  
        style.layout("Horizontal.Dark.TScrollbar", [
            ("Horizontal.Scrollbar.trough", {
                "children": [
                    ("Horizontal.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})
                ],
                "sticky": "ew"
            })
        ])
        style.configure("Horizontal.Dark.TScrollbar",
                        troughcolor=BG_PRIMARY,
                        background=BORDER,
                        bordercolor=BG_PRIMARY,
                        arrowsize=0)
        style.map("Horizontal.Dark.TScrollbar",
                  background=[("active", ACCENT), ("pressed", ACCENT_LIGHT)])

    # ----------------------------------------------------------
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_SECONDARY, pady=12,
                       highlightthickness=1, highlightbackground=BORDER)
        hdr.pack(fill="x")
        
        title_f = tk.Frame(hdr, bg=BG_SECONDARY)
        title_f.pack(side="left", padx=20)
        
        tk.Label(title_f, text="◈  PVT CALCULATOR",
                 bg=BG_SECONDARY, fg=ACCENT,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        tk.Label(title_f, text="Fluid Properties Analysis",
                 bg=BG_SECONDARY, fg=TEXT_SEC,
                 font=("Segoe UI", 10)).pack(side="left", padx=10)
                 
        meta_f = tk.Frame(hdr, bg=BG_SECONDARY)
        meta_f.pack(side="right", padx=20)
        
        tk.Label(meta_f, text="Nama Anggota Kelompok:",
                 bg=BG_SECONDARY, fg=TEXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="e")
        tk.Label(meta_f, text="Muhammad Reyvan Andrian • 12224096",
                 bg=BG_SECONDARY, fg=ACCENT2,
                 font=("Segoe UI", 10, "bold")).pack(anchor="e")

    # ----------------------------------------------------------
    def _build_footer(self):
        pass

    # ----------------------------------------------------------
    def _build_notebook(self):
        nb = ttk.Notebook(self, style="Dark.TNotebook")
        nb.pack(fill="both", expand=True, padx=10, pady=8)

        self._build_oil_tab(nb)
        self._build_gas_tab(nb)
        self._build_water_tab(nb)
        self._build_tables_tab(nb)
        self._build_reference_tab(nb)

    # ==========================================================
    #  OIL TAB
    # ==========================================================
    def _build_oil_tab(self, nb):
        outer = tk.Frame(nb, bg=BG_PRIMARY)
        nb.add(outer, text="Oil Properties")

        # ---- Variables ----
        self.oil_api    = tk.StringVar(value="35")
        self.oil_gasSG  = tk.StringVar(value="0.75")
        self.oil_temp   = tk.StringVar(value="180")
        self.oil_pres   = tk.StringVar(value="2500")
        self.oil_gor    = tk.StringVar(value="")
        self.oil_sepP   = tk.StringVar(value="100")
        self.oil_sepT   = tk.StringVar(value="80")
        self.oil_corr   = tk.StringVar(value="Standing (1947)")

        # Results
        self.res_oil_pb          = tk.StringVar(value="--")
        self.res_oil_rs          = tk.StringVar(value="--")
        self.res_oil_bo          = tk.StringVar(value="--")
        self.res_oil_density     = tk.StringVar(value="--")
        self.res_oil_visc_dead   = tk.StringVar(value="--")
        self.res_oil_visc_live   = tk.StringVar(value="--")
        self.res_oil_visc_unsat  = tk.StringVar(value="--")
        self.res_oil_comp_above  = tk.StringVar(value="--")
        self.res_oil_comp_below  = tk.StringVar(value="--")
        self.res_oil_state       = tk.StringVar(value="--")

        # Comparison
        self.comp_pb_st  = tk.StringVar(value="--")
        self.comp_pb_vb  = tk.StringVar(value="--")
        self.comp_pb_pf  = tk.StringVar(value="--")
        self.comp_rs_st  = tk.StringVar(value="--")
        self.comp_rs_vb  = tk.StringVar(value="--")
        self.comp_rs_pf  = tk.StringVar(value="--")
        self.comp_bo_st  = tk.StringVar(value="--")
        self.comp_bo_vb  = tk.StringVar(value="--")
        self.comp_bo_pf  = tk.StringVar(value="--")

        # ---- Layout: responsive columns (no canvas wrapper) ----
        cols = tk.Frame(outer, bg=BG_PRIMARY)
        cols.pack(fill="both", expand=True, padx=8, pady=8)

        col1 = tk.Frame(cols, bg=BG_SECONDARY, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        col1.pack(side="left", fill="y", padx=(0, 8), pady=4)
        col1.pack_propagate(False)
        col1.config(width=340)

        col2 = tk.Frame(cols, bg=BG_SECONDARY, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        col2.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=4)

        col3 = tk.Frame(cols, bg=BG_SECONDARY, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        col3.pack(side="left", fill="y", padx=(0, 0), pady=4)
        col3.pack_propagate(False)
        col3.config(width=330)

        # ---- Column 1: Inputs ----
        styled_label(col1, "Oil Input Parameters", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))

        form_row(col1, [("API Gravity", self.oil_api),
                        ("Gas Specific Gravity", self.oil_gasSG)])
        form_row(col1, [("Temperature (F)", self.oil_temp),
                        ("Pressure (psia)", self.oil_pres)])

        tk.Frame(col1, bg=BORDER, height=1).pack(fill="x", pady=8)
        styled_label(col1, "GOR (scf/STB) – Optional (blank = calculate Rs)").pack(anchor="w", pady=(0, 2))
        styled_entry(col1, self.oil_gor, width=28).pack(fill="x")

        tk.Frame(col1, bg=BORDER, height=1).pack(fill="x", pady=8)
        section_label(col1, "Separator Conditions (for Vasquez-Beggs)")
        form_row(col1, [("Sep. Pressure (psia)", self.oil_sepP),
                        ("Sep. Temperature (F)", self.oil_sepT)])

        tk.Frame(col1, bg=BORDER, height=1).pack(fill="x", pady=8)
        section_label(col1, "Select Correlation")
        styled_combo(col1, self.oil_corr,
                     ["Standing (1947)", "Vasquez-Beggs (1980)", "Petrosky-Farshad (1993)"],
                     width=28).pack(fill="x", pady=(0, 10))

        make_button(col1, "Calculate Oil Properties", self._calc_oil, width=30).pack(
            fill="x", pady=(12, 0))

        # ---- Column 2: Results ----
        styled_label(col2, "Calculated Oil Properties", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))

        section_label(col2, "PVT Properties")
        r_grid = tk.Frame(col2, bg=BG_SECONDARY)
        r_grid.pack(fill="x")
        for i, (lbl, var, unit, hi) in enumerate([
            ("Bubble Point Pressure", self.res_oil_pb,         "psia",       True),
            ("Solution GOR (Rs)",     self.res_oil_rs,         "scf/STB",    True),
            ("Oil FVF (Bo)",          self.res_oil_bo,         "RB/STB",     False),
            ("Oil Density",           self.res_oil_density,    "lb/ft3",     False),
        ]):
            result_frame(r_grid, lbl, var, unit, hi).grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(4):
            r_grid.columnconfigure(i, weight=1)

        section_label(col2, "Viscosity (Beggs-Robinson)")
        v_grid = tk.Frame(col2, bg=BG_SECONDARY)
        v_grid.pack(fill="x")
        for i, (lbl, var) in enumerate([
            ("Dead Oil Viscosity",    self.res_oil_visc_dead),
            ("Live Oil Viscosity",    self.res_oil_visc_live),
            ("Undersaturated Visc",   self.res_oil_visc_unsat),
        ]):
            result_frame(v_grid, lbl, var, "cp").grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(3):
            v_grid.columnconfigure(i, weight=1)

        section_label(col2, "Oil Compressibility")
        c_grid = tk.Frame(col2, bg=BG_SECONDARY)
        c_grid.pack(fill="x")
        for i, (lbl, var) in enumerate([
            ("Above Pb (Undersaturated)", self.res_oil_comp_above),
            ("Below Pb (Saturated)",      self.res_oil_comp_below),
        ]):
            result_frame(c_grid, lbl, var, "psi\u207b\u00b9 x 10\u207b\u2076").grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(2):
            c_grid.columnconfigure(i, weight=1)

        section_label(col2, "State at Current Pressure")
        state_f = tk.Frame(col2, bg=BG_TERTIARY, pady=8, highlightthickness=1, highlightbackground=BORDER)
        state_f.pack(fill="x", padx=4, pady=4)
        tk.Label(state_f, textvariable=self.res_oil_state,
                 bg=BG_TERTIARY, fg=WARNING,
                 font=("Segoe UI", 11, "bold")).pack()

        # ---- Column 3: Comparison ----
        styled_label(col3, "Comparison by Correlation", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))

        comp_tbl = tk.Frame(col3, bg=BG_TERTIARY, highlightthickness=1, highlightbackground=BORDER)
        comp_tbl.pack(fill="x", pady=4)
        headers = ["Property", "Standing", "Vasquez-B.", "Petrosky"]
        for j, h in enumerate(headers):
            tk.Label(comp_tbl, text=h, bg=BG_TERTIARY, fg=ACCENT,
                     font=("Segoe UI", 8, "bold"), padx=4, pady=4,
                     relief="flat").grid(row=0, column=j, sticky="nsew")
        rows_data = [
            ("Pb (psia)", self.comp_pb_st, self.comp_pb_vb, self.comp_pb_pf),
            ("Rs (scf/STB)", self.comp_rs_st, self.comp_rs_vb, self.comp_rs_pf),
            ("Bo (RB/STB)", self.comp_bo_st, self.comp_bo_vb, self.comp_bo_pf),
        ]
        for ri, (prop, v1, v2, v3) in enumerate(rows_data):
            tk.Label(comp_tbl, text=prop, bg=BG_TERTIARY, fg=TEXT_PRIMARY,
                     font=("Segoe UI", 8), padx=4, pady=4,
                     relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER).grid(row=ri+1, column=0, sticky="nsew")
            for ci, var in enumerate([v1, v2, v3]):
                tk.Label(comp_tbl, textvariable=var, bg=BG_TERTIARY, fg=ACCENT_LIGHT,
                         font=("Consolas", 8, "bold"), padx=4, pady=4,
                         relief="flat", bd=0, highlightthickness=1, highlightbackground=BORDER).grid(row=ri+1, column=ci+1, sticky="nsew")
        for j in range(4):
            comp_tbl.columnconfigure(j, weight=1)

        tk.Frame(col3, bg=BORDER, height=1).pack(fill="x", pady=12)
        guide = (
            "Correlation Selection Guide\n\n"
            "Standing:\n  General-purpose, API 16-63,\n  T 100-258°F, Pb < 5000 psi\n\n"
            "Vasquez-Beggs:\n  Wide range, uses separator\n  conditions for accuracy\n\n"
            "Petrosky-Farshad:\n  Gulf of Mexico oils,\n  API 16-45, T 114-288°F"
        )
        tk.Label(col3, text=guide, bg=BG_SECONDARY, fg=TEXT_SEC,
                 font=("Segoe UI", 8), justify="left").pack(anchor="w", padx=4)

    # ----------------------------------------------------------
    def _calc_oil(self):
        try:
            API   = float(self.oil_api.get())
            gasSG = float(self.oil_gasSG.get())
            T     = float(self.oil_temp.get())
            P     = float(self.oil_pres.get())
            gorRaw = self.oil_gor.get().strip()
            gor   = float(gorRaw) if gorRaw else None
            sepP  = float(self.oil_sepP.get())
            sepT  = float(self.oil_sepT.get())
            corr  = self.oil_corr.get()
            oilSG = 141.5 / (API + 131.5)

            if "Standing" in corr:
                Pb, Rs, Bo = standing_correlation(API, gasSG, T, P, gor)
            elif "Vasquez" in corr:
                Pb, Rs, Bo = vasquez_beggs_correlation(API, gasSG, T, P, gor, sepP, sepT)
            else:
                Pb, Rs, Bo = petrosky_farshad_correlation(API, gasSG, T, P, oilSG, gor)

            muod, muo, muUnsat = beggs_robinson_viscosity(API, T, P, Pb, Rs)
            rho = calculate_oil_density(oilSG, gasSG, Rs, Bo)
            coAbove, coBelow = calculate_oil_compressibility(API, gasSG, T, P, Rs)

            self.res_oil_pb.set(f"{Pb:.1f}")
            self.res_oil_rs.set(f"{Rs:.1f}")
            self.res_oil_bo.set(f"{Bo:.4f}")
            self.res_oil_density.set(f"{rho:.2f}")
            self.res_oil_visc_dead.set(f"{muod:.3f}")
            self.res_oil_visc_live.set(f"{muo:.3f}")
            self.res_oil_visc_unsat.set(f"{(muUnsat if P > Pb else muo):.3f}")
            self.res_oil_comp_above.set(f"{coAbove*1e6:.2f}")
            self.res_oil_comp_below.set(f"{coBelow*1e6:.2f}")
            
            # Saturated/Undersaturated status
            if P > Pb:
                self.res_oil_state.set("Undersaturated (P > Pb)")
            else:
                self.res_oil_state.set("Saturated (P ≤ Pb)")

            # Comparison
            Pb_st, Rs_st, Bo_st = standing_correlation(API, gasSG, T, P, gor)
            Pb_vb, Rs_vb, Bo_vb = vasquez_beggs_correlation(API, gasSG, T, P, gor, sepP, sepT)
            Pb_pf, Rs_pf, Bo_pf = petrosky_farshad_correlation(API, gasSG, T, P, oilSG, gor)
            self.comp_pb_st.set(f"{Pb_st:.0f}")
            self.comp_pb_vb.set(f"{Pb_vb:.0f}")
            self.comp_pb_pf.set(f"{Pb_pf:.0f}")
            self.comp_rs_st.set(f"{Rs_st:.0f}")
            self.comp_rs_vb.set(f"{Rs_vb:.0f}")
            self.comp_rs_pf.set(f"{Rs_pf:.0f}")
            self.comp_bo_st.set(f"{Bo_st:.4f}")
            self.comp_bo_vb.set(f"{Bo_vb:.4f}")
            self.comp_bo_pf.set(f"{Bo_pf:.4f}")
        except Exception as e:
            messagebox.showerror("Calculation Error", str(e))

    # ==========================================================
    #  GAS TAB
    # ==========================================================
    def _build_gas_tab(self, nb):
        outer = tk.Frame(nb, bg=BG_PRIMARY)
        nb.add(outer, text="Gas Properties")

        # Variables
        self.gas_sg     = tk.StringVar(value="0.75")
        self.gas_temp   = tk.StringVar(value="200")
        self.gas_pres   = tk.StringVar(value="3000")
        self.gas_n2     = tk.StringVar(value="0")
        self.gas_co2    = tk.StringVar(value="0")
        self.gas_h2s    = tk.StringVar(value="0")
        self.gas_zmethod= tk.StringVar(value="Dranchuk-Abou-Kassem (DAK)")

        self.res_gas_ppc_raw = tk.StringVar(value="--")
        self.res_gas_tpc_raw = tk.StringVar(value="--")
        self.res_gas_ppc     = tk.StringVar(value="--")
        self.res_gas_tpc     = tk.StringVar(value="--")
        self.res_gas_pr      = tk.StringVar(value="--")
        self.res_gas_tr      = tk.StringVar(value="--")
        self.res_gas_z       = tk.StringVar(value="--")
        self.res_gas_bg      = tk.StringVar(value="--")
        self.res_gas_density = tk.StringVar(value="--")
        self.res_gas_visc    = tk.StringVar(value="--")
        self.res_gas_comp    = tk.StringVar(value="--")
        self.res_gas_cgp     = tk.StringVar(value="--")

        cols = tk.Frame(outer, bg=BG_PRIMARY)
        cols.pack(fill="both", expand=True, padx=8, pady=8)

        col1 = tk.Frame(cols, bg=BG_SECONDARY, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        col1.pack(side="left", fill="y", padx=(0, 8), pady=4)
        col1.pack_propagate(False)
        col1.config(width=340)

        col2 = tk.Frame(cols, bg=BG_SECONDARY, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        col2.pack(side="left", fill="both", expand=True, pady=4)

        # Inputs
        styled_label(col1, "Gas Input Parameters", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))
        form_row(col1, [("Gas Specific Gravity (air=1)", self.gas_sg),
                        ("Temperature (F)", self.gas_temp)])
        styled_label(col1, "Pressure (psia)").pack(anchor="w", pady=(4, 0))
        styled_entry(col1, self.gas_pres, width=28).pack(fill="x")

        tk.Frame(col1, bg=BORDER, height=1).pack(fill="x", pady=8)
        section_label(col1, "Non-Hydrocarbon Components (mol%)")
        form_row(col1, [("N2 %", self.gas_n2), ("CO2 %", self.gas_co2)])
        styled_label(col1, "H2S %").pack(anchor="w", pady=(4, 0))
        styled_entry(col1, self.gas_h2s, width=28).pack(fill="x", pady=(0, 4))
        styled_label(col1, "Used for Wichert-Aziz correction to pseudocritical properties",
                     font_size=7, fg=TEXT_MUTED).pack(anchor="w")

        tk.Frame(col1, bg=BORDER, height=1).pack(fill="x", pady=8)
        section_label(col1, "Z-Factor Method")
        styled_combo(col1, self.gas_zmethod,
                     ["Dranchuk-Abou-Kassem (DAK)", "Hall-Yarborough"],
                     width=28).pack(fill="x", pady=(0, 10))

        make_button(col1, "Calculate Gas Properties", self._calc_gas, width=30).pack(
            fill="x", pady=(12, 0))

        # Results
        styled_label(col2, "Calculated Gas Properties", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))

        section_label(col2, "Pseudocritical Properties (Sutton Correlation)")
        pc_grid = tk.Frame(col2, bg=BG_SECONDARY)
        pc_grid.pack(fill="x")
        for i, (lbl, var, unit, hi) in enumerate([
            ("Ppc (uncorrected)", self.res_gas_ppc_raw, "psia", False),
            ("Tpc (uncorrected)", self.res_gas_tpc_raw, "R",    False),
            ("Ppc (corrected)",   self.res_gas_ppc,     "psia", True),
            ("Tpc (corrected)",   self.res_gas_tpc,     "R",    True),
        ]):
            result_frame(pc_grid, lbl, var, unit, hi).grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(4): pc_grid.columnconfigure(i, weight=1)

        section_label(col2, "Reduced Properties")
        rp_grid = tk.Frame(col2, bg=BG_SECONDARY)
        rp_grid.pack(fill="x")
        for i, (lbl, var) in enumerate([
            ("Reduced Pressure (Pr)", self.res_gas_pr),
            ("Reduced Temperature (Tr)", self.res_gas_tr),
        ]):
            result_frame(rp_grid, lbl, var, "dimensionless").grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(2): rp_grid.columnconfigure(i, weight=1)

        section_label(col2, "Gas Properties")
        gp_grid = tk.Frame(col2, bg=BG_SECONDARY)
        gp_grid.pack(fill="x")
        for i, (lbl, var, unit, hi) in enumerate([
            ("Z-Factor",         self.res_gas_z,       "dimensionless", True),
            ("Gas FVF (Bg)",     self.res_gas_bg,      "RCF/SCF",       True),
            ("Gas Density",      self.res_gas_density, "lb/ft3",        False),
            ("Gas Viscosity",    self.res_gas_visc,    "cp",            False),
        ]):
            result_frame(gp_grid, lbl, var, unit, hi).grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(4): gp_grid.columnconfigure(i, weight=1)

        section_label(col2, "Compressibility")
        cg_grid = tk.Frame(col2, bg=BG_SECONDARY)
        cg_grid.pack(fill="x")
        for i, (lbl, var, unit) in enumerate([
            ("Gas Compressibility (cg)", self.res_gas_comp, "psi\u207b\u00b9 x 10\u207b\u2074"),
            ("cg \u00d7 P",              self.res_gas_cgp,  "dimensionless"),
        ]):
            result_frame(cg_grid, lbl, var, unit).grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(2): cg_grid.columnconfigure(i, weight=1)

    # ----------------------------------------------------------
    def _calc_gas(self):
        try:
            gasSG = float(self.gas_sg.get())
            T     = float(self.gas_temp.get())
            P     = float(self.gas_pres.get())
            yN2   = float(self.gas_n2.get()) / 100
            yCO2  = float(self.gas_co2.get()) / 100
            yH2S  = float(self.gas_h2s.get()) / 100
            zmet  = self.gas_zmethod.get()
            Tabs  = T + 460

            Tpc_raw = 169.2 + 349.5 * gasSG - 74.0 * gasSG ** 2
            Ppc_raw = 756.8 - 131.07 * gasSG - 3.6 * gasSG ** 2

            A = yH2S + yCO2
            B = yH2S
            epsilon = (120 * (A ** 0.9 - A ** 1.6)
                       + 15 * (B ** 0.5 - B ** 4))
            Tpc = Tpc_raw - epsilon
            Ppc = Ppc_raw * Tpc / (Tpc_raw + B * (1 - B) * epsilon) if (Tpc_raw + B * (1 - B) * epsilon) != 0 else Ppc_raw

            Pr = P / Ppc
            Tr = Tabs / Tpc

            if "DAK" in zmet or "Dranchuk" in zmet:
                Z = dranchuk_abou_kassem(Pr, Tr)
            else:
                Z = hall_yarborough(Pr, Tr)

            Bg  = 0.02827 * Z * Tabs / P
            M   = 28.967 * gasSG
            rhog = P * M / (Z * 10.73 * Tabs)
            mug  = lee_gonzalez_eakin(T, P, Z, gasSG)
            cg, cgP = calculate_gas_compressibility(P, Z, Pr, Tr,
                                                    "dak" if "DAK" in zmet or "Dranchuk" in zmet else "hall")

            self.res_gas_ppc_raw.set(f"{Ppc_raw:.1f}")
            self.res_gas_tpc_raw.set(f"{Tpc_raw:.1f}")
            self.res_gas_ppc.set(f"{Ppc:.1f}")
            self.res_gas_tpc.set(f"{Tpc:.1f}")
            self.res_gas_pr.set(f"{Pr:.4f}")
            self.res_gas_tr.set(f"{Tr:.4f}")
            self.res_gas_z.set(f"{Z:.4f}")
            self.res_gas_bg.set(f"{Bg:.6f}")
            self.res_gas_density.set(f"{rhog:.4f}")
            self.res_gas_visc.set(f"{mug:.5f}")
            self.res_gas_comp.set(f"{cg*1e4:.4f}")
            self.res_gas_cgp.set(f"{cgP:.4f}")
        except Exception as e:
            messagebox.showerror("Calculation Error", str(e))

    # ==========================================================
    #  WATER TAB
    # ==========================================================
    def _build_water_tab(self, nb):
        outer = tk.Frame(nb, bg=BG_PRIMARY)
        nb.add(outer, text="Water Properties")

        self.water_sal    = tk.StringVar(value="50000")
        self.water_temp   = tk.StringVar(value="180")
        self.water_pres   = tk.StringVar(value="3000")
        self.water_gasSG  = tk.StringVar(value="0.75")

        self.res_water_bw       = tk.StringVar(value="--")
        self.res_water_density  = tk.StringVar(value="--")
        self.res_water_visc     = tk.StringVar(value="--")
        self.res_water_rsw      = tk.StringVar(value="--")
        self.res_water_comp     = tk.StringVar(value="--")
        self.res_water_comp_res = tk.StringVar(value="--")

        cols = tk.Frame(outer, bg=BG_PRIMARY)
        cols.pack(fill="both", expand=True, padx=8, pady=8)

        col1 = tk.Frame(cols, bg=BG_SECONDARY, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        col1.pack(side="left", fill="y", padx=(0, 8), pady=4)
        col1.pack_propagate(False)
        col1.config(width=340)

        col2 = tk.Frame(cols, bg=BG_SECONDARY, padx=14, pady=14,
                        highlightthickness=1, highlightbackground=BORDER)
        col2.pack(side="left", fill="both", expand=True, pady=4)

        styled_label(col1, "Water Input Parameters", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))
        styled_label(col1, "Salinity (ppm or mg/L TDS)").pack(anchor="w")
        styled_entry(col1, self.water_sal, width=28).pack(fill="x")
        styled_label(col1, "Fresh water: 0, Seawater: ~35,000, Brine: 50k-300k",
                     font_size=7, fg=TEXT_MUTED).pack(anchor="w", pady=(1, 4))

        form_row(col1, [("Temperature (F)", self.water_temp),
                        ("Pressure (psia)", self.water_pres)])
        styled_label(col1, "Gas Specific Gravity (for Rsw)").pack(anchor="w", pady=(6, 0))
        styled_entry(col1, self.water_gasSG, width=28).pack(fill="x", pady=(0, 10))

        make_button(col1, "Calculate Water Properties", self._calc_water, width=30).pack(
            fill="x", pady=(12, 0))

        styled_label(col2, "Calculated Water Properties", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))

        section_label(col2, "Formation Volume Factor & Density")
        wd_grid = tk.Frame(col2, bg=BG_SECONDARY)
        wd_grid.pack(fill="x")
        for i, (lbl, var, unit, hi) in enumerate([
            ("Water FVF (Bw)", self.res_water_bw,      "RB/STB",  True),
            ("Water Density",  self.res_water_density, "lb/ft3",  True),
        ]):
            result_frame(wd_grid, lbl, var, unit, hi).grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(2): wd_grid.columnconfigure(i, weight=1)

        section_label(col2, "Viscosity & Gas Solubility")
        wv_grid = tk.Frame(col2, bg=BG_SECONDARY)
        wv_grid.pack(fill="x")
        for i, (lbl, var, unit) in enumerate([
            ("Water Viscosity",  self.res_water_visc, "cp"),
            ("Dissolved Gas (Rsw)", self.res_water_rsw, "scf/STB"),
        ]):
            result_frame(wv_grid, lbl, var, unit).grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(2): wv_grid.columnconfigure(i, weight=1)

        section_label(col2, "Compressibility")
        wc_grid = tk.Frame(col2, bg=BG_SECONDARY)
        wc_grid.pack(fill="x")
        for i, (lbl, var) in enumerate([
            ("Water Compressibility (cw)", self.res_water_comp),
            ("cw @ Reservoir",             self.res_water_comp_res),
        ]):
            result_frame(wc_grid, lbl, var, "psi\u207b\u00b9 x 10\u207b\u2076").grid(
                row=0, column=i, padx=4, pady=4, sticky="nsew")
        for i in range(2): wc_grid.columnconfigure(i, weight=1)

        section_label(col2, "Reference Values")
        ref_txt = (
            "Fresh water at STC:  Bw = 1.0, density = 62.4 lb/ft³, μ = 1.0 cp\n"
            "Typical reservoir brine:  Bw = 1.01-1.06, density = 65-75 lb/ft³\n"
            "Water compressibility:  2.5-4.0 × 10⁻⁶ psi⁻¹"
        )
        tk.Label(col2, text=ref_txt, bg=BG_SECONDARY, fg=TEXT_SEC,
                 font=("Consolas", 8), justify="left").pack(anchor="w", padx=4, pady=4)

    # ----------------------------------------------------------
    def _calc_water(self):
        try:
            salinity = float(self.water_sal.get())
            T        = float(self.water_temp.get())
            P        = float(self.water_pres.get())
            S        = salinity / 10000

            Bw   = calculate_water_bw(T, P, S)
            rhow = calculate_water_density(salinity, Bw)
            muw  = calculate_water_viscosity(T, P, S)
            Rsw  = calculate_rsw(T, P, S)
            cw   = calculate_water_compressibility(T, P, salinity)

            self.res_water_bw.set(f"{Bw:.5f}")
            self.res_water_density.set(f"{rhow:.2f}")
            self.res_water_visc.set(f"{muw:.4f}")
            self.res_water_rsw.set(f"{Rsw:.2f}")
            self.res_water_comp.set(f"{cw*1e6:.2f}")
            self.res_water_comp_res.set(f"{cw*1e6:.2f}")
        except Exception as e:
            messagebox.showerror("Calculation Error", str(e))

    # ==========================================================
    #  PROPERTY TABLES TAB
    # ==========================================================
    def _build_tables_tab(self, nb):
        outer = tk.Frame(nb, bg=BG_PRIMARY)
        nb.add(outer, text="Property Tables")

        self.tbl_api    = tk.StringVar(value="35")
        self.tbl_gasSG  = tk.StringVar(value="0.75")
        self.tbl_temp   = tk.StringVar(value="180")
        self.tbl_pb     = tk.StringVar(value="2500")
        self.tbl_pmin   = tk.StringVar(value="500")
        self.tbl_pmax   = tk.StringVar(value="5000")
        self.tbl_pstep  = tk.StringVar(value="250")
        self.tbl_corr   = tk.StringVar(value="Standing")

        self._table_data = []

        # --- Top input bar ---
        inp = tk.Frame(outer, bg=BG_SECONDARY, padx=14, pady=10,
                       highlightthickness=1, highlightbackground=BORDER)
        inp.pack(fill="x", pady=(0, 6))

        styled_label(inp, "Generate PVT Property Tables", fg=ACCENT,
                     font_size=11, bold=True).grid(row=0, column=0,
                     columnspan=8, sticky="w", pady=(0, 8))

        params = [
            ("API Gravity",          self.tbl_api),
            ("Gas SG",               self.tbl_gasSG),
            ("Temperature (F)",      self.tbl_temp),
            ("Bubble Point (psia)",  self.tbl_pb),
            ("Min Pressure (psia)",  self.tbl_pmin),
            ("Max Pressure (psia)",  self.tbl_pmax),
            ("Pressure Step (psi)",  self.tbl_pstep),
        ]
        for col, (lbl, var) in enumerate(params):
            tk.Label(inp, text=lbl, bg=BG_SECONDARY, fg=TEXT_SEC,
                     font=("Segoe UI", 8, "bold")).grid(row=1, column=col, sticky="w", padx=4)
            styled_entry(inp, var, width=10).grid(row=2, column=col, padx=4, pady=(2, 6))

        tk.Label(inp, text="Correlation", bg=BG_SECONDARY, fg=TEXT_SEC,
                 font=("Segoe UI", 8, "bold")).grid(row=1, column=7, sticky="w", padx=4)
        styled_combo(inp, self.tbl_corr,
                     ["Standing", "Vasquez-Beggs", "Petrosky-Farshad"],
                     width=16).grid(row=2, column=7, padx=4, pady=(2, 6))

        btn_row = tk.Frame(inp, bg=BG_SECONDARY)
        btn_row.grid(row=3, column=0, columnspan=8, sticky="w", pady=(6, 0))
        make_button(btn_row, "Generate Table", self._generate_table, width=18).pack(side="left", padx=(0, 8))
        make_button(btn_row, "Export to CSV",  self._export_csv,     width=16,
                    color="#1a3a1a").pack(side="left")

        # --- Bottom area: table + chart ---
        bottom = tk.Frame(outer, bg=BG_PRIMARY)
        bottom.pack(fill="both", expand=True)

        # Table panel
        tbl_frame = tk.Frame(bottom, bg=BG_SECONDARY, padx=12, pady=12,
                             highlightthickness=1, highlightbackground=BORDER)
        tbl_frame.pack(side="left", fill="both", expand=True, padx=(0, 6), pady=4)

        styled_label(tbl_frame, "PVT Property Table", fg=ACCENT,
                     font_size=11, bold=True).pack(anchor="w", pady=(0, 8))

        cols_tbl = ("P (psia)", "Bo (RB/STB)", "Rs (scf/STB)",
                    "μo (cp)", "ρo (lb/ft³)", "Z", "Bg (RCF/SCF)", "μg (cp)")

        tv_frame = tk.Frame(tbl_frame, bg=BG_TERTIARY, highlightthickness=1, highlightbackground=BORDER)
        tv_frame.pack(fill="both", expand=True)

        self._tv = ttk.Treeview(tv_frame, columns=cols_tbl, show="headings",
                                style="Dark.Treeview")
        for c in cols_tbl:
            self._tv.heading(c, text=c)
            self._tv.column(c, width=105, minwidth=100, stretch=True, anchor="center")

        vsb = ttk.Scrollbar(tv_frame, orient="vertical", command=self._tv.yview, style="Dark.TScrollbar")
        hsb = ttk.Scrollbar(tv_frame, orient="horizontal", command=self._tv.xview, style="Dark.TScrollbar")
        self._tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tv_frame.rowconfigure(0, weight=1)
        tv_frame.columnconfigure(0, weight=1)

        # Contextual mouse wheel bindings for vertical and horizontal scrolling
        def _on_tree_mousewheel(event):
            self._tv.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        def _on_tree_shift_mousewheel(event):
            self._tv.xview_scroll(int(-1 * (event.delta / 120)), "units")

        self._tv.bind("<Enter>", lambda e: (
            self._tv.bind_all("<MouseWheel>", _on_tree_mousewheel),
            self._tv.bind_all("<Shift-MouseWheel>", _on_tree_shift_mousewheel)
        ))
        self._tv.bind("<Leave>", lambda e: (
            self._tv.unbind_all("<MouseWheel>"),
            self._tv.unbind_all("<Shift-MouseWheel>")
        ))

        # Chart panel
        chart_frame = tk.Frame(bottom, bg=BG_SECONDARY, padx=12, pady=12,
                               highlightthickness=1, highlightbackground=BORDER)
        chart_frame.pack(side="left", fill="both", expand=True, pady=4)

        chart_hdr = tk.Frame(chart_frame, bg=BG_SECONDARY)
        chart_hdr.pack(fill="x", pady=(0, 8))

        styled_label(chart_hdr, "Property Charts", fg=ACCENT,
                     font_size=11, bold=True).pack(side="left", anchor="w")

        styled_label(chart_hdr, "Cetak Grafik:", fg=TEXT_SEC, font_size=9).pack(side="left", padx=(20, 4))

        self.chart_choice = tk.StringVar(value="P vs Bo")
        self.chart_combo = styled_combo(chart_hdr, self.chart_choice, [
            "P vs Bw",
            "P vs Bo",
            "P vs Rs",
            "P vs Rsw",
            "P vs Water Content",
            "P vs Brine Density",
            "P vs Brine Viscosity",
            "P vs Z",
            "P vs Bg",
            "P vs Eg",
            "P vs Cg",
            "P vs Gas Viscosity",
            "P vs Co"
        ], width=18)
        self.chart_combo.pack(side="left", padx=4)
        self.chart_combo.bind("<<ComboboxSelected>>", lambda e: self._update_chart())

        self._pvt_fig = Figure(figsize=(6, 5), dpi=100, facecolor=BG_PRIMARY)
        self._pvt_ax1 = self._pvt_fig.add_subplot(111)
        self._pvt_ax2 = self._pvt_ax1.twinx()
        self._pvt_canvas = FigureCanvasTkAgg(self._pvt_fig, master=chart_frame)
        self._pvt_canvas.get_tk_widget().pack(fill="both", expand=True)

    # ----------------------------------------------------------
    def _update_chart(self):
        try:
            Pb = float(self.tbl_pb.get())
            self._draw_pvt_chart(Pb)
        except Exception:
            pass

    # ----------------------------------------------------------
    def _generate_table(self):
        try:
            API   = float(self.tbl_api.get())
            gasSG = float(self.tbl_gasSG.get())
            T     = float(self.tbl_temp.get())
            Pb    = float(self.tbl_pb.get())
            Pmin  = float(self.tbl_pmin.get())
            Pmax  = float(self.tbl_pmax.get())
            Pstep = float(self.tbl_pstep.get())
            corr  = self.tbl_corr.get()
            oilSG = 141.5 / (API + 131.5)

            # Clear tree
            for row in self._tv.get_children():
                self._tv.delete(row)
            self._table_data = []

            Tpc = 169.2 + 349.5 * gasSG - 74.0 * gasSG ** 2
            Ppc = 756.8 - 131.07 * gasSG - 3.6 * gasSG ** 2
            Tabs = T + 460

            P = Pmin
            idx = 0
            while P <= Pmax + 1e-6:
                # ---- Oil ----
                if "Standing" in corr:
                    Pb_c, Rs_c, Bo_c = standing_correlation(API, gasSG, T, P)
                    Pb_at, Rs_at, Bo_at = standing_correlation(API, gasSG, T, Pb)
                elif "Vasquez" in corr:
                    Pb_c, Rs_c, Bo_c = vasquez_beggs_correlation(API, gasSG, T, P)
                    Pb_at, Rs_at, Bo_at = vasquez_beggs_correlation(API, gasSG, T, Pb)
                else:
                    Pb_c, Rs_c, Bo_c = petrosky_farshad_correlation(API, gasSG, T, P, oilSG)
                    Pb_at, Rs_at, Bo_at = petrosky_farshad_correlation(API, gasSG, T, Pb, oilSG)

                if P <= Pb:
                    Rs = Rs_c
                    Bo = Bo_c
                else:
                    Rs = Rs_at
                    Bo = calculate_undersaturated_bo(Bo_at, P, Pb, API, gasSG, T, Rs_at)

                _, muo, _ = beggs_robinson_viscosity(API, T, P, Pb, Rs)
                rhoOil = calculate_oil_density(oilSG, gasSG, Rs, Bo)

                # ---- Gas ----
                Pr = P / Ppc
                Tr = Tabs / Tpc
                Z   = dranchuk_abou_kassem(Pr, Tr)
                Bg  = 0.02827 * Z * Tabs / P
                mug = lee_gonzalez_eakin(T, P, Z, gasSG)

                # ---- Water & Extras ----
                try:
                    salinity = float(self.water_sal.get())
                except Exception:
                    salinity = 50000.0
                S_sal = salinity / 10000.0

                Bw = calculate_water_bw(T, P, S_sal)
                Rsw = calculate_rsw(T, P, S_sal)
                W_content = calculate_water_content_bukacek(T, P)
                rhoBrine = calculate_water_density(salinity, Bw)
                muBrine = calculate_water_viscosity(T, P, S_sal)
                Eg = 1.0 / Bg if Bg != 0 else 0.0
                cg, _ = calculate_gas_compressibility(P, Z, Pr, Tr, "dak")
                coAbove, coBelow = calculate_oil_compressibility(API, gasSG, T, P, Rs)
                Co = coAbove if P > Pb else coBelow

                row = dict(
                    P=P, Bo=Bo, Rs=Rs, muo=muo, rhoOil=rhoOil,
                    Z=Z, Bg=Bg, mug=mug,
                    Bw=Bw, Rsw=Rsw, WaterContent=W_content,
                    rhoBrine=rhoBrine, muBrine=muBrine, Eg=Eg,
                    cg=cg, Co=Co
                )
                self._table_data.append(row)

                is_pb_row = abs(P - Pb) < Pstep / 2
                tag = "pb" if is_pb_row else ("even" if idx % 2 == 0 else "odd")
                self._tv.insert("", "end", values=(
                    f"{P:.0f}{'*' if is_pb_row else ''}",
                    f"{Bo:.4f}", f"{Rs:.1f}", f"{muo:.3f}",
                    f"{rhoOil:.2f}", f"{Z:.4f}", f"{Bg:.6f}", f"{mug:.5f}"
                ), tags=(tag,))

                P += Pstep
                idx += 1

            # Tag row configurations
            self._tv.tag_configure("even", background=BG_SECONDARY)
            self._tv.tag_configure("odd", background=BG_TERTIARY)
            self._tv.tag_configure("pb", background="#381608", foreground=ACCENT_LIGHT)
            
            self._draw_pvt_chart(Pb)

        except Exception as e:
            messagebox.showerror("Calculation Error", str(e))

    # ----------------------------------------------------------
    def _draw_pvt_chart(self, Pb):
        ax1 = self._pvt_ax1
        ax2 = self._pvt_ax2
        ax1.cla()
        ax2.cla()
        
        # Completely hide the second axes by default (since we do single property plots)
        ax2.get_yaxis().set_visible(False)
        ax2.spines['right'].set_visible(False)

        if not self._table_data:
            return

        choice = self.chart_choice.get()
        
        chart_config = {
            "P vs Bw":             {"key": "Bw",           "label": "Bw (RB/STB)",                 "color": ACCENT,  "title": "Water Formation Volume Factor (Bw) vs Pressure"},
            "P vs Bo":             {"key": "Bo",           "label": "Bo (RB/STB)",                 "color": ACCENT,  "title": "Oil Formation Volume Factor (Bo) vs Pressure"},
            "P vs Rs":             {"key": "Rs",           "label": "Rs (scf/STB)",                 "color": SUCCESS, "title": "Solution Gas-Oil Ratio (Rs) vs Pressure"},
            "P vs Rsw":            {"key": "Rsw",          "label": "Rsw (scf/STB)",                "color": SUCCESS, "title": "Gas Solubility in Water (Rsw) vs Pressure"},
            "P vs Water Content":  {"key": "WaterContent", "label": "Water Content (lb/MMscf)",      "color": WARNING, "title": "Gas Water Content vs Pressure (Bukacek)"},
            "P vs Brine Density":  {"key": "rhoBrine",     "label": "Brine Density (lb/ft³)",       "color": ACCENT2, "title": "Formation Water Brine Density vs Pressure"},
            "P vs Brine Viscosity":{"key": "muBrine",      "label": "Brine Viscosity (cp)",         "color": INFO,    "title": "Formation Water Brine Viscosity vs Pressure"},
            "P vs Z":              {"key": "Z",            "label": "Z-Factor (dimensionless)",     "color": SUCCESS, "title": "Gas Deviation Factor (Z) vs Pressure"},
            "P vs Bg":             {"key": "Bg",           "label": "Bg (RCF/SCF)",                 "color": ACCENT,  "title": "Gas Formation Volume Factor (Bg) vs Pressure"},
            "P vs Eg":             {"key": "Eg",           "label": "Eg (SCF/RCF)",                 "color": INFO,    "title": "Gas Expansion Factor (Eg) vs Pressure"},
            "P vs Cg":             {"key": "cg",           "label": "cg (psi⁻¹ x 10⁻⁴)",            "color": WARNING, "title": "Gas Compressibility (cg) vs Pressure", "mult": 1e4},
            "P vs Gas Viscosity":  {"key": "mug",          "label": "Gas Viscosity (cp)",           "color": INFO,    "title": "Gas Viscosity vs Pressure"},
            "P vs Co":             {"key": "Co",           "label": "Co (psi⁻¹ x 10⁻⁶)",            "color": DANGER,  "title": "Oil Compressibility (Co) vs Pressure", "mult": 1e6},
        }

        cfg = chart_config.get(choice, chart_config["P vs Bo"])
        y_key = cfg["key"]
        y_label = cfg["label"]
        color = cfg["color"]
        title = cfg["title"]
        mult = cfg.get("mult", 1.0)

        pressures = [d["P"] for d in self._table_data]
        y_vals = [d[y_key] * mult for d in self._table_data]

        # Glow fill underneath curves
        ax1.fill_between(pressures, y_vals, alpha=0.15, color=color)

        # Plot curves
        ax1.plot(pressures, y_vals, color=color, linewidth=2, label=y_label)

        pmin, pmax = min(pressures), max(pressures)
        if pmin <= Pb <= pmax:
            ax1.axvline(x=Pb, color=DANGER, linestyle="--", linewidth=1.5, alpha=0.8)
            ymin, ymax = min(y_vals), max(y_vals)
            ypos = ymin + (ymax - ymin) * 0.9 if ymax != ymin else ymin
            ax1.text(Pb, ypos, f" Pb = {Pb:.0f} psia", color=DANGER, fontsize=8, fontweight="bold", fontfamily="Segoe UI")

        # Custom high-end dark graph theme configurations
        ax1.set_facecolor(BG_SECONDARY)
        self._pvt_fig.set_facecolor(BG_PRIMARY)
        ax1.tick_params(colors=TEXT_SEC, labelsize=8)
        
        # Hide unnecessary frame spines
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.spines['left'].set_color(BORDER)
        ax1.spines['bottom'].set_color(BORDER)
        
        ax1.grid(True, which="both", color=BORDER, linestyle=":", alpha=0.4)
        
        ax1.set_xlabel("Pressure (psia)", color=TEXT_SEC, fontsize=9, fontfamily="Segoe UI")
        ax1.set_ylabel(y_label, color=color, fontsize=9, fontfamily="Segoe UI")
        ax1.set_title(title, color=TEXT_PRIMARY, fontsize=10, fontweight="bold", fontfamily="Segoe UI")

        ax1.legend(facecolor=BG_TERTIARY, edgecolor=BORDER,
                   labelcolor=TEXT_PRIMARY, fontsize=8,
                   loc="upper left")

        self._pvt_canvas.draw()

    # ----------------------------------------------------------
    def _export_csv(self):
        if not self._table_data:
            messagebox.showwarning("No Data", "Please generate a table first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="pvt_properties.csv")
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Pressure (psia)", "Bo (RB/STB)", "Rs (scf/STB)",
                             "Oil Viscosity (cp)", "Oil Density (lb/ft3)",
                             "Z-Factor", "Bg (RCF/SCF)", "Gas Viscosity (cp)"])
            for d in self._table_data:
                writer.writerow([
                    d["P"], f"{d['Bo']:.4f}", f"{d['Rs']:.1f}",
                    f"{d['muo']:.3f}", f"{d['rhoOil']:.2f}",
                    f"{d['Z']:.4f}", f"{d['Bg']:.6f}", f"{d['mug']:.5f}"
                ])
        messagebox.showinfo("Export Complete", f"Saved to:\n{path}")


# ============================================================
#  CORRELATIONS REFERENCE TAB
# ============================================================
    def _build_reference_tab(self, nb):
        outer = tk.Frame(nb, bg=BG_PRIMARY)
        nb.add(outer, text="Correlations Reference")

        inner = ttk.Notebook(outer, style="Inner.TNotebook")
        inner.pack(fill="both", expand=True)

        self._build_oil_ref(inner)
        self._build_gas_ref(inner)
        self._build_water_ref(inner)

    def _ref_card(self, parent, title, lines, border_color=BORDER):
        f = tk.Frame(parent, bg=BG_SECONDARY, padx=14, pady=12,
                     highlightthickness=1, highlightbackground=border_color)
        f.pack(fill="x", pady=6, padx=8)
        
        tk.Label(f, text=title, bg=BG_SECONDARY, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
        
        for line in lines:
            if line.startswith("REF:"):
                tk.Label(f, text=line[4:], bg=BG_SECONDARY, fg=TEXT_MUTED,
                         font=("Segoe UI", 8, "italic"),
                         wraplength=800, justify="left").pack(anchor="w")
            elif line.startswith("RANGE:"):
                tk.Label(f, text=line[6:], bg=BG_SECONDARY, fg=WARNING,
                         font=("Segoe UI", 8, "bold"), wraplength=800,
                         justify="left").pack(anchor="w", pady=(2, 0))
            else:
                # Highlight mathematical formulas
                tk.Label(f, text=line, bg=BG_SECONDARY, fg=TEXT_PRIMARY,
                         font=("Consolas", 9),
                         wraplength=800, justify="left").pack(anchor="w", padx=10, pady=1)

    def _scrollable_frame(self, nb, title):
        frame = tk.Frame(nb, bg=BG_PRIMARY)
        nb.add(frame, text=title)

        canvas = tk.Canvas(frame, bg=BG_PRIMARY, highlightthickness=0)
        sb = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview, style="Dark.TScrollbar")
        
        inner = tk.Frame(canvas, bg=BG_PRIMARY)
        
        def configure_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(win_id, width=canvas.winfo_width())
            
        inner.bind("<Configure>", configure_inner)
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))
        
        # Contextual mouse wheel binding to prevent screen scroll jumping
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))
        
        return inner

    def _build_oil_ref(self, nb):
        f = self._scrollable_frame(nb, "Oil Correlations")
        self._ref_card(f, "Standing Correlation (1947) – Bubble Point, Bo, Rs", [
            "Pb = 18.2 * [(Rs/γg)^0.83 * 10^a – 1.4]",
            "a = 0.00091*T – 0.0125*API",
            "Rs = γg * [(P/18.2 + 1.4) * 10^(–a)]^1.2048",
            "Bo = 0.9759 + 0.00012 * [Rs*(γg/γo)^0.5 + 1.25*T]^1.2",
            "RANGE: API 16.5-63.8, T 100-258°F, Pb 130-7000 psia",
            "REF: Standing, M.B. (1947). A Pressure-Volume-Temperature Correlation for Mixtures of California Oils and Gases",
        ])
        self._ref_card(f, "Vasquez-Beggs Correlation (1980) – Bo, Rs", [
            "γg_corr = γg * [1 + 5.912e-5 * API * Tsep * log10(Psep/114.7)]",
            "For API ≤ 30: Rs = 0.0362 * γg * P^1.0937 * exp[25.724 * API / (T+460)]",
            "For API > 30: Rs = 0.0178 * γg * P^1.187  * exp[23.931 * API / (T+460)]",
            "Bo = 1 + C1*Rs + C2*(T–60)*(API/γg) + C3*Rs*(T–60)*(API/γg)",
            "RANGE: API 15.3-59.5, T 75-294°F, P 15-6055 psia, Rs 0-2199 scf/STB",
            "REF: Vasquez, M. and Beggs, H.D. (1980). Correlations for Fluid Physical Property Prediction",
        ])
        self._ref_card(f, "Petrosky-Farshad Correlation (1993) – Gulf of Mexico Oils", [
            "X = 4.561e-5 * T^1.3911 – 7.916e-4 * API^1.541",
            "Pb = [112.727 * Rs^0.577421 / (γg^0.8439 * 10^X)]^1.7669",
            "Rs = [(Pb/112.727 * 10^X)^0.5657 * γg^0.8439]^1.7326",
            "Bo = 1.0113 + 7.2046e-5 * [Rs^0.3738 * (γg^0.2914/γo^0.6265) + 0.24626*T^0.5371]^3.0936",
            "RANGE: API 16.3-45, T 114-288°F, Pb 1574-6523 psia, Rs 217-1406 scf/STB",
            "REF: Petrosky, G.E. and Farshad, F.F. (1993). PVT Correlations for Gulf of Mexico Crude Oils",
        ])
        self._ref_card(f, "Beggs-Robinson Viscosity Correlation (1975)", [
            "Z = 3.0324 – 0.02023*API;  Y = 10^Z;  X = Y * T^(–1.163)",
            "μod = 10^X – 1   (dead oil)",
            "A = 10.715*(Rs+100)^(–0.515);  B = 5.44*(Rs+150)^(–0.338)",
            "μo = A * μod^B   (live / saturated oil)",
            "μo_unsat = μo_b * (P/Pb)^m;  m = 2.6*P^1.187*exp(–11.513–8.98e-5*P)",
            "RANGE: API 16-58, T 70-295°F, P 132-5265 psia",
            "REF: Beggs, H.D. and Robinson, J.R. (1975). Estimating the Viscosity of Crude Oil Systems",
        ])

    def _build_gas_ref(self, nb):
        f = self._scrollable_frame(nb, "Gas Correlations")
        self._ref_card(f, "Sutton Correlation (1985) – Pseudocritical Properties", [
            "Tpc = 169.2 + 349.5*γg – 74.0*γg²  (°R)",
            "Ppc = 756.8 – 131.07*γg – 3.6*γg²  (psia)",
            "RANGE: γg 0.57-1.68",
            "REF: Sutton, R.P. (1985). Compressibility Factors for High-Molecular-Weight Reservoir Gases",
        ])
        self._ref_card(f, "Wichert-Aziz Correction (1972) – Sour Gas", [
            "ε = 120*(A^0.9 – A^1.6) + 15*(B^0.5 – B^4)",
            "A = yH2S + yCO2  (mole fractions);  B = yH2S",
            "Tpc' = Tpc – ε",
            "Ppc' = Ppc * Tpc' / (Tpc + B*(1–B)*ε)",
            "REF: Wichert, E. and Aziz, K. (1972). Calculate Z's for Sour Gases",
        ])
        self._ref_card(f, "Dranchuk-Abou-Kassem Z-Factor (1975)", [
            "Z solved iteratively; ρr = 0.27*Pr/(Z*Tr)",
            "Z = 1 + (A1+A2/Tr+A3/Tr³+A4/Tr⁴+A5/Tr⁵)*ρr",
            "  + (A6+A7/Tr+A8/Tr²)*ρr² – A9*(A7/Tr+A8/Tr²)*ρr⁵",
            "  + A10*(1+A11*ρr²)*(ρr²/Tr³)*exp(–A11*ρr²)",
            "Constants: A1=0.3265, A2=–1.07, A3=–0.5339, A4=0.01569, A5=–0.05165",
            "           A6=0.5475, A7=–0.7361, A8=0.1844, A9=0.1056, A10=0.6134, A11=0.721",
            "RANGE: 0.2 ≤ Pr ≤ 30, 1.0 ≤ Tr ≤ 3.0",
            "REF: Dranchuk, P.M. and Abou-Kassem, J.H. (1975). Z Factors Calculation Using EOS",
        ])
        self._ref_card(f, "Hall-Yarborough Z-Factor (1973)", [
            "t = 1/Tr;  A = 0.06125*t*exp(–1.2*(1–t)²)",
            "Z = A*Pr/Y   where Y solved from F(Y)=0 by Newton-Raphson",
            "F(Y) = –A*Pr + (Y+Y²+Y³–Y⁴)/(1–Y)³",
            "       –(14.76t–9.76t²+4.58t³)*Y²",
            "       +(90.7t–242.2t²+42.4t³)*Y^(2.18+2.82t)",
            "RANGE: 0.1 ≤ Pr ≤ 24, Tr ≥ 1.0",
            "REF: Hall, K.R. and Yarborough, L. (1973). A New Equation of State for Z-Factor Calculations",
        ])
        self._ref_card(f, "Lee-Gonzalez-Eakin Gas Viscosity (1966)", [
            "μg = K * exp(X * ρg^Y) / 10000  (cp)",
            "K = (9.4+0.02M)*T^1.5 / (209+19M+T);  M = 28.967*γg",
            "X = 3.5 + 986/T + 0.01*M;  Y = 2.4 – 0.2*X",
            "ρg = P*M / (Z*10.73*T)  (lb/ft³, then /62.4 for g/cc)",
            "RANGE: T 100-340°F, P 100-8000 psia, γg 0.55-1.5",
            "REF: Lee, A.L., Gonzalez, M.H., and Eakin, B.E. (1966). The Viscosity of Natural Gases",
        ])

    def _build_water_ref(self, nb):
        f = self._scrollable_frame(nb, "Water Correlations")
        self._ref_card(f, "McCain Water FVF (1991)", [
            "Bw = (1 + dVwT) * (1 + dVwP)",
            "dVwT = –1.0001e-2 + 1.33391e-4*T + 5.50654e-7*T²",
            "dVwP = –1.95301e-9*P*T – 1.72834e-13*P²*T – 3.58922e-7*P – 2.25341e-10*P²",
            "Salinity correction applied via S (wt%)",
            "REF: McCain, W.D. (1991). Reservoir Fluid Property Correlations – State of the Art",
        ])
        self._ref_card(f, "Water Viscosity Correlation", [
            "A = 109.574 – 8.40564S + 0.313314S² + 8.72213e-3*S³",
            "B = –1.12166 + 2.63951e-2*S – 6.79461e-4*S² – 5.47119e-5*S³ + 1.55586e-6*S⁴",
            "μw_pure = A * T^B",
            "μw = μw_pure * (0.9994 + 4.0295e-5*P + 3.1062e-9*P²)",
            "RANGE: T 100-400°F, P 14.7-10000 psia, S 0-26 wt%",
        ])
        self._ref_card(f, "Water Compressibility (Osif, 1988)", [
            "cw = 1 / (7.033*P + 541.5*S – 537*T + 403300)  (psi⁻¹)",
            "S in g/L NaCl  (ppm ÷ 1000)",
            "RANGE: T 200-270°F, P 1000-20000 psia, S 0-200 g/L",
            "REF: Osif, T.L. (1988). Salt, Gas, Temp, and Pressure effects on Water Compressibility",
        ])
        self._ref_card(f, "Gas Solubility in Water (McCain, 1991)", [
            "A = 8.15839 – 6.12265e-2*T + 1.91663e-4*T² – 2.1654e-7*T³",
            "B = 1.01021e-2 – 7.44241e-5*T + 3.05553e-7*T² – 2.94883e-10*T³",
            "C = –1e-7*(9.02505–0.130237T+8.53425e-4*T²–2.34122e-6*T³+2.37049e-9*T⁴)",
            "Rsw_pure = A + B*P + C*P²",
            "Rsw = Rsw_pure * 10^(–0.0840655*S*T^(–0.285854))",
            "REF: McCain, W.D. (1991). Reservoir Fluid Property Correlations",
        ])


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    app = PVTCalculator()
    app.mainloop()
