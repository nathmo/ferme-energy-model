"""
Scenario simulation for the Ferme, Saint-Legier (see model.py for physics & data).

Scenarios
  A  do nothing          : free-floating temperature, no heating at all
  O  oil boiler          : the incumbent system (RegBL records oil for this building)
  B  electric heaters    : 20 C occupied, 16 C setback when away
  C  wood stove          : 15 kW stove alone -- deliberately under-sized, see below
  C2 wood + electric top-up : stove plus electric for whatever it cannot carry
  P  pellet boiler       : 30 kW, programmable, covers the whole load
  D  + solar thermal     : 10 m2 collector, DHW + space support on top of B
  E  air-source heat pump: same setpoints as B, COP(T) model
  F  PV on the SSW pan   : 25.5 kWp + 20 kWh battery feeding E
  F2 PV on both pans     : 62.5 kWp + 20 kWh battery feeding E

OCCUPANCY IS THE BIG CHANGE from the chalet this model came from. A two-dwelling
farmhouse at 600 m on the Vaud Riviera is a primary residence, so the calendar
is "lived in all year, away about three weeks". Frost guard is therefore no
longer the interesting question -- a setback temperature is. If the building is
in fact only partly occupied, edit `occupancy()` and `SETPOINT_AWAY` below and
everything downstream follows.

SIZING: design load is ~30 kW (H = 1085 W/K against -8 C). A single 15 kW wood
stove cannot hold 20 C in January and is not meant to -- scenario C shows what
actually happens, which is the point of running it.

Climate: every run is shifted to a target year with day/night-specific monthly
warming trends (CMIP6-HighRes); horizons now / +10 / +20 / +30 / +40 / +50 years.
"""
import numpy as np
import os
import model as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

# ---------------------------------------------------------------- occupancy calendar
SETPOINT_OCC = 20.0     # degC when someone is home
SETPOINT_AWAY = 16.0    # degC setback while away (not a frost guard: it is lived in)
BASE_W_OCC = 700.0      # W non-heating electricity, two dwellings occupied
BASE_W_AWAY = 250.0     # W with the fridges, freezer and router still running
BATT_KWH = 20.0         # kWh usable storage (scaled to this building's load)
BATT_P_MAX = 10000.0    # W charge/discharge limit

def occupancy(w):
    """Boolean hourly array. Primary residence: lived in all year bar ~3 weeks.

    Two absences, which is what a household with school holidays looks like:
    a fortnight in summer and a week in February.
    """
    doy = w["doy"].astype(int)
    away = np.zeros(len(doy), bool)
    away |= (doy >= 196) & (doy <= 209)      # Jul 15 - Jul 28
    away |= (doy >= 46) & (doy <= 52)        # mid-February week
    return ~away

# ---------------------------------------------------------------- helpers
def kwh(q_w):
    return float(np.sum(q_w)) / 1000.0

def freeze_stats(tin):
    return dict(t_min=float(tin.min()),
                h_below0=int(np.sum(tin < 0)),
                h_below5=int(np.sum(tin < 5)),
                t_max=float(tin.max()),
                h_above26=int(np.sum(tin > 26)))

def pv_production(w, el, az, hz, svf, kwp, tilt, surf_az, shade=1.0):
    """Hourly AC output (W) for kwp installed at tilt/azimuth.

    `hz` should already be the roof's own horizon (DEM + tree, seen from mid-pan
    height) -- see model.horizon_at. `shade` carries anything the geometry does
    not explain, which for this building is the SSW pan's residual.
    """
    alb = M.snow_albedo(w["month"])
    poa = M.poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"],
                           tilt, surf_az, hz, svf, alb)
    return kwp * 1000.0 * poa / 1000.0 * M.PV_PR * shade

def battery_dispatch(pv_w, load_w, cap_kwh=10.0, p_max=3000.0, eff=0.92,
                     return_series=False):
    """Greedy self-consumption. Returns (grid_import_kWh, export_kWh, self_cons_kWh);
    with return_series=True additionally a dict of hourly arrays (W):
    pv_direct, batt_charge (AC in), batt_discharge (AC out), grid_import,
    grid_export, soc (Wh stored)."""
    soc = 0.0
    cap = cap_kwh * 1000.0  # Wh
    imp = exp = self_c = 0.0
    sq = np.sqrt(eff)
    ser = ({k: np.zeros(len(pv_w)) for k in
            ("pv_direct", "batt_charge", "batt_discharge",
             "grid_import", "grid_export", "soc")} if return_series else None)
    for i, (pv, ld) in enumerate(zip(pv_w, load_w)):
        direct = min(pv, ld)
        self_c += direct
        surplus, deficit = pv - direct, ld - direct
        chg = dis_ac = ex = im = 0.0
        if surplus > 0:
            chg = min(surplus, p_max, (cap - soc) / sq)
            soc += chg * sq
            ex = surplus - chg
            exp += ex
        if deficit > 0:
            dis = min(deficit / sq, p_max, soc)
            soc -= dis
            dis_ac = dis * sq
            self_c += dis_ac
            im = deficit - dis_ac
            imp += im
        if ser is not None:
            ser["pv_direct"][i] = direct; ser["batt_charge"][i] = chg
            ser["batt_discharge"][i] = dis_ac; ser["grid_import"][i] = im
            ser["grid_export"][i] = ex; ser["soc"][i] = soc
    out = (imp / 1000.0, exp / 1000.0, self_c / 1000.0)
    return out + (ser,) if return_series else out

def dhw_load(w, occ):
    """Electric DHW, drawn 11h-17h UTC so a PV system can actually reach it.

    21 kWh/day is sonnendach's estimate for this building's two dwellings
    (7 632 kWh/yr). While the household is away the tank still stands but nobody
    draws from it, so only standing losses remain -- taken as 15 %.
    """
    load = np.zeros(len(occ))
    day_hours = (w["hour"] >= 11) & (w["hour"] < 17)
    daily = np.where(occ, M.DHW_KWH_DAY, 0.15 * M.DHW_KWH_DAY)
    load[day_hours] = (daily[day_hours] * 1000.0 / 6.0)
    return load

def solar_thermal(w, el, az, hz, svf, area=10.0, tilt=45.0, surf_az=M.AZ_S):
    """Flat-plate collector gross output (W): eta = 0.75 - 3.5*(45-Ta)/G."""
    alb = M.snow_albedo(w["month"])
    poa = M.poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"],
                           tilt, surf_az, hz, svf, alb)
    with np.errstate(divide="ignore", invalid="ignore"):
        eta = 0.75 - 3.5 * (45.0 - w["t2m"]) / np.where(poa > 30, poa, np.inf)
    return area * poa * np.clip(eta, 0, 0.75)

# ---------------------------------------------------------------- main
def run(tag="TMY", year=None, slopes=None):
    w = M.load_tmy()
    if year is not None:                     # shift to target-year climate, day/night trends
        w = M.apply_warming(w, year, slopes)
    hz = M.load_horizon()
    svf = M.sky_view_factor(hz)
    q_sol, el, az = M.solar_gains(w, hz, svf)
    occ = occupancy(w)
    occ_days = int(np.sum(occ) / 24)
    base = np.where(occ, BASE_W_OCC, BASE_W_AWAY)   # plugs, fridges, router, pumps
    e_base = kwh(base)
    dhw = dhw_load(w, occ)
    e_dhw = kwh(dhw)
    res = {}

    # --- A: do nothing (no heating; plugs + DHW still run)
    a = M.simulate(w, q_sol, occ, setpoint_occ=SETPOINT_OCC,
                   setpoint_abs=None, capacity=0.0)
    res["A do nothing"] = dict(freeze_stats(a["tin"]), heat_kwh=0,
                               elec_kwh=e_dhw + e_base,
                               cost=(e_dhw + e_base) * M.ELEC_PRICE)
    tin_free = a["tin"]

    # --- O: the incumbent oil boiler. Same comfort as B; the difference is only
    # what the heat costs and what it emits, so it shares B's demand.
    # The boiler makes the hot water too (owner), so DHW burns oil here and does
    # NOT appear on the electricity meter -- unlike every other scenario below.
    # This is the one scenario directly comparable to the measured bill, so keep
    # the two loads adding into the same litres.
    o = M.simulate(w, q_sol, occ, setpoint_occ=SETPOINT_OCC,
                   setpoint_abs=SETPOINT_AWAY, capacity=M.CAP_OIL)
    oil_l = (kwh(o["q_heat"]) + e_dhw) / (M.OIL_EFF * M.OIL_KWH_L)
    res["O oil boiler"] = dict(freeze_stats(o["tin"]), heat_kwh=kwh(o["q_heat"]),
                               oil_litres=oil_l, oil_dhw_l=e_dhw / (M.OIL_EFF * M.OIL_KWH_L),
                               elec_kwh=e_base,
                               cost=oil_l * M.OIL_PRICE_L + e_base * M.ELEC_PRICE)

    # --- B: electric heaters, 16 C setback while away
    b = M.simulate(w, q_sol, occ, setpoint_occ=SETPOINT_OCC,
                   setpoint_abs=SETPOINT_AWAY, capacity=M.CAP_ELECTRIC)
    q_occ = kwh(b["q_heat"][occ]); q_abs = kwh(b["q_heat"][~occ])
    res["B electric"] = dict(freeze_stats(b["tin"]), heat_kwh=q_occ + q_abs,
                             heat_occ=q_occ, heat_frost=q_abs,
                             elec_kwh=q_occ + q_abs + e_dhw + e_base,
                             cost=(q_occ + q_abs + e_dhw + e_base) * M.ELEC_PRICE)

    # --- C: wood stove alone. 15 kW against a 30 kW design load: the stove runs
    # flat out and the house still drifts below setpoint. freeze_stats tells you
    # how far.
    c = M.simulate(w, q_sol, occ, setpoint_occ=SETPOINT_OCC,
                   setpoint_abs=SETPOINT_AWAY, capacity=M.CAP_STOVE)
    wood_del = kwh(c["q_heat"])
    steres = wood_del / (M.STOVE_EFF * M.WOOD_KWH_STERE)
    res["C wood only"] = dict(freeze_stats(c["tin"]), heat_kwh=wood_del,
                              steres=steres, elec_kwh=e_dhw + e_base,
                              cost=steres * M.WOOD_PRICE_STERE
                                   + (e_dhw + e_base) * M.ELEC_PRICE)

    # --- C2: the same stove, with electric resistance covering the shortfall
    q2_wood = wood_del
    q2_el = max(kwh(b["q_heat"]) - q2_wood, 0.0)
    steres2 = q2_wood / (M.STOVE_EFF * M.WOOD_KWH_STERE)
    res["C2 wood+electric"] = dict(freeze_stats(b["tin"]),
                                   heat_kwh=q2_wood + q2_el,
                                   steres=steres2, elec_kwh=q2_el + e_dhw + e_base,
                                   cost=steres2 * M.WOOD_PRICE_STERE
                                        + (q2_el + e_dhw + e_base) * M.ELEC_PRICE)

    # --- P: pellet boiler, programmable, sized for the whole load
    p = M.simulate(w, q_sol, occ, setpoint_occ=SETPOINT_OCC,
                   setpoint_abs=SETPOINT_AWAY, capacity=M.CAP_PELLET)
    kg = kwh(p["q_heat"]) / (M.PELLET_EFF * M.PELLET_KWH_KG)
    on = p["q_heat"] > 0                       # stove electronics: fans, auger, igniter
    start = on & ~np.roll(on, 1); start[0] = on[0]
    e_aux = kwh(on * M.PELLET_EL_RUN
                + start * (M.PELLET_EL_IGN - M.PELLET_EL_RUN) * M.PELLET_IGN_H)
    res["P pellet boiler"] = dict(freeze_stats(p["tin"]), heat_kwh=kwh(p["q_heat"]),
                                  pellets_kg=kg, aux_kwh=e_aux,
                                  elec_kwh=e_aux + e_dhw + e_base,
                                  cost=kg * M.PELLET_PRICE_KG
                                       + (e_aux + e_dhw + e_base) * M.ELEC_PRICE)

    # --- D: solar thermal on top of B (DHW first, then space heating support)
    st = solar_thermal(w, el, az, hz, svf)
    useful_dhw = np.minimum(st, dhw)
    useful_space = np.minimum(st - useful_dhw, b["q_heat"])
    st_useful = kwh(useful_dhw + useful_space)
    elec_d = res["B electric"]["elec_kwh"] - st_useful
    res["D +solar thermal"] = dict(freeze_stats(b["tin"]),
                                   heat_kwh=res["B electric"]["heat_kwh"],
                                   st_gross=kwh(st), st_useful=st_useful,
                                   elec_kwh=elec_d, cost=elec_d * M.ELEC_PRICE)

    # --- E: heat pump (same comfort as B), resistance backup above capacity
    cap_hp = M.hp_capacity(w["t2m"])
    e = M.simulate(w, q_sol, occ, setpoint_occ=SETPOINT_OCC,
                   setpoint_abs=SETPOINT_AWAY, capacity=None)   # unconstrained need
    need = e["q_heat"]
    q_hp = np.minimum(need, cap_hp)
    q_bu = need - q_hp
    elec_hp = q_hp / M.hp_cop(w["t2m"]) + q_bu                       # W
    e_hp_kwh = kwh(elec_hp) + e_dhw + e_base
    res["E heat pump"] = dict(freeze_stats(e["tin"]), heat_kwh=kwh(need),
                              elec_kwh=e_hp_kwh, backup_kwh=kwh(q_bu),
                              cost=e_hp_kwh * M.ELEC_PRICE)

    # --- F / F2: PV + battery on top of E — the SSW pan alone, or both pans.
    # Real pan geometry from the federal solar cadastre: 28 deg at 206 deg for
    # the SSW pan, 27 deg at 26 deg for the big NNE one.
    hz_roof = M.horizon_at(hz, M.H_VIEW_ROOF)     # DEM + the tree, from mid-pan
    svf_roof = M.sky_view_factor(hz_roof)
    pv_s = pv_production(w, el, az, hz_roof, svf_roof, M.PV_KWP_SSW, 28.0, M.AZ_S,
                         M.PV_RESIDUAL_SSW)
    pv_n = pv_production(w, el, az, hz_roof, svf_roof, M.PV_KWP_NNE, 27.0, M.AZ_N)
    load = elec_hp + dhw + base
    for name, pv, kwp in (("F PV SSW pan", pv_s, M.PV_KWP_SSW),
                          ("F2 PV both pans", pv_s + pv_n,
                           M.PV_KWP_SSW + M.PV_KWP_NNE)):
        imp, exp, selfc = battery_dispatch(pv, load, cap_kwh=BATT_KWH,
                                           p_max=BATT_P_MAX)
        bill = imp * M.ELEC_PRICE - exp * M.FEED_IN
        res[name] = dict(freeze_stats(e["tin"]),
                         heat_kwh=res["E heat pump"]["heat_kwh"],
                         pv_kwh=kwh(pv), pv_kwp=kwp,
                         grid_import=imp, export=exp, self_kwh=selfc,
                         elec_kwh=kwh(load), cost=bill)

    # reference: 20 C everywhere, all year, no setback at all — the upper bound
    r = M.simulate(w, q_sol, np.ones(len(occ), bool), setpoint_occ=SETPOINT_OCC,
                   setpoint_abs=SETPOINT_OCC, capacity=M.CAP_ELECTRIC)
    e_ref = kwh(r["q_heat"]) + M.DHW_KWH_DAY * 365 + kwh(np.full(len(occ), BASE_W_OCC))
    res["Ref 20C no setback"] = dict(freeze_stats(r["tin"]), heat_kwh=kwh(r["q_heat"]),
                                     elec_kwh=e_ref, cost=e_ref * M.ELEC_PRICE)

    return res, dict(w=w, occ=occ, occ_days=occ_days, tin_free=tin_free,
                     q_sol=q_sol, b=b, pv=pv_s, pv_n=pv_n, st=st, el=el, az=az,
                     hz=hz, svf=svf, need=need, elec_hp=elec_hp, dhw=dhw, base=base)

def report(res, tag):
    print(f"\n=== {tag} ===")
    cols = ["heat_kwh", "elec_kwh", "cost", "t_min", "h_below0", "h_above26"]
    print(f"{'scenario':<18}" + "".join(f"{c:>12}" for c in cols) + "   extras")
    for name, r in res.items():
        row = f"{name:<18}"
        for c in cols:
            v = r.get(c, "")
            row += f"{v:>12.0f}" if isinstance(v, float) else f"{v:>12}"
        extra = []
        for k in ("steres", "oil_litres", "pellets_kg", "aux_kwh", "st_useful",
                  "st_gross", "backup_kwh", "pv_kwp", "pv_kwh", "grid_import",
                  "export", "heat_frost", "heat_occ"):
            if k in r:
                extra.append(f"{k}={r[k]:.0f}" if k != "steres" else f"steres={r[k]:.1f}")
        row += "   " + " ".join(extra)
        print(row)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
HORIZONS = [(2026, "now"), (2036, "+10y"), (2046, "+20y"),
            (2056, "+30y"), (2066, "+40y"), (2076, "+50y")]

def day_night_report(slopes):
    """Outdoor day/night temperatures per climate horizon; returns CSV rows."""
    w0 = M.load_tmy()
    rows = [["horizon", "year", "annual_day", "annual_night"]
            + [f"{m}_{k}" for m in MONTHS for k in ("day", "night")]]
    print("\n=== Outdoor day / night temperature, climate horizons (degC) ===")
    print(f"{'horizon':<12}{'annual day':>11}{'annual night':>13}{'Jan day':>9}"
          f"{'Jan night':>10}{'Jul day':>9}{'Jul night':>10}")
    for year, lab in HORIZONS:
        w = M.apply_warming(w0, year, slopes)
        day_m, night_m, day_a, night_a = M.day_night_monthly(w)
        print(f"{lab + f' ({year})':<12}{day_a:>11.1f}{night_a:>13.1f}{day_m[0]:>9.1f}"
              f"{night_m[0]:>10.1f}{day_m[6]:>9.1f}{night_m[6]:>10.1f}")
        rows.append([lab, year, round(day_a, 2), round(night_a, 2)]
                    + [round(v, 2) for pair in zip(day_m, night_m) for v in pair])
    return rows

def pv_roof_report(ctx):
    """Roof pans + monthly kWh/day for the SSW pan and for both; CSV rows."""
    month = ctx["w"]["month"].astype(int)
    pv_ssw, pv_both = ctx["pv"], ctx["pv"] + ctx["pv_n"]
    ndays = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
    print("\n=== Roof PV potential (pans measured by sonnendach.ch / LiDAR) ===")
    print(f"SSW pan: {M.A_PAN_SSW:.1f} m2 at 206 deg / 28 deg pitch -> "
          f"{M.PV_KWP_SSW:.1f} kWp ({M.PV_MOD_SSW} modules)")
    print(f"NNE pan: {M.A_PAN_NNE:.1f} m2 at  26 deg / 27 deg pitch -> "
          f"{M.PV_KWP_NNE:.1f} kWp ({M.PV_MOD_NNE} modules)")
    print(f"near-field shading: tree at {M.TREE_AZ:.0f} deg ({M.TREE_TOP:.0f} m tall, "
          f"{M.TREE_CROWN_R:.0f} m crown, {M.TREE_DIST:.0f} m out)"
          f" + SSW residual x{M.PV_RESIDUAL_SSW:.2f}")
    rows = [["month", "ssw_pan_kwh_day", "both_pans_kwh_day"]]
    print(f"{'month':<8}{'SSW kWh/d':>11}{'both kWh/d':>11}")
    for k in range(1, 13):
        h = np.sum(pv_ssw[month == k]) / 1000.0 / ndays[k - 1]
        f_ = np.sum(pv_both[month == k]) / 1000.0 / ndays[k - 1]
        rows.append([MONTHS[k - 1], round(h, 1), round(f_, 1)])
        print(f"{MONTHS[k - 1]:<8}{h:>11.1f}{f_:>11.1f}")
    h_yr, f_yr = np.sum(pv_ssw) / 1e3, np.sum(pv_both) / 1e3
    print(f"{'YEAR':<8}{h_yr / 365:>11.1f}{f_yr / 365:>11.1f}   "
          f"({h_yr:.0f} / {f_yr:.0f} kWh/yr; "
          f"{h_yr / M.PV_KWP_SSW:.0f} kWh/kWp on the SSW pan)")
    print(f"cross-check, sonnendach's own full-pan estimates: "
          f"{M.SONNENDACH_PV_SSW:.0f} / "
          f"{M.SONNENDACH_PV_SSW + M.SONNENDACH_PV_NNE:.0f} kWh/yr")
    rows.append(["year_total_kwh", round(h_yr), round(f_yr)])
    return rows

def co2_report(res_now, res_end, horizon=50.0):
    """Operational + embodied CO2 per scenario over `horizon` years; CSV rows."""
    import carbon as CB
    g = CB.ELEC_G_KWH[CB.ELEC_DEFAULT]
    g_pel = CB.wood_fuel_g_kwh(CB.PELLET_G_KWH)
    g_log = CB.wood_fuel_g_kwh(CB.WOOD_LOG_G_KWH)

    def op(r):
        # PV scenarios buy only their grid import; the rest is self-consumed
        e = r.get("grid_import", r.get("elec_kwh", 0))
        return (e * g
                + r.get("oil_litres", 0) * M.OIL_KWH_L * CB.OIL_G_KWH
                + r.get("pellets_kg", 0) * M.PELLET_KWH_KG * g_pel
                + r.get("steres", 0) * M.WOOD_KWH_STERE * g_log) / 1000.0

    equip = {   # scenario -> [(item, kg CO2eq, life years)]
        "O oil boiler": [("oil boiler", CB.OIL_BOILER_KG, CB.OIL_BOILER_LIFE)],
        "P pellet boiler": [("pellet boiler", CB.PELLET_STOVE_KG,
                             CB.PELLET_STOVE_LIFE)],
        "E heat pump": [("heat pump", CB.HP_KG, CB.HP_LIFE)],
        "F PV SSW pan": [("heat pump", CB.HP_KG, CB.HP_LIFE),
                         ("PV", M.PV_KWP_SSW * CB.PV_KG_PER_KWP, CB.PV_LIFE),
                         ("battery", BATT_KWH * CB.BATT_KG_PER_KWH,
                          CB.BATT_LIFE_CAL)],
        "F2 PV both pans": [("heat pump", CB.HP_KG, CB.HP_LIFE),
                            ("PV", (M.PV_KWP_SSW + M.PV_KWP_NNE)
                             * CB.PV_KG_PER_KWP, CB.PV_LIFE),
                            ("battery", BATT_KWH * CB.BATT_KG_PER_KWH,
                             CB.BATT_LIFE_CAL)],
    }
    print(f"\n=== CO2 ({CB.ELEC_DEFAULT} {g:.0f} g/kWh, pellets {g_pel:.0f} g/kWh, "
          f"biogenic counted {CB.BIOGENIC_COUNTED * 100:.0f} %) ===")
    print(f"{'scenario':<18}{'kg/yr now':>11}{'t use 50y':>11}{'t equip 50y':>13}"
          f"{'t TOTAL 50y':>13}")
    rows = [["scenario", "kg_per_year_now", "t_use_50y", "t_equipment_50y", "t_total_50y"]]
    for name in res_now:
        if name.startswith("Ref"):
            continue
        o_now, o_end = op(res_now[name]), op(res_end[name])
        use = horizon * (o_now + o_end) / 2 / 1000.0
        emb = CB.embodied_over_horizon(equip.get(name, []), horizon)[1] / 1000.0
        if name.startswith(("E", "F")):
            emb += CB.refrigerant_kg(horizon=horizon) / 1000.0
        print(f"{name:<18}{o_now:>11.0f}{use:>11.1f}{emb:>13.1f}{use + emb:>13.1f}")
        rows.append([name, round(o_now), round(use, 2), round(emb, 2),
                     round(use + emb, 2)])
    return rows

if __name__ == "__main__":
    import csv
    os.makedirs(OUT, exist_ok=True)
    slopes = M.monthly_warming_slopes()

    all_res = {}
    for year, lab in HORIZONS:
        res, ctx = run(lab, year=year, slopes=slopes)
        all_res[(year, lab)] = res
        report(res, f"{lab} ({year}) - occupied {ctx['occ_days']} days/yr")
        if lab == "now":
            ctx_now = ctx

    dn_rows = day_night_report(slopes)
    pv_rows = pv_roof_report(ctx_now)
    co2_rows = co2_report(all_res[HORIZONS[0]], all_res[(2076, "+50y")])

    with open(os.path.join(OUT, "scenarios.csv"), "w", newline="") as f:
        wcsv = csv.writer(f)
        keys = ["scenario", "horizon", "year", "heat_kwh", "elec_kwh", "cost_chf",
                "t_min", "h_below0", "h_below5", "t_max", "h_above26"]
        wcsv.writerow(keys)
        for (year, lab), rr in all_res.items():
            for name, r in rr.items():
                wcsv.writerow([name, lab, year]
                              + [round(r.get(k.replace("cost_chf", "cost"), 0), 1)
                                 for k in keys[3:]])
    for fname, rows in (("daynight.csv", dn_rows), ("pv_roof.csv", pv_rows),
                        ("co2.csv", co2_rows)):
        with open(os.path.join(OUT, fname), "w", newline="") as f:
            csv.writer(f).writerows(rows)
    print(f"\nsaved scenarios.csv, daynight.csv, pv_roof.csv, co2.csv in {OUT}")
