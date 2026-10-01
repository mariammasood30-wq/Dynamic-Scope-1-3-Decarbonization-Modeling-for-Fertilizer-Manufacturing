"""FORGE-2026 web simulator (Streamlit).  Run locally:  streamlit run app.py
Keeps forge_decarb.py unchanged: all numbers come from Plant / Params."""
import matplotlib
matplotlib.use("Agg")
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from forge_decarb import Plant, Params

GREEN, DARK, PALE, GREY = "#2e7d32", "#1b5e20", "#e8f5e9", "#9e9e9e"
LIGHT, ORANGE = "#a5d6a7", "#d35400"

st.set_page_config(page_title="FORGE-2026 | Ammonia & Urea Decarbonization Simulator",
                   page_icon="🌿", layout="wide")

st.markdown(f"""
<style>
  .stApp {{ background: {PALE}; }}
  [data-testid="stSidebar"] {{ background: white; }}
  h1, h2, h3 {{ color: {DARK}; }}
  .card {{ background: white; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px;
           border-left: 6px solid {GREEN}; }}
  .card .sub {{ font-weight: 600; color: {DARK}; font-size: 0.95rem; }}
  .card .val {{ font-size: 1.9rem; font-weight: 700; }}
  .note {{ background: white; border-radius: 8px; padding: 12px 16px; color: {DARK}; }}
  .small {{ color: #6b6b6b; font-size: 0.8rem; }}
</style>
""", unsafe_allow_html=True)

# ---------------- defaults / reset ----------------
DEFAULTS = {"cap": 200000, "h2": 0.0, "hr": 0, "solar": 0.0}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


# ---------------- sidebar: inputs ----------------
sb = st.sidebar
sb.title("Inputs")
sb.number_input("Ammonia capacity (t NH3/yr)", min_value=1000, max_value=5_000_000,
                step=10_000, key="cap")
plant = Plant(Params(capacity=float(st.session_state.cap)))

sb.slider("Green hydrogen blending (%)", 0.0, 10.0, step=0.1, key="h2")
h2 = st.session_state.h2 / 100
h2_mass, ro_water = plant.h2_water(h2)
h2_elec_mwh, h2_elec_kwh_day = plant.h2_electricity(h2)
sb.caption(f"Green H2: {h2_mass:,.0f} t/yr  |  RO water: {ro_water:,.0f} m3/yr")
sb.caption(f"Electrolysis electricity: {h2_elec_mwh:,.0f} MWh/yr ({h2_elec_kwh_day:,.0f} kWh/day), "
           "counted in Scope 2b")

sb.slider("Heat recovery on combustion (%)", 0, 90, step=1, key="hr")
heat_recovery = st.session_state.hr / 100
c_before = plant.streams()["combustion"]

plant_kwh_day = plant.total_electricity_kwh_day()
combined_kwh_day = plant_kwh_day + h2_elec_kwh_day
solar_max = plant.p.daylight_cap * combined_kwh_day
if st.session_state.solar > solar_max:          # keep the stored value inside the allowed range
    st.session_state.solar = float(solar_max)
sb.markdown(f"**Plant electricity required:** {plant_kwh_day:,.0f} kWh/day "
            f"({plant_kwh_day * 365 / 1000:,.0f} MWh/yr)")
sb.slider("Solar PV (kWh/day)", 0.0, float(solar_max), step=float(solar_max) / 100,
          format="%.0f", key="solar")
sb.caption("Solar is available in daylight only (~9 h). The slider is capped at the maximum "
           "deliverable share of plant + electrolyzer load without battery storage.")
sol_kwh = st.session_state.solar
sol = sol_kwh / combined_kwh_day if combined_kwh_day else 0.0

c_after = plant.streams(h2, sol, heat_recovery)["combustion"]
sb.caption(f"Combustion CO2: {c_before:,.0f} -> {c_after:,.0f} t/yr "
           f"({c_before - c_after:,.0f} t avoided)")
sb.button("Reset", on_click=reset, width="stretch")

# ---------------- header ----------------
st.title("FORGE-2026 | Ammonia & Urea Decarbonization Simulator")
st.caption(f"Green H2 {h2 * 100:.1f}%  |  Heat recovery {heat_recovery * 100:.0f}%  |  "
           f"Solar {sol_kwh:,.0f} kWh/day ({sol * 100:.0f}% of combined load)")


# ---------------- figures ----------------
def diagram_fig():
    fig = Figure(figsize=(9, 5.2), dpi=100)
    ax = fig.add_subplot(111)
    ax.axis("off")
    before, after = plant.streams(), plant.streams(h2, sol, heat_recovery)
    groups = [("Scope 1", [("SMR process", before["smr"], after["smr"]),
                           ("Combustion", before["combustion"], after["combustion"])]),
              ("Scope 2", [("Plant electricity", before["scope2_plant"], after["scope2_plant"]),
                           ("Electrolyzer", before["scope2_electrolyzer"], after["scope2_electrolyzer"])]),
              ("Scope 3", [("Supply chain", before["scope3"], after["scope3"])])]
    bar_w, pair_gap, src_gap, group_gap, y0 = 0.75, 0.06, 0.30, 0.7, 0.7
    max_val = max(v for _, boxes in groups for _, bv, av in boxes for v in (bv, av)) or 1
    scale = 2.6 / max_val
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
        ax.text((gx0 + gx1) / 2, y0 + 2.85, f"{tb:,.0f} -> {ta:,.0f} t CO2/yr", ha="center",
                va="bottom", fontsize=9, fontweight="bold", color=DARK)
        x += group_gap
    ax.add_patch(Rectangle((0, y0 + 3.05), 0.3, 0.15, facecolor=LIGHT, edgecolor=DARK, linewidth=1))
    ax.text(0.35, y0 + 3.12, "before intervention", fontsize=8, va="center", color=DARK)
    ax.add_patch(Rectangle((2.6, y0 + 3.05), 0.3, 0.15, facecolor=GREEN, edgecolor=DARK, linewidth=1))
    ax.text(2.95, y0 + 3.12, "after intervention", fontsize=8, va="center", color=DARK)
    ax.set_xlim(-0.3, x + 0.3)
    ax.set_ylim(-0.1, y0 + 3.4)
    ax.set_title("Emissions before -> after", fontsize=11, fontweight="bold", color=DARK)
    fig.tight_layout()
    return fig


def mac_fig(levers):
    fig = Figure(figsize=(7, 4.6), dpi=100)
    ax = fig.add_subplot(111)
    order = ["Solar PV", "Heat recovery", "Green H2 blending"]    # first = bottom bar
    names = [n for n in order if n in levers]
    costs = [levers[n][1] for n in names]
    bars = ax.barh(names, costs, color=GREEN, edgecolor="white", height=0.55)
    max_cost = max(costs) if costs else 1
    for b, c in zip(bars, costs):
        ax.text(b.get_width() + max_cost * 0.02, b.get_y() + b.get_height() / 2,
                f"{c:.0f}", va="center", fontsize=10, color=DARK)
    ax.set_xlim(0, max_cost * 1.2)
    ax.set_title("Abatement cost (USD / t CO2 avoided)", fontsize=11, fontweight="bold", color=DARK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    return fig


def card(sub, value, color=GREEN):
    st.markdown(f'<div class="card"><div class="sub">{sub}</div>'
                f'<div class="val" style="color:{color}">{value}</div></div>', unsafe_allow_html=True)


# ---------------- tabs ----------------
t_table, t_diag, t_mac, t_cost = st.tabs(
    ["Scope 1-3 table", "Scope diagram", "MAC curve", "Upgrading cost"])

with t_table:
    rows = plant.table(h2, sol, heat_recovery)
    fmt = lambda v: f"{v:,.0f}"
    data = [(n, fmt(a), fmt(b), fmt(av), f"{pct:.1f} %") for n, a, b, av, pct in rows]
    data += [("Green H2 required (t/yr)", "-", f"{h2_mass:,.0f}", "-", "-"),
             ("RO water required (m3/yr)", "-", f"{ro_water:,.0f}", "-", "-"),
             ("Electrolysis electricity required (MWh/yr)", "-", f"{h2_elec_mwh:,.0f}", "-", "-")]
    df = pd.DataFrame(data, columns=["Source", "Without (t CO2/yr)", "With", "Avoided", "% avoided"])
    bold = ("Scope 1 total", "Scope 2 total", "TOTAL", "Green H2", "RO water", "Electrolysis")
    styled = df.style.apply(
        lambda r: [f"background-color:{PALE if r['Source'].startswith(bold) else 'white'};"
                   f"font-weight:{'700' if r['Source'].startswith(bold) else '400'}"] * len(r), axis=1)
    st.dataframe(styled, hide_index=True, width="stretch", height=400)

with t_diag:
    st.pyplot(diagram_fig(), width="stretch")

with t_mac:
    levers = {n: (avoided, cost) for n, avoided, cost in plant.levers(h2, sol, heat_recovery)}
    left, right = st.columns([3, 2])
    with left:
        st.pyplot(mac_fig(levers), width="stretch")
        st.markdown('<span class="small">*Green H2\'s listed cost assumes clean electrolyzer power.</span>',
                    unsafe_allow_html=True)
    with right:
        card(f"Solar PV avoided (Scope 2a), at {sol * 100:.0f}% solar",
             f"{levers['Solar PV'][0]:,.0f} t CO2/yr")
        card(f"Heat recovery avoided (Scope 1a), at {heat_recovery * 100:.0f}%",
             f"{levers['Heat recovery'][0]:,.0f} t CO2/yr")
        h2_av = levers["Green H2 blending"][0]
        card(f"Green H2 net effect (Scope 1b + 2b), at {h2 * 100:.1f}% H2",
             f"{h2_av:+,.0f} t CO2/yr", GREEN if h2_av >= 0 else ORANGE)

with t_cost:
    d = plant.solar_sizing(h2, sol)
    max_kwh_day = d["total_kwh_day"] * plant.p.daylight_cap
    st.subheader("Solar cost")
    st.markdown(
        f'<div class="note">Combined electricity need (plant + electrolyzer) is '
        f'{d["total_kwh_day"]:,.0f} kWh/day. You selected {d["need_kwh_day"]:,.0f} kWh/day from solar '
        f'(~{d["achievable"] * 100:.0f}% of demand). Without battery storage, solar (daylight only, ~9 h) '
        f'can cover at most ~{plant.p.daylight_cap * 100:.0f}% of a round-the-clock load, about '
        f'{max_kwh_day:,.0f} kWh/day here. Whatever isn\'t covered still comes from the grid.</div>',
        unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("System size needed", f"{d['system_kwp']:,.0f} kWp")
    c2.metric(f"Panels ({plant.p.panel_watt:.0f} W each)", f"{d['panels']:,.0f}")
    c3.metric("Land required", f"{d['land_acres']:,.1f} acres")
    c4.metric("Estimated installed cost", f"PKR {d['cost_pkr']:,.0f}")
    st.caption("Assumptions: 9 effective daylight hours/day, 80% system performance ratio, PKR 100/W "
               "installed, 585 W panels, 5 acres/MW land, no battery. Adjustable in Params "
               "(forge_decarb.py).")

    st.subheader("Green H2")
    e1, e2 = st.columns(2)
    e1.metric("Electrolyzer size needed", f"{plant.electrolyzer_size_kw(h2):,.0f} kW")
    e2.metric("Estimated electrolyzer installed cost", f"USD {plant.electrolyzer_cost(h2):,.0f}")
    st.caption("Assumptions: electrolyzer runs continuously (24 h/day), so it draws grid power whenever "
               "solar isn't available. Installed cost USD 800/kW (ASSUMPTION, alkaline electrolyzer, "
               "2026 turnkey pricing). Adjustable in Params (forge_decarb.py).")

st.markdown(f'<div class="note"><b>{plant.recommend(h2, sol, heat_recovery).replace(chr(10), "<br>")}</b></div>',
            unsafe_allow_html=True)
