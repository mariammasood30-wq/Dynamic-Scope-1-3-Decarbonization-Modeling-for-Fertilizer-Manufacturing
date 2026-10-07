"""FORGE-2026: modular OOP model of ammonia/urea emissions (Scope 1-3) with a MAC ranking.

Units: tonnes CO2 per year. Interventions are fractions 0-1.
Values marked (ASSUMPTION) are placeholders: replace with your own data or literature.

v2 changes:
  - Heat recovery is now a third lever that reduces Scope 1a (combustion) CO2.
  - Scope 2 electricity is split into two streams: "plant" (existing load) and
    "electrolyzer" (grid power to run the electrolyzer that makes the green H2).
    The electrolyzer is assumed to run continuously (24 h/day); solar can only
    offset the fraction of its draw that falls inside daylight_hours, so at
    night the electrolyzer's electricity is 100% grid (and therefore carries
    the full grid emissions factor).
  - Electrolyzer sizing (kW) and installed cost are now available via
    electrolyzer_size_kw() / electrolyzer_cost().
"""
from dataclasses import dataclass

M_CO2, M_NH3 = 44.0, 34.0  # 2 NH3 + CO2 -> urea: 44/34 t CO2 per t NH3 converted
M_UREA = 60.0               # 2 NH3 + CO2 -> urea + H2O: 34 + 44 - 18 = 60 (g/mol basis, per 2 NH3)


@dataclass
class Params:
    capacity: float = 200_000   # t NH3/yr (the "feed")
    process_ef: float = 1.20    # t CO2/t NH3, SMR reaction (from abstract)
    combustion_ef: float = 1.15  # t CO2/t NH3, gas firing (reformers + boilers)
    urea_share: float = 0.50    # fraction of NH3 converted to urea (set 0 to see GROSS process CO2)
    stoich_process_ef: float = 0.44 * 44.01 / 17.031  # t CO2/t NH3 = 1.137, ideal 0.88CH4+1.24H2O+1.26air -> 2NH3+0.88CO2
    combustion_h2_share: float = 1.0  # fraction of combustion CO2 tied to reforming duty, scales with SMR H2 (ASSUMPTION: 1.0 = all)
    power_mwh: float = 0.25     # MWh grid power per t NH3 (ASSUMPTION)
    grid_ef: float = 0.45       # t CO2/MWh grid (ASSUMPTION)
    logistics_ef: float = 0.05  # t CO2 per t NH3 shipped (ASSUMPTION)
    h2_cost: float = 33_600.0   # PKR per t CO2 avoided, green H2 (was 120 USD at 280 PKR/USD) (ASSUMPTION)
    solar_cost: float = 7_000.0  # PKR per t CO2 avoided, solar PV (was 25 USD) (ASSUMPTION)
    heat_recovery_cost: float = 12_600.0  # PKR per t CO2 avoided, waste-heat recovery on flue gas (was 45 USD) (ASSUMPTION)
    h2_demand_ef: float = 6 / 34  # t H2 per t NH3, from 3H2 + N2 -> 2NH3 stoichiometry
    ro_water_ef: float = 11.0   # kg RO water per kg green H2 (9 kg stoichiometric + RO reject losses) (ASSUMPTION)
    electrolysis_kwh_per_kg: float = 55.0  # kWh electricity per kg green H2, grid-connected electrolyzer (ASSUMPTION)
    electrolyzer_operating_hours: float = 24.0  # electrolyzer assumed to run continuously (ASSUMPTION)
    electrolyzer_cost_per_kw: float = 224_000.0  # PKR per kW installed, alkaline electrolyzer turnkey 2026 (was 800 USD) (ASSUMPTION)

    # --- Feedstock (raw material) basis, used by the Feedstock tab ---
    ch4_co2_ratio: float = 44.01 / 16.043   # t CO2 released per t CH4 burned/reformed = 2.743 (assumes pure methane)
    process_water_ef: float = 0.62 * 18.015 / 17.031  # t water per t NH3 used in reforming/shift = 0.656 (from 1.24 H2O per 2 NH3)
    n2_ef: float = 28.014 / (2 * 17.031)    # t N2 per t NH3, from N2 + 3H2 -> 2NH3 = 0.822

    # --- Solar sizing (no battery: daylight only, Rahim Yar Khan, ~9 h daylight) ---
    daylight_cap: float = 0.55      # max share of round-the-clock load solar can cover w/o storage (ASSUMPTION)
    daylight_hours: float = 9.0     # effective daylight hours/day used for sizing (ASSUMPTION, site not measured)
    performance_ratio: float = 0.80  # system losses: heat, wiring, inverter, soiling (ASSUMPTION)
    panel_watt: float = 585         # W per panel, common 2026 Pakistan commercial stock (ASSUMPTION)
    cost_per_watt_pkr: float = 100.0  # PKR/W turnkey installed, licensed installer (ASSUMPTION, 2026 market)
    land_acres_per_mw: float = 5.0   # acres per MW, Quaid-e-Azam Solar Park ratio (ASSUMPTION)


class Source:
    """One emission source. Subclasses say how big it is and which lever touches it."""
    scope, name = 0, ""

    def __init__(self, p):
        self.p = p

    def gross(self):
        raise NotImplementedError

    def after(self, h2, solar, heat_recovery=0.0):
        return self.gross()  # default: no lever affects this source


class CombustionCO2(Source):          # Scope 1a: natural gas burned for heat
    scope, name = 1, "Gas combustion"

    def gross(self):
        return self.p.capacity * self.p.combustion_ef

    def after(self, h2, solar, heat_recovery=0.0):
        # green H2 displaces SMR H2, so the reformer furnace fuel falls with it (reforming duty ~ CH4 reformed);
        # waste-heat recovery then cuts the remaining fuel burned
        return self.gross() * (1 - h2 * self.p.combustion_h2_share) * (1 - heat_recovery)


class ProcessCO2(Source):             # Scope 1b: SMR reaction CO2
    scope, name = 1, "SMR process"

    def gross(self):
        return self.p.capacity * self.p.process_ef

    def after(self, h2, solar, heat_recovery=0.0):    # green H2 replaces fossil H2
        return self.gross() * (1 - h2)


class LogisticsCO2(Source):           # Scope 3
    scope, name = 3, "Supply chain logistics"

    def gross(self):
        return self.p.capacity * self.p.logistics_ef


def urea_credit(p, process_co2):
    """CO2 locked into urea; can't exceed the process CO2 actually available."""
    return min(p.capacity * p.urea_share * M_CO2 / M_NH3, process_co2)


class Plant:
    def __init__(self, params=None):
        self.p = params or Params()
        self.combustion = CombustionCO2(self.p)
        self.process = ProcessCO2(self.p)
        self.logistics = LogisticsCO2(self.p)

    # ---------- Scope 2, split into plant load vs electrolyzer load ----------
    def _scope2(self, h2, solar):
        """Split Scope 2 grid electricity into 'plant' and 'electrolyzer' streams.

        Both loads are assumed constant (round-the-clock) draws. Solar is only
        produced during daylight_hours, so at night BOTH loads are 100% grid.
        During the day, the achievable solar output is shared between the two
        loads in proportion to how much each is drawing at that time.
        """
        p = self.p
        plant_kwh_day = self.total_electricity_kwh_day()
        _, elec_kwh_day = self.h2_electricity(h2)
        combined_kwh_day = plant_kwh_day + elec_kwh_day

        achievable = min(solar, p.daylight_cap)
        solar_kwh_day = combined_kwh_day * achievable

        day_share = p.daylight_hours / 24.0
        night_share = 1 - day_share

        plant_day, plant_night = plant_kwh_day * day_share, plant_kwh_day * night_share
        elec_day, elec_night = elec_kwh_day * day_share, elec_kwh_day * night_share
        daytime_demand = plant_day + elec_day

        if daytime_demand > 0:
            solar_to_plant = solar_kwh_day * (plant_day / daytime_demand)
            solar_to_elec = solar_kwh_day * (elec_day / daytime_demand)
        else:
            solar_to_plant = solar_to_elec = 0.0

        plant_grid_kwh_day = max(plant_day - solar_to_plant, 0) + plant_night
        elec_grid_kwh_day = max(elec_day - solar_to_elec, 0) + elec_night

        to_co2 = lambda kwh_day: kwh_day * 365 / 1000 * p.grid_ef  # kWh/day -> MWh/yr -> t CO2/yr
        return {"plant": to_co2(plant_grid_kwh_day), "electrolyzer": to_co2(elec_grid_kwh_day),
                "plant_grid_kwh_day": plant_grid_kwh_day, "elec_grid_kwh_day": elec_grid_kwh_day,
                "solar_kwh_day": solar_kwh_day, "combined_kwh_day": combined_kwh_day}

    def streams(self, h2=0.0, solar=0.0, heat_recovery=0.0):
        proc = self.process.after(h2, solar, heat_recovery)
        scope2 = self._scope2(h2, solar)
        credit = urea_credit(self.p, proc)
        return {"combustion": self.combustion.after(h2, solar, heat_recovery),
                "smr_gross": proc,                          # gross SMR process CO2 (before urea)
                "urea_credit": credit,                      # CO2 consumed in urea synthesis
                "smr": proc - credit,                       # net of urea CO2
                "scope2_plant": scope2["plant"],
                "scope2_electrolyzer": scope2["electrolyzer"],
                "scope3": self.logistics.after(h2, solar, heat_recovery)}

    def table(self, h2, solar, heat_recovery=0.0):
        """Rows: (label, without, with, avoided, % avoided)."""
        a, b = self.streams(), self.streams(h2, solar, heat_recovery)
        scope1 = lambda d: d["combustion"] + d["smr"]
        scope2 = lambda d: d["scope2_plant"] + d["scope2_electrolyzer"]
        total = lambda d: scope1(d) + scope2(d) + d["scope3"]
        rows = [("Scope 1a - Combustion CO2", a["combustion"], b["combustion"]),
                ("Scope 1b-i - SMR process CO2 (gross)", a["smr_gross"], b["smr_gross"]),
                ("Scope 1b-ii - less: CO2 used in urea", a["urea_credit"], b["urea_credit"]),
                ("Scope 1b - SMR process CO2 (net of urea)", a["smr"], b["smr"]),
                ("Scope 1 total", scope1(a), scope1(b)),
                ("Scope 2a - Purchased electricity (plant)", a["scope2_plant"], b["scope2_plant"]),
                ("Scope 2b - Purchased electricity (electrolyzer)", a["scope2_electrolyzer"], b["scope2_electrolyzer"]),
                ("Scope 2 total", scope2(a), scope2(b)),
                ("Scope 3 - Supply chain", a["scope3"], b["scope3"]),
                ("TOTAL", total(a), total(b))]
        # reference only (not in totals): ideal stoichiometric gross CO2 for the same capacity and blending
        ref = self.p.capacity * self.p.stoich_process_ef
        rows.append(("Ref: stoichiometric gross CO2 (1.137 t/t)", ref, ref * (1 - h2)))
        return [(n, x, y, x - y, 100 * (x - y) / x if x else 0.0) for n, x, y in rows]

    def levers(self, h2, solar, heat_recovery=0.0):
        """MAC data: (lever, t CO2 avoided, PKR/t), cheapest first."""
        tot = lambda d: (d["combustion"] + d["smr"] + d["scope2_plant"]
                         + d["scope2_electrolyzer"] + d["scope3"])
        base = tot(self.streams())
        out = [("Green H2 blending", base - tot(self.streams(h2, 0, 0)), self.p.h2_cost),
               ("Solar PV", base - tot(self.streams(0, solar, 0)), self.p.solar_cost),
               ("Heat recovery", base - tot(self.streams(0, 0, heat_recovery)), self.p.heat_recovery_cost)]
        return sorted(out, key=lambda r: r[2])

    def feedstock(self, h2=0.0, heat_recovery=0.0):
        """Annual raw-material use and product output (t/yr unless the key says otherwise).
        Natural gas is back-calculated from the model's own CO2 numbers: every t of CH4
        reformed or burned releases ch4_co2_ratio t of CO2, so  gas (t) = CO2 (t) / ratio.
        Call with no arguments for the 'without levers' case."""
        p = self.p
        s = self.streams(h2, 0.0, heat_recovery)
        ch4_feed = s["smr_gross"] / p.ch4_co2_ratio          # gas used as reforming feedstock
        ch4_fuel = s["combustion"] / p.ch4_co2_ratio         # gas burned for heat
        h2_mass, ro_water = self.h2_water(h2)
        mwh_plant = self.total_electricity_kwh_day() * 365 / 1000
        mwh_elec, _ = self.h2_electricity(h2)
        co2_in_urea = s["urea_credit"]                       # CO2 locked into urea
        nh3_to_urea = co2_in_urea * M_NH3 / M_CO2            # 2 NH3 + CO2 -> urea
        return {"ch4_feed": ch4_feed, "ch4_fuel": ch4_fuel, "ch4_total": ch4_feed + ch4_fuel,
                "water_process": p.capacity * p.process_water_ef * (1 - h2),
                "water_ro": ro_water, "n2": p.capacity * p.n2_ef, "h2_green": h2_mass,
                "elec_mwh": mwh_plant + mwh_elec,
                "nh3_made": p.capacity, "nh3_to_urea": nh3_to_urea,
                "nh3_sold": p.capacity - nh3_to_urea,
                "urea": co2_in_urea * M_UREA / M_CO2, "co2_in_urea": co2_in_urea}

    def h2_water(self, h2):
        """Green H2 required (t/yr) and RO water required (m3/yr) for the blended fraction."""
        h2_mass_t = self.p.capacity * self.p.h2_demand_ef * h2
        ro_water_m3 = h2_mass_t * 1000 * self.p.ro_water_ef / 1000  # t H2 -> kg H2 * kg water/kg H2 -> kg water -> m3
        return h2_mass_t, ro_water_m3

    def h2_electricity(self, h2):
        """Electrolyzer electricity required (MWh/yr, kWh/day) to make the green H2 blended in.
        This is the electrolyzer's OWN demand; it is now costed into Scope 2 via _scope2()."""
        h2_mass_t, _ = self.h2_water(h2)
        mwh_yr = h2_mass_t * 1000 * self.p.electrolysis_kwh_per_kg / 1000
        return mwh_yr, mwh_yr * 1000 / 365

    def electrolyzer_size_kw(self, h2):
        """Continuous (24 h/day) power rating the electrolyzer must have to hit the annual H2 target."""
        _, kwh_day = self.h2_electricity(h2)
        return kwh_day / self.p.electrolyzer_operating_hours

    def electrolyzer_cost(self, h2):
        """Estimated installed cost (PKR) for an electrolyzer of the required size."""
        return self.electrolyzer_size_kw(h2) * self.p.electrolyzer_cost_per_kw

    def total_electricity_kwh_day(self):
        """Baseline PLANT electricity demand (kWh/day) -- does not include the electrolyzer."""
        return self.p.capacity * self.p.power_mwh * 1000 / 365

    def solar_sizing(self, h2, solar):
        """Panels, land and cost for the achievable (daylight-capped) solar share, sized against
        the COMBINED load (plant + electrolyzer) so the solar system covers both.
        Returns: target %, achievable %, capped?, total/achievable daily kWh,
        system size (kWp), panel count, land (acres), install cost (PKR)."""
        p = self.p
        plant_kwh_day = self.total_electricity_kwh_day()
        _, elec_kwh_day = self.h2_electricity(h2)
        combined_kwh_day = plant_kwh_day + elec_kwh_day

        achievable = min(solar, p.daylight_cap)
        need_kwh_day = combined_kwh_day * achievable
        system_kwp = need_kwh_day / (p.daylight_hours * p.performance_ratio) if need_kwh_day else 0.0
        panels = system_kwp * 1000 / p.panel_watt
        land_acres = system_kwp / 1000 * p.land_acres_per_mw
        cost_pkr = system_kwp * 1000 * p.cost_per_watt_pkr
        return {"target": solar, "achievable": achievable, "capped": solar > p.daylight_cap,
                "total_kwh_day": combined_kwh_day, "need_kwh_day": need_kwh_day,
                "system_kwp": system_kwp, "panels": panels,
                "land_acres": land_acres, "cost_pkr": cost_pkr}

    def recommend(self, h2, solar, heat_recovery=0.0):
        """Plain-English summary shown in the green banner at the bottom of the GUI."""
        if h2 <= 0 and solar <= 0 and heat_recovery <= 0:
            return "Set a lever above 0% to see a recommendation."
        total = self.table(h2, solar, heat_recovery)[9]   # TOTAL row (the stoichiometric ref row is last)
        levers = self.levers(h2, solar, heat_recovery)
        active = [l for l in levers if l[1] > 0]           # levers that cut CO2 on their own
        losers = [l for l in levers if l[1] < 0]           # levers that ADD CO2 on their own
        # Warning line: green H2 can raise emissions when the electrolyzer runs on grid power
        warn = "".join(f"\nWarning: {name} on its own ADDS {abs(av):,.0f} t CO2/yr - its grid electricity "
                       f"emits more than the SMR CO2 it displaces. Add more solar or lower the blend."
                       for name, av, _ in losers)
        if total[3] <= 0:
            return f"Total emissions rise by {abs(total[3]):,.0f} t CO2/yr with these settings." + warn
        if not active:
            return f"Total emissions fall by {total[4]:.1f}% ({total[3]:,.0f} t CO2/yr)." + warn
        cheapest, biggest = active[0], max(active, key=lambda l: l[1])
        if cheapest[0] == biggest[0]:                      # same lever wins both: say it once
            lever_note = (f"{cheapest[0]} is both the cheapest lever (~PKR {cheapest[2]:,.0f}/t) "
                          f"and the one that avoids the most CO2.")
        else:
            lever_note = (f"{cheapest[0]} is the cheapest lever (~PKR {cheapest[2]:,.0f}/t); "
                          f"{biggest[0]} avoids the most CO2.")
        combustion_note = ("Combustion CO2 is untouched: raise heat recovery above 0% or add CCS."
                            if heat_recovery <= 0 else
                            f"Heat recovery is cutting combustion CO2 by {heat_recovery * 100:.0f}%.")
        return (f"Total emissions fall by {total[4]:.1f}% ({total[3]:,.0f} t CO2/yr). {lever_note}\n"
                f"{combustion_note} Electrolyzer power is its own Scope 2 stream: after dark it draws "
                f"grid power at the full grid emissions factor.{warn}")


if __name__ == "__main__":
    g = Plant(Params(urea_share=0.0))   # urea off: Scope 1b net must equal the gross process CO2
    print("urea OFF  gross vs net:", g.streams()["smr_gross"], g.streams()["smr"],
          "| stoich ref:", g.p.capacity * g.p.stoich_process_ef)
    plant = Plant()
    h2, solar, hr = 0.05, 0.50, 0.15
    for row in plant.table(h2, solar, hr):
        print(f"{row[0]:50s}{row[1]:>12,.0f}{row[2]:>12,.0f}{row[3]:>12,.0f}{row[4]:>8.1f}%")
    print(plant.levers(h2, solar, hr))
    print(plant.recommend(h2, solar, hr))
    print("Green H2 (t/yr), RO water (m3/yr):", plant.h2_water(h2))
    print("Electrolysis electricity (MWh/yr, kWh/day):", plant.h2_electricity(h2))
    print("Electrolyzer size (kW), cost (PKR):", plant.electrolyzer_size_kw(h2), plant.electrolyzer_cost(h2))
    print("Total plant electricity (kWh/day):", plant.total_electricity_kwh_day())
    print("Solar sizing @ 55% (max):", plant.solar_sizing(h2, 0.55))