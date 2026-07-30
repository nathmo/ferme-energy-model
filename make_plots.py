"""2D figures: sun path vs local horizon, monthly energy, costs, free-float temp."""
import numpy as np
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import model as M
import simulate as S

OUT = S.OUT
os.makedirs(OUT, exist_ok=True)

# reference palette (dataviz skill), light mode
SURF = "#fcfcfb"; INK = "#0b0b0b"; INK2 = "#52514e"; MUTED = "#898781"
GRID = "#e1e0d9"; BASE = "#c3c2b7"
C1, C2, C3, C4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"

plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "text.color": INK, "axes.edgecolor": BASE, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.family": "sans-serif", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False,
})

SLOPES = M.monthly_warming_slopes()
res, ctx = S.run("now", year=2026, slopes=SLOPES)
w, occ, hz = ctx["w"], ctx["occ"], ctx["hz"]
month = w["month"].astype(int)

def monthly(x, mask=None):
    m = np.ones(len(x), bool) if mask is None else mask
    return np.array([np.sum(x[(month == k) & m]) / 1000.0 for k in range(1, 13)])

MON = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"]

# ---------------------------------------------------------------- 1. sun path vs horizon
fig, ax = plt.subplots(figsize=(9, 4.6))
azg = np.linspace(45, 315, 400)
ax.fill_between(azg, 0, hz(azg), color="#d8d7d0", zorder=1)
ax.plot(azg, hz(azg), color=MUTED, lw=1.2, zorder=2)
dates = [(355, "21 Dec", C1), (80, "21 Mar", C2), (172, "21 Jun", C3)]
for doy, lab, col in dates:
    hrs = np.arange(0, 24, 0.1)
    el, az = M.sun_position(np.full_like(hrs, doy), hrs)
    keep = el > -2
    el, az, hrs_k = el[keep], az[keep], hrs[keep]
    o = np.argsort(az)
    el, az, hrs_k = el[o], az[o], hrs_k[o]
    vis = el > hz(az)
    ax.plot(az, np.where(vis, el, np.nan), color=col, lw=2.2, zorder=4)
    ax.plot(az, np.where(~vis, el, np.nan), color=col, lw=1.1, ls=(0, (2, 3)),
            alpha=0.55, zorder=3)
    # hour dots (local winter time UTC+1)
    for h in range(6, 20):
        i = np.argmin(np.abs(hrs_k - (h - 1)))
        if el[i] > 0:
            ax.plot(az[i], el[i], "o", ms=4, color=col, zorder=5)
            if doy == 172 and h in (7, 10, 13, 16, 19) or doy == 355 and h in (10, 14):
                ax.annotate(f"{h}h", (az[i], el[i]), textcoords="offset points",
                            xytext=(0, 7), ha="center", fontsize=8, color=INK2)
    lab_i = np.argmax(el)
    ax.annotate(lab, (az[lab_i], el[lab_i] + 3.2), ha="center", fontsize=10,
                color=col, fontweight="bold")
ax.annotate("rising ground\ntowards Les Pléiades", (110, 11), fontsize=9, color=INK2,
            ha="center")
ax.annotate("open towards\nthe lake", (250, 6), fontsize=9, color=INK2, ha="center")
for a, lab in ((M.AZ_S, "S facade"), (M.AZ_E, "E facade"), (M.AZ_W, "W facade")):
    ax.axvline(a, color=BASE, lw=1, ls=(0, (2, 4)))
    ax.annotate(lab, (a, 70), fontsize=8, color=MUTED, ha="center")
ax.set_xticks([90, 135, 180, 225, 270], ["E", "SE", "S", "SW", "W"])
ax.set_xlim(60, 300); ax.set_ylim(0, 74)
ax.set_ylabel("elevation above horizon (°)")
ax.set_title(f"Sun paths over the local horizon — Saint-Légier, {M.ALT:.0f} m\n"
             "solid = sun visible, dotted = blocked by terrain  (dots = full hours, local winter time)\n"
             "NB: the DEM horizon peaks at only 16.8° here — trees and neighbours are NOT in it",
             fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "sunpath.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 2. monthly energy
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.4))
x = np.arange(12)
q = ctx["b"]["q_heat"]
occ_m = monthly(q, occ); frost_m = monthly(q, ~occ)
ax1.bar(x, occ_m, 0.62, color=C1, label=f"heating while home ({S.SETPOINT_OCC:.0f} °C)")
ax1.bar(x, frost_m, 0.62, bottom=occ_m, color=C2,
        label=f"setback while away ({S.SETPOINT_AWAY:.0f} °C)", edgecolor=SURF, linewidth=2)
for i in range(12):
    t = occ_m[i] + frost_m[i]
    if t > 40:
        ax1.annotate(f"{t:.0f}", (i, t), textcoords="offset points", xytext=(0, 3),
                     ha="center", fontsize=8, color=INK2)
ax1.set_xticks(x, MON); ax1.set_ylabel("kWh / month")
ax1.set_title(f"Monthly heating need — electric scenario (primary residence, "
              f"occupied {ctx['occ_days']} days/yr)", fontsize=10, color=INK)
ax1.legend(frameon=False, fontsize=9)

pv_half_m = monthly(ctx["pv"])
pv_full_m = monthly(ctx["pv"] + ctx["pv_n"])
load_m = monthly(ctx["elec_hp"] + ctx["dhw"] + ctx["base"])
ax2.plot(x, load_m, color=C1, lw=2.2, marker="o", ms=5, label="electricity demand (heat pump + DHW + plugs)")
ax2.plot(x, pv_half_m, color=C4, lw=2.2, marker="o", ms=5,
         label=f"PV on the SSW pan, {M.PV_KWP_SSW:.1f} kWp")
ax2.plot(x, pv_full_m, color=C4, lw=1.6, ls=(0, (4, 3)), marker="o", ms=4,
         label=f"PV on both pans, {M.PV_KWP_SSW + M.PV_KWP_NNE:.1f} kWp")
ax2.set_xticks(x, MON); ax2.set_ylabel("kWh / month"); ax2.set_ylim(0, None)
ax2.set_title("The winter mismatch: PV vs demand", fontsize=10, color=INK)
ax2.legend(frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "energy.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 3. annual cost comparison
fig, ax = plt.subplots(figsize=(9, 4.6))
names = ["O oil boiler", "B electric", "C wood only", "C2 wood+electric",
         "P pellet boiler", "D +solar thermal", "E heat pump",
         "F PV SSW pan", "F2 PV both pans"]
labels = ["Oil boiler (the incumbent system)", "Electric heaters",
          "Wood stove alone*", "Wood stove + electric top-up",
          "Pellet boiler (30 kW, programmed)",
          "Electric + 10 m² solar thermal", "Air-source heat pump",
          f"Heat pump + PV SSW pan ({M.PV_KWP_SSW:.0f} kWp) + battery",
          f"Heat pump + PV both pans ({M.PV_KWP_SSW + M.PV_KWP_NNE:.0f} kWp) + battery"]
vals = [res[n]["cost"] for n in names]
o = np.argsort(vals)[::-1]
y = np.arange(len(names))
ax.barh(y, [vals[i] for i in o], 0.6, color=C1)
ax.axvline(0, color=BASE, lw=1)
ax.set_yticks(y, [labels[i] for i in o])
for j, i in enumerate(o):
    ax.annotate(f"{vals[i]:,.0f} CHF", (max(vals[i], 0), j), textcoords="offset points",
                xytext=(6, 0), va="center", fontsize=9, color=INK2)
ax.set_xlim(min(0, min(vals) * 1.3), max(vals) * 1.18)
ax.set_xlabel("running cost, CHF / year (energy only, no investment)")
ax.set_title(f"Annual running cost — same comfort ({S.SETPOINT_OCC:.0f} °C home, "
             f"{S.SETPOINT_AWAY:.0f} °C away)\n"
             f"*the 15 kW stove cannot carry a 30 kW load — it delivers only "
             f"{res['C wood only']['heat_kwh'] / res['B electric']['heat_kwh'] * 100:.0f} % "
             f"of the heat",
             fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "costs.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 4. free-float temperature
fig, ax = plt.subplots(figsize=(9, 4.2))
days = np.arange(365)
tin_d = ctx["tin_free"][:8760].reshape(365, 24)
tout_d = w["t2m"][:8760].reshape(365, 24)
ax.fill_between(days, tin_d.min(1), tin_d.max(1), color=C1, alpha=0.25, lw=0)
ax.plot(days, tin_d.mean(1), color=C1, lw=1.8, label="indoor, no heating (daily range)")
ax.plot(days, tout_d.mean(1), color=MUTED, lw=1.2, label="outdoor (daily mean)")
ax.axhline(0, color=C2, lw=1.2, ls=(0, (4, 3)))
ax.annotate("0 °C — pipes freeze", (185, 0.8), fontsize=9, color=C2)
ax.annotate(f"τ = {M.C_EFF / M.H_TOT / 3600:.0f} h — {M.C_EFF / 3.6e6:.0f} kWh/K of stone:\n"
            "the blue band is the indoor daily range, and it is\n"
            "almost a line next to the grey outdoor trace",
            (12, 19.5), fontsize=9, color=INK2, va="top")
mstart = np.cumsum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30])
ax.set_xticks(mstart, MON); ax.set_xlim(0, 364)
ax.set_ylabel("temperature (°C)")
ax.set_title("Scenario A, do nothing: indoor temperature free-floats\n"
             f"house spends {np.sum(ctx['tin_free'] < 0):,} h/yr below 0 °C — max summer indoor "
             f"{ctx['tin_free'].max():.0f} °C (no cooling problem)", fontsize=10, color=INK)
ax.legend(frameon=False, fontsize=9, loc="upper left")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "freefloat.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 5. day/night temps, now vs +50y
fig, ax = plt.subplots(figsize=(9, 4.4))
w0 = M.load_tmy()
for year, col in [(2026, C1), (2076, C2)]:
    ww = M.apply_warming(w0, year, SLOPES)
    day_m, night_m, day_a, night_a = M.day_night_monthly(ww)
    ax.plot(np.arange(12), day_m, color=col, lw=2.2, marker="o", ms=5)
    ax.plot(np.arange(12), night_m, color=col, lw=1.6, ls=(0, (4, 3)), marker="o", ms=4)
    dodge = max(0.0, (1.4 - (day_m[-1] - night_m[-1])) / 2)   # keep end labels apart
    ax.annotate(f"{year} day", (11.15, day_m[-1] + dodge), color=col, fontsize=9,
                fontweight="bold", va="center")
    ax.annotate(f"{year} night", (11.15, night_m[-1] - dodge), color=col,
                fontsize=9, va="center")
ax.axhline(0, color=MUTED, lw=1, ls=(0, (4, 3)))
ax.set_xticks(np.arange(12), MON); ax.set_xlim(-0.3, 13.2)
ax.set_ylabel("outdoor temperature (°C)")
ax.set_title("Day (solid) and night (dashed) outdoor temperature — now vs +50 years\n"
             "CMIP6-HighRes trends: nights warm faster "
             f"(+{np.mean(SLOPES['night']) * 10:.1f} K/decade) than days "
             f"(+{np.mean(SLOPES['day']) * 10:.1f} K/decade)", fontsize=10, color=INK)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "daynight.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 6. roof PV: kWh/day by month
fig, ax = plt.subplots(figsize=(9, 4.2))
ndays = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
half_d = monthly(ctx["pv"]) / ndays
north_d = monthly(ctx["pv_n"]) / ndays
ax.bar(np.arange(12), half_d, 0.62, color=C4,
       label=f"SSW pan — {M.A_PAN_SSW:.0f} m², {M.PV_KWP_SSW:.1f} kWp")
ax.bar(np.arange(12), north_d, 0.62, bottom=half_d, color=C1,
       label=f"+ NNE pan — {M.A_PAN_NNE:.0f} m², {M.PV_KWP_NNE:.1f} kWp",
       edgecolor=SURF, linewidth=2)
for i in range(12):
    ax.annotate(f"{half_d[i] + north_d[i]:.0f}", (i, half_d[i] + north_d[i]),
                textcoords="offset points", xytext=(0, 3), ha="center",
                fontsize=8, color=INK2)
ax.set_xticks(np.arange(12), MON)
ax.set_ylabel("kWh / day")
ax.set_title(f"PV production per day — pans measured by sonnendach.ch: "
             f"{M.A_PAN_SSW + M.A_PAN_NNE:.0f} m², 27–28° pitch, facing 206°/26°\n"
             f"year: {np.sum(ctx['pv']) / 1e3:.0f} kWh (SSW pan) / "
             f"{np.sum(ctx['pv'] + ctx['pv_n']) / 1e3:.0f} kWh (both) — "
             f"shaded by the SE tree ({M.TREE_TOP:.0f} m) + a ×{M.PV_RESIDUAL_SSW:.2f} "
             "residual on the SSW pan",
             fontsize=10, color=INK)
ax.legend(frameon=False, fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "pvroof.png"), dpi=150); plt.close(fig)

# ---------------------------------------------------------------- 7. facade elevations
# 3D views always hide half the building; this shows all four facades flat, which
# is the only honest way to check the window survey against the model.
LAYOUT = M.window_layout()
FACADES = [("SOUTH", "S", M.AZ_S, M.LEN_RIDGE, M.A_WIN_S, M.U_WIN_S, "replaced < 5 y"),
           ("WEST", "W", M.AZ_W, M.LEN_SLOPE, M.A_WIN_W, M.U_WIN_W, "replaced < 5 y"),
           ("EAST", "E", M.AZ_E, M.LEN_SLOPE, M.A_WIN_E, M.U_WIN_E, "replaced ~20 y"),
           ("NORTH", "N", M.AZ_N, M.LEN_RIDGE, 0.0, float("nan"), "blind")]
fig, axes = plt.subplots(1, 4, figsize=(15.5, 4.4))
for ax, (name, key, azm, width, area, u, note) in zip(axes, FACADES):
    gable = key in ("W", "E")            # the gables sit at the ends of the ridge
    ax.add_patch(plt.Rectangle((-width / 2, 0), width, M.EAVES_H,
                               facecolor="#c9ab86", edgecolor="#6b5844", lw=1.2))
    if gable:
        ax.add_patch(plt.Polygon([(-width / 2, M.EAVES_H), (width / 2, M.EAVES_H),
                                  (0, M.RIDGE_H)], facecolor="#c9ab86",
                                 edgecolor="#6b5844", lw=1.2))
    else:                                # roof pan seen edge-on behind the wall
        ax.plot([-width / 2, width / 2], [M.RIDGE_H, M.RIDGE_H], color=BASE,
                lw=1, ls=(0, (4, 3)))
    got = 0.0
    for o, z, w_, h_ in LAYOUT[key]:
        ax.add_patch(plt.Rectangle((o - w_ / 2, z), w_, h_, facecolor="#9ec5f4",
                                   edgecolor="#4d6a86", lw=1.1))
        got += w_ * h_
    ax.axhline(3.0, color=MUTED, lw=0.8, ls=(0, (3, 4)))     # floor level
    ax.annotate("1st floor", (0.03, 3.15), xycoords=("axes fraction", "data"),
                fontsize=7.5, color=MUTED)
    # Each facade is drawn AS SEEN FROM OUTSIDE. Standing in front of the south
    # or east wall you have +x / +y on your right; in front of the west or north
    # wall you have them on your left, so those two axes are flipped.
    lo, hi = -width / 2 - 0.8, width / 2 + 0.8
    ax.set_xlim((hi, lo) if key in ("W", "N") else (lo, hi))
    ax.set_ylim(-0.4, M.RIDGE_H + 0.8)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for s in ("left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.grid(False)
    u_txt = "—" if area == 0 else f"Uw {u:.1f}"
    ax.set_title(f"{name} · {azm:.0f}°\n{len(LAYOUT[key])} windows, {got:.1f} m² "
                 f"({u_txt}) — {note}", fontsize=9.5, color=INK)
# The tree sits off the corner shared by the south and east facades: on the right
# of the south elevation, on the left of the east one.
axes[0].annotate(f"the {M.TREE_TOP:.0f} m tree is off this corner →",
                 (M.LEN_RIDGE / 2 + 0.6, 0.4), fontsize=8, color="#2f5130",
                 ha="right", va="bottom")
axes[2].annotate(f"← and off this one",
                 (-M.LEN_SLOPE / 2 - 0.6, 0.4), fontsize=8, color="#2f5130",
                 ha="left", va="bottom")
fig.suptitle("The four facades, flat — window survey as modelled "
             f"({M.A_WIN:.0f} m² of glazing, {M.A_WIN * 100 / M.A_WALL:.0f} % of the wall)",
             fontsize=11, color=INK, y=0.99)
fig.tight_layout(rect=(0, 0, 1, 0.97))
fig.savefig(os.path.join(OUT, "facades.png"), dpi=150); plt.close(fig)

print("saved sunpath.png energy.png costs.png freefloat.png daynight.png pvroof.png "
      "facades.png in", OUT)
