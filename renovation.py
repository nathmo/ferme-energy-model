"""
Envelope breakdown and renovation measures for the Ferme, Saint-Legier.

Two things live here, deliberately kept apart from the heating side of the model:

1. ELEMENTS — how the single heat-loss coefficient H that `model.simulate()`
   integrates splits into the parts of the building that actually lose the heat:
   walls, roof, windows, floor over the cellar, and air changes. The split is
   exact — the element conductances sum to H — so an annual heat balance built
   from them closes to within the change in stored heat.

2. MEASURES — a catalogue of renovation measures. A measure only ever does four
   things: it lowers one fabric parameter (a U-value or the air change rate), it
   costs money, it embodies CO2, and it may add a small permanent electric load.
   Nothing here knows about heating systems, PV or energy prices. The dashboard
   feeds the modified fabric straight back into the same simulation, so heating
   demand, running cost and CO2 all follow by themselves — which is the whole
   point: a measure is judged by the physics, not by a claimed saving.

Costs are installed prices incl. VAT for a large, road-accessible building on the
Vaud Riviera (2025-26). They differ from the alpine chalet this model came from
in both directions: the unit rates are lower, because 400 m2 of wall and 230 m2
of floor buy volume pricing and the lorry parks next to the site — but the
quantities are five to eight times larger, so the totals are far higher.
Embodied figures are KBOB/ecoinvent order-of-magnitude values for the material
plus its fixing. Both are rounded to something defensible rather than exact, and
the dashboard lets you edit every one of them.

Two things about *this* building shape the catalogue:

- The walls are 50-100 cm of bare stone at U 1.72. They are far and away the
  dominant loss, and they are also the whole thermal mass: insulating them from
  the inside cuts the loss but throws most of the 50 kWh/K away with it
  (`c_mult`), which is why the measure carries one.
- Only the EAST windows are old. South and west were replaced within the last
  five years, so a "new windows" measure here buys 6 m2, not 21 — the catalogue
  bills it on 6 m2 via an explicit `qty`, and the U it sets is the new
  *area-weighted average* over all three facades, not a per-window value.

Subsidies: the Swiss *Programme Bâtiments* (M-01) pays a flat rate per m2 for
insulating an opaque element against outside air or an unheated space — ~70
CHF/m2 in Vaud, subject to a minimum project size and a permit *before* the work
starts. Windows on their own, air sealing and ventilation do not qualify.
Heritage constraints matter more here than the subsidy does: see the note on
external wall insulation.
"""

import numpy as np

import carbon as CB
import model as M

# ----------------------------------------------------------------------------- elements
# Element -> (area key, fabric key, unit of the spec shown in the dashboard).
ELEMENT_SPEC = {
    "walls":                   ("wall",   "u_wall",  "W/m²K"),
    "roof":                    ("roof",   "u_roof",  "W/m²K"),
    "windows":                 ("window", "u_win",   "W/m²K"),
    "floor → cellar":          ("floor",  "u_floor", "W/m²K"),
    "ventilation & air leaks": (None,     "ach",     "1/h"),
}

ELEMENT_COLORS = {
    "walls":                   "#b08d63",
    "roof":                    "#8a63d2",
    "windows":                 "#2a78d6",
    "floor → cellar":          "#6f5a3e",
    "ventilation & air leaks": "#898781",
}


def base_fabric(u_wall=M.U_WALL, u_roof=M.U_ROOF, u_win=M.U_WIN,
                u_floor=M.U_FLOOR, ach=M.ACH):
    """The five numbers a renovation measure is allowed to touch (+ mass factor)."""
    return dict(u_wall=u_wall, u_roof=u_roof, u_win=u_win, u_floor=u_floor,
                ach=ach, c_mult=1.0)


def element_areas(a_win=M.A_WIN, len_ns=M.LEN_NS, len_ew=M.LEN_EW,
                  eaves_h=M.EAVES_H, ridge_h=M.RIDGE_H):
    """Envelope areas (m²). Wall is the four facades + both gables, net of glazing."""
    return {
        "wall": (2 * (len_ns + len_ew) * eaves_h
                 + 2 * 0.5 * len_ns * (ridge_h - eaves_h) - a_win),
        "roof": M.A_ROOF,
        "window": a_win,
        "floor": M.A_FLOOR,
    }


def conductances(fabric, ar, volume=M.VOLUME, b_floor=M.B_FLOOR):
    """W/K per element. The sum is exactly the H that model.simulate() uses."""
    return {
        "walls": ar["wall"] * fabric["u_wall"],
        "roof": ar["roof"] * fabric["u_roof"],
        "windows": ar["window"] * fabric["u_win"],
        "floor → cellar": ar["floor"] * fabric["u_floor"] * b_floor,
        "ventilation & air leaks": fabric["ach"] * volume * 0.34,
    }


# ----------------------------------------------------------------------------- measures
INSULATION_SUBSIDY = 70.0   # CHF/m², Programme Bâtiments M-01 (opaque elements only)

M_FLOOR = "floor — 16 cm under the vault/joists, worked from the cellar"
M_SEAL = "air sealing — joints, penetrations, cellar hatch, doors"
M_WIN_E = "windows — replace the remaining EAST glazing (6 m², triple, Uw 0.9)"
M_WIN_E2 = "windows — replace the remaining EAST glazing (6 m², double, Uw 1.3)"
M_ROOF = "roof — 12 cm added under the rafters"
M_WALL_IN = "walls — 12 cm wood fibre lining, from the inside"
M_WALL_OUT = "walls — 16 cm outside, behind a new render"
M_MVHR = "ventilation — MVHR unit with 80 % heat recovery"

MEASURES = {
    M_FLOOR: dict(
        tag="floor", unit="floor", sets=dict(u_floor=0.20),
        chf=90.0, kg=12.0, life=40, subsidised=True,
        note="230 m² reachable from an unheated cellar without disturbing a "
             "single room upstairs, and the subsidy applies. On a building whose "
             "walls cannot easily be touched, this is the one large, cheap, "
             "uncontroversial measure. Start here."),
    M_SEAL: dict(
        tag="air sealing", unit="lump", sets=dict(ach=0.35),
        chf=12000.0, kg=600.0, life=30,
        note="Massive stone is not especially leaky in itself — the air goes "
             "past the old east windows, through the cellar hatch, up the "
             "chimney and out at the wall/roof junction. Less to win here than "
             "in a timber building, and a blower-door test is what makes any of "
             "it real."),
    M_WIN_E: dict(
        tag="windows E 3×", unit="window", qty=M.A_WIN_E,
        sets=dict(u_win=(M.A_WIN_S * M.U_WIN_S + M.A_WIN_W * M.U_WIN_W
                         + M.A_WIN_E * 0.9) / M.A_WIN),
        group="windows", chf=1100.0, kg=120.0, life=30,
        note="Only the east facade is still on 20-year-old glazing; south and "
             "west are already new and are left alone. 6 m² is a small job with "
             "a correspondingly small effect on H — worth doing for the comfort "
             "and the draught, not as an energy investment."),
    M_WIN_E2: dict(
        tag="windows E 2×", unit="window", qty=M.A_WIN_E,
        sets=dict(u_win=(M.A_WIN_S * M.U_WIN_S + M.A_WIN_W * M.U_WIN_W
                         + M.A_WIN_E * 1.3) / M.A_WIN),
        group="windows", chf=850.0, kg=95.0, life=30,
        note="The cheaper swap on the east side, glazing units only, for when "
             "the frames are sound."),
    M_ROOF: dict(
        tag="roof", unit="roof", sets=dict(u_roof=0.14),
        chf=120.0, kg=14.0, life=40, subsidised=True,
        note="The roof was redone around 2000 and already carries ~14 cm, so it "
             "is no longer a weak point — it is 6 % of the losses against the "
             "walls' 64 %. Adding under the rafters is worth doing when the "
             "attic is converted anyway, rarely on its own."),
    M_WALL_IN: dict(
        tag="walls inside", unit="wall", sets=dict(u_wall=0.28), c_mult=0.45,
        group="walls", chf=220.0, kg=20.0, life=40, subsidised=True,
        note="The big one: 406 m² at U 1.72 is roughly two thirds of everything "
             "this building loses, and interior lining is usually the only "
             "version a stone farmhouse's facade will accept. But it has a real "
             "cost beyond money — it buries the stone, and with it most of the "
             "50 kWh/K of thermal mass (c_mult 0.45), so the house becomes "
             "quicker to heat and quicker to cool. Dew-point and vapour control "
             "on massive masonry are not optional; get them designed."),
    M_WALL_OUT: dict(
        tag="walls outside", unit="wall", sets=dict(u_wall=0.22),
        group="walls", chf=320.0, kg=34.0, life=40, subsidised=True,
        note="Thermally better — it wraps the cold bridges at the floors and "
             "keeps all the stone mass inside the envelope. On a rural building "
             "of this age it is also the version most likely to be refused: it "
             "buries the stonework and moves the facade out by 20 cm. Check the "
             "commune's plan d'affectation and the cantonal heritage inventory "
             "(recensement architectural) BEFORE costing it."),
    M_MVHR: dict(
        tag="MVHR", unit="lump", sets=dict(ach=0.20),
        chf=45000.0, kg=2200.0, life=20, aux_w=60.0,
        note="Ducting 380 m² over two storeys of a stone building is expensive "
             "and invasive, and only pays off once the envelope is sealed — on a "
             "leaky house the air goes round it. The fans run all year (60 W), "
             "which is why it carries a permanent electric load."),
}

PACKAGES = {
    "quick wins (floor + air sealing + east windows)": [
        M_FLOOR, M_SEAL, M_WIN_E,
    ],
    "everything except the facade": [
        M_FLOOR, M_SEAL, M_WIN_E, M_ROOF, M_WALL_IN,
    ],
    "deep retrofit (external wall insulation, if permitted)": [
        M_FLOOR, M_SEAL, M_WIN_E, M_ROOF, M_WALL_OUT, M_MVHR,
    ],
}


def resolve(names, cat=None):
    """(measures actually carried out, measures superseded).

    Two ways of insulating the same element — inside vs outside on the walls,
    triple vs double on the windows — are alternatives, not additions: only the
    better one survives, and only it is paid for. Measures without a `group`
    (sealing and MVHR both act on the air changes) stack normally.
    """
    cat = MEASURES if cat is None else cat
    best = {}
    for n in names:
        g = cat[n].get("group")
        if g is None:
            continue
        k = next(iter(cat[n]["sets"]))
        if g not in best or cat[n]["sets"][k] < cat[best[g]]["sets"][k]:
            best[g] = n
    dropped = [n for n in names
               if cat[n].get("group") and n != best[cat[n]["group"]]]
    return [n for n in names if n not in dropped], dropped


def fabric_after(names, fabric, cat=None):
    """Fabric after the measures. A measure can only improve a parameter, so
    picking two measures on the same element simply keeps the better one."""
    cat = MEASURES if cat is None else cat
    out = dict(fabric)
    for n in names:
        m = cat[n]
        for k, v in m["sets"].items():
            out[k] = min(out[k], v)
        out["c_mult"] = out.get("c_mult", 1.0) * m.get("c_mult", 1.0)
    return out


def measure_items(names, ar, subsidy=0.0, cat=None):
    """Cost / embodied / lifetime row per selected measure (defaults; editable)."""
    cat = MEASURES if cat is None else cat
    out = []
    for n in names:
        m = cat[n]
        # `qty` overrides the element area when a measure only touches part of an
        # element — the east windows are 6 m² of the 21 m² of glazing.
        q = m.get("qty", 1.0 if m["unit"] == "lump" else ar[m["unit"]])
        gross = m["chf"] * q
        out.append(dict(measure=n, tag=m["tag"], unit=m["unit"], quantity=q,
                        chf=gross, kg=m["kg"] * q, life=float(m["life"]),
                        subsidy=min(subsidy * q, gross) if m.get("subsidised") else 0.0,
                        aux_w=m.get("aux_w", 0.0), note=m["note"]))
    return out


def capex(items):
    """(gross CHF, subsidy CHF, net CHF, annualised net CHF/yr straight-line)."""
    gross = sum(i["chf"] for i in items)
    sub = sum(min(i["subsidy"], i["chf"]) for i in items)
    per_yr = sum(max(i["chf"] - i["subsidy"], 0.0) / max(i["life"], 1.0)
                 for i in items)
    return gross, sub, gross - sub, per_yr


def embodied_kg(items, horizon=CB.HORIZON_Y):
    """Embodied CO2 over the horizon, re-buying anything that wears out inside it."""
    return sum(CB.units_needed(i["life"], horizon) * i["kg"] for i in items)


def embodied_kg_once(items):
    """Embodied CO2 of building it once — the number a CO2 payback is measured against."""
    return sum(i["kg"] for i in items)


def aux_watts(items):
    """Permanent electric load the measures add (MVHR fans)."""
    return sum(i["aux_w"] for i in items)


# ----------------------------------------------------------------------------- balance
def heat_balance(tin, t_out, cond, gains, t0=5.0):
    """Annual heat balance (kWh), losses split by envelope element.

    `gains` maps a label to an hourly W array (heating, sun, occupants). Losses
    use the indoor temperature at the *start* of each hour, which is exactly what
    model.simulate() integrates, so gains − losses closes on the heat left stored
    in the structure (returned as `storage`, normally a few kWh out of thousands).

    Sums are signed and annual: an element that gains heat on a hot afternoon is
    netted against what it loses the rest of the year.
    """
    tin = np.asarray(tin, float)
    t_prev = np.concatenate(([t0], tin[:-1]))
    dtemp = t_prev - np.asarray(t_out, float)
    loss_w = {k: h * dtemp for k, h in cond.items()}
    losses = {k: float(v.sum()) / 1000.0 for k, v in loss_w.items()}
    gains_kwh = {k: float(np.sum(v)) / 1000.0 for k, v in gains.items()}
    return dict(losses=losses, gains=gains_kwh, loss_w=loss_w,
                storage=sum(gains_kwh.values()) - sum(losses.values()))


if __name__ == "__main__":
    ar = element_areas()
    fab0 = base_fabric()
    c0 = conductances(fab0, ar)
    h0 = sum(c0.values())
    print(f"as built:  H = {h0:.1f} W/K")
    for k, v in c0.items():
        area = ar[ELEMENT_SPEC[k][0]] if ELEMENT_SPEC[k][0] else float("nan")
        print(f"  {k:<26}{area:6.1f} m²{v:8.1f} W/K{v / h0 * 100:7.1f} %")

    for pkg, names in PACKAGES.items():
        fab = fabric_after(names, fab0)
        c = conductances(fab, ar)
        h = sum(c.values())
        items = measure_items(names, ar, INSULATION_SUBSIDY)
        gross, sub, net, per_yr = capex(items)
        print(f"\n{pkg}:  H = {h:.1f} W/K  ({(1 - h / h0) * 100:.0f} % lower)")
        print(f"  {net:,.0f} CHF net ({gross:,.0f} gross − {sub:,.0f} subsidy), "
              f"{per_yr:,.0f} CHF/yr amortized, "
              f"{embodied_kg_once(items) / 1000:.1f} t CO₂eq embodied, "
              f"+{aux_watts(items):.0f} W permanent load")
        for k, v in c.items():
            print(f"  {k:<26}{v:8.1f} W/K{v / h * 100:7.1f} %")
