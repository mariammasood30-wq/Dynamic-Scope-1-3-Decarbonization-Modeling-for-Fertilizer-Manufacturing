"""FORGE-2026 desktop simulator.  Run:  python forge_gui.py
Install once:  pip install customtkinter matplotlib pillow
Keep forge_decarb.py and background_faded.png in the same folder."""
import os
import tkinter as tk
import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
from forge_decarb import Plant, Params

GREEN, DARK, PALE, GREY = "#2e7d32", "#1b5e20", "#e8f5e9", "#9e9e9e"
ORANGE = "#d35400"   # used for a lever whose net effect is negative (emissions increase)
WIN_W, WIN_H = 1180, 780
BG_IMG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background_faded.png")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("FORGE-2026 | Ammonia & Urea Decarbonization Simulator")
        self.geometry(f"{WIN_W}x{WIN_H}")
        self.resizable(False, False)
        self._background()
        self._solar_max = 0
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        self._inputs()
        self._outputs()
        self.update_all()

    def _background(self):
        """Faded plant photo as the window background, behind the input/output cards."""
        if os.path.exists(BG_IMG):
            img = Image.open(BG_IMG).resize((WIN_W, WIN_H), Image.LANCZOS)
            self._bg_photo = ImageTk.PhotoImage(img)          # keep a reference
            canvas = tk.Canvas(self, width=WIN_W, height=WIN_H, highlightthickness=0)
            canvas.place(x=0, y=0)
            canvas.create_image(0, 0, image=self._bg_photo, anchor="nw")
        else:
            self.configure(fg_color=PALE)

    # ---------- left panel: inputs ----------
    def _inputs(self):
        f = ctk.CTkFrame(self, fg_color="white", corner_radius=12, width=290)
        f.grid(row=0, column=0, sticky="ns", padx=12, pady=12)
        ctk.CTkLabel(f, text="INPUTS", font=("Arial", 18, "bold"), text_color=DARK).pack(pady=(16, 8))

        ctk.CTkLabel(f, text="Ammonia capacity (t NH3/yr)").pack(anchor="w", padx=16)
        self.cap = ctk.CTkEntry(f, width=240)
        self.cap.insert(0, "200000")
        self.cap.pack(padx=16, pady=(2, 14))
        self.cap.bind("<Return>", self.update_all)
        self.cap.bind("<FocusOut>", self.update_all)

        self.h2, self.h2_lbl = self._slider(f, "Green hydrogen blending", to=10)
        self.h2o_lbl = ctk.CTkLabel(f, text="Green H2: 0 t/yr  |  RO water: 6,600 m3/yr",
                                    font=("Arial", 11), text_color=GREY, wraplength=250, justify="left")
        self.h2o_lbl.pack(anchor="w", padx=16, pady=(0, 2))
        self.h2e_lbl = ctk.CTkLabel(f, text="Electrolysis electricity: 0 MWh/yr",
                                    font=("Arial", 11), text_color=GREY, wraplength=250, justify="left")
        self.h2e_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        # --- Heat recovery lever (Scope 1a combustion) ---
        self.hr, self.hr_lbl = self._slider(f, "Heat recovery (combustion)", to=90)
        self.hr_effect_lbl = ctk.CTkLabel(f, text="Combustion CO2: - t/yr",
                                          font=("Arial", 11), text_color=GREY, wraplength=250, justify="left")
        self.hr_effect_lbl.pack(anchor="w", padx=16, pady=(0, 10))

        self.elec_lbl = ctk.CTkLabel(f, text="Plant electricity required: - kWh/day",
                                     font=("Arial", 12, "bold"), text_color=DARK, wraplength=250, justify="left")
        self.elec_lbl.pack(anchor="w", padx=16, pady=(0, 4))

        self.solar, self.solar_lbl = self._slider(f, "Solar PV (kWh/day)", to=1000, is_solar=True)
        ctk.CTkLabel(f, text="Solar available in daylight only (~9 h); slider capped at the max "
                     "deliverable (plant + electrolyzer) without battery storage.", font=("Arial", 10),
                     text_color=GREY, wraplength=250, justify="left").pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkButton(f, text="Run", fg_color=GREEN, hover_color=DARK, command=self.update_all).pack(pady=(18, 6))
        ctk.CTkButton(f, text="Reset", fg_color=GREY, command=self.reset).pack()

    def _slider(self, parent, text, to=100, is_solar=False):
        lbl = ctk.CTkLabel(parent, text=f"{text}: 0")
        lbl.pack(anchor="w", padx=16)
        s = ctk.CTkSlider(parent, from_=0, to=to, number_of_steps=100, width=240,
                          progress_color=GREEN, button_color=DARK, command=lambda _: self.update_all())
        s.set(0)
        s.pack(padx=16, pady=(2, 14))
        s.text, s.is_solar = text, is_solar
        return s, lbl

    def reset(self):
        self.h2.set(0)
        self.hr.set(0)
        self.solar.set(0)
        self.cap.delete(0, "end")
        self.cap.insert(0, "200000")
        self.update_all()

    # ---------- right panel: outputs ----------
    def _outputs(self):
        f = ctk.CTkFrame(self, fg_color="white", corner_radius=12)
        f.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        self.tabs = ctk.CTkTabview(f, segmented_button_selected_color=GREEN)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        self.t_table = self.tabs.add("Scope 1-3 table")
        self.t_streams = self.tabs.add("Scope diagram")
        self.t_mac = self.tabs.add("MAC curve")
        self.t_solar = self.tabs.add("Upgrading cost")

        self.fig_s, self.ax_s, self.cv_s = self._chart(self.t_streams)
        self._mac_tab()
        self._upgrade_tab()
        self.rec = ctk.CTkLabel(f, text="", wraplength=780, justify="left", text_color=DARK,
                                font=("Arial", 14, "bold"), fg_color=PALE, corner_radius=8)
        self.rec.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8), ipady=8)

    def _mac_tab(self):
        """MAC tab: horizontal bars of each lever's per-tonne cost on the left,
        stacked stat cards with the CO2 each lever avoids (at current slider
        settings) on the right -- mirrors the FORGE-2026 slide layout."""
        self.t_mac.columnconfigure(0, weight=3)
        self.t_mac.columnconfigure(1, weight=2)
        self.t_mac.rowconfigure(0, weight=1)

        chart_frame = ctk.CTkFrame(self.t_mac, fg_color="transparent")
        chart_frame.grid(row=0, column=0, sticky="nsew")
        self.fig_m, self.ax_m, self.cv_m = self._chart(chart_frame)
        ctk.CTkLabel(chart_frame, text="*Green H2's listed cost assumes clean electrolyzer power.",
                     font=("Arial", 10, "italic"), text_color=GREY).pack(side="bottom", pady=(0, 4))

        cards_frame = ctk.CTkFrame(self.t_mac, fg_color="transparent")
        cards_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 10), pady=10)

        self._mac_cards = {}
        for key in ("solar", "heat_recovery", "h2"):
            card = ctk.CTkFrame(cards_frame, fg_color=PALE, corner_radius=10)
            card.pack(fill="x", pady=(0, 14), ipady=6)
            sub = ctk.CTkLabel(card, text="", font=("Arial", 12, "bold"), text_color=DARK,
                                wraplength=260, justify="left", anchor="w")
            sub.pack(fill="x", padx=14, pady=(10, 2))
            val = ctk.CTkLabel(card, text="", font=("Arial", 24, "bold"), text_color=GREEN, anchor="w")
            val.pack(fill="x", padx=14, pady=(0, 10))
            self._mac_cards[key] = (sub, val)

    def _upgrade_tab(self):
        """4th tab: capital cost of the two physical upgrades -- solar and the electrolyzer."""
        ctk.CTkLabel(self.t_solar, text="Solar cost", font=("Arial", 16, "bold"),
                     text_color=DARK, anchor="w").pack(fill="x", padx=6, pady=(8, 2))
        self.solar_note = ctk.CTkLabel(self.t_solar, text="", font=("Arial", 12), text_color=DARK,
                                       fg_color=PALE, corner_radius=8, justify="left", wraplength=760, anchor="w")
        self.solar_note.pack(fill="x", padx=6, pady=(0, 8), ipady=8, ipadx=10)
        self.solar_rows = ctk.CTkFrame(self.t_solar, fg_color="transparent")
        self.solar_rows.pack(fill="x", padx=6)
        self.solar_rows.columnconfigure(0, weight=2)
        self.solar_rows.columnconfigure(1, weight=1)
        self._solar_labels = []
        for i, label in enumerate(["System size needed", "Number of panels (585 W each)",
                                    "Land required", "Estimated installed cost"]):
            ctk.CTkLabel(self.solar_rows, text=label, anchor="w").grid(row=i, column=0, sticky="ew", pady=6)
            val = ctk.CTkLabel(self.solar_rows, text="-", anchor="e", font=("Arial", 13, "bold"), text_color=DARK)
            val.grid(row=i, column=1, sticky="ew", pady=6)
            self._solar_labels.append(val)
        ctk.CTkLabel(self.t_solar, text="Assumptions: 9 effective daylight hours/day, 80% system performance "
                     "ratio, PKR 100/W installed, 585 W panels, 5 acres/MW land, no battery -> solar capped "
                     "at 55% of round-the-clock combined (plant + electrolyzer) load. Adjustable in Params "
                     "(forge_decarb.py).", font=("Arial", 10), text_color=GREY, wraplength=760,
                     justify="left").pack(anchor="w", padx=6, pady=(10, 18))

        ctk.CTkLabel(self.t_solar, text="Green H2", font=("Arial", 16, "bold"),
                     text_color=DARK, anchor="w").pack(fill="x", padx=6, pady=(2, 2))
        self.h2_rows = ctk.CTkFrame(self.t_solar, fg_color="transparent")
        self.h2_rows.pack(fill="x", padx=6)
        self.h2_rows.columnconfigure(0, weight=2)
        self.h2_rows.columnconfigure(1, weight=1)
        self._h2_labels = []
        for i, label in enumerate(["Electrolyzer size needed", "Estimated electrolyzer installed cost"]):
            ctk.CTkLabel(self.h2_rows, text=label, anchor="w").grid(row=i, column=0, sticky="ew", pady=6)
            val = ctk.CTkLabel(self.h2_rows, text="-", anchor="e", font=("Arial", 13, "bold"), text_color=DARK)
            val.grid(row=i, column=1, sticky="ew", pady=6)
            self._h2_labels.append(val)
        ctk.CTkLabel(self.t_solar, text="Assumptions: electrolyzer runs continuously (24 h/day) to maximize "
                     "utilization, so it draws grid power whenever solar isn't available (e.g. at night). "
                     "Installed cost taken at USD 800/kW (ASSUMPTION, alkaline electrolyzer, 2026 turnkey "
                     "pricing). Adjustable in Params (forge_decarb.py).", font=("Arial", 10), text_color=GREY,
                     wraplength=760, justify="left").pack(anchor="w", padx=6, pady=(10, 0))

    def _draw_upgrade(self, plant, h2, sol, elec_kw, elec_cost):
        d = plant.solar_sizing(h2, sol)
        max_kwh_day = d["total_kwh_day"] * plant.p.daylight_cap
        msg = (f"Combined electricity need (plant + electrolyzer) is {d['total_kwh_day']:,.0f} kWh/day. "
               f"You've selected {d['need_kwh_day']:,.0f} kWh/day from solar (~{d['achievable']*100:.0f}% "
               f"of demand). Without battery storage, solar (daylight only, ~9 h) can cover at most "
               f"~{plant.p.daylight_cap*100:.0f}% of a round-the-clock load — about {max_kwh_day:,.0f} "
               f"kWh/day here. Whatever isn't covered still comes from the grid.")
        self.solar_note.configure(text=msg)
        vals = [f"{d['system_kwp']:,.0f} kWp", f"{d['panels']:,.0f} panels",
                f"{d['land_acres']:,.1f} acres", f"PKR {d['cost_pkr']:,.0f}"]
        for lbl, v in zip(self._solar_labels, vals):
            lbl.configure(text=v)

        h2_vals = [f"{elec_kw:,.0f} kW", f"USD {elec_cost:,.0f}"]
        for lbl, v in zip(self._h2_labels, h2_vals):
            lbl.configure(text=v)

    def _chart(self, parent):
        fig = Figure(figsize=(7, 4.6), dpi=100)
        ax = fig.add_subplot(111)
        cv = FigureCanvasTkAgg(fig, master=parent)
        cv.get_tk_widget().pack(fill="both", expand=True)
        return fig, ax, cv

    # ---------- refresh ----------
    def update_all(self, *_):
        try:
            cap = float(self.cap.get().replace(",", ""))
        except ValueError:
            cap = 200000.0
        plant = Plant(Params(capacity=cap))

        h2 = self.h2.get() / 100                      # slider 0-10 -> fraction 0-0.10
        heat_recovery = self.hr.get() / 100            # slider 0-90 -> fraction 0-0.90

        # solar slider's achievable range depends on the COMBINED load (plant + electrolyzer)
        plant_kwh_day = plant.total_electricity_kwh_day()
        _, elec_kwh_day = plant.h2_electricity(h2)
        combined_kwh_day = plant_kwh_day + elec_kwh_day
        solar_max = plant.p.daylight_cap * combined_kwh_day

        if abs(getattr(self, "_solar_max", -1) - solar_max) > 1:
            self._solar_max = solar_max
            self.solar.configure(to=solar_max)
            if self.solar.get() > solar_max:
                self.solar.set(solar_max)

        sol_kwh = self.solar.get()                                  # slider is kWh/day directly
        sol = sol_kwh / combined_kwh_day if combined_kwh_day else 0.0

        self.h2_lbl.configure(text=f"Green hydrogen blending: {h2 * 100:.1f} %")
        self.hr_lbl.configure(text=f"Heat recovery (combustion): {heat_recovery * 100:.0f} %")
        self.solar_lbl.configure(text=f"Solar PV: {sol_kwh:,.0f} kWh/day")
        self.elec_lbl.configure(text=f"Plant electricity required: {plant_kwh_day:,.0f} kWh/day "
                                     f"({plant_kwh_day * 365 / 1000:,.0f} MWh/yr)")

        h2_mass, ro_water = plant.h2_water(h2)
        h2_elec_mwh, h2_elec_kwh_day = plant.h2_electricity(h2)
        elec_kw = plant.electrolyzer_size_kw(h2)
        elec_cost = plant.electrolyzer_cost(h2)

        rows = plant.table(h2, sol, heat_recovery)
        rows.append(("Green H2 required (t/yr)", "-", f"{h2_mass:,.0f}", "-", "-"))
        rows.append(("RO water required (m3/yr)", "-", f"{ro_water:,.0f}", "-", "-"))
        rows.append(("Electrolysis electricity required (MWh/yr)", "-", f"{h2_elec_mwh:,.0f}", "-", "-"))
        self._draw_table(rows)
        self._draw_diagram(plant, h2, sol, heat_recovery)
        self._draw_mac(plant, h2, sol, heat_recovery)
        self._draw_upgrade(plant, h2, sol, elec_kw, elec_cost)
        self.rec.configure(text=plant.recommend(h2, sol, heat_recovery))
        self.h2o_lbl.configure(text=f"Green H2: {h2_mass:,.0f} t/yr  |  RO water: {ro_water:,.0f} m3/yr")
        self.h2e_lbl.configure(text=f"Electrolysis electricity: {h2_elec_mwh:,.0f} MWh/yr "
                                    f"({h2_elec_kwh_day:,.0f} kWh/day) — split into Scope 2b below")

        combustion_before = plant.streams()["combustion"]
        combustion_after = plant.streams(h2, sol, heat_recovery)["combustion"]
        self.hr_effect_lbl.configure(
            text=f"Combustion CO2: {combustion_before:,.0f} -> {combustion_after:,.0f} t/yr "
                 f"({combustion_before - combustion_after:,.0f} t avoided)")

    def _draw_table(self, rows):
        for w in self.t_table.winfo_children():
            w.destroy()
        heads = ["Source", "Without (t CO2/yr)", "With", "Avoided", "% avoided"]
        for c, h in enumerate(heads):
            ctk.CTkLabel(self.t_table, text=h, font=("Arial", 13, "bold"), text_color="white",
                         fg_color=GREEN, corner_radius=4).grid(row=0, column=c, sticky="ew", padx=2, pady=2, ipady=4)
        for r, (name, a, b, av, pct) in enumerate(rows, start=1):
            bold = name.startswith(("Scope 1 total", "Scope 2 total", "TOTAL", "Green H2", "RO water", "Electrolysis"))
            fmt = lambda v: v if isinstance(v, str) else f"{v:,.0f}"
            vals = [name, fmt(a), fmt(b), fmt(av), (pct if isinstance(pct, str) else f"{pct:.1f} %")]
            for c, v in enumerate(vals):
                ctk.CTkLabel(self.t_table, text=v, anchor="w" if c == 0 else "e",
                             font=("Arial", 13, "bold" if bold else "normal"),
                             fg_color=PALE if bold else "transparent").grid(row=r, column=c, sticky="ew", padx=2, pady=1, ipady=3)
        self.t_table.columnconfigure(0, weight=3)
        for c in range(1, 5):
            self.t_table.columnconfigure(c, weight=1)

    def _draw_diagram(self, plant, h2, sol, heat_recovery):
        """Boxed diagram, like the hand sketch: each source gets a before/after pair
        (light green = before intervention, dark green = after), bracketed per scope
        with a before -> after total."""
        LIGHT = "#a5d6a7"
        ax = self.ax_s
        ax.clear()
        ax.axis("off")
        before = plant.streams()
        after = plant.streams(h2, sol, heat_recovery)
        groups = [("Scope 1", [("SMR process", before["smr"], after["smr"]),
                                ("Combustion", before["combustion"], after["combustion"])]),
                  ("Scope 2", [("Plant electricity", before["scope2_plant"], after["scope2_plant"]),
                               ("Electrolyzer", before["scope2_electrolyzer"], after["scope2_electrolyzer"])]),
                  ("Scope 3", [("Supply chain", before["scope3"], after["scope3"])])]
        bar_w, pair_gap, src_gap, group_gap, y0 = 0.75, 0.06, 0.30, 0.7, 0.7
        max_val = max(v for _, boxes in groups for _, bv, av in boxes for v in (bv, av)) or 1
        scale = 2.6 / max_val   # tallest bar = 2.6 data units on the axes

        x = 0.0
        for gname, boxes in groups:
            gx0 = x
            for label, bv, av in boxes:
                bh, ah = bv * scale, av * scale
                ax.add_patch(Rectangle((x, y0), bar_w, bh, facecolor=LIGHT, edgecolor=DARK, linewidth=1.2))
                ax.text(x + bar_w / 2, y0 + bh + 0.06, f"{bv:,.0f}", ha="center", va="bottom",
                        fontsize=8, color=DARK)
                x2 = x + bar_w + pair_gap
                ax.add_patch(Rectangle((x2, y0), bar_w, ah, facecolor=GREEN, edgecolor=DARK, linewidth=1.2))
                ax.text(x2 + bar_w / 2, y0 + ah + 0.06, f"{av:,.0f}", ha="center", va="bottom",
                        fontsize=8, color=DARK, fontweight="bold")
                ax.text(x + bar_w + pair_gap / 2, y0 - 0.10, label, ha="center", va="top",
                        fontsize=8, color=DARK)
                x = x2 + bar_w + src_gap
            gx1 = x - src_gap
            tb, ta = sum(b for _, b, _ in boxes), sum(a for _, _, a in boxes)
            by = y0 - 0.38
            ax.plot([gx0, gx0, gx1, gx1], [by + 0.08, by, by, by + 0.08], color=DARK, linewidth=1.3)
            ax.text((gx0 + gx1) / 2, by - 0.10, gname, ha="center", va="top",
                     fontsize=11, fontweight="bold", color=DARK)
            ax.text((gx0 + gx1) / 2, y0 + 2.85, f"{tb:,.0f} -> {ta:,.0f} t CO2/yr", ha="center", va="bottom",
                     fontsize=9, fontweight="bold", color=DARK)
            x += group_gap

        ax.add_patch(Rectangle((0, y0 + 3.05), 0.3, 0.15, facecolor=LIGHT, edgecolor=DARK, linewidth=1))
        ax.text(0.35, y0 + 3.12, "before intervention", fontsize=8, va="center", color=DARK)
        ax.add_patch(Rectangle((2.6, y0 + 3.05), 0.3, 0.15, facecolor=GREEN, edgecolor=DARK, linewidth=1))
        ax.text(2.95, y0 + 3.12, "after intervention", fontsize=8, va="center", color=DARK)

        ax.set_xlim(-0.3, x + 0.3)
        ax.set_ylim(-0.1, y0 + 3.4)
        ax.set_title(f"Emissions before -> after (H2 {h2*100:.1f}%, heat recovery "
                     f"{heat_recovery*100:.0f}%, solar {sol*100:.0f}%)",
                     fontsize=11, fontweight="bold", color=DARK)
        self.fig_s.tight_layout()
        self.cv_s.draw()

    def _draw_mac(self, plant, h2, sol, heat_recovery):
        """Left: horizontal bars of each lever's fixed USD/t cost (bottom -> top:
        Solar PV, Heat recovery, Green H2). Right: a card per lever showing how
        much CO2 it avoids (or adds) at the current slider settings."""
        ax = self.ax_m
        ax.clear()
        levers = {name: (avoided, cost) for name, avoided, cost in plant.levers(h2, sol, heat_recovery)}
        order = ["Solar PV", "Heat recovery", "Green H2 blending"]   # first = bottom bar
        names = [n for n in order if n in levers]
        costs = [levers[n][1] for n in names]

        bars = ax.barh(names, costs, color=GREEN, edgecolor="white", height=0.55)
        max_cost = max(costs) if costs else 1
        for b, c in zip(bars, costs):
            ax.text(b.get_width() + max_cost * 0.02, b.get_y() + b.get_height() / 2,
                     f"{c:.0f}", va="center", fontsize=10, color=DARK)
        ax.set_xlim(0, max_cost * 1.2)
        ax.set_title("Abatement cost (USD / t CO2 avoided)", fontsize=11, fontweight="bold", color=DARK)
        ax.tick_params(axis="y", labelsize=10)
        ax.tick_params(axis="x", labelsize=9)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        self.fig_m.tight_layout()
        self.cv_m.draw()

        solar_av = levers.get("Solar PV", (0, 0))[0]
        hr_av = levers.get("Heat recovery", (0, 0))[0]
        h2_av = levers.get("Green H2 blending", (0, 0))[0]

        sub, val = self._mac_cards["solar"]
        sub.configure(text=f"Solar PV avoided (Scope 2a) \u2014 at {sol * 100:.0f}% solar")
        val.configure(text=f"{solar_av:,.0f} t CO2/yr", text_color=GREEN)

        sub, val = self._mac_cards["heat_recovery"]
        sub.configure(text=f"Heat recovery avoided (Scope 1a) \u2014 at {heat_recovery * 100:.0f}%")
        val.configure(text=f"{hr_av:,.0f} t CO2/yr", text_color=GREEN)

        sub, val = self._mac_cards["h2"]
        sub.configure(text=f"Green H2 net effect (Scope 1b + 2b) \u2014 at {h2 * 100:.1f}% H2")
        val.configure(text=f"{h2_av:+,.0f} t CO2/yr", text_color=GREEN if h2_av >= 0 else ORANGE)


if __name__ == "__main__":
    App().mainloop()
