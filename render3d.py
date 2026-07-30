"""3D scene: the farmhouse (two storeys under a 27.5 deg gable), the sloping
terrain, the local horizon as a grey wall on a sky dome, and sun paths for the
solstices and equinox (gold where visible, grey-dashed where blocked by terrain).

NOTE: drawn in the building's own frame, ridge along the x axis. The real
building is rotated 26 deg off the cardinal grid -- model.py uses the true
azimuths, this drawing does not rotate the terrain with it.

Run `python render3d.py --show` for an interactive window.
"""
import sys
import numpy as np
import math
import os
import matplotlib
if "--show" not in sys.argv:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import model as M

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

R = 20.0                       # sky-dome radius, m
EAVES, RIDGE = M.EAVES_H, M.RIDGE_H
hz = M.load_horizon()

# x = east, y = north, z = up; house footprint x in [-3,3], y in [-5,5]
fig = plt.figure(figsize=(11, 8.5), facecolor="#fcfcfb")
ax = fig.add_subplot(111, projection="3d", computed_zorder=False)
ax.set_facecolor("#fcfcfb")

# ---------------- terrain (21.5 % slope up to the east)
g = np.linspace(-R, R, 30)
X, Y = np.meshgrid(g, g)
Z = M.TERRAIN_SLOPE_E * X + M.TERRAIN_SLOPE_N * Y
Z[X**2 + Y**2 > R**2] = np.nan
ax.plot_surface(X, Y, Z, color="#dfe3d8", alpha=0.9, linewidth=0, zorder=1)

# ---------------- house
def quad(p1, p2, p3, p4, color, alpha=1.0, edge="#6b5844", zorder=10):
    ax.add_collection3d(Poly3DCollection([[p1, p2, p3, p4]], facecolor=color,
                                         edgecolor=edge, linewidth=0.8,
                                         alpha=alpha, zorder=zorder))

wood, roof_c, win_c = "#b08d63", "#5a5a5a", "#9ec5f4"
# Real footprint, in the building's own frame: ridge along x, pans spanning y.
# -y is the occupant's "south" (206 deg), +x their "east" (116), -x "west" (296).
x0, x1 = -M.LEN_RIDGE / 2, M.LEN_RIDGE / 2
y0, y1 = -M.LEN_SLOPE / 2, M.LEN_SLOPE / 2
# walls
quad((x0, y0, 0), (x1, y0, 0), (x1, y0, EAVES), (x0, y0, EAVES), wood)          # S
quad((x0, y1, 0), (x1, y1, 0), (x1, y1, EAVES), (x0, y1, EAVES), wood)          # N (blind)
quad((x0, y0, 0), (x0, y1, 0), (x0, y1, EAVES), (x0, y0, EAVES), "#a5825a")     # W
quad((x1, y0, 0), (x1, y1, 0), (x1, y1, EAVES), (x1, y0, EAVES), "#a5825a")     # E
# gable triangles on the walls at each end of the ridge
for xg in (x0, x1):
    ax.add_collection3d(Poly3DCollection(
        [[(xg, y0, EAVES), (xg, y1, EAVES), (xg, 0, RIDGE)]],
        facecolor=wood, edgecolor="#6b5844", linewidth=0.8, zorder=11))
# roof pans (ridge along x at y=0) -> pans face 206 deg (SSW) and 26 deg (NNE)
quad((x0, y0, EAVES), (x1, y0, EAVES), (x1, 0, RIDGE), (x0, 0, RIDGE),
     roof_c, edge="#3d3d3d", zorder=12)                                          # SSW pan
quad((x0, y1, EAVES), (x1, y1, EAVES), (x1, 0, RIDGE), (x0, 0, RIDGE),
     roof_c, edge="#3d3d3d", zorder=12)                                          # NNE pan

# ---------------- windows, from the single layout in model.py
e = 0.02
LAYOUT = M.window_layout()
for o, z, w_, h_ in LAYOUT["E"]:                       # +x face
    quad((x1 + e, o - w_ / 2, z), (x1 + e, o + w_ / 2, z),
         (x1 + e, o + w_ / 2, z + h_), (x1 + e, o - w_ / 2, z + h_),
         win_c, edge="#4d6a86", zorder=13)
for o, z, w_, h_ in LAYOUT["W"]:                       # -x face
    quad((x0 - e, o - w_ / 2, z), (x0 - e, o + w_ / 2, z),
         (x0 - e, o + w_ / 2, z + h_), (x0 - e, o - w_ / 2, z + h_),
         win_c, edge="#4d6a86", zorder=13)
for o, z, w_, h_ in LAYOUT["S"]:                       # -y face
    quad((o - w_ / 2, y0 - e, z), (o + w_ / 2, y0 - e, z),
         (o + w_ / 2, y0 - e, z + h_), (o - w_ / 2, y0 - e, z + h_),
         win_c, edge="#4d6a86", zorder=13)

# ---------------- the tree off the south-east corner
if M.TREE_ON:
    # bearing measured from the ridge (+x is the 116 deg facade, -y the 206 one)
    th = math.radians(M.TREE_AZ - 116.0)
    tx, ty = M.TREE_DIST * math.cos(th), -M.TREE_DIST * math.sin(th)
    tz = M.TREE_TOP - M.TREE_CROWN_R                       # crown centre
    u, v = np.mgrid[0:2 * np.pi:24j, 0:np.pi:14j]
    ax.plot_surface(tx + M.TREE_CROWN_R * np.cos(u) * np.sin(v),
                    ty + M.TREE_CROWN_R * np.sin(u) * np.sin(v),
                    tz + M.TREE_CROWN_R * np.cos(v),
                    color="#4b7a4b", alpha=0.55, linewidth=0, zorder=14)
    ax.plot([tx, tx], [ty, ty], [0, tz], color="#5c4630", lw=4, zorder=14)
    ax.text(tx, ty, M.TREE_TOP + 0.8, f"tree ~{M.TREE_TOP:.0f} m",
            fontsize=9, color="#2f5130", ha="center", zorder=15)

# ---------------- mountain horizon wall on the sky dome
az_g = np.radians(np.linspace(0, 360, 181))          # compass
s_g = np.linspace(0, 1, 12)
AZ, S = np.meshgrid(az_g, s_g)
ELh = np.radians(hz(np.degrees(AZ.ravel())).reshape(AZ.shape)) * S
Xh = R * np.cos(ELh) * np.sin(AZ)
Yh = R * np.cos(ELh) * np.cos(AZ)
Zh = R * np.sin(ELh)
ax.plot_surface(Xh, Yh, Zh, color="#b9b7ae", alpha=0.55, linewidth=0, zorder=2)
# crest line
crest = np.radians(hz(np.degrees(az_g)))
ax.plot(R * np.cos(crest) * np.sin(az_g), R * np.cos(crest) * np.cos(az_g),
        R * np.sin(crest), color="#7d7b73", lw=1.5, zorder=3)

# ---------------- sun paths (dome radius): 21 Dec / 21 Mar / 21 Jun
def dome(el_deg, az_deg):
    el, az = np.radians(el_deg), np.radians(az_deg)
    return R * np.cos(el) * np.sin(az), R * np.cos(el) * np.cos(az), R * np.sin(el)

for doy, lab, col in [(355, "21 Dec", "#2a78d6"), (80, "21 Mar", "#eb6834"),
                      (172, "21 Jun", "#1baf7a")]:
    hrs = np.arange(0, 24, 0.05)
    el, az = M.sun_position(np.full_like(hrs, doy), hrs)
    up = el > 0
    el, az = el[up], az[up]
    vis = el > hz(az)
    x, y, z = dome(el, az)
    ax.plot(np.where(vis, x, np.nan), np.where(vis, y, np.nan),
            np.where(vis, z, np.nan), color=col, lw=2.5, zorder=20)
    ax.plot(np.where(~vis, x, np.nan), np.where(~vis, y, np.nan),
            np.where(~vis, z, np.nan), color=col, lw=1.2, ls=":", alpha=0.7, zorder=20)
    xi, yi, zi = dome(el[np.argmax(el)], az[np.argmax(el)])
    ax.text(xi, yi, zi + 1.6, lab, color=col, fontsize=11, ha="center",
            fontweight="bold", zorder=21)

# hourly suns on the June & Dec paths
for doy in (172, 355):
    hrs = np.arange(24, dtype=float)
    el, az = M.sun_position(np.full(24, doy), hrs)
    for e_, a_ in zip(el, az):
        if e_ > 0:
            x, y, z = dome(e_, a_)
            ax.scatter(x, y, z, s=14, c="#eda100" if e_ > hz(a_) else "#9a988f",
                       zorder=21)

# ---------------- cardinal labels on the terrain edge
for lab, a_ in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
    x, y = (R + 1.5) * math.sin(math.radians(a_)), (R + 1.5) * math.cos(math.radians(a_))
    ax.text(x, y, M.TERRAIN_SLOPE_E * x + M.TERRAIN_SLOPE_N * y + 0.5, lab,
            fontsize=13, ha="center", color="#0b0b0b", fontweight="bold", zorder=22)

ax.set_box_aspect((1, 1, 0.55))
ax.set_xlim(-R, R); ax.set_ylim(-R, R); ax.set_zlim(-4, R * 0.9)
ax.view_init(elev=22, azim=-125)      # camera SW & above: shows S + W facades
ax.set_axis_off()
ax.set_title(f"Stone farmhouse, Saint-Légier (~{M.ALT:.0f} m) — sun paths vs the local horizon\n"
             "grey wall = real horizon (PVGIS DEM)  ·  solid = sun visible, dotted = blocked\n"
             f"{M.LEN_RIDGE:.1f} × {M.LEN_SLOPE:.1f} m · roof {np.degrees(M.ROOF_PITCH):.1f}°, "
             "ridge at 116°: pans face 206° (SSW) and 26° (NNE)",
             fontsize=10, color="#0b0b0b")
fig.tight_layout()
if "--show" in sys.argv:
    plt.show()
else:
    fig.savefig(os.path.join(OUT, "house3d.png"), dpi=150)
    print("saved", os.path.join(OUT, "house3d.png"))
