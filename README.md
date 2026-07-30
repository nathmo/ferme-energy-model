# Ferme, Saint-Légier — thermal model

Hourly thermal model of a **stone farmhouse ("ferme") in Saint-Légier, Vaud,
Switzerland** — real footprint, real roof geometry, real terrain horizon, and
climate data for the site.

Adapted from [zinal-chalet-model](https://github.com/nathmo/zinal-chalet-model),
which modelled a timber chalet at 1680 m in Valais. Almost every number changed,
and several of the *conclusions* invert — see [What changed](#what-changed-vs-the-chalet).

> **This is a specific building, not an archetype.** Unlike the chalet version,
> the geometry here is measured rather than assumed — off the cadastral survey
> and the federal solar cadastre. The address and register identifiers are
> deliberately left out; the site coordinates live in [model.py](model.py).

| register | value |
|---|---|
| commune | Saint-Légier (VD), **601 m** |
| GKLAS / GASTW | 1121 two-dwelling building / 2 full storeys |
| GBAUJ | 1966 *(registered year — see the caveat below)* |
| GAREA | 259 m² footprint |

**Caveat on GBAUJ 1966.** Walls of 50–100 cm of rubble stone are not a 1966
construction. For old rural buildings the RegBL year is usually the year of a
major transformation or of first registration. Treat 1966 as "last big works",
not as the age of the fabric.

## The building (as modeled)

| item | value | source |
|---|---|---|
| footprint | **14.82 × 15.53 m = 230 m²** | cadastral survey (via OpenStreetMap) |
| orientation | ridge at **116°** (WNW–ESE); pans face **206°** and **26°** | sonnendach.ch + footprint, agreeing to <1° |
| storeys | 2 full storeys + attic, cellar below | RegBL GASTW = 2 |
| eaves / ridge | 6.0 m / 10.04 m | derived from pitch + span |
| heated | ~380 m², ~1000 m³ | **assumption — see below** |
| walls | **50–100 cm rubble stone, no insulation** → U = **1.72** | owner survey; λ 1.7 W/mK at 0.70 m |
| roof | redone ~2000, ~14 cm mineral wool → U = 0.25 | owner; SIA 380/1 standard of the day |
| windows | S 8 m² (1 big central GF + 1 on the 1F, west end) · W 7 m² (3 per floor, both floors) · E 6 m² (5 in one row) · **none on N** | owner survey |
| window ages | S and W replaced <5 y (Uw 1.1); E ~20 y (Uw 1.6) | owner survey |
| near-field | **a massive tree off the SE corner** (~21 m) | owner; see below |
| floor → cellar | 230 m², U 0.8, b = 0.6 | era-typical |
| infiltration | 0.55 air changes/h | assumption |
| **heat-loss coeff.** | **H = 1085 W/K**, τ ≈ 46 h | computed |
| **design load** | **30.4 kW** at −8 °C | computed |
| thermal mass | 50 kWh/K (SIA "heavy": bare stone is fully accessible) | computed |

The roof pans are bigger than the footprint implies (359 m² against 230 m² of
plan) because a farmhouse roof overhangs generously and sweeps down over the
annexes — the large NNE pan is why the north facade is blind.

### The assumption that matters most

**How much of the building is heated.** `FLOOR_AREA = 380 m²` / `VOLUME = 1000 m³`
assumes both storeys are kept warm. If part of it is a cold barn or grange, cut
those two numbers in [model.py](model.py) and *everything* downstream follows —
demand, cost, CO₂, payback. Nothing else in the file has anything like this
leverage.

## Data in `data/`

Re-downloadable in one command — `python data/download_data.py` reads the site
coordinates straight out of `model.py`, so changing the site is a two-line edit.

- `tmy.json` — PVGIS typical meteorological year, hourly. **GHI 1390 kWh/m²/yr**,
  mean 10.8 °C. The PVGIS cell sits at 612 m against the site's 601 m, so unlike
  the alpine version the temperature bias correction is a small one.
- `horizon.json` — PVGIS DEM horizon. **Peaks at only 16.8°**, sky-view factor
  0.98: this site is essentially open, which is the biggest single difference
  from a valley flank in Anniviers.
- `archive.json` — ERA5 daily means 2015-2025 (grid elevation 595 m)
- `climate.json` / `climate_minmax.json` — CMIP6-HighRes daily 2026-2050, 3 models

## Shading: the tree, and the thing that is not the tree

The PVGIS horizon is computed from a *terrain* model. It cannot see vegetation.
The federal solar cadastre (sonnendach.ch) can, because it is built from LiDAR —
and the two disagreed, which is how the model found the tree before anyone
mentioned it:

| roof pan | bare-horizon model | sonnendach (LiDAR) | implied shading |
|---|---|---|---|
| SSW (206°, 28°) | 1561 kWh/m²/yr | **1035** | **×0.66** |
| NNE (26°, 27°) | 1013 kWh/m²/yr | **923** | ×0.91 |

There is indeed **a massive tree off the south-east corner**. It is modelled as a
real object — a 7 m-radius crown topping out at 21 m, 13 m from the centre of the
house — and not as a flat factor, because how much it takes depends on how high
you stand. `python -c "import model; model.shading_report()"`:

| surface | looks out from | bare | with the tree | factor | sonnendach |
|---|---|---|---|---|---|
| roof SSW | 8.0 m | 1561 | 1343 | 0.86 | **1035** |
| roof NNE | 8.0 m | 1013 | 935 | 0.92 | **923** |
| windows S | 3.1 m | 1096 | 865 | 0.79 | — |
| windows W | 3.1 m | 689 | 658 | 0.95 | — |
| windows E | 1.6 m | 894 | 648 | **0.73** | — |

That is worth reading carefully. The tree reproduces the **NNE pan's measured
shading almost exactly** (0.92 against 0.91), which is a real validation of the
geometry. It also does something no single factor could: the east windows, low
and right behind it, lose **27 %** while the west windows on the far side lose
**5 %**.

**But it only gets the SSW pan to 0.86 against a measured 0.66.** Growing the
tree until that matches (25 m tall, 9 m crown) drags the NNE pan down to 0.76,
contradicting the measurement. Sweeping the tree's size and bearing does not
resolve it: shading that hits a SSW-facing pan hard while barely touching a
NNE-facing one has to sit to the **south or south-west**, not the south-east.

So there is a second obstruction out there, and until someone looks it lives in
`model.py` as an explicit `PV_RESIDUAL_SSW = 0.77` on that pan only. It is
deliberately **not** applied to the south windows: if the residual is real
vegetation to the south then those windows are over-credited and the heating
demand here is slightly optimistic, but inventing a second factor from no
evidence would be worse than naming the gap. **A photo looking south and
south-west from the facade settles it.**

Set `TREE_ON = False` to see the unobstructed potential.

## Where the heat goes — and why this building is different

`renovation.py` splits H exactly into the elements that lose the heat:

| part | area | U (as built) | W/K | share |
|---|---|---|---|---|
| **walls** | 406.0 m² | **1.72** | **697.8** | **64 %** |
| ventilation & air leaks | — | 0.55 /h | 187.0 | 17 % |
| floor → cellar | 230.2 m² | 0.80 | 110.5 | 10 % |
| roof | 259.5 m² | 0.25 | 64.0 | 6 % |
| windows | 21.0 m² | 1.24 | 26.1 | 2 % |

**Two thirds of everything this building loses goes straight through bare
stone.** That single fact reorganises the whole problem. On the chalet, losses
were spread across five elements and the cheap fixes mattered; here, anything
that does not touch the walls is rearranging 36 % of the problem.

Note also what the window numbers say: 21 m² of glazing is **2 %** of the losses,
and the 6 m² of old east glazing is a fraction of that. Replacing them is a
comfort and draught measure, not an energy investment — and the model says so
rather than flattering it.

### Cross-check against the federal estimate

sonnendach publishes its own demand estimate for this building: **59 036 kWh/yr**
space heating, 7 632 kWh/yr hot water, 3 197 K·d of heating degree days. This
model gives **≈82 000 kWh/yr** at 20 °C with a 16 °C setback — about 39 % higher.
The gap is roughly what you would expect from the heated-area assumption and a
different setpoint convention, and the two are the same order of magnitude,
which is the useful part of the check.

**The number that would settle it is your actual oil consumption.** The model
says 9 609 litres/yr; sonnendach implies nearer 7 000. If you know what the tank
actually takes, that pins `FLOOR_AREA`, `ACH` and `U_WALL` in one step, and every
result below tightens.

## Headline results — now (2026), 20 °C occupied / 16 °C away, 344 days/yr

All rows include non-heating electricity (700 W present / 250 W away, ≈ 5 700
kWh/yr) and hot water (21 kWh/day, ≈ 7 500 kWh/yr).

| scenario | energy bought | cost/yr | notes |
|---|---|---|---|
| A do nothing | 13 200 kWh el | 3 827 CHF | indoor floor **−1 °C**, only 25 h/yr below 0 — the mass and the mild climate do the rest |
| **O oil boiler** *(incumbent)* | **9 622 L oil** + 13 200 kWh | **14 892 CHF** | the system RegBL records for this building |
| B electric heaters | 93 900 kWh el | 27 231 CHF | |
| C wood stove alone (15 kW) | 61.8 steres + 13 200 kWh | 13 098 CHF | delivers only **91 %** of the demand — 15 kW against a 30 kW design load |
| C2 wood + electric top-up | 61.8 steres + 20 350 kWh | 15 172 CHF | |
| P pellet boiler (30 kW) | 19 575 kg + 14 800 kWh | 13 687 CHF | one appliance covers the whole load |
| D + 10 m² solar thermal | | 25 551 CHF | 5 790 kWh/yr useful — worth far more here than on the chalet |
| **E air-source heat pump** | 42 389 kWh el | **12 293 CHF** | COP-weighted, incl. backup |
| F HP + PV **SSW pan** (25.5 kWp) + 20 kWh batt | 29 400 kWh net | **7 739 CHF** | export 7 800 kWh |
| F2 HP + PV **both pans** (62.5 kWp) + 20 kWh batt | 24 600 kWh net | **4 068 CHF** | export 30 600 kWh |
| Ref: 20 °C, no setback | 95 500 kWh | 27 699 CHF | upper bound |

**Two things here are worth not glossing over.**

The heat pump saves about **2 600 CHF/yr against oil — only 17 %**, far less than
its COP suggests. Per kWh of heat delivered, oil costs 0.135 CHF and the heat
pump 0.103 CHF: at 0.29 CHF/kWh of electricity against 1.15 CHF/L of oil, the
tariff ratio eats most of a COP of 2.8. The heat pump's case here is the CO₂
column, not the cost column — and it improves sharply if the envelope is fixed
first, because a smaller load raises the share the pump carries without backup.

The **16 °C setback saves almost nothing** — 470 CHF/yr, B against the no-setback
reference. That is not a bug: at 344 days of occupancy the setback only ever
applies for three weeks a year. Setback strategies are for buildings that stand
empty; this one does not.

## Roof PV

Pans as measured by the federal cadastre; 425 Wp modules at 80 % packing.

| | SSW pan (206°, 28°) | both pans |
|---|---|---|
| area | 147.1 m² | 358.5 m² |
| installed | **25.5 kWp** (60 modules) | **62.5 kWp** (147 modules) |
| year | **21 101 kWh** (827 kWh/kWp) | **48 765 kWh** |
| December | 19.2 kWh/day | 35.2 kWh/day |
| June | 93.9 kWh/day | 250.0 kWh/day |

*(sonnendach's own full-pan estimates, for comparison: 24 352 / 55 581 kWh/yr.)*

827 kWh/kWp is a mediocre yield for the Swiss plateau — that is the tree and its
unidentified companion talking, not the orientation. **Resolve the shading before
sizing a system**: with nothing in the way the SSW pan alone would make ~32 000
kWh, so the difference between the two answers is about 11 000 kWh/yr. It is also
the one case in this whole model where a chainsaw is a legitimate energy measure —
though a 21 m tree on the south-east is worth something too, in August.

## CO₂ — and the one result that is not close

| scenario | kg CO₂/yr now | t use (50 y) | t equipment (50 y) | **t total** |
|---|---|---|---|---|
| A do nothing | 264 | 13.2 | 0 | **13.2** |
| E air-source heat pump | 848 | 39.9 | 9.6 | **49.5** |
| F HP + PV SSW + battery | 588 | 27.0 | 50.1 | **77.1** |
| C wood only | 1 735 | 83.9 | 0 | **83.9** |
| B electric heaters | 1 878 | 88.9 | 0 | **88.9** |
| F2 HP + PV both pans + battery | 491 | 22.2 | 101.9 | **124.1** |
| P pellet boiler | 3 584 | 168.3 | 4.2 | **172.5** |
| **O oil boiler** | **30 959** | **1 445.9** | 2.7 | **1 448.6** |

**The oil boiler emits about 31 tonnes of CO₂ a year — nearly 1 450 tonnes over
50 years, an order of magnitude beyond every alternative on the list.** On the
chalet, the honest conclusion was that nothing much mattered: demand was small,
the local electricity was clean, and hardware cost more carbon than it saved.
Here the opposite holds. Getting off oil is worth more than every other decision
in this model put together, and it is not close.

Two things follow that are easy to miss:

- **PV + battery still does not pay back in carbon** against hydro-supplied
  electricity (F2 costs 102 t to build and saves ~18 t of use-phase against E).
  It pays back handsomely in *money*. Those are different questions, and the
  dashboard keeps them apart.
- **Pellets are not a free pass.** At 35 g/kWh with biogenic carbon counted as
  zero, the pellet boiler is still 172 t — because the demand is enormous. Move
  the biogenic slider off 0 % and it deteriorates fast. Insulate first.

Factors live in [carbon.py](carbon.py) and are all editable in the dashboard.
Heating oil at 319 g/kWh (KBOB) is fossil carbon with no accounting argument
available; electricity defaults to a Romande Energie hydro-based product at
20 g/kWh — **check your actual contract**, and try the 400 g/kWh European
winter-marginal figure to see how much the ranking depends on it.

## What renovating changes

| package | H | net cost (after subsidy) | amortized | embodied |
|---|---|---|---|---|
| as built | 1085 W/K | — | — | — |
| quick wins (floor + sealing + east windows) | 930 W/K (−14 %) | 23 200 CHF | 735 CHF/yr | 4.1 t |
| everything except the facade | 319 W/K (−71 %) | 97 100 CHF | 2 582 CHF/yr | 15.8 t |
| deep retrofit (external wall insulation) | 243 W/K (−78 %) | 182 700 CHF | 5 847 CHF/yr | 23.7 t |

**Here it is the wall package that pays, not the quick wins.** The quick wins buy
14 % because they cannot touch the walls; insulating the walls buys the other
57 %. Scaling the oil bill's fuel component (11 065 CHF/yr) by the demand cut:

| package | ≈ saving vs oil | net cost | ≈ simple payback |
|---|---|---|---|
| quick wins | 1 550 CHF/yr | 23 200 CHF | ~15 y |
| everything except the facade | 7 850 CHF/yr | 97 100 CHF | **~12 y** |
| deep retrofit | 8 600 CHF/yr | 182 700 CHF | ~21 y |

Rough — it scales the fuel linearly with H rather than re-running the
simulation, and it ignores interest, price escalation and the fact that mild
future winters stretch every payback. The dashboard does it properly per
scenario. But the shape is robust: **a payback in the region of a decade, not
the century the chalet showed**, and the marginal 75 000 CHF for external wall
insulation over internal is the weakest part of the spend.

The catch is not money, it is permission. Interior insulation buries the stone
and takes most of the 50 kWh/K of thermal mass with it (`c_mult = 0.45`);
exterior insulation is thermally better and keeps the mass inside, but on a rural
building of this age it is the version most likely to be refused. **Check the
commune's plan d'affectation and the cantonal recensement architectural before
costing anything on the facade.** And whatever opens the walls is also the cheap
moment to add seismic ties — see [HAZARDS.md](HAZARDS.md).

## Climate horizons — read these with care

| | now | +10 y | +20 y | +30 y | +40 y | +50 y |
|---|---|---|---|---|---|---|
| O oil, litres/yr | 9 622 | 9 363 | 9 105 | 8 850 | 8 596 | 8 343 |
| E heat pump, kWh el | 42 389 | 41 305 | 40 279 | 39 296 | 38 355 | 37 454 |
| E heat pump, CHF/yr | 12 293 | 11 978 | 11 681 | 11 395 | 11 123 | 10 862 |
| F2 both pans, CHF/yr | 4 068 | 3 762 | 3 473 | 3 196 | 2 931 | 2 678 |
| A free-float, min °C | −0.7 | −0.1 | 0.6 | 1.0 | 1.3 | 1.6 |
| indoor h > 26 °C | 0 | 0 | 0 | 25 | 51 | **82** |

**Caveat, and it is a real one.** Fitting the CMIP6-HighRes 3-model mean over
2026-2050 at this grid cell gives only **+0.22 K/decade** (day +0.18, night
+0.30) — well below what CMIP6 projects for Switzerland, and several monthly
slopes come out *negative* (June −0.43, October −0.45 K/decade). A 25-year linear
fit on one grid cell is dominated by internal variability. **Treat the columns
above as a mild-warming sensitivity test, not a projection**, and do not read the
individual months at all. The heating trend is directionally right; the
magnitude is soft.

The overheating row is the one worth watching: this building has **no cooling
problem today**, and by 2076 still only ~72 hours above 26 °C. Heavy stone plus
a mild plateau climate is a good combination for a warming world. Nothing here
justifies air conditioning.

## Natural hazards

The picture inverts completely from the alpine version: no avalanche, no
rockfall, no debris flow, no permafrost. What matters instead is **seismic zone
Z2 on ground class E** applied to **unreinforced rubble stone masonry**, plus a
**3.5 cm 50-year hailstone** that exceeds standard PV module certification.

And a caveat that outranks both: **the canton has not assessed this location** —
every process in the cantonal hazard-map survey layer comes back `non_evalue`.
The blank danger map is missing data, not a clean bill of health. Method, point
queries, 50-year probabilities and sources in [HAZARDS.md](HAZARDS.md)
(checked 31.07.2026).

## Interactive dashboard

```
pip install -r requirements.txt
streamlit run app.py
```

- interactive **3D scene**, hourly **indoor + outdoor temperature** for any
  horizon, daily mean ±σ bands, presence shading
- **electricity flows**: annual Sankey (PV → direct / battery / export, grid) +
  daily stacked areas by end use and by source, dispatched against any scenario
- scenarios toggle on/off: free-float, **oil**, electric, wood, wood + top-up,
  pellet boiler, heat pump; PV one pan / both pans affects the cost table
- **every assumption is editable** in the sidebar — including the three window
  areas on their true azimuths and the oil price, efficiency and CO₂ factor
- **envelope flows**: a second Sankey from heat sources through the rooms to the
  walls, roof, windows, floor and air changes that let it back out
- **renovation measures**, each one only moving a U-value or the ACH, with net
  cost after subsidy, embodied CO₂ and money/carbon payback
- **CO₂ section** with the biogenic-carbon slider and equipment replacement
- **off-grid switch**: coupled thermal/electrical simulation where heating only
  runs if PV + battery can power it

## Files

- [`model.py`](model.py) — site, geometry, fabric, systems; weather loaders,
  solar geometry + horizon masking, warming trends, 1-node RC model
- [`data/download_data.py`](data/download_data.py) — re-downloads all five
  datasets for whatever coordinates `model.py` declares
- [`renovation.py`](renovation.py) — envelope split + measure catalogue;
  `python renovation.py` prints the loss breakdown per package
- [`simulate.py`](simulate.py) — occupancy, scenarios × 6 climate horizons;
  writes the CSVs in `out/`
- [`carbon.py`](carbon.py) — CO₂ factors and lifetimes, sources documented inline
- [`make_plots.py`](make_plots.py) / [`render3d.py`](render3d.py) — figures,
  including `out/facades.png`, the four facades flat with the window survey on
  them (a 3D view always hides half the building)
- [`app.py`](app.py) / [`scene3d.py`](scene3d.py) — the Streamlit dashboard
- [`HAZARDS.md`](HAZARDS.md) — natural hazard assessment at the exact building

Run: `python simulate.py && python make_plots.py && python render3d.py`

## What changed vs the chalet

| | Zinal chalet | Ferme, Saint-Légier |
|---|---|---|
| H | 115 W/K | **1085 W/K** (9×) |
| dominant loss | walls 30 %, spread across five elements | **walls 64 %** |
| thermal mass | 4 kWh/K, τ 35 h | **50 kWh/K, τ 46 h** |
| occupancy | 74 days/yr, frost guard | **344 days/yr, 16 °C setback** |
| horizon | mountains to 29° | open, 16.8° |
| the problem | pipes freezing in an empty house | **31 t CO₂/yr and a 15 000 CHF oil bill** |
| does insulation pay? | no — century-long payback | **yes — roughly a decade** |
| does PV+battery pay in carbon? | no | still no (but it pays in money) |

## Main modeling assumptions to keep in mind

- **Heated floor area (380 m²) is an assumption**, and the highest-leverage one
- Single thermal zone; a farmhouse with a cold barn section is really two
- Wall λ 1.7 W/mK at 0.70 m average thickness — the owner reports 50–100 cm, and
  U scales strongly with which end of that range dominates
- The roof is assumed insulated to ~2000 standards because it was redone then;
  nobody has opened it up to check
- The tree's size and distance are calibrated, not surveyed — they reproduce the
  NNE pan's measured shading, which is the only hard check available
- `PV_RESIDUAL_SSW = 0.77` stands for an obstruction to the S/SW that nobody has
  identified yet; the south windows are NOT charged for it
- The 26° building rotation is real and applied throughout, but the model still
  treats the roof as a symmetric gable for *thermal* purposes while using the
  true asymmetric pan areas for PV
- Climate slopes are soft (see above); PV uses an isotropic sky and no snow
  blackout
- Prices: 0.29 CHF/kWh electricity, 1.15 CHF/L oil, 150 CHF/stere, 0.48 CHF/kg
  pellets, 0.10 CHF/kWh feed-in — all in `model.py`, all editable in the dashboard
