"""FORGE-2026 desktop simulator.

Run with ``python forge_gui.py``. Requires customtkinter and matplotlib, and
``forge_decarb.py`` in the same directory.

UI settings are defined in the constants below. Basis fields are listed in
``BASIS_GROUPS``; calculations and model defaults live in ``forge_decarb.py``.
"""
from dataclasses import fields              # lets us loop over every field in Params automatically
import customtkinter as ctk                 # modern-looking widgets (buttons, sliders, tabs...)
import matplotlib                           # charting library
matplotlib.use("TkAgg")                     # tell matplotlib to draw inside a Tk window
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator   # puts commas in axis numbers (10,000 not 10000)
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from forge_decarb import Plant, Params      # the calculation engine (forge_decarb.py)

# ---------------------------------------------------------------------------
# CONSTANTS: colours, window size, picture location. Safe to edit.
# ---------------------------------------------------------------------------
# COLOUR SCHEME: restrained teal-green accent with neutral dashboard surfaces
GREEN, DARK, PALE = "#17796f", "#18332f", "#e8f4f1"   # accent teal-green, deep text, pale accent surface
APP_BG = "#f2f6f5"
SURFACE_BORDER = "#dce7e4"
GREY = "#40534f"        # darker secondary text for readable assumptions and notes
BTN_GREY = "#edf2f0"    # secondary button surface
TAB_BG = "white"        # background of the tab area (white makes the notes easy to read)
TAB_SEL = "#d9eee9"     # selected tab surface
ORANGE = "#b9582a"      # used for a lever whose net effect is negative (emissions increase)
RED = "#c3424d"         # border colour of a basis box that contains something that is not a number
WIN_W, WIN_H = 1240, 720      # fits a 1366x768 screen even with a side taskbar
FONT_FAMILY = "Segoe UI"      # modern, clean sans-serif closer to Claude's UI text
# FONT SIZES (points). Compact hierarchy, with emphasis reserved for key values.
F_LABEL = 12       # normal labels
F_NOTE = 10        # secondary notes
F_TABLE = 12       # results table text
F_HEAD = 14        # section headings
F_TITLE = 16       # big headings
F_BIG = 20         # big numbers on the MAC cards
F_VALUE = 14       # numbers on the Upgrading cost tab
F_TAB = 13         # primary tab buttons at the top
F_BANNER = 11      # recommendation banner
CH_TXT = 9         # chart text (matplotlib): labels, numbers on bars
CH_HEAD = 11       # chart titles and scope names

# The default value of every factor, read straight from the Params class.
# Example: DEFAULTS["grid_ef"] == 0.45.  Used by the Reset buttons and as a fallback
# when a box on the Basis tab contains something that is not a number.
DEFAULTS = {f.name: f.default for f in fields(Params)}

# ---------------------------------------------------------------------------
# BASIS TAB CONTENT
# ---------------------------------------------------------------------------
# Basic reaction shown at the top of the Basis tab.
EQUATIONS_TEXT = "0.88 CH₄ + 1.24 H₂O + 1.26 air → 2 NH₃ + 0.88 CO₂"

# Every factor in Params, grouped for display.
# Each row is: (name in Params, friendly label, unit, plain-English explanation)
# The "name in Params" MUST match forge_decarb.py exactly. To add a new factor:
#   1) add it to the Params class in forge_decarb.py, 2) add a row here. That's all.
BASIS_GROUPS = [
    ("1. Plant and process (Scope 1)", [
        ("capacity", "Ammonia capacity", "t NH3/yr",
         "Yearly ammonia output. Same box as on the left panel (they stay in sync)."),
        ("urea_share", "Urea share of NH3", "fraction 0-1",
         "Part of the ammonia turned into urea. Urea locks up CO2. 0 shows the gross CO2."),
        ("process_ef", "SMR process CO2 factor", "t CO2 / t NH3",
         "CO2 released by the steam-methane-reforming reaction itself."),
        ("combustion_ef", "Gas combustion CO2 factor", "t CO2 / t NH3",
         "CO2 from burning natural gas in reformers and boilers."),
        ("stoich_process_ef", "Stoichiometric CO2 factor", "t CO2 / t NH3",
         "Ideal textbook value. Only used for the reference row in the table."),
        ("combustion_h2_share", "Combustion tied to H2 production", "fraction 0-1",
         "How much combustion CO2 falls when green H2 replaces SMR H2 (1.0 = all of it)."),
    ]),
    ("2. Electricity and supply chain (Scope 2 and 3)", [
        ("power_mwh", "Plant electricity use", "MWh / t NH3",
         "Grid power the existing plant needs per tonne of ammonia."),
        ("grid_ef", "Grid emissions factor", "t CO2 / MWh",
         "CO2 released per MWh of grid electricity."),
        ("logistics_ef", "Logistics CO2 factor", "t CO2 / t NH3",
         "CO2 from shipping one tonne of ammonia (Scope 3)."),
    ]),
    ("3. Green hydrogen and electrolyzer", [
        ("h2_demand_ef", "H2 needed per t NH3", "t H2 / t NH3",
         "From the reaction 3H2 + N2 -> 2NH3 (6/34)."),
        ("ro_water_ef", "RO water per kg H2", "kg water / kg H2",
         "Water for electrolysis: 9 kg stoichiometric plus reverse-osmosis reject losses."),
        ("electrolysis_kwh_per_kg", "Electrolyzer energy use", "kWh / kg H2",
         "Electricity needed to make 1 kg of green hydrogen."),
        ("electrolyzer_operating_hours", "Electrolyzer running hours", "hours/day",
         "24 = runs non-stop. Sets the kW rating needed to reach the yearly H2 target."),
        ("electrolyzer_cost_per_kw", "Electrolyzer installed cost", "PKR / kW",
         "Turnkey price of the electrolyzer per kW of rating."),
    ]),
    ("4. Abatement costs (used for the MAC ranking)", [
        ("h2_cost", "Green H2 blending", "PKR / t CO2 avoided",
         "Cost of avoiding one tonne of CO2 with green hydrogen."),
        ("solar_cost", "Solar PV", "PKR / t CO2 avoided",
         "Cost of avoiding one tonne of CO2 with solar panels."),
        ("heat_recovery_cost", "Waste-heat recovery", "PKR / t CO2 avoided",
         "Cost of avoiding one tonne of CO2 by recovering heat from flue gas."),
    ]),
    ("5. Solar PV sizing (no battery, daylight only)", [
        ("daylight_cap", "Max solar share without storage", "fraction 0-1",
         "Highest share of a round-the-clock load that solar can cover without batteries."),
        ("daylight_hours", "Effective daylight hours", "hours/day",
         "Hours per day the panels produce usable power."),
        ("performance_ratio", "System performance ratio", "fraction 0-1",
         "Losses from heat, wiring, inverter and dust (0.80 = 20% lost)."),
        ("panel_watt", "Panel rating", "W per panel",
         "Size of one solar panel."),
        ("cost_per_watt_pkr", "Installed solar cost", "PKR / W",
         "Turnkey installed price per watt of solar."),
        ("land_acres_per_mw", "Land needed", "acres / MW",
         "Land used per MW of solar installed."),
    ]),
    ("6. Feedstock (raw materials, used by the Feedstock tab)", [
        ("ch4_co2_ratio", "CO2 per tonne of natural gas", "t CO2 / t CH4",
         "CO2 released per tonne of methane reformed or burned (44.01/16.043). Gas t = CO2 t / this."),
        ("process_water_ef", "Process water per t NH3", "t water / t NH3",
         "Water used in reforming and shift reactions (1.24 H2O per 2 NH3)."),
        ("n2_ef", "Nitrogen per t NH3", "t N2 / t NH3",
         "From N2 + 3H2 -> 2NH3 (28/34). Same for every plant, shown for completeness."),
    ]),
]


# Rows of the Feedstock tab. ("#", title) = a section heading.
# Other rows: (label, unit, key from Plant.feedstock() in forge_decarb.py, is_bold)
FEED_ROWS = [
    ("#", "RAW MATERIALS IN"),
    ("Natural gas - reforming feedstock", "t/yr", "ch4_feed", False),
    ("Natural gas - fuel (furnaces, boilers)", "t/yr", "ch4_fuel", False),
    ("Natural gas - total", "t/yr", "ch4_total", True),
    ("Process water (reforming / shift)", "t/yr", "water_process", False),
    ("RO water for electrolysis", "m3/yr", "water_ro", False),
    ("Nitrogen (N2, from air)", "t/yr", "n2", False),
    ("Green hydrogen (electrolysis)", "t/yr", "h2_green", False),
    ("Electricity (plant + electrolyzer)", "MWh/yr", "elec_mwh", True),
    ("#", "PRODUCTS OUT"),
    ("Ammonia produced", "t/yr", "nh3_made", False),
    ("   of which used to make urea", "t/yr", "nh3_to_urea", False),
    ("Ammonia sold as NH3", "t/yr", "nh3_sold", True),
    ("Urea produced", "t/yr", "urea", True),
    ("CO2 locked into urea", "t/yr", "co2_in_urea", False),
]
FEED_NOTE = ("Natural gas is worked out from the model's CO2 numbers (assumes pure methane): "
             "gas = CO2 / 2.743. Green H2 replaces SMR hydrogen, so it lowers reforming gas, furnace gas "
             "and process water, but adds RO water and electricity. Factors are on the Basis tab (group 6).")


def fmt_num(v):
    """Turn a number into clean text for a box: 200000.0 -> '200000', 0.45 -> '0.45'.
    Full precision is kept so values like 6/34 are not rounded when read back."""
    v = float(v)
    return str(int(v)) if v == int(v) else repr(v)


class App(ctk.CTk):
    """The main window. Everything on screen is created in __init__ (once),
    then update_all() refreshes the numbers/charts whenever something changes."""

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("FORGE-2026 | Ammonia & Urea Decarbonization Simulator")
        self.geometry(f"{WIN_W}x{WIN_H}+8+8")   # +8+8 = open near the top-left corner
        self.resizable(False, False)
        self.configure(fg_color=APP_BG)
        self._solar_max = 0                      # remembers the solar slider's maximum between updates
        self.basis = {}                          # name in Params -> the editable box on the Basis tab
        self.columnconfigure(1, weight=1)        # right panel stretches
        self.rowconfigure(0, weight=1)
        self._inputs()                           # build left panel (sliders and boxes)
        self._outputs()                          # build right panel (tabs, charts, tables)
        self.update_all()                        # first calculation so the screen isn't empty

    # ---------- left panel: inputs ----------
    def _inputs(self):
        f = ctk.CTkFrame(self, fg_color="white", corner_radius=14, width=290,
                         border_width=1, border_color=SURFACE_BORDER)
        f.grid(row=0, column=0, sticky="ns", padx=12, pady=12)
        ctk.CTkLabel(
            f,
            text="Created by Mariam Masood · mariam.masood30@gmail.com",
            font=("Segoe UI", F_NOTE - 1),
            text_color=GREY,
            wraplength=250,
            justify="center",
        ).pack(side="bottom", padx=12, pady=(6, 12))
        ctk.CTkLabel(f, text="Model inputs", font=("Segoe UI", F_TITLE, "bold"),
                     text_color=DARK).pack(anchor="w", padx=16, pady=(14, 10))

        # Capacity box. Pressing Enter or clicking away runs update_all().
        ctk.CTkLabel(f, text="Ammonia capacity (t NH3/yr)", font=("Segoe UI", F_LABEL, "bold")).pack(anchor="w", padx=16)
        self.cap = ctk.CTkEntry(f, width=240, font=("Segoe UI", F_LABEL), border_width=1,
                                border_color=SURFACE_BORDER, fg_color="#fbfcfc")
        self.cap.insert(0, "200000")
        self.cap.pack(padx=16, pady=(2, 8))
        self.cap.bind("<Return>", self.update_all)
        self.cap.bind("<FocusOut>", self.update_all)

        # Urea share box (typed here as a PERCENT; the Basis tab shows it as a 0-1 fraction)
        ctk.CTkLabel(f, text="Urea share of NH3 (%)  (0 = gross CO2)", font=("Segoe UI", F_LABEL, "bold")).pack(anchor="w", padx=16)
        self.urea = ctk.CTkEntry(f, width=240, font=("Segoe UI", F_LABEL), border_width=1,
                                 border_color=SURFACE_BORDER, fg_color="#fbfcfc")
        self.urea.insert(0, "50")
        self.urea.pack(padx=16, pady=(2, 8))
        self.urea.bind("<Return>", self.update_all)
        self.urea.bind("<FocusOut>", self.update_all)

        # --- Green hydrogen lever ---
        self.h2, self.h2_lbl = self._slider(f, "Green hydrogen blending", to=10)
        self.h2o_lbl = ctk.CTkLabel(f, text="Green H2: 0 t/yr  |  RO water: 0 m3/yr",
                                    font=("Segoe UI", F_NOTE), text_color=GREY, wraplength=250, justify="left")
        self.h2o_lbl.pack(anchor="w", padx=16, pady=(0, 2))
        self.h2e_lbl = ctk.CTkLabel(f, text="Electrolysis electricity: 0 MWh/yr",
                                    font=("Segoe UI", F_NOTE), text_color=GREY, wraplength=250, justify="left")
        self.h2e_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        # --- Heat recovery lever (Scope 1a combustion) ---
        self.hr, self.hr_lbl = self._slider(f, "Heat recovery (combustion)", to=90)
        self.hr_effect_lbl = ctk.CTkLabel(f, text="Combustion CO2: - t/yr",
                                          font=("Segoe UI", F_NOTE), text_color=GREY, wraplength=250, justify="left")
        self.hr_effect_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        # Two lines: plant-only load (fixed) and combined plant + electrolyzer load (grows with H2)
        self.elec_lbl = ctk.CTkLabel(f, text="Plant only: - kWh/day (fixed)\nPlant + electrolyzer: - kWh/day",
                                     font=("Segoe UI", F_NOTE + 1, "bold"), text_color=DARK, wraplength=250, justify="left")
        self.elec_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        # --- Solar lever (slider is in kWh/day; its maximum is set inside update_all) ---
        self.solar, self.solar_lbl = self._slider(f, "Solar PV (kWh/day)", to=1000, is_solar=True)
        ctk.CTkLabel(f, text="Solar available in daylight only (~9 h); slider capped at the max "
                     "deliverable (plant + electrolyzer) without battery storage.", font=("Segoe UI", F_NOTE),
                     text_color=GREY, wraplength=250, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        # Run and Reset side by side (saves vertical space so the bigger fonts still fit)
        btns = ctk.CTkFrame(f, fg_color="transparent")
        btns.pack(pady=(10, 8))
        ctk.CTkButton(btns, text="Run model", width=115, font=("Segoe UI", F_LABEL, "bold"), fg_color=GREEN,
                      hover_color=DARK, corner_radius=8, command=self.update_all).pack(side="left", padx=5)
        ctk.CTkButton(btns, text="Reset", width=115, font=("Segoe UI", F_LABEL, "bold"), fg_color=BTN_GREY,
                      hover_color=SURFACE_BORDER, text_color=DARK, corner_radius=8,
                      command=self.reset).pack(side="left", padx=5)

    def _slider(self, parent, text, to=100, is_solar=False):
        """Helper: makes a label + slider pair. Every move of the slider calls update_all()."""
        lbl = ctk.CTkLabel(parent, text=f"{text}: 0", font=("Segoe UI", F_LABEL, "bold"))
        lbl.pack(anchor="w", padx=16)
        s = ctk.CTkSlider(parent, from_=0, to=to, number_of_steps=100, width=240,
                          progress_color=GREEN, button_color=GREEN, button_hover_color=DARK,
                          command=lambda _: self.update_all())
        s.set(0)
        s.pack(padx=16, pady=(2, 8))
        s.text, s.is_solar = text, is_solar
        return s, lbl

    def reset(self):
        """Left-panel Reset: sliders to 0, and ALL basis factors back to their defaults."""
        self.h2.set(0)
        self.hr.set(0)
        self.solar.set(0)
        self._reset_basis(refresh=False)         # restores every basis box (including capacity and urea share)
        self.cap.delete(0, "end")
        self.cap.insert(0, fmt_num(DEFAULTS["capacity"]))
        self.urea.delete(0, "end")
        self.urea.insert(0, fmt_num(DEFAULTS["urea_share"] * 100))
        self.update_all()

    # ---------- right panel: outputs ----------
    def _outputs(self):
        f = ctk.CTkFrame(self, fg_color="white", corner_radius=14,
                         border_width=1, border_color=SURFACE_BORDER)
        f.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        # Tab strip: the strip's own background is white (same as the page) so no grey bar shows.
        # Unselected tabs are white with dark text; the selected tab is light green with dark text.
        self.tabs = ctk.CTkTabview(f, fg_color=TAB_BG, corner_radius=10, border_width=0,
                                   segmented_button_fg_color=TAB_BG,              # strip background = white (no grey strip)
                                   segmented_button_selected_color=TAB_SEL,       # selected tab
                                   segmented_button_selected_hover_color=TAB_SEL,
                                   segmented_button_unselected_color=TAB_BG,      # other tabs
                                   segmented_button_unselected_hover_color=PALE,  # when the mouse is over a tab
                                   text_color=DARK)                               # tab text colour
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        # Each add() creates a tab. The order here is the order on screen.
        self.t_feed = self.tabs.add("Feedstock")                 # NEW: first tab
        self.t_table = self.tabs.add("Scope 1-3 table")
        self.t_streams = self.tabs.add("Scope diagram")
        self.t_mac = self.tabs.add("MAC curve")
        self.t_solar = self.tabs.add("Upgrading cost")
        self.t_basis = self.tabs.add("Basis & equations")
        try:                                                     # bigger tab buttons (reads from far away)
            self.tabs._segmented_button.configure(font=("Segoe UI", F_TAB, "bold"), height=34)
        except Exception:
            pass                                                 # if customtkinter changes, the tabs just stay small

        ctk.CTkLabel(self.t_table, text="CO2 emissions", font=("Segoe UI", F_TITLE, "bold"),
                     text_color=DARK, anchor="w").pack(fill="x", padx=8, pady=(5, 2))
        self.table_body = ctk.CTkFrame(self.t_table, fg_color="transparent")
        self.table_body.pack(fill="both", expand=True)

        streams_panel = ctk.CTkFrame(self.t_streams, fg_color="transparent")
        streams_panel.pack(fill="both", expand=True)
        ctk.CTkLabel(streams_panel, text="CO2 emissions by scope", font=("Segoe UI", F_TITLE, "bold"),
                     text_color=DARK, anchor="w").pack(fill="x", padx=8, pady=(5, 0))
        self.fig_s, self.ax_s, self.cv_s = self._chart(streams_panel)
        self._feed_tab()
        self._mac_tab()
        self._upgrade_tab()
        self._basis_tab()
        # Green recommendation banner under the tabs
        self.rec = ctk.CTkLabel(f, text="", wraplength=800, justify="left", text_color=DARK,
                                font=("Segoe UI", F_BANNER, "bold"), fg_color=PALE, corner_radius=9)
        self.rec.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10), ipady=8)

    # ---------- Basis & equations tab ----------
    def _basis_tab(self):
        """One scrolling page. Top row: title + reset button. Then the equations, then every factor
        from Params in an editable box. Type a number and press Enter (or click away): the model recalculates."""
        hint = ctk.CTkFrame(self.t_basis, fg_color="transparent")
        hint.pack(fill="x", padx=6, pady=(2, 2))
        ctk.CTkLabel(hint, text="Basis factors (editable) - press Enter to apply",
                     font=("Segoe UI", F_HEAD, "bold"), text_color=DARK).pack(side="left")
        ctk.CTkButton(hint, text="Reset basis to defaults", width=180, font=("Segoe UI", F_LABEL, "bold"),
                      fg_color=BTN_GREY, hover_color=SURFACE_BORDER, text_color=DARK, corner_radius=8,
                      command=self._reset_basis).pack(side="right")

        body = ctk.CTkScrollableFrame(self.t_basis, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=2, pady=(2, 0))
        body.columnconfigure(3, weight=1)           # the explanation column takes the spare width

        # Simple process equation at the top of the Basis tab, without the large explanatory box.
        eq = ctk.CTkLabel(body, text=EQUATIONS_TEXT, font=("Segoe UI", 20, "bold"), text_color=DARK,
                          justify="left", anchor="w")
        eq.grid(row=0, column=0, columnspan=4, sticky="ew", padx=6, pady=(0, 10))

        r = 1                                        # r = the grid row we are currently filling
        for group_name, rows in BASIS_GROUPS:
            ctk.CTkLabel(body, text=group_name, font=("Segoe UI", F_HEAD - 1, "bold"), text_color="white",
                         fg_color=GREEN, corner_radius=6, anchor="w").grid(
                row=r, column=0, columnspan=4, sticky="ew", padx=2, pady=(10, 4), ipady=3, ipadx=6)
            r += 1
            for key, label, unit, note in rows:
                ctk.CTkLabel(body, text=label, anchor="w", width=210, font=("Segoe UI", F_LABEL)).grid(
                    row=r, column=0, sticky="w", padx=(6, 4), pady=3)
                entry = ctk.CTkEntry(body, width=115, justify="right", font=("Segoe UI", F_LABEL, "bold"),
                                     border_width=1, border_color=SURFACE_BORDER, fg_color="#fbfcfc")
                entry.insert(0, fmt_num(DEFAULTS[key]))
                entry.grid(row=r, column=1, padx=4, pady=3)
                entry._normal_border = entry.cget("border_color")   # remembered so we can undo the red border
                # When the user finishes typing, apply the change (sync + recalculate)
                entry.bind("<Return>", lambda e, k=key: self._basis_edited(k))
                entry.bind("<FocusOut>", lambda e, k=key: self._basis_edited(k))
                ctk.CTkLabel(body, text=unit, anchor="w", width=135, font=("Segoe UI", F_NOTE + 1),
                             text_color=DARK).grid(row=r, column=2, sticky="w", padx=4)
                ctk.CTkLabel(body, text=note, anchor="w", justify="left", wraplength=290,
                             font=("Segoe UI", F_NOTE), text_color=GREY).grid(row=r, column=3, sticky="w", padx=4)
                self.basis[key] = entry
                r += 1

    def _basis_values(self):
        """Read every basis box and return {name: number}. A box that does not hold a valid
        number falls back to its default and gets a red border so you can spot it."""
        values = {}
        for key, entry in self.basis.items():
            try:
                values[key] = float(entry.get().replace(",", ""))
                entry.configure(border_color=entry._normal_border)
            except ValueError:
                values[key] = DEFAULTS[key]
                entry.configure(border_color=RED)
        return values

    def _set_basis(self, key, value):
        """Write a number into a basis box, but only if it changed (avoids needless redraws)."""
        entry = self.basis[key]
        try:
            if float(entry.get().replace(",", "")) == float(value):
                return
        except ValueError:
            pass                                    # box held junk: overwrite it below
        entry.delete(0, "end")
        entry.insert(0, fmt_num(value))
        entry.configure(border_color=entry._normal_border)

    def _basis_edited(self, key):
        """Called when a basis box is committed. Capacity and urea share also live on the
        left panel, so copy the new value there first, then recalculate everything."""
        vals = self._basis_values()
        if key == "capacity":
            self.cap.delete(0, "end")
            self.cap.insert(0, fmt_num(vals["capacity"]))
        elif key == "urea_share":
            self.urea.delete(0, "end")
            self.urea.insert(0, fmt_num(min(max(vals["urea_share"], 0.0), 1.0) * 100))   # fraction -> percent
        self.update_all()

    def _reset_basis(self, refresh=True):
        """Put every basis box back to the default value defined in Params."""
        for key, entry in self.basis.items():
            entry.delete(0, "end")
            entry.insert(0, fmt_num(DEFAULTS[key]))
            entry.configure(border_color=entry._normal_border)
        if refresh:
            self.cap.delete(0, "end")
            self.cap.insert(0, fmt_num(DEFAULTS["capacity"]))
            self.urea.delete(0, "end")
            self.urea.insert(0, fmt_num(DEFAULTS["urea_share"] * 100))
            self.update_all()

    # ---------- MAC tab ----------
    def _mac_tab(self):
        """MAC tab: horizontal bars of each lever's per-tonne cost on the left,
        stacked stat cards with the CO2 each lever avoids (and its annual cost) on the right."""
        self.t_mac.columnconfigure(0, weight=3)
        self.t_mac.columnconfigure(1, weight=2)
        self.t_mac.rowconfigure(0, weight=1)

        chart_frame = ctk.CTkFrame(self.t_mac, fg_color="transparent")
        chart_frame.grid(row=0, column=0, sticky="nsew")
        self.fig_m, self.ax_m, self.cv_m = self._chart(chart_frame)
        ctk.CTkLabel(chart_frame, text="*Green H2's listed cost assumes clean electrolyzer power.",
                     font=("Segoe UI", F_NOTE, "italic"), text_color=GREY).pack(side="bottom", pady=(0, 4))

        cards_frame = ctk.CTkFrame(self.t_mac, fg_color="transparent")
        cards_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 10), pady=10)

        # One card per lever: a small title (sub) and a big number (val). Text is filled in _draw_mac.
        self._mac_cards = {}
        for key in ("solar", "heat_recovery", "h2"):
            card = ctk.CTkFrame(cards_frame, fg_color=PALE, corner_radius=12,
                                border_width=1, border_color=SURFACE_BORDER)
            card.pack(fill="x", pady=(0, 14), ipady=6)
            sub = ctk.CTkLabel(card, text="", font=("Segoe UI", F_LABEL, "bold"), text_color=DARK,
                                wraplength=245, justify="left", anchor="w")
            sub.pack(fill="x", padx=14, pady=(10, 2))
            val = ctk.CTkLabel(card, text="", font=("Segoe UI", F_BIG, "bold"), text_color=GREEN, anchor="w")
            val.pack(fill="x", padx=14, pady=(0, 10))
            self._mac_cards[key] = (sub, val)

    # ---------- Upgrading cost tab ----------
    def _upgrade_tab(self):
        """4th tab: capital cost of the two physical upgrades -- solar and the electrolyzer."""
        ctk.CTkLabel(self.t_solar, text="Solar cost", font=("Segoe UI", F_TITLE, "bold"),
                     text_color=DARK, anchor="w").pack(fill="x", padx=6, pady=(8, 2))
        self.solar_note = ctk.CTkLabel(self.t_solar, text="", font=("Segoe UI", F_LABEL), text_color=DARK,
                                       fg_color=PALE, corner_radius=8, justify="left", wraplength=780, anchor="w")
        self.solar_note.pack(fill="x", padx=6, pady=(0, 8), ipady=8, ipadx=10)
        self.solar_rows = ctk.CTkFrame(self.t_solar, fg_color="transparent")
        self.solar_rows.pack(fill="x", padx=6)
        self.solar_rows.columnconfigure(0, weight=2)
        self.solar_rows.columnconfigure(1, weight=1)
        self._solar_labels = []                 # the right-hand value labels, filled in _draw_upgrade
        self._solar_names = []                  # the left-hand name labels (the panels one changes with panel_watt)
        for i, label in enumerate(["System size needed", "Number of panels",
                                    "Land required", "Estimated installed cost (PKR million)"]):
            name = ctk.CTkLabel(self.solar_rows, text=label, anchor="w", font=("Segoe UI", F_HEAD))
            name.grid(row=i, column=0, sticky="ew", pady=6)
            val = ctk.CTkLabel(self.solar_rows, text="-", anchor="e", font=("Segoe UI", F_VALUE, "bold"), text_color=DARK)
            val.grid(row=i, column=1, sticky="ew", pady=6)
            self._solar_names.append(name)
            self._solar_labels.append(val)
        # This note is rewritten in _draw_upgrade so it always shows the current basis values
        self.solar_assump = ctk.CTkLabel(self.t_solar, text="", font=("Segoe UI", F_NOTE), text_color=GREY,
                                         wraplength=780, justify="left")
        self.solar_assump.pack(anchor="w", padx=6, pady=(10, 18))

        ctk.CTkLabel(self.t_solar, text="Green H2", font=("Segoe UI", F_TITLE, "bold"),
                     text_color=DARK, anchor="w").pack(fill="x", padx=6, pady=(2, 2))
        self.h2_rows = ctk.CTkFrame(self.t_solar, fg_color="transparent")
        self.h2_rows.pack(fill="x", padx=6)
        self.h2_rows.columnconfigure(0, weight=2)
        self.h2_rows.columnconfigure(1, weight=1)
        self._h2_labels = []
        for i, label in enumerate(["Electrolyzer size needed", "Estimated installed cost (PKR million)"]):
            ctk.CTkLabel(self.h2_rows, text=label, anchor="w", font=("Segoe UI", F_HEAD)).grid(row=i, column=0, sticky="ew", pady=6)
            val = ctk.CTkLabel(self.h2_rows, text="-", anchor="e", font=("Segoe UI", F_VALUE, "bold"), text_color=DARK)
            val.grid(row=i, column=1, sticky="ew", pady=6)
            self._h2_labels.append(val)
        self.h2_assump = ctk.CTkLabel(self.t_solar, text="", font=("Segoe UI", F_NOTE), text_color=GREY,
                                      wraplength=780, justify="left")
        self.h2_assump.pack(anchor="w", padx=6, pady=(10, 0))

    def _draw_upgrade(self, plant, h2, sol, elec_kw, elec_cost):
        """Fill the Upgrading cost tab with numbers for the current settings."""
        p = plant.p                                           # the Params (basis values) in use
        d = plant.solar_sizing(h2, sol)
        max_kwh_day = d["total_kwh_day"] * p.daylight_cap
        msg = (f"Combined electricity need (plant + electrolyzer) is {d['total_kwh_day']:,.0f} kWh/day. "
               f"You've selected {d['need_kwh_day']:,.0f} kWh/day from solar (~{d['achievable']*100:.0f}% "
               f"of demand). Without battery storage, solar (daylight only, ~{p.daylight_hours:g} h) can cover at most "
               f"~{p.daylight_cap*100:.0f}% of a round-the-clock load — about {max_kwh_day:,.0f} "
               f"kWh/day here. Whatever isn't covered still comes from the grid.")
        self.solar_note.configure(text=msg)
        self._solar_names[1].configure(text=f"Number of panels ({p.panel_watt:g} W each)")
        vals = [f"{d['system_kwp']:,.0f} kWp", f"{d['panels']:,.0f} panels",
                f"{d['land_acres']:,.1f} acres", f"PKR {d['cost_pkr'] / 1e6:,.1f} million"]
        for lbl, v in zip(self._solar_labels, vals):
            lbl.configure(text=v)

        h2_vals = [f"{elec_kw:,.0f} kW", f"PKR {elec_cost / 1e6:,.1f} million"]
        for lbl, v in zip(self._h2_labels, h2_vals):
            lbl.configure(text=v)

        self.solar_assump.configure(
            text=f"Assumptions: {p.daylight_hours:g} effective daylight hours/day, "
                 f"{p.performance_ratio*100:.0f}% system performance ratio, PKR {p.cost_per_watt_pkr:g}/W installed, "
                 f"{p.panel_watt:g} W panels, {p.land_acres_per_mw:g} acres/MW land, no battery -> solar capped "
                 f"at {p.daylight_cap*100:.0f}% of round-the-clock combined (plant + electrolyzer) load. "
                 f"Editable in the Basis & equations tab.")
        self.h2_assump.configure(
            text=f"Assumptions: electrolyzer runs {p.electrolyzer_operating_hours:g} h/day, so it draws grid power "
                 f"whenever solar isn't available (e.g. at night). Installed cost taken at "
                 f"PKR {p.electrolyzer_cost_per_kw:,.0f}/kW. Editable in the Basis & equations tab.")

    def _chart(self, parent):
        """Helper: makes an empty matplotlib chart inside 'parent' and returns (figure, axes, canvas)."""
        fig = Figure(figsize=(7, 4.6), dpi=100, facecolor="white")
        ax = fig.add_subplot(111)
        ax.set_facecolor("white")
        matplotlib.rcParams["font.family"] = FONT_FAMILY
        cv = FigureCanvasTkAgg(fig, master=parent)
        cv.get_tk_widget().pack(fill="both", expand=True)
        return fig, ax, cv

    # ---------- refresh ----------
    def update_all(self, *_):
        """The heart of the GUI. Runs on every slider move / box edit:
        read inputs -> build a Plant -> recalculate -> redraw every tab."""
        # 1) Read the left-panel boxes (fall back to defaults if the text is not a number)
        try:
            cap = float(self.cap.get().replace(",", ""))
        except ValueError:
            cap = DEFAULTS["capacity"]
        try:
            urea_share = min(max(float(self.urea.get().replace(",", "")) / 100, 0.0), 1.0)   # % -> fraction
        except ValueError:
            urea_share = DEFAULTS["urea_share"]

        # 2) Keep the Basis tab in sync with the left panel
        self._set_basis("capacity", cap)
        self._set_basis("urea_share", urea_share)

        # 3) Build the Plant from ALL basis values; capacity and urea share come from the left panel
        params = self._basis_values()
        params["capacity"], params["urea_share"] = cap, urea_share
        plant = Plant(Params(**params))

        h2 = self.h2.get() / 100                      # slider 0-10 -> fraction 0-0.10
        heat_recovery = self.hr.get() / 100            # slider 0-90 -> fraction 0-0.90

        # 4) Solar slider's achievable range depends on the COMBINED load (plant + electrolyzer)
        plant_kwh_day = plant.total_electricity_kwh_day()
        _, elec_kwh_day = plant.h2_electricity(h2)
        combined_kwh_day = plant_kwh_day + elec_kwh_day
        solar_max = plant.p.daylight_cap * combined_kwh_day

        if abs(getattr(self, "_solar_max", -1) - solar_max) > 1:
            self._solar_max = solar_max
            self.solar.configure(to=max(solar_max, 1))     # max() stops the slider breaking if the max is 0
            if self.solar.get() > solar_max:
                self.solar.set(solar_max)

        sol_kwh = self.solar.get()                                  # slider is kWh/day directly
        sol = sol_kwh / combined_kwh_day if combined_kwh_day else 0.0   # convert to a 0-1 share

        # 5) Update the labels on the left panel
        self.h2_lbl.configure(text=f"Green hydrogen blending: {h2 * 100:.1f} %")
        self.hr_lbl.configure(text=f"Heat recovery (combustion): {heat_recovery * 100:.0f} %")
        self.solar_lbl.configure(text=f"Solar PV: {sol_kwh:,.0f} kWh/day")
        # Plant-only load never changes with H2; the combined load (plant + electrolyzer) does
        self.elec_lbl.configure(text=f"Plant only: {plant_kwh_day:,.0f} kWh/day (fixed)\n"
                                     f"Plant + electrolyzer: {combined_kwh_day:,.0f} kWh/day")

        h2_mass, ro_water = plant.h2_water(h2)
        h2_elec_mwh, h2_elec_kwh_day = plant.h2_electricity(h2)
        elec_kw = plant.electrolyzer_size_kw(h2)
        elec_cost = plant.electrolyzer_cost(h2)

        # 6) Redraw every tab
        rows = plant.table(h2, sol, heat_recovery)
        rows.append(("Green H2 required (t/yr)", "-", f"{h2_mass:,.0f}", "-", "-"))
        rows.append(("RO water required (m3/yr)", "-", f"{ro_water:,.0f}", "-", "-"))
        rows.append(("Electrolysis electricity required (MWh/yr)", "-", f"{h2_elec_mwh:,.0f}", "-", "-"))
        self._draw_feed(plant, h2, heat_recovery)
        self._draw_table(rows)
        self._draw_diagram(plant, h2, sol, heat_recovery)
        self._draw_mac(plant, h2, sol, heat_recovery)
        self._draw_upgrade(plant, h2, sol, elec_kw, elec_cost)
        self.rec.configure(text=plant.recommend(h2, sol, heat_recovery))
        self.h2o_lbl.configure(text=f"Green H2: {h2_mass:,.0f} t/yr  |  RO water: {ro_water:,.0f} m3/yr")
        self.h2e_lbl.configure(text=f"Electrolysis electricity: {h2_elec_mwh:,.0f} MWh/yr "
                                    f"({h2_elec_kwh_day:,.0f} kWh/day)")

        combustion_before = plant.streams()["combustion"]
        combustion_after = plant.streams(h2, sol, heat_recovery)["combustion"]
        self.hr_effect_lbl.configure(
            text=f"Combustion CO2: {combustion_before:,.0f} -> {combustion_after:,.0f} t/yr "
                 f"({combustion_before - combustion_after:,.0f} avoided)")

    # ---------- Feedstock tab ----------
    def _feed_tab(self):
        """First tab: raw materials the plant uses and products it makes. The note goes at the
        bottom (packed first so it is never squeezed out), the scrolling table fills the rest."""
        ctk.CTkLabel(self.t_feed, text=FEED_NOTE, font=("Segoe UI", F_NOTE), text_color=GREY,
                     wraplength=800, justify="left", anchor="w").pack(side="bottom", fill="x", padx=8, pady=(4, 2))
        self.feed_body = ctk.CTkScrollableFrame(self.t_feed, fg_color="transparent")
        self.feed_body.pack(fill="both", expand=True)

    def _draw_feed(self, plant, h2, heat_recovery):
        """Rebuild the feedstock table: without levers vs with the current slider settings.
        In the RAW MATERIALS section a fall is green (less to buy) and a rise is orange."""
        for w in self.feed_body.winfo_children():
            w.destroy()
        a = plant.feedstock()                         # without levers
        b = plant.feedstock(h2, heat_recovery)        # with levers
        heads = ["Raw material in / product out", "Without", "With", "Change"]
        for c, h in enumerate(heads):
            ctk.CTkLabel(self.feed_body, text=h, font=("Segoe UI", F_TABLE, "bold"), text_color="white",
                         fg_color=GREEN, corner_radius=4).grid(row=0, column=c, sticky="ew", padx=2, pady=2, ipady=4)
        r, in_inputs = 1, True
        for item in FEED_ROWS:
            if item[0] == "#":                         # section heading row
                in_inputs = item[1].startswith("RAW")
                ctk.CTkLabel(self.feed_body, text=item[1], font=("Segoe UI", F_TABLE, "bold"), text_color=DARK,
                             fg_color=TAB_SEL, anchor="w", corner_radius=4).grid(
                    row=r, column=0, columnspan=4, sticky="ew", padx=2, pady=(8, 2), ipady=3, ipadx=6)
                r += 1
                continue
            label, unit, key, bold = item
            x, y = a[key], b[key]
            if x == 0 and y == 0:
                change, color = "-", DARK
            elif x == 0:
                change, color = "new", ORANGE if in_inputs else DARK
            else:
                pct = (y - x) / x * 100
                change = f"{pct:+.1f} %"
                color = DARK if abs(pct) < 0.05 or not in_inputs else (GREEN if pct < 0 else ORANGE)
            row_bg = PALE if bold else "transparent"
            item_cell = ctk.CTkFrame(self.feed_body, fg_color=row_bg, corner_radius=0)
            item_cell.grid(row=r, column=0, sticky="ew", padx=2, pady=1, ipady=2)
            ctk.CTkLabel(item_cell, text=label, anchor="w", text_color=DARK,
                         font=("Segoe UI", F_TABLE, "bold" if bold else "normal"),
                         fg_color="transparent").pack(side="left", padx=(0, 6))
            ctk.CTkLabel(item_cell, text=unit, anchor="e", text_color=GREY,
                         font=("Segoe UI", F_NOTE, "bold" if bold else "normal"),
                         fg_color="transparent").pack(side="right", padx=(6, 2))
            for c, v in enumerate((f"{x:,.0f}", f"{y:,.0f}", change), start=1):
                ctk.CTkLabel(self.feed_body, text=v, anchor="e",
                             text_color=color if c == 3 else DARK,
                             font=("Segoe UI", F_TABLE, "bold" if bold else "normal"),
                             fg_color=row_bg).grid(row=r, column=c, sticky="ew", padx=2, pady=1, ipady=2)
            r += 1
        self.feed_body.columnconfigure(0, weight=1)
        for c in range(1, 4):
            self.feed_body.columnconfigure(c, weight=2)

    # ---------- Scope 1-3 table tab ----------
    def _draw_table(self, rows):
        """Rebuild the results table from scratch each time (simple and reliable).
        Colour code: green number = emissions saved, orange = emissions increased.
        TOTAL row = dark green band with white text. Reference row = grey italic."""
        for w in self.table_body.winfo_children():
            w.destroy()
        heads = ["Source", "Without (t CO2/yr)", "With (t CO2/yr)", "Avoided (t CO2/yr)", "% avoided"]
        for c, h in enumerate(heads):
            ctk.CTkLabel(self.table_body, text=h, font=("Segoe UI", F_TABLE, "bold"), text_color="white",
                         fg_color=GREEN, corner_radius=4).grid(row=0, column=c, sticky="ew", padx=2, pady=2, ipady=4)
        for r, (name, a, b, av, pct) in enumerate(rows, start=1):
            is_total = name == "TOTAL"
            is_ref = name.startswith("Ref:")
            # Rows starting with these words are shown bold on a pale background
            bold = is_total or name.startswith(("Scope 1b - ", "Scope 1 total", "Scope 2 total", "Green H2", "RO water", "Electrolysis"))
            fmt = lambda v: v if isinstance(v, str) else f"{v:,.0f}"
            vals = [name, fmt(a), fmt(b), fmt(av), (pct if isinstance(pct, str) else f"{pct:.1f} %")]
            row_bg = DARK if is_total else (PALE if bold else "transparent")
            for c, v in enumerate(vals):
                color = "white" if is_total else (GREY if is_ref else DARK)
                if c >= 3 and not is_total and not isinstance(av, str):     # Avoided / % avoided columns
                    color = GREEN if av > 0.5 else (ORANGE if av < -0.5 else DARK)
                weight = "bold" if bold else "normal"
                slant = "italic" if is_ref else "roman"
                ctk.CTkLabel(self.table_body, text=v, anchor="w" if c == 0 else "e", text_color=color,
                             font=("Segoe UI", F_TABLE + (1 if is_total else 0), weight, slant),
                             fg_color=row_bg).grid(row=r, column=c, sticky="ew", padx=2, pady=1, ipady=2)
        self.table_body.columnconfigure(0, weight=4)
        for c in range(1, 5):
            self.table_body.columnconfigure(c, weight=1)

    # ---------- Scope diagram tab ----------
    def _draw_diagram(self, plant, h2, sol, heat_recovery):
        """Boxed diagram, like the hand sketch: each source gets a before/after pair
        (light green = before intervention, dark green = after), bracketed per scope
        with a before -> after total and the % change."""
        LIGHT = "#b8ddd5"
        ax = self.ax_s
        ax.clear()
        ax.axis("off")
        ax.set_facecolor("white")
        before = plant.streams()                              # emissions with no levers
        after = plant.streams(h2, sol, heat_recovery)         # emissions with the chosen levers
        # Each group: (scope name, [(box label, before value, after value), ...])
        groups = [("Scope 1", [("SMR process", before["smr"], after["smr"]),
                                ("Combustion", before["combustion"], after["combustion"])]),
                  ("Scope 2", [("Plant power", before["scope2_plant"], after["scope2_plant"]),
                               ("Electrolyzer", before["scope2_electrolyzer"], after["scope2_electrolyzer"])]),
                  ("Scope 3", [("Supply chain", before["scope3"], after["scope3"])])]
        # Layout numbers (bar width and gaps). Change these to space the bars differently.
        bar_w, pair_gap, src_gap, group_gap, y0 = 0.75, 0.06, 0.30, 0.7, 0.9
        max_val = max(v for _, boxes in groups for _, bv, av in boxes for v in (bv, av)) or 1
        scale = 2.2 / max_val   # tallest bar = 2.2 data units (leaves room above for the totals text)

        x = 0.0
        for gname, boxes in groups:
            gx0 = x
            for label, bv, av in boxes:
                bh, ah = bv * scale, av * scale
                # light "before" bar
                ax.add_patch(Rectangle((x, y0), bar_w, bh, facecolor=LIGHT, edgecolor=DARK, linewidth=1.5))
                ax.text(x + bar_w / 2, y0 + bh + 0.06, f"{bv:,.0f}", ha="center", va="bottom",
                        fontsize=CH_TXT, color=DARK)
                # dark "after" bar, right next to it
                x2 = x + bar_w + pair_gap
                ax.add_patch(Rectangle((x2, y0), bar_w, ah, facecolor=GREEN, edgecolor=DARK, linewidth=1.5))
                ax.text(x2 + bar_w / 2, y0 + ah + 0.06, f"{av:,.0f}", ha="center", va="bottom",
                        fontsize=CH_TXT, color=DARK, fontweight="bold")
                ax.text(x + bar_w + pair_gap / 2, y0 - 0.10, label, ha="center", va="top",
                        fontsize=CH_TXT, color=DARK)
                x = x2 + bar_w + src_gap
            # bracket under the group + scope name + before -> after total
            gx1 = x - src_gap
            tb, ta = sum(b for _, b, _ in boxes), sum(a for _, _, a in boxes)
            change = (ta - tb) / tb * 100 if tb else 0.0
            by = y0 - 0.45
            ax.plot([gx0, gx0, gx1, gx1], [by + 0.08, by, by, by + 0.08], color=DARK, linewidth=1.8)
            ax.text((gx0 + gx1) / 2, by - 0.10, gname, ha="center", va="top",
                     fontsize=CH_HEAD, fontweight="bold", color=DARK)
            # two-line total above the bars: "before -> after" and the % change (green = lower, orange = higher)
            ax.text((gx0 + gx1) / 2, y0 + 2.80, f"{tb:,.0f} -> {ta:,.0f}", ha="center", va="bottom",
                     fontsize=CH_TXT, fontweight="bold", color=DARK)
            ax.text((gx0 + gx1) / 2, y0 + 2.62, f"t CO2/yr  ({change:+.1f}%)", ha="center", va="bottom",
                     fontsize=CH_TXT, fontweight="bold", color=GREEN if change <= 0 else ORANGE)
            x += group_gap

        # legend (two small coloured squares with text)
        ax.add_patch(Rectangle((0, y0 + 3.35), 0.3, 0.18, facecolor=LIGHT, edgecolor=DARK, linewidth=1))
        ax.text(0.38, y0 + 3.44, "before intervention", fontsize=CH_TXT, va="center", color=DARK)
        ax.add_patch(Rectangle((3.0, y0 + 3.35), 0.3, 0.18, facecolor=GREEN, edgecolor=DARK, linewidth=1))
        ax.text(3.38, y0 + 3.44, "after intervention", fontsize=CH_TXT, va="center", color=DARK)

        ax.set_xlim(-0.3, x + 0.1)
        ax.set_ylim(-0.1, y0 + 3.7)
        ax.set_title(f"Emissions before -> after (H2 {h2*100:.1f}%, heat recovery "
                     f"{heat_recovery*100:.0f}%, solar {sol*100:.0f}%)",
                     fontsize=CH_HEAD, fontweight="bold", color=DARK)
        self.fig_s.tight_layout()
        self.cv_s.draw()

    # ---------- MAC curve tab ----------
    def _draw_mac(self, plant, h2, sol, heat_recovery):
        """Left: horizontal bars of each lever's fixed cost per tonne of CO2 avoided (PKR / t).
        Right: a card per lever showing the CO2 it avoids (or adds) at the current slider settings
        AND its annual cost in PKR million = CO2 avoided (t) x cost (PKR/t) / 1,000,000."""
        ax = self.ax_m
        ax.clear()
        ax.set_facecolor("white")
        levers = {name: (avoided, cost) for name, avoided, cost in plant.levers(h2, sol, heat_recovery)}
        order = ["Solar PV", "Heat recovery", "Green H2 blending"]   # first = bottom bar
        names = [n for n in order if n in levers]
        costs = [levers[n][1] for n in names]

        bars = ax.barh(names, costs, color=GREEN, edgecolor="white", height=0.55)
        max_cost = max(costs) if costs else 1
        for b, c in zip(bars, costs):
            ax.text(b.get_width() + max_cost * 0.02, b.get_y() + b.get_height() / 2,
                     f"{c:,.0f}", va="center", fontsize=CH_TXT + 2, fontweight="bold", color=DARK)
        ax.set_xlim(0, max_cost * 1.3)
        ax.set_title("Abatement cost (PKR / t CO2 avoided)", fontsize=CH_HEAD, fontweight="bold", color=DARK)
        ax.tick_params(axis="y", labelsize=CH_TXT + 2)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))     # few ticks = no overlapping numbers
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        ax.tick_params(axis="x", labelsize=CH_TXT)
        ax.grid(axis="x", color=SURFACE_BORDER, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(SURFACE_BORDER)
        self.fig_m.tight_layout()
        self.cv_m.draw()

        def cost_line(lever):
            """Second line of a card: annual cost of the lever in PKR million (only if it saves CO2)."""
            avoided, per_t = levers.get(lever, (0, 0))
            if avoided <= 0:
                return "\nAnnual cost: - (no CO2 saved)"
            return f"\nAnnual cost: PKR {avoided * per_t / 1e6:,.1f} million/yr"

        solar_av = levers.get("Solar PV", (0, 0))[0]
        hr_av = levers.get("Heat recovery", (0, 0))[0]
        h2_av = levers.get("Green H2 blending", (0, 0))[0]

        sub, val = self._mac_cards["solar"]
        sub.configure(text=f"Solar PV avoided (Scope 2a) \u2014 at {sol * 100:.0f}% solar" + cost_line("Solar PV"))
        val.configure(text=f"{solar_av:,.0f} t CO2/yr", text_color=GREEN)

        sub, val = self._mac_cards["heat_recovery"]
        sub.configure(text=f"Heat recovery avoided (Scope 1a) \u2014 at {heat_recovery * 100:.0f}%" + cost_line("Heat recovery"))
        val.configure(text=f"{hr_av:,.0f} t CO2/yr", text_color=GREEN)

        sub, val = self._mac_cards["h2"]
        sub.configure(text=f"Green H2 net effect (Scope 1a + 1b + 2b) \u2014 at {h2 * 100:.1f}% H2" + cost_line("Green H2 blending"))
        val.configure(text=f"{h2_av:+,.0f} t CO2/yr", text_color=GREEN if h2_av >= 0 else ORANGE)


if __name__ == "__main__":
    App().mainloop()       # opens the window and waits for the user
