"""Interactive plotly 3D scene of the modelled farmhouse for the Streamlit dashboard.

Same geometry as render3d.py: house (two storeys under a 27.5 deg gable),
sloping terrain, terrain-horizon wall on a sky dome, sun paths for the solstices
and equinox (gold/colored where visible, faint where blocked).

NOTE: the scene is drawn in the building's own frame, with the ridge along the
x axis. The real building is rotated 26 deg off the cardinal grid (ridge at
116 deg, pans facing 206 and 26 deg) -- the physics in model.py uses the true
azimuths, but this drawing does not rotate the terrain with it.
"""
import math

import numpy as np
import plotly.graph_objects as go

import model as M

R = 20.0                       # sky-dome radius, m
LIGHT = dict(ambient=0.62, diffuse=0.45, specular=0.05, roughness=0.9)


def _quad(fig, pts, color, name=None):
    x, y, z = zip(*pts)
    fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=[0, 0], j=[1, 2], k=[2, 3],
                            color=color, flatshading=True, lighting=LIGHT,
                            hoverinfo="skip" if name is None else "name",
                            name=name or "", showlegend=False))


def _tri(fig, pts, color):
    x, y, z = zip(*pts)
    fig.add_trace(go.Mesh3d(x=x, y=y, z=z, i=[0], j=[1], k=[2], color=color,
                            flatshading=True, lighting=LIGHT,
                            hoverinfo="skip", showlegend=False))


def _dome(el_deg, az_deg):
    el, az = np.radians(el_deg), np.radians(az_deg)
    return R * np.cos(el) * np.sin(az), R * np.cos(el) * np.cos(az), R * np.sin(el)


def build_scene():
    hz = M.load_horizon()
    EAVES, RIDGE = M.EAVES_H, M.RIDGE_H
    fig = go.Figure()

    # ---------------- terrain (21.5 % up to the east), polar grid -> clean edge
    r_g = np.linspace(0, R, 24)
    th_g = np.radians(np.linspace(0, 360, 121))
    Rg, Th = np.meshgrid(r_g, th_g)
    X, Y = Rg * np.sin(Th), Rg * np.cos(Th)
    Z = M.TERRAIN_SLOPE_E * X + M.TERRAIN_SLOPE_N * Y
    fig.add_trace(go.Surface(x=X, y=Y, z=Z, showscale=False, hoverinfo="skip",
                             colorscale=[[0, "#dfe3d8"], [1, "#dfe3d8"]],
                             lighting=dict(ambient=0.75, diffuse=0.3, specular=0.02)))

    # ---------------- house, real footprint in the building's own frame:
    # ridge along x; -y is the occupant's "south" (206 deg), +x "east" (116),
    # -x "west" (296), +y "north" (26, blind).
    wood, wood2, roof_c, win_c = "#b08d63", "#a5825a", "#5a5a5a", "#9ec5f4"
    x0, x1 = -M.LEN_RIDGE / 2, M.LEN_RIDGE / 2
    y0, y1 = -M.LEN_SLOPE / 2, M.LEN_SLOPE / 2
    _quad(fig, [(x0, y0, 0), (x1, y0, 0), (x1, y0, EAVES), (x0, y0, EAVES)], wood)   # S wall
    _quad(fig, [(x0, y1, 0), (x1, y1, 0), (x1, y1, EAVES), (x0, y1, EAVES)], wood)   # N wall
    _quad(fig, [(x0, y0, 0), (x0, y1, 0), (x0, y1, EAVES), (x0, y0, EAVES)], wood2)  # W wall
    _quad(fig, [(x1, y0, 0), (x1, y1, 0), (x1, y1, EAVES), (x1, y0, EAVES)], wood2)  # E wall
    for xg in (x0, x1):                                   # gables at the ridge ends
        _tri(fig, [(xg, y0, EAVES), (xg, y1, EAVES), (xg, 0, RIDGE)], wood2)
    # roof pans, ridge along x at y=0 -> pans face 206 deg (SSW) and 26 deg (NNE)
    _quad(fig, [(x0, y0, EAVES), (x1, y0, EAVES), (x1, 0, RIDGE), (x0, 0, RIDGE)],
          roof_c, name="SSW roof pan (147 m²)")
    _quad(fig, [(x0, y1, EAVES), (x1, y1, EAVES), (x1, 0, RIDGE), (x0, 0, RIDGE)],
          roof_c, name="NNE roof pan (211 m²)")
    # ridge line
    fig.add_trace(go.Scatter3d(x=[x0, x1], y=[0, 0], z=[RIDGE, RIDGE], mode="lines",
                               line=dict(color="#3d3d3d", width=4),
                               hoverinfo="skip", showlegend=False))

    # ---------------- windows, from the single layout in model.py
    e = 0.05
    layout = M.window_layout()
    for o, z, w_, h_ in layout["E"]:                       # +x face
        _quad(fig, [(x1 + e, o - w_ / 2, z), (x1 + e, o + w_ / 2, z),
                    (x1 + e, o + w_ / 2, z + h_), (x1 + e, o - w_ / 2, z + h_)], win_c)
    for o, z, w_, h_ in layout["W"]:                       # -x face
        _quad(fig, [(x0 - e, o - w_ / 2, z), (x0 - e, o + w_ / 2, z),
                    (x0 - e, o + w_ / 2, z + h_), (x0 - e, o - w_ / 2, z + h_)], win_c)
    for o, z, w_, h_ in layout["S"]:                       # -y face
        _quad(fig, [(o - w_ / 2, y0 - e, z), (o + w_ / 2, y0 - e, z),
                    (o + w_ / 2, y0 - e, z + h_), (o - w_ / 2, y0 - e, z + h_)], win_c)

    # ---------------- the tree off the south-east corner
    if M.TREE_ON:
        th = math.radians(M.TREE_AZ - 116.0)      # bearing measured from the ridge
        tx, ty = M.TREE_DIST * math.cos(th), -M.TREE_DIST * math.sin(th)
        tz = M.TREE_TOP - M.TREE_CROWN_R
        u, v = np.mgrid[0:2 * np.pi:28j, 0:np.pi:16j]
        fig.add_trace(go.Surface(
            x=tx + M.TREE_CROWN_R * np.cos(u) * np.sin(v),
            y=ty + M.TREE_CROWN_R * np.sin(u) * np.sin(v),
            z=tz + M.TREE_CROWN_R * np.cos(v),
            showscale=False, opacity=0.6, hoverinfo="name",
            name=f"tree, {M.TREE_TOP:.0f} m",
            colorscale=[[0, "#4b7a4b"], [1, "#4b7a4b"]],
            lighting=dict(ambient=0.7, diffuse=0.4, specular=0.05)))
        fig.add_trace(go.Scatter3d(x=[tx, tx], y=[ty, ty], z=[0, tz], mode="lines",
                                   line=dict(color="#5c4630", width=9),
                                   hoverinfo="skip", showlegend=False))

    # ---------------- terrain-horizon wall on the sky dome
    az_g = np.radians(np.linspace(0, 360, 181))
    s_g = np.linspace(0, 1, 10)
    AZ, S = np.meshgrid(az_g, s_g)
    ELh = np.radians(hz(np.degrees(AZ.ravel())).reshape(AZ.shape)) * S
    fig.add_trace(go.Surface(x=R * np.cos(ELh) * np.sin(AZ),
                             y=R * np.cos(ELh) * np.cos(AZ),
                             z=R * np.sin(ELh),
                             showscale=False, opacity=0.45, hoverinfo="skip",
                             colorscale=[[0, "#b9b7ae"], [1, "#b9b7ae"]],
                             lighting=dict(ambient=0.9, diffuse=0.1)))
    crest = hz(np.degrees(az_g))
    xc, yc, zc = _dome(crest, np.degrees(az_g))
    fig.add_trace(go.Scatter3d(x=xc, y=yc, z=zc, mode="lines",
                               line=dict(color="#7d7b73", width=4),
                               name="horizon crest", hoverinfo="skip", showlegend=False))

    # ---------------- sun paths: 21 Dec / 21 Mar / 21 Jun
    for doy, lab, col in [(355, "21 Dec", "#2a78d6"), (80, "21 Mar", "#eb6834"),
                          (172, "21 Jun", "#1baf7a")]:
        hrs = np.arange(0, 24, 0.05)
        el, az = M.sun_position(np.full_like(hrs, doy), hrs)
        up = el > 0
        el, az = el[up], az[up]
        vis = el > hz(az)
        x, y, z = _dome(el, az)
        fig.add_trace(go.Scatter3d(
            x=np.where(vis, x, np.nan), y=np.where(vis, y, np.nan),
            z=np.where(vis, z, np.nan), mode="lines", name=f"{lab} (visible)",
            line=dict(color=col, width=7), hoverinfo="name", showlegend=False))
        fig.add_trace(go.Scatter3d(
            x=np.where(~vis, x, np.nan), y=np.where(~vis, y, np.nan),
            z=np.where(~vis, z, np.nan), mode="lines", name=f"{lab} (blocked)",
            line=dict(color=col, width=2), opacity=0.35,
            hoverinfo="name", showlegend=False))
        i = int(np.argmax(el))
        xi, yi, zi = _dome(el[i], az[i])
        fig.add_trace(go.Scatter3d(x=[xi], y=[yi], z=[zi + 2.0], mode="text",
                                   text=[lab], textfont=dict(color=col, size=13),
                                   hoverinfo="skip", showlegend=False))

    # hourly sun dots on the June & December paths
    for doy in (172, 355):
        hrs = np.arange(24, dtype=float)
        el, az = M.sun_position(np.full(24, doy), hrs)
        up = el > 0
        el, az, hrs = el[up], az[up], hrs[up]
        vis = el > hz(az)
        x, y, z = _dome(el, az)
        fig.add_trace(go.Scatter3d(
            x=x, y=y, z=z, mode="markers",
            marker=dict(size=4, color=np.where(vis, "#eda100", "#9a988f")),
            text=[f"{int(h) + 1}h local winter time" for h in hrs],
            hoverinfo="text", showlegend=False))

    # cardinal labels
    for lab, a in [("N", 0), ("E", 90), ("S", 180), ("W", 270)]:
        x = (R + 2) * math.sin(math.radians(a))
        y = (R + 2) * math.cos(math.radians(a))
        z = M.TERRAIN_SLOPE_E * x + M.TERRAIN_SLOPE_N * y + 0.6
        fig.add_trace(go.Scatter3d(x=[x], y=[y], z=[z], mode="text", text=[lab],
                                   textfont=dict(size=15, color="#0b0b0b"),
                                   hoverinfo="skip", showlegend=False))

    ax_off = dict(visible=False)
    fig.update_layout(
        scene=dict(xaxis=ax_off, yaxis=ax_off, zaxis=ax_off,
                   aspectmode="manual", aspectratio=dict(x=1, y=1, z=0.55),
                   camera=dict(eye=dict(x=-1.05, y=-1.35, z=0.5)),
                   bgcolor="rgba(0,0,0,0)"),
        height=560, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
    return fig


if __name__ == "__main__":
    fig = build_scene()
    fig.write_image("out/house3d_plotly.png", width=1100, height=700, scale=2)
    print("saved out/house3d_plotly.png")
