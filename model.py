"""
Thermal model of a stone farmhouse -- "la Ferme", Saint-Legier, Vaud,
Switzerland.

The building as the federal registers describe it:

    GKLAS  1121     two-dwelling building, GASTW 2 (two full storeys)
    GBAUJ  1966     registered construction year -- see the caveat below
    GAREA  259 m2   registered footprint

Unlike the chalet model this was derived from, the geometry here is *measured*,
not assumed: the footprint comes from the cadastral survey (via OpenStreetMap,
itself traced from the Cartoriviera orthophoto), and the roof pans come from the
federal solar cadastre (sonnendach.ch, layer ch.bfe.solarenergie-eignung-daecher),
which is built from swisstopo LiDAR. The two sources agree on the orientation to
within half a degree.

CAVEAT on GBAUJ 1966: walls of 50-100 cm of rubble stone are not a 1966
construction. For old rural buildings the RegBL year is frequently the year of a
major transformation or simply of first registration. Treat 1966 as "last big
works", not as the age of the fabric.

Data sources (downloaded into ./data/ by `python data/download_data.py`):
- horizon.json  : PVGIS DEM-calculated horizon profile (terrain shading)
- tmy.json      : PVGIS Typical Meteorological Year, hourly (T, DNI, DHI, GHI, wind)
- archive.json  : Open-Meteo ERA5 daily mean temperature 2015-2025
- climate.json  : Open-Meteo CMIP6-HighRes daily mean temperature 2026-2050 (3 models)
- climate_minmax.json : same source, daily max/min -> separate day & night warming trends

Terrain: 601 m, gentle slope ~13.7 % falling to the north-north-west
(swisstopo swissALTI3D, 4-point gradient on a 200 m baseline).

Orientation: the ridge runs WNW-ESE at 116 deg, so the two pans face
NNE (26 deg) and SSW (206 deg) -- the building sits about 26 deg off the
cardinal grid. The occupant's "south / east / west" facades are therefore at
206 / 116 / 296 deg; the "north" facade (26 deg) is blind, the big NNE roof pan
sweeping down over it.
"""

import json
import math
import os
import numpy as np

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# ----------------------------------------------------------------------------- site
LAT = 46.4820            # deg N, site
LON = 6.8777             # deg E
ALT = 601.0              # m, swisstopo swissALTI3D at the parcel
TERRAIN_SLOPE_E = 0.0765  # dz/dx toward east  (590.5 -> 605.8 m over 200 m: rises east)
TERRAIN_SLOPE_N = -0.1135 # dz/dy toward north (614.3 -> 591.6 m over 200 m: falls north)

# ----------------------------------------------------------------------------- geometry
# The building is rotated 26 deg off the cardinal grid. To keep the rest of the
# model (and the 3D scene) working in a simple local frame, the "long/short"
# axes below are expressed in the *building's own* frame:
#   LEN_RIDGE  runs along the ridge   (azimuth 116 / 296 deg, WNW-ESE)
#   LEN_SLOPE  runs across the ridge  (azimuth  26 / 206 deg, NNE-SSW)
# Measured off the cadastral footprint: a near-rectangle of
# 14.82 m x 15.53 m = 230 m2. RegBL registers 259 m2, the difference being an
# annex or the eaves overhang; the thermal envelope uses the measured rectangle.
LEN_RIDGE = 14.82                  # m, along the ridge
LEN_SLOPE = 15.53                  # m, across the ridge (the pans span this)
LEN_NS, LEN_EW = LEN_SLOPE, LEN_RIDGE   # back-compat aliases for the 3D scene
EAVES_H = 6.0                      # m, two full storeys (GASTW = 2) + floor build-up
ROOF_PITCH = math.radians(27.5)    # sonnendach: 27 deg NNE pan, 28 deg SSW pan
RIDGE_H = EAVES_H + (LEN_SLOPE / 2) * math.tan(ROOF_PITCH)   # 10.04 m

# Facade azimuths (compass deg, N=0 E=90). The occupant's cardinal names map onto
# the rotated building as follows -- these are what the solar gain calculation uses.
AZ_S = 206.0                       # "south"  facade (SSW)
AZ_E = 116.0                       # "east"   facade (ESE)
AZ_W = 296.0                       # "west"   facade (WNW)
AZ_N = 26.0                        # "north"  facade (NNE) -- blind, no windows

# ASSUMPTION, most important one in the file: how much of the building is heated.
# Two storeys inside walls that are ~0.7 m thick leave ~190 m2 of usable floor
# each. Set FLOOR_AREA/VOLUME to the part actually kept warm -- if a barn or
# grange section is cold, cut these down and the whole model follows.
FLOOR_AREA = 380.0                 # m2 heated (2 storeys, interior of the thick walls)
VOLUME = 1000.0                    # m3 heated

# Windows, as surveyed by the owner. None on the north facade.
# South and west were replaced within the last ~5 years, east ~20 years ago.
A_WIN_S = 8.0                      # m2 "south" facade (206 deg)
A_WIN_W = 7.0                      # m2 "west"  facade (296 deg)
A_WIN_E = 6.0                      # m2 "east"  facade (116 deg)
A_WIN = A_WIN_S + A_WIN_W + A_WIN_E                        # 21.0 m2

# Where the glazing actually sits, as surveyed. One definition, consumed by the
# 3D scene, the plotly scene and the facade elevations, so the three cannot drift:
#   south -- one big central opening on the ground floor, one on the first floor
#            towards the west end
#   west  -- three per floor, evenly spread, on both floors
#   east  -- five in a single row (assumed ground floor; move WIN_SILL_GF ->
#            WIN_SILL_1F below if the row is actually upstairs)
#   north -- none
WIN_SILL_GF, WIN_SILL_1F = 1.0, 4.0        # m, two storeys at 3.0 m floor-to-floor


def window_layout():
    """{facade: [(offset along the facade, sill, width, height)]}, metres.

    `offset` is measured from the middle of that facade. Areas reproduce
    A_WIN_S / A_WIN_W / A_WIN_E to within a few cm2.
    """
    half_r, half_s = LEN_RIDGE / 2, LEN_SLOPE / 2
    return {
        "S": [(0.0, 0.9, 2.4, 2.08),                       # big central, ground
              (-half_r + 3.2, WIN_SILL_1F, 1.7, 1.76)],    # first floor, west end
        "W": [(o, z, 1.1, 1.06)
              for z in (WIN_SILL_GF, WIN_SILL_1F)
              for o in np.linspace(-half_s + 2.2, half_s - 2.2, 3)],
        "E": [(o, WIN_SILL_GF, 1.1, 1.1)
              for o in np.linspace(-half_s + 2.0, half_s - 2.0, 5)],
        "N": [],
    }


# Wall, broken out per facade. The ridge runs at 116/296 deg, so the two long
# eaves facades face "north" (26) and "south" (206) and are LEN_RIDGE wide; the
# two gable ends face "east" (116) and "west" (296), are LEN_SLOPE wide and each
# carry a gable triangle up to the ridge. Windows come off their own facade.
STOREY_H = 3.0                                             # m floor-to-floor
A_GABLE_TRI = 0.5 * LEN_SLOPE * (RIDGE_H - EAVES_H)        # 31.4 m2 per gable
A_WALL_N = LEN_RIDGE * EAVES_H                             # 88.9 m2, blind
A_WALL_S = LEN_RIDGE * EAVES_H - A_WIN_S                   # 80.9 m2
A_WALL_E = LEN_SLOPE * EAVES_H + A_GABLE_TRI - A_WIN_E     # 118.6 m2
A_WALL_W = LEN_SLOPE * EAVES_H + A_GABLE_TRI - A_WIN_W     # 117.6 m2
A_WALL = A_WALL_N + A_WALL_S + A_WALL_E + A_WALL_W         # = 405.9 m2 as before

# Where the internal lining is (owner, tentative -- "it's possible there is
# insulation"): the WHOLE west gable, and the EAST gable's ground floor only.
# North and south are bare stone over their full height. The east row of windows
# sits on the ground floor (see window_layout), so it comes out of the lined part.
A_WALL_E_GF = LEN_SLOPE * STOREY_H - A_WIN_E               # 40.6 m2 lined
A_WALL_E_UP = A_WALL_E - A_WALL_E_GF                       # 78.0 m2 bare (1F + gable)
A_WALL_LINED = A_WALL_W + A_WALL_E_GF                      # 158.1 m2  (39 %)
A_WALL_BARE = A_WALL_N + A_WALL_S + A_WALL_E_UP            # 247.8 m2  (61 %)

# --------------------------------------------------------------- cut into the slope
# The parcel falls 13.7 % to the north-north-west, and the building is dug into
# it: the owner describes two storeys, "~3 in the middle where the roof is
# highest, the rest below ground". A wall against earth is not a wall against
# air -- it sees ground temperature, which at 1-3 m depth barely drops below
# ~8-10 degC while the design air temperature is -8.
#
# Defaults below are DERIVED, not measured: take the swissALTI3D gradient already
# in this file, put the lowest floor at the downhill (NW) grade, and read off how
# deep each facade sits. The uphill SE corner then has 2.8 m buried and the
# downhill NW corner none, which is exactly the "2 storeys, 3 in the middle"
# the owner describes. Override the four numbers once someone measures them.
def _ground_drop(az_deg, dist):
    """Ground level at a facade midpoint vs the building centre, m (+ = uphill)."""
    a = math.radians(az_deg)
    return dist * (math.cos(a) * TERRAIN_SLOPE_N + math.sin(a) * TERRAIN_SLOPE_E)

_Z_LOW = (_ground_drop(26.0, LEN_SLOPE / 2)                # NW corner, the low point
          + _ground_drop(296.0, LEN_RIDGE / 2))
BURIED_N = _ground_drop(26.0, LEN_SLOPE / 2) - _Z_LOW      # 0.88 m
BURIED_S = _ground_drop(206.0, LEN_SLOPE / 2) - _Z_LOW     # 1.94 m
BURIED_E = _ground_drop(116.0, LEN_RIDGE / 2) - _Z_LOW     # 2.29 m
BURIED_W = _ground_drop(296.0, LEN_RIDGE / 2) - _Z_LOW     # 0.53 m
# SIA 380/1 reduction factor for a wall in contact with earth. Ground at depth is
# far milder than winter air; 0.5 is the usual figure for a shallow basement wall.
B_GROUND = 0.5
A_FOOTPRINT = LEN_RIDGE * LEN_SLOPE                        # 230.2 m2
A_ROOF = A_FOOTPRINT / math.cos(ROOF_PITCH)                # 259.4 m2 of roof plane
A_ROOF_PAN = A_ROOF / 2
A_FLOOR = A_FOOTPRINT                                      # 230.2 m2 on the cellar

# Roof windows (owner): four Velux, 0.7 m2 each, changed around 2010, two per pan.
# They matter twice over -- as a small hole in the best-insulated surface, and as
# the only glazing this building has that faces anywhere near the sky, so their
# solar gain per m2 beats any of the vertical facades.
A_VELUX_1 = 0.7                    # m2 each
N_VELUX_SSW = 2                    # on the 206 deg pan
N_VELUX_NNE = 2                    # on the 26 deg pan
A_VELUX_SSW = N_VELUX_SSW * A_VELUX_1                      # 1.4 m2
A_VELUX_NNE = N_VELUX_NNE * A_VELUX_1                      # 1.4 m2
A_VELUX = A_VELUX_SSW + A_VELUX_NNE                        # 2.8 m2
A_ROOF_OPAQUE = A_ROOF - A_VELUX                           # 256.6 m2 of insulated roof

# Roof surfaces available to PV, measured by the federal solar cadastre
# (sonnendach.ch / swisstopo LiDAR). These are the *real* pans, bigger than the
# heated footprint because the roof overhangs and extends over the annexes.
A_PAN_SSW = 147.05                 # m2, azimuth 206 deg, 28 deg pitch, class "good"
A_PAN_NNE = 211.47                 # m2, azimuth  26 deg, 27 deg pitch, class "medium"

# sonnendach's own independent estimates for this building, kept as a cross-check
# on this model rather than as an input to it:
SONNENDACH_HEAT_KWH = 59036.0      # kWh/yr space heating
SONNENDACH_DHW_KWH = 7632.0        # kWh/yr hot water
SONNENDACH_HDD = 3197.0            # K.d/yr heating degree days at the site
SONNENDACH_PV_SSW = 24352.0        # kWh/yr if the SSW pan were fully covered
SONNENDACH_PV_NNE = 31229.0        # kWh/yr if the NNE pan were fully covered

# ----------------------------------------------------------------- THE MEASURED ANCHOR
# The only hard numbers in this file. Everything above is derived from registers,
# LiDAR and standard tables; this is what the building actually burns, from the
# owner. The boiler makes the hot water as well, so the oil covers both loads,
# and the whole building is kept warm -- there is no cold wing to hide demand in.
# A wood stove runs alongside it, but only 2-3 steres, which is 280-420 L of
# oil-equivalent: real, and far too small to explain the gap on its own.
#
# Together they disagree with both this model and sonnendach by a factor of ~2,
# and the disagreement is NOT resolvable by tuning: see calibration_report() and
# lining_thickness_sweep(). Run those before trusting any absolute number
# downstream -- the design load, the heat-pump sizing and every payback in
# renovation.py all scale with it.
MEASURED_OIL_L = (3500.0, 4500.0)     # litres/yr, heating + DHW (owner)
MEASURED_WOOD_STERE = (2.0, 3.0)      # steres/yr burnt alongside (owner)
MEASURED_MID_L = sum(MEASURED_OIL_L) / 2

# ----------------------------------------------------------------------------- fabric
# Wall: rubble stone masonry, 50-100 cm, NO insulation. lambda for natural stone
# masonry with mortar joints ~1.7 W/mK (SIA 279 / DIN 4108 range 1.4-2.3).
# Thickness varies around the building; 0.70 m is the working average.
WALL_THICK = 0.70    # m of stone (owner: "50 cm to 1 m")
WALL_LAMBDA = 1.7    # W/mK, rubble stone masonry
U_WALL_BARE = 1 / (0.13 + WALL_THICK / WALL_LAMBDA + 0.04)   # 1.72 W/m2K
# The lined facades (full west + east ground floor). Thickness is NOT known --
# the owner reports the lining exists, not what is in it. 6 cm of mineral wool
# plus a plasterboard skin is the middle of what a Swiss doublage of the 1966
# transformation era would be; WALL_INSUL is the single knob to turn once someone
# opens a reveal. 4 cm gives U 0.60, 8 cm gives U 0.37, 12 cm gives U 0.27.
WALL_INSUL = 0.06    # m of mineral wool behind the lining
U_WALL_LINED = 1 / (0.13 + WALL_THICK / WALL_LAMBDA + WALL_INSUL / 0.038
                    + 0.013 / 0.25 + 0.04)                   # 0.45 W/m2K
# Area-weighted mean, kept so the dashboard, renovation.py and the plots that
# still think of "the wall" as one surface keep working.
U_WALL = (A_WALL_BARE * U_WALL_BARE + A_WALL_LINED * U_WALL_LINED) / A_WALL
# Roof redone ~2000, so insulated to the standard of the day (SIA 380/1 1988/2001
# asked ~0.25 W/m2K for roofs): ~14 cm mineral wool + boarding.
ROOF_INSUL = 0.14    # m of mineral wool
U_ROOF = 1 / (0.10 + 0.03 / 0.13 + ROOF_INSUL / 0.038 + 0.04)  # 0.25 W/m2K
# Windows are NOT all the same age -- south and west replaced within ~5 years
# (modern insulating double/triple glazing), east ~20 years ago (2000s double
# glazing with a first-generation low-e coating). Whole-window U incl. frame.
U_WIN_S = 1.1        # replaced < 5 y
U_WIN_W = 1.1        # replaced < 5 y
U_WIN_E = 1.6        # replaced ~20 y
U_WIN = (A_WIN_S * U_WIN_S + A_WIN_W * U_WIN_W
         + A_WIN_E * U_WIN_E) / A_WIN                        # 1.24 area-weighted
# Velux changed ~2010 and described as well insulated: that is the GGL/GGU
# generation with --59 or --60 double glazing, whole-window U around 1.3 incl.
# frame. Roof windows never reach facade-window numbers -- the frame is a bigger
# fraction of a 0.7 m2 unit, and the sash sits in the insulation plane.
U_VELUX = 1.3        # W/m2K, whole roof window incl. frame
G_VELUX = 0.60       # slightly clearer than the newest facade glazing
G_WIN = 0.55         # solar factor: modern coated glazing passes less than old clear glass
WIN_EFF = 0.70 * 0.9 # frame fraction x dirt/curtain factor on solar gains
VELUX_EFF = 0.65 * 0.85  # smaller units: more frame, and roof glass soils faster
U_FLOOR = 0.8        # timber/vaulted floor over an unheated cellar
B_FLOOR = 0.6        # SIA reduction factor: cellar/ground is milder than outside
# Massive masonry is fairly airtight in itself; the leaks are at the roof, the
# floor junctions and the old east windows. New windows on two facades help.
ACH = 0.55           # air changes per hour

def wall_conductance(buried=None, b_ground=B_GROUND, u_bare=None, u_lined=None,
                     detail=False):
    """W/K through the four facades, splitting each into air-facing and buried.

    The buried strip is always at the BASE of a facade, so on the west (lined
    full height) and the east (lined on the ground floor) the buried part is
    lined; on the blind north and the south it is bare stone.

    `buried` is (N, S, E, W) metres below grade; None uses the DEM-derived
    defaults. Areas are net of glazing, and burial is capped at the rectangular
    part of the facade so a gable triangle is never "underground".
    """
    n, s, e, wst = (BURIED_N, BURIED_S, BURIED_E, BURIED_W) if buried is None else buried
    ub = U_WALL_BARE if u_bare is None else u_bare
    ul = U_WALL_LINED if u_lined is None else u_lined
    rows = (  # width, net area, depth, U of the base zone
        ("N", LEN_RIDGE, A_WALL_N, n, ub),
        ("S", LEN_RIDGE, A_WALL_S, s, ub),
        ("E", LEN_SLOPE, A_WALL_E, e, ul),      # east base is the lined ground floor
        ("W", LEN_SLOPE, A_WALL_W, wst, ul),    # west is lined full height
    )
    out, h = {}, 0.0
    for name, width, a_net, depth, u_base in rows:
        a_bur = min(max(depth, 0.0) * width, width * EAVES_H, a_net)
        # the rest of this facade, at whatever U that facade carries above grade
        if name == "W":
            u_air, a_air = ul, a_net - a_bur
        elif name == "E":
            a_lined_air = max(A_WALL_E_GF - a_bur, 0.0)
            a_air = a_net - a_bur
            u_air = ((a_lined_air * ul + (a_air - a_lined_air) * ub) / a_air
                     if a_air > 0 else ub)
        else:
            u_air, a_air = ub, a_net - a_bur
        contrib = a_air * u_air + a_bur * u_base * b_ground
        out[name] = dict(a_air=a_air, a_buried=a_bur, u_air=u_air, h=contrib)
        h += contrib
    return (h, out) if detail else h


H_WALL = wall_conductance()
H_TRANS = (H_WALL + A_ROOF_OPAQUE * U_ROOF + A_VELUX * U_VELUX
           + A_WIN_S * U_WIN_S + A_WIN_W * U_WIN_W + A_WIN_E * U_WIN_E
           + A_FLOOR * U_FLOOR * B_FLOOR)                    # W/K
H_VENT = ACH * VOLUME * 0.34                                 # W/K
H_TOT = H_TRANS + H_VENT                                     # ~1090 W/K

# Heavy masonry, uninsulated and therefore fully accessible from inside: the
# inner ~12 cm of stone follows the daily cycle, plus floors and partitions.
# ~0.13 kWh/m2K of floor area, the SIA 380/1 "heavy" class.
C_EFF = 50.0 * 3.6e6  # J/K  (50 kWh/K -> time constant ~ 46 h)

# ----------------------------------------------------------------------------- internal gains
# Every watt of electricity used inside the envelope ends up as heat in it, and
# so does every occupant. The old default (250 W) was inherited from a weekend
# chalet and contradicted this model's own electricity assumption: simulate.py
# draws 700 W of plugs while two dwellings are occupied, then the thermal model
# credited only 250 W of gain. SIA 380/1 gives 2.5-5 W/m2 for dwellings; at
# 380 m2 that is 950-1900 W, and the low end of that already exceeds what was
# being used. Broken out so the number is arguable rather than magic:
#     plugs, lighting, fridges, pumps, router   700 W  (= simulate.BASE_W_OCC)
#     occupants, ~4 people at 70 W x presence   200 W
#     cooking, averaged over the day            100 W
#     DHW tank + distribution losses indoors    100 W
Q_INT_OCC = 1100.0   # W while the household is home (2.9 W/m2)
Q_INT_ABS = 300.0    # W while away: fridges, freezer, router, standing tank losses

# ----------------------------------------------------------------------------- energy prices & systems
ELEC_PRICE = 0.29        # CHF/kWh (Romande Energie region, incl. grid & taxes)
FEED_IN = 0.10           # CHF/kWh PV export
WOOD_PRICE_STERE = 150.0 # CHF/stere delivered (Riviera / Haut-Lac)
WOOD_KWH_STERE = 1700.0  # kWh primary per stere (dry hardwood mix)
STOVE_EFF = 0.70
OIL_PRICE_L = 1.15       # CHF/litre delivered, small order
OIL_KWH_L = 10.0         # kWh per litre of heating oil
OIL_EFF = 0.85           # seasonal efficiency of an existing oil boiler

# Design load. H ~1090 W/K against the SIA 384/1 design temperature for this
# altitude in Vaud (-8 degC) gives ~30 kW -- an order of magnitude above the
# chalet this model came from, so every appliance is sized up accordingly.
T_DESIGN = -8.0          # degC
CAP_ELECTRIC = 20000.0   # W (about the most a domestic supply will carry)
CAP_STOVE = 15000.0      # W, large wood stove / cooker
CAP_HP_NOM = 25000.0     # W thermal, air-source (large unit or cascade)
CAP_OIL = 35000.0        # W, existing-style oil boiler
DHW_KWH_DAY = 21.0       # kWh/day hot water (sonnendach: 7 632 kWh/yr for 2 dwellings)

# Pellet boiler: programmable, covers the whole heat load
CAP_PELLET = 30000.0     # W thermal
PELLET_EFF = 0.87        # combustion efficiency
PELLET_KWH_KG = 4.8      # kWh per kg pellets
PELLET_PRICE_KG = 0.48   # CHF/kg (bulk delivery ~480 CHF/t)
PELLET_EL_RUN = 250.0    # W electrical while burning (auger, fans, control)
PELLET_EL_IGN = 800.0    # W electrical during ignition ...
PELLET_IGN_H = 0.25      # ... for 15 minutes at each cold start

# PV on the roof: 425 Wp glass-glass modules, 1.72 x 1.13 m = 1.944 m2.
# Pan areas are the sonnendach/LiDAR measurements; PV_PACKING is the fraction
# actually coverable once ridge, eaves, edges, chimneys and dormers are removed.
PV_MOD_KWP = 0.425
PV_MOD_M2 = 1.72 * 1.13
PV_PACKING = 0.80
PV_MOD_SSW = int(A_PAN_SSW * PV_PACKING / PV_MOD_M2)   # 60 modules
PV_MOD_NNE = int(A_PAN_NNE * PV_PACKING / PV_MOD_M2)   # 87 modules
PV_KWP_SSW = PV_MOD_SSW * PV_MOD_KWP                   # 25.5 kWp on the good pan
PV_KWP_NNE = PV_MOD_NNE * PV_MOD_KWP                   # 37.0 kWp on the big NNE pan
PV_KWP_PAN = PV_KWP_SSW                                # back-compat: "half roof"
PV_PR = 0.80                               # inverter, temp, wiring, soiling avg

# ----------------------------------------------------------------- near-field shading
# THE TREE. A large tree stands off the SOUTH-EAST corner of the house (owner).
# That single object is what the numbers were already pointing at: the PVGIS
# horizon is computed from a DEM, so it sees the terrain (max 16.8 deg here) but
# no vegetation, while sonnendach is built from LiDAR and does. Run this model
# with a bare horizon and the SSW pan gets 1561 kWh/m2/yr against the cadastre's
# measured 1035; the NNE pan gets 1013 against 923. A big relative loss on the
# sunny side and a small one on the diffuse-dominated shady side is exactly what
# one obstruction to the south-east does.
#
# It is modelled as a real object rather than as a flat factor, because how much
# it takes depends on how high you stand: the roof looks over part of the crown,
# the ground-floor east windows sit right behind it. The crown is a sphere; the
# trunk and everything below the crown count as blocked too, which is what a
# free-standing tree with a full canopy actually does.
#
# Size is CALIBRATED so the SSW roof pan loses what sonnendach measures -- see
# `python -c "import model; model.shading_report()"`. Set TREE_ON = False to
# see the unobstructed potential.
TREE_ON = True
TREE_AZ = 161.0        # deg compass: the SE corner, between the 116 and 206 facades
TREE_DIST = 13.0       # m from the centre of the house (~3 m clear of the corner)
TREE_TOP = 21.0        # m above ground -- "massive"
TREE_CROWN_R = 7.0     # m crown radius

# ...and the part the tree does NOT explain.
# Sized as above, the tree reproduces the NNE pan's measured shading almost
# exactly (0.92 computed vs 0.91 measured) but only gets the SSW pan to 0.86
# against a measured 0.66. Growing the tree until the SSW pan matches (25 m tall,
# 9 m crown at 12 m) drags the NNE pan down to 0.76, which contradicts the
# measurement. No single object at the SE corner can do both: shading that hits a
# SSW-facing pan hard while barely touching a NNE-facing one has to sit to the
# SOUTH or SOUTH-WEST, not the south-east.
#
# So something else is out there -- a second tree, a treeline, or a neighbouring
# building to the S/SW. Until someone looks, it lives here as an explicit
# residual on the SSW pan only, anchored on the cadastre measurement:
#     0.66 (measured) / 0.86 (tree alone) = 0.77
# It is deliberately NOT applied to the south windows. If the residual turns out
# to be real vegetation to the south then those windows are over-credited too and
# the heating demand below is optimistic -- but inventing a second factor from no
# evidence would be worse than naming the gap. A photo south from the facade
# settles it.
PV_RESIDUAL_SSW = 0.77

# Viewing heights: what each surface looks out from. This is the whole point of
# modelling the tree geometrically instead of with one factor.
H_VIEW_ROOF = (EAVES_H + RIDGE_H) / 2          # 8.0 m, mid-pan
H_VIEW_WIN_S = 3.1     # m, area-weighted: big ground-floor window + one above
H_VIEW_WIN_W = 3.1     # m, three per floor over two floors
H_VIEW_WIN_E = 1.6     # m, the single ground-floor row -- lowest and closest


def tree_horizon(view_h, az_deg=TREE_AZ, dist=TREE_DIST, top=TREE_TOP,
                 r=TREE_CROWN_R):
    """Elevation (deg) blocked by the tree as seen from height `view_h`, vs azimuth."""
    h_centre = top - r
    def f(a):
        d_az = np.radians((np.asarray(a, float) - az_deg + 180.0) % 360.0 - 180.0)
        perp = dist * np.sin(d_az)                        # sideways miss distance
        along = dist * np.cos(d_az)
        half = np.sqrt(np.clip(r ** 2 - perp ** 2, 0.0, None))   # crown half-height
        el = np.degrees(np.arctan2(h_centre + half - view_h, np.maximum(along, 0.1)))
        return np.where((np.abs(perp) < r) & (along > 0), np.clip(el, 0.0, None), 0.0)
    return f


def horizon_at(dem, view_h):
    """DEM horizon combined with the tree, for a surface looking out from `view_h`."""
    if not TREE_ON:
        return dem
    t = tree_horizon(view_h)
    return lambda a: np.maximum(dem(a), t(a))

def hp_cop(t_out):
    """Air-water heat pump COP vs outdoor temp (datasheet-shaped, conservative).

    Lower than the chalet's air-air split: this building needs radiators or a
    high-temperature distribution, which costs a few tenths of COP.
    """
    return np.clip(2.6 + 0.065 * t_out, 1.6, 4.2)

def hp_capacity(t_out):
    """Thermal capacity derating in deep cold."""
    return CAP_HP_NOM * np.clip(1 + 0.025 * np.minimum(t_out + 7, 0), 0.55, 1.0)

# ============================================================================= weather
def _obs_monthly_means(y0=2015, y1=2025):
    """Observed ERA5 monthly mean T (degC) for the valley, elevation-corrected."""
    with open(os.path.join(DATA, "archive.json")) as f:
        d = json.load(f)["daily"]
    sums = np.zeros(12); cnt = np.zeros(12)
    for t, v in zip(d["time"], d["temperature_2m_mean"]):
        if v is None:
            continue
        y, m = int(t[:4]), int(t[5:7])
        if y0 <= y <= y1:
            sums[m - 1] += v; cnt[m - 1] += 1
    return sums / cnt

def load_tmy():
    """Return dict of hourly arrays (8760): month, day, hour(UTC), t2m, ghi, dni, dhi, wind.

    PVGIS TMY T2m comes from a coarse ERA5 grid cell centred well above the
    valley floor and runs several K too cold. Each month's mean is therefore
    corrected onto the ERA5 elevation-corrected observation for the valley
    (2015-2025); the TMY keeps its hourly structure and its (satellite-based,
    trustworthy) irradiance. Temperatures then represent ~2020 climate.
    """
    with open(os.path.join(DATA, "tmy.json")) as f:
        rows = json.load(f)["outputs"]["tmy_hourly"]
    out = {k: np.empty(len(rows)) for k in
           ("month", "day", "hour", "t2m", "ghi", "dni", "dhi", "wind")}
    for i, r in enumerate(rows):
        ts = r["time(UTC)"]                      # e.g. 20160101:0000
        out["month"][i] = int(ts[4:6])
        out["day"][i] = int(ts[6:8])
        out["hour"][i] = int(ts[9:11])
        out["t2m"][i] = r["T2m"]
        out["ghi"][i] = r["G(h)"]
        out["dni"][i] = r["Gb(n)"]
        out["dhi"][i] = r["Gd(h)"]
        out["wind"][i] = r["WS10m"]
    # day of year (non-leap)
    cum = np.cumsum([0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30])
    out["doy"] = cum[out["month"].astype(int) - 1] + out["day"]
    m = out["month"].astype(int)
    raw_monthly = np.array([out["t2m"][m == k].mean() for k in range(1, 13)])
    out["t2m"] = out["t2m"] + (_obs_monthly_means() - raw_monthly)[m - 1]
    return out

TMY_CENTER_YEAR = 2020.0   # temperatures are anchored on ERA5 obs 2015-2025

def _monthly_year_means(times, values):
    """(12, n_years) array of monthly means and the year vector."""
    years = sorted({int(t[:4]) for t in times})
    yi = {y: j for j, y in enumerate(years)}
    sums = np.zeros((12, len(years))); cnt = np.zeros((12, len(years)))
    for t, v in zip(times, values):
        if v is None:
            continue
        m, j = int(t[5:7]) - 1, yi[int(t[:4])]
        sums[m, j] += v; cnt[m, j] += 1
    return sums / np.maximum(cnt, 1), np.array(years, float)

def monthly_warming_slopes():
    """Per-month linear warming trends (K/yr), CMIP6-HighRes 3-model mean 2026-2050.

    Returns {'mean','day','night'}: 12 monthly slopes each. 'day' fits the daily-max
    series, 'night' the daily-min (days and nights do not warm at the same rate).
    Model bias cancels because only the slope is used; beyond 2050 the linear
    trend is extrapolated.
    """
    with open(os.path.join(DATA, "climate.json")) as f:
        mean_d = json.load(f)["daily"]
    with open(os.path.join(DATA, "climate_minmax.json")) as f:
        mm_d = json.load(f)["daily"]
    out = {}
    for kind, daily, stem in (("mean", mean_d, "temperature_2m_mean"),
                              ("day", mm_d, "temperature_2m_max"),
                              ("night", mm_d, "temperature_2m_min")):
        models = [k for k in daily if k.startswith(stem)]
        per_year = np.mean([_monthly_year_means(daily["time"], daily[k])[0]
                            for k in models], axis=0)
        years = _monthly_year_means(daily["time"], daily[models[0]])[1]
        out[kind] = np.array([np.polyfit(years, per_year[m], 1)[0] for m in range(12)])
    return out

def apply_warming(w, year, slopes=None):
    """Copy of the weather dict with temperatures shifted to `year`'s climate.

    Hours with the sun up get the daytime (daily-max) trend, night hours the
    nighttime (daily-min) trend, month by month. The TMY represents ~2014, so
    even 'now' gets a small positive shift.
    """
    if slopes is None:
        slopes = monthly_warming_slopes()
    el, _ = sun_position(w["doy"], w["hour"])
    m = w["month"].astype(int) - 1
    dt_years = year - TMY_CENTER_YEAR
    delta = np.where(el > 0, slopes["day"][m], slopes["night"][m]) * dt_years
    w2 = dict(w)
    w2["t2m"] = w["t2m"] + delta
    return w2

def day_night_monthly(w):
    """Monthly mean day (sun up) and night temperatures, plus annual means."""
    el, _ = sun_position(w["doy"], w["hour"])
    day = el > 0
    m = w["month"].astype(int)
    t = w["t2m"]
    day_m = np.array([t[(m == k) & day].mean() for k in range(1, 13)])
    night_m = np.array([t[(m == k) & ~day].mean() for k in range(1, 13)])
    return day_m, night_m, float(t[day].mean()), float(t[~day].mean())

# ============================================================================= solar geometry
def sun_position(doy, hour_utc):
    """Solar elevation & compass azimuth (deg, N=0 E=90) for arrays. Mid-hour."""
    n = np.asarray(doy, dtype=float)
    B = 2 * math.pi * (n - 1) / 365.0
    decl = (0.006918 - 0.399912 * np.cos(B) + 0.070257 * np.sin(B)
            - 0.006758 * np.cos(2 * B) + 0.000907 * np.sin(2 * B)
            - 0.002697 * np.cos(3 * B) + 0.00148 * np.sin(3 * B))       # rad
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(B) - 0.032077 * np.sin(B)
                    - 0.014615 * np.cos(2 * B) - 0.04089 * np.sin(2 * B))  # minutes
    tst = np.asarray(hour_utc, dtype=float) + 0.5 + LON / 15.0 + eot / 60.0
    omega = np.radians(15.0 * (tst - 12.0))
    lat = math.radians(LAT)
    sin_el = np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.cos(omega)
    el = np.degrees(np.arcsin(np.clip(sin_el, -1, 1)))
    cos_az = ((np.sin(decl) - sin_el * math.sin(lat))
              / np.maximum(np.cos(np.radians(el)) * math.cos(lat), 1e-9))
    az0 = np.degrees(np.arccos(np.clip(cos_az, -1, 1)))   # 0..180 from north
    az = np.where(omega <= 0, az0, 360.0 - az0)           # morning east, afternoon west
    return el, az

def load_horizon():
    """Horizon elevation (deg) as a function of compass azimuth, callable."""
    with open(os.path.join(DATA, "horizon.json")) as f:
        prof = json.load(f)["outputs"]["horizon_profile"]
    # PVGIS: A=0 south, -90 east, +90 west  ->  compass = A + 180
    az = np.array([(p["A"] + 180.0) % 360.0 for p in prof])
    h = np.array([p["H_hor"] for p in prof])
    order = np.argsort(az)
    az, h = az[order], h[order]
    az = np.concatenate([[az[-1] - 360], az, [az[0] + 360]])   # wrap
    h = np.concatenate([[h[-1]], h, [h[0]]])
    return lambda a: np.interp(np.asarray(a) % 360.0, az, h)

def sky_view_factor(horizon):
    a = np.linspace(0, 360, 361)
    return float(np.mean(np.cos(np.radians(horizon(a))) ** 2))

def poa_irradiance(el, az, dni, dhi, ghi, tilt, surf_az, horizon, svf, albedo):
    """Plane-of-array irradiance W/m2 with horizon masking of the beam (isotropic sky)."""
    elr, tr = np.radians(el), math.radians(tilt)
    cos_inc = (np.sin(elr) * math.cos(tr)
               + np.cos(elr) * math.sin(tr) * np.cos(np.radians(az - surf_az)))
    visible = el > horizon(az)                       # mountains block the beam
    beam = dni * np.clip(cos_inc, 0, None) * visible * (el > 0)
    sky = dhi * (1 + math.cos(tr)) / 2 * svf
    ground = ghi * albedo * (1 - math.cos(tr)) / 2
    return beam + sky + ground

def snow_albedo(month):
    """Ground albedo. At 601 m snow lies only intermittently, a few weeks a year,
    so the winter months get a mild lift rather than the 0.6 of a snow-covered
    alpine village."""
    return np.where(np.isin(month, (12, 1, 2)), 0.3, 0.2)

# ============================================================================= building
def solar_gains(w, horizon, svf, a_win_w=A_WIN_W, a_win_s=A_WIN_S, a_win_e=A_WIN_E,
                g_win=G_WIN, win_eff=WIN_EFF,
                a_velux_s=A_VELUX_SSW, a_velux_n=A_VELUX_NNE,
                g_velux=G_VELUX, velux_eff=VELUX_EFF):
    """Hourly solar heat gain through the glazing, W.

    Three glazed facades, each on its true azimuth rather than a cardinal one:
    "south" 206 deg, "west" 296 deg, "east" 116 deg. The 26 deg rotation is not
    cosmetic -- it shifts the west facade's gain later into the evening and
    swings the east facade round towards the winter sun.

    Plus the four roof windows, which are a different animal: tilted 27-28 deg
    they see most of the sky dome, so even the two on the NNE pan collect real
    diffuse energy, and they look out from mid-pan height where the tree blocks
    much less than it does from a ground-floor sill.
    """
    el, az = sun_position(w["doy"], w["hour"])
    alb = snow_albedo(w["month"])
    q = np.zeros(len(el))
    for area, surf_az, h_view in ((a_win_s, AZ_S, H_VIEW_WIN_S),
                                  (a_win_w, AZ_W, H_VIEW_WIN_W),
                                  (a_win_e, AZ_E, H_VIEW_WIN_E)):
        if area <= 0:
            continue
        hz = horizon_at(horizon, h_view)      # each facade sees its own obstruction
        q += area * poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"], 90,
                                   surf_az, hz, sky_view_factor(hz), alb)
    q *= g_win * win_eff

    qv = np.zeros(len(el))
    hz_roof = horizon_at(horizon, H_VIEW_ROOF)     # same view as the PV pans
    svf_roof = sky_view_factor(hz_roof)
    for area, tilt, surf_az in ((a_velux_s, 28.0, AZ_S),
                                (a_velux_n, 27.0, AZ_N)):
        if area <= 0:
            continue
        qv += area * poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"], tilt,
                                    surf_az, hz_roof, svf_roof, alb)
    return q + qv * g_velux * velux_eff, el, az


def shading_report(w=None, show=True):
    """Annual irradiance on each surface with and without the tree.

    The roof rows carry sonnendach's LiDAR-derived measurement, which is what the
    tree geometry is calibrated against -- if those two columns drift apart, the
    tree in `model.py` no longer matches the tree in the garden.
    """
    w = load_tmy() if w is None else w
    dem = load_horizon()
    svf0 = sky_view_factor(dem)
    el, az = sun_position(w["doy"], w["hour"])
    alb = snow_albedo(w["month"])
    surfaces = (("roof SSW", 28.0, AZ_S, H_VIEW_ROOF, 1035.0),
                ("roof NNE", 27.0, AZ_N, H_VIEW_ROOF, 923.0),
                ("windows S", 90.0, AZ_S, H_VIEW_WIN_S, None),
                ("windows W", 90.0, AZ_W, H_VIEW_WIN_W, None),
                ("windows E", 90.0, AZ_E, H_VIEW_WIN_E, None))
    out = {}
    for name, tilt, sa, h_view, measured in surfaces:
        bare = poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"], tilt, sa,
                              dem, svf0, alb).sum() / 1000.0
        hz = horizon_at(dem, h_view)
        shaded = poa_irradiance(el, az, w["dni"], w["dhi"], w["ghi"], tilt, sa,
                                hz, sky_view_factor(hz), alb).sum() / 1000.0
        out[name] = dict(bare=bare, shaded=shaded,
                         factor=shaded / bare if bare else 1.0, measured=measured)
    if show:
        print(f"tree: {TREE_TOP:.0f} m tall, {TREE_CROWN_R:.0f} m crown radius, "
              f"{TREE_DIST:.0f} m from the house centre at {TREE_AZ:.0f} deg "
              f"({'ON' if TREE_ON else 'OFF'})")
        print(f"{'surface':<12}{'view h':>8}{'bare':>9}{'shaded':>9}{'factor':>9}"
              f"{'sonnendach':>12}")
        for name, r in out.items():
            h_view = dict(zip((s[0] for s in surfaces),
                              (s[3] for s in surfaces)))[name]
            m = f"{r['measured']:.0f}" if r["measured"] else "—"
            print(f"{name:<12}{h_view:>7.1f}m{r['bare']:>9.0f}{r['shaded']:>9.0f}"
                  f"{r['factor']:>9.2f}{m:>12}")
    return out

def simulate(w, q_solar, occupied, setpoint_occ=20.0, setpoint_abs=None,
             capacity=None, preheat_h=12, t0=5.0,
             h_tot=None, c_eff=None, q_int_occ=Q_INT_OCC, q_int_abs=Q_INT_ABS):
    """Single-node RC simulation over the year.

    occupied     : bool array (8760)
    setpoint_abs : frost-guard setpoint when absent (None = no heating when absent)
    capacity     : heater capacity in W (scalar or array), None = unlimited
    h_tot, c_eff : override the module-level fabric constants (for the dashboard)
    Returns dict with indoor temp and heating power arrays.
    """
    H = H_TOT if h_tot is None else h_tot
    C = C_EFF if c_eff is None else c_eff
    n = len(q_solar)
    dt = 3600.0
    tin = np.empty(n); q_heat = np.zeros(n)
    t = t0
    # pre-heat: allow comfort setpoint a few hours before arrival
    occ_pre = occupied.copy()
    idx = np.where(occupied)[0]
    for i in idx:
        occ_pre[max(0, i - preheat_h):i] = True
    q_int = np.where(occupied, q_int_occ, q_int_abs)   # people/cooking vs standby
    cap = np.broadcast_to(np.asarray(capacity if capacity is not None else np.inf), (n,))
    for i in range(n):
        gain = q_solar[i] + q_int[i]
        t_free = t + dt / C * (gain - H * (t - w["t2m"][i]))
        sp = setpoint_occ if occ_pre[i] else setpoint_abs
        if sp is not None and t_free < sp:
            need = (sp - t_free) * C / dt
            q_heat[i] = min(need, cap[i])
            t_free += q_heat[i] * dt / C
        t = t_free
        tin[i] = t
    return {"tin": tin, "q_heat": q_heat}

def simulate_offgrid(w, q_solar, occupied, pv_w, aux_w,
                     setpoint_occ=20.0, setpoint_abs=None, capacity=None,
                     heat_mode="direct", cop_arr=None, hpcap_arr=None,
                     batt_kwh=10.0, p_max=3000.0, eff=0.92,
                     preheat_h=12, t0=5.0, h_tot=None, c_eff=None,
                     q_int_occ=Q_INT_OCC, q_int_abs=Q_INT_ABS,
                     pel_run=PELLET_EL_RUN, pel_ign=PELLET_EL_IGN,
                     pel_ign_h=PELLET_IGN_H):
    """Coupled thermal + PV/battery simulation with NO grid connection.

    heat_mode: 'none'        heat needs no electricity (wood stove)
               'direct'      electric heating, 1 kWh el = 1 kWh heat
               'hp'          heat pump (cop_arr, hpcap_arr) + resistance backup
               'direct_away' stove when present, electric frost guard when away
                             (only the away part needs power)
               'pellet'      pellet stove: fuel gives the heat, but the electronics
                             need PELLET_EL_RUN while burning plus an ignition
                             surge (PELLET_EL_IGN for PELLET_IGN_H) at each start;
                             without that power the stove will not light
    aux_w : non-heating electric load (plugs + DHW), served FIRST; shedding it
            does not affect temperature. Heating gets the remaining power.
    Surplus PV charges the battery; the rest is curtailed (no export).
    Returns dict: tin, q_heat (delivered), ser (hourly W arrays: pv_direct,
    batt_charge, batt_discharge, curtailed, unserved_aux, unserved_heat_el,
    heat_el, soc).
    """
    H = H_TOT if h_tot is None else h_tot
    C = C_EFF if c_eff is None else c_eff
    n = len(q_solar)
    dt = 3600.0
    occ_pre = occupied.copy()
    for i in np.where(occupied)[0]:
        occ_pre[max(0, i - preheat_h):i] = True
    q_int = np.where(occupied, q_int_occ, q_int_abs)
    cap = np.broadcast_to(np.asarray(capacity if capacity is not None else np.inf), (n,))
    sq = math.sqrt(eff)
    batt = batt_kwh * 1000.0
    soc = 0.0
    tin = np.empty(n); q_heat = np.zeros(n)
    ser = {k: np.zeros(n) for k in
           ("pv_direct", "batt_charge", "batt_discharge", "curtailed",
            "unserved_aux", "unserved_heat_el", "heat_el", "soc")}
    t = t0
    burning = False          # pellet stove state, for ignition-surge accounting
    for i in range(n):
        pv = pv_w[i]
        dis_budget = p_max
        # --- non-heating load first
        aux = aux_w[i]
        direct = min(pv, aux)
        pv -= direct
        dis = min((aux - direct) / sq, dis_budget, soc)
        soc -= dis; dis_budget -= dis
        ser["pv_direct"][i] += direct
        ser["batt_discharge"][i] += dis * sq
        ser["unserved_aux"][i] = aux - direct - dis * sq
        # --- thermal free-float and heating need
        gain = q_solar[i] + q_int[i]
        t_free = t + dt / C * (gain - H * (t - w["t2m"][i]))
        sp = setpoint_occ if occ_pre[i] else setpoint_abs
        need = 0.0
        if sp is not None and t_free < sp:
            need = min((sp - t_free) * C / dt, cap[i])
        # electricity that heat requires
        stove_hour = heat_mode == "none" or (heat_mode == "direct_away" and occ_pre[i])
        pellet_hour = heat_mode == "pellet"
        if stove_hour:
            e_req = 0.0
        elif pellet_hour:
            # auxiliaries only: running draw + ignition surge if it must (re)light
            e_req = (pel_run + (0.0 if burning else (pel_ign - pel_run) * pel_ign_h)
                     ) if need > 0 else 0.0
        elif heat_mode == "hp":
            need = min(need, hpcap_arr[i])   # HP thermal cap; no resistance backup off-grid
            e_req = need / cop_arr[i]
        else:
            e_req = need
        # serve heating with what remains
        heat = need if stove_hour else 0.0
        if e_req > 0:
            direct = min(pv, e_req)
            pv -= direct
            dis = min((e_req - direct) / sq, dis_budget, soc)
            soc -= dis; dis_budget -= dis
            e_served = direct + dis * sq
            if pellet_hour:
                # the burner is all-or-nothing: no auxiliary power, no fire
                lit = e_served >= e_req - 1e-6
                heat = need if lit else 0.0
                burning = lit
            else:
                heat = need * (e_served / e_req)
            ser["pv_direct"][i] += direct
            ser["batt_discharge"][i] += dis * sq
            ser["heat_el"][i] = e_served
            ser["unserved_heat_el"][i] = e_req - e_served
        elif pellet_hour:
            burning = False          # no heat demand this hour: the burner shuts down
        # surplus PV -> battery, rest curtailed
        chg = min(pv, p_max, (batt - soc) / sq)
        soc += chg * sq
        ser["batt_charge"][i] = chg
        ser["curtailed"][i] = pv - chg
        ser["soc"][i] = soc
        q_heat[i] = heat
        t = t_free + heat * dt / C
        tin[i] = t
    return {"tin": tin, "q_heat": q_heat, "ser": ser}

def measured_useful_kwh():
    """(low, high) kWh/yr of useful heat the owner actually buys: oil + wood.

    Expressed as one number so the model has a single target to hit, and in
    oil-equivalent litres so it is comparable with scenario O.
    """
    lo = MEASURED_OIL_L[0] * OIL_EFF * OIL_KWH_L + MEASURED_WOOD_STERE[0] * WOOD_KWH_STERE * STOVE_EFF
    hi = MEASURED_OIL_L[1] * OIL_EFF * OIL_KWH_L + MEASURED_WOOD_STERE[1] * WOOD_KWH_STERE * STOVE_EFF
    return lo, hi


def lining_thickness_sweep(show=True):
    """How much insulation on the LINED facades would it take to match the bill?

    Answer: none is enough. The lined facades (full west gable + east ground
    floor) are 158 of 406 m2 of wall, and the wall is only part of H. Sweep the
    thickness from nothing to infinity and the model moves 9900 -> 7340 L, never
    reaching the 3800-4900 L the owner actually burns. The insulation thickness
    is therefore NOT the unknown -- the gap is somewhere else entirely.
    """
    import simulate as S
    w = load_tmy(); hz = load_horizon(); svf = sky_view_factor(hz)
    q_sol, _, _ = solar_gains(w, hz, svf)
    occ = S.occupancy(w)
    dhw = DHW_KWH_DAY * 365
    h_rest = H_TOT - A_WALL_LINED * U_WALL_LINED      # all but the lined facades
    lo, hi = measured_useful_kwh()

    def u_of(cm):
        if cm is None:
            return 0.0
        if cm <= 0:
            return U_WALL_BARE
        return 1 / (0.13 + WALL_THICK / WALL_LAMBDA + (cm / 100) / 0.038
                    + 0.013 / 0.25 + 0.04)

    out = {}
    if show:
        print(f"lined facades: {A_WALL_LINED:.1f} m2 "
              f"(full west gable + east ground floor)")
        print(f"{'insul':>8}{'U':>8}{'H W/K':>8}{'kWh':>9}{'L oil-eq':>10}")
    for cm in (0, 2, 4, 6, 8, 10, 12, 16, 20, 30, 50, None):
        u = u_of(cm)
        H = h_rest + A_WALL_LINED * u
        o = simulate(w, q_sol, occ, setpoint_occ=20.0, setpoint_abs=16.0,
                     capacity=1e9, h_tot=H)
        q = S.kwh(o["q_heat"])
        out[cm] = dict(u=u, H=H, kwh=q, litres=(q + dhw) / (OIL_EFF * OIL_KWH_L))
        if show:
            lbl = "none" if cm == 0 else ("U=0" if cm is None else f"{cm} cm")
            print(f"{lbl:>8}{u:>8.3f}{H:>8.0f}{q:>9.0f}"
                  f"{out[cm]['litres']:>10.0f}")
    if show:
        floor = out[None]["litres"]
        print()
        print(f"target incl. wood: {lo / (OIL_EFF * OIL_KWH_L):.0f}-"
              f"{hi / (OIL_EFF * OIL_KWH_L):.0f} L oil-equivalent")
        print(f"even at U=0 the model sits at {floor:.0f} L, "
              f"{floor / (hi / (OIL_EFF * OIL_KWH_L)):.1f}x the top of the band.")
        print("=> no thickness on these facades can close it.")
    return out


def calibration_report(show=True):
    """Model vs the owner's actual oil bill, and what would have to be true to close it.

    This is the check that matters. The building burns 3500-4500 L/yr for heating
    AND hot water, with the whole envelope kept warm. The model says ~9900 L. The
    table below solves, for a given comfort assumption, the wall U-value the bill
    demands -- and that is where the story falls apart: a bare 70 cm rubble wall
    cannot be below ~0.8 W/m2K, yet the bill asks for 0.0-0.4. The gap is not in
    the arithmetic, it is in one of the physical premises.
    """
    import simulate as S                       # local: simulate imports model
    w = load_tmy(); hz = load_horizon(); svf = sky_view_factor(hz)
    q_sol, _, _ = solar_gains(w, hz, svf)
    occ = S.occupancy(w)
    dhw = DHW_KWH_DAY * 365
    # Everything except the 248 m2 of bare stone, which is the one big unknown
    # left: the lined facades are credited at U_WALL_LINED throughout.
    non_bare = H_TOT - A_WALL_BARE * U_WALL_BARE

    def q_of(H, sp, sb):
        o = simulate(w, q_sol, occ, setpoint_occ=sp, setpoint_abs=sb,
                     capacity=1e9, h_tot=H)
        return S.kwh(o["q_heat"])

    grid = np.arange(150.0, 1250.0, 50.0)
    out = {}
    litres_now = (q_of(H_TOT, 20, 16) + dhw) / (OIL_EFF * OIL_KWH_L)
    if show:
        print(f"measured   {MEASURED_OIL_L[0]:.0f}-{MEASURED_OIL_L[1]:.0f} L/yr "
              f"(heating + DHW, whole building warm)")
        print(f"model      {litres_now:.0f} L/yr   ratio {litres_now / MEASURED_MID_L:.1f}x")
        print(f"sonnendach {(SONNENDACH_HEAT_KWH + SONNENDACH_DHW_KWH) / (OIL_EFF * OIL_KWH_L):.0f} L/yr"
              f"   ratio {(SONNENDACH_HEAT_KWH + SONNENDACH_DHW_KWH) / (OIL_EFF * OIL_KWH_L) / MEASURED_MID_L:.1f}x")
        print()
        print(f"lined  {A_WALL_LINED:6.1f} m2 at U {U_WALL_LINED:.2f}  (west gable + east ground floor)")
        print(f"bare   {A_WALL_BARE:6.1f} m2 at U {U_WALL_BARE:.2f}  (north + south + east upper)")
        print()
        print(f"solving for the BARE stone, lining held at {U_WALL_LINED:.2f}:")
        print(f"{'mean indoor':<14}{'litres':>9}{'H needed':>10}{'U_bare needed':>15}"
              f"{'plausible?':>12}")
    for sp, sb, lbl in ((20.0, 16.0, "20 / 16 C"), (19.0, 15.0, "19 / 15 C"),
                        (18.0, 15.0, "18 / 15 C"), (17.0, 14.0, "17 / 14 C")):
        qs = np.array([q_of(H, sp, sb) for H in grid])
        row = {}
        for L in MEASURED_OIL_L:
            H = float(np.interp(L * OIL_EFF * OIL_KWH_L - dhw, qs, grid))
            row[L] = dict(H=H, u_bare=(H - non_bare) / A_WALL_BARE)
        out[lbl] = row
        if show:
            for L in MEASURED_OIL_L:
                r = row[L]
                ok = "yes" if r["u_bare"] >= 0.8 else "NO"
                print(f"{lbl if L == MEASURED_OIL_L[0] else '':<14}{L:>9.0f}"
                      f"{r['H']:>10.0f}{r['u_bare']:>15.2f}{ok:>12}")
    if show:
        print()
        print(f"a bare 70 cm rubble wall is 1.2-1.7 W/m2K; 'plausible' needs >= 0.8.")
        print(f"rows marked NO cannot be reached by any bare-stone value, so a")
        print(f"premise other than the wall is still wrong.")
    return out


if __name__ == "__main__":
    print(f"H_trans={H_TRANS:.0f} W/K  H_vent={H_VENT:.0f} W/K  H_tot={H_TOT:.0f} W/K")
    print(f"U wall={U_WALL:.2f} roof={U_ROOF:.2f}  A wall={A_WALL:.0f} roof={A_ROOF:.0f} m2"
          f" ({A_ROOF_PAN:.1f} per pan)")
    print(f"time constant = {C_EFF / H_TOT / 3600:.0f} h")
    w = load_tmy()
    hz = load_horizon()
    print(f"SVF = {sky_view_factor(hz):.2f}")
    s = monthly_warming_slopes()
    for k in ("mean", "day", "night"):
        print(f"warming slope {k:>5}: annual {np.mean(s[k]) * 10:.2f} K/decade, "
              f"monthly K/decade {np.round(s[k] * 10, 2)}")
