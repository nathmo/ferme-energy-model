# Natural hazard context — Ferme, Saint-Légier (VD)

Checked **31.07.2026** by point query at the building itself (coordinates in
`model.py`): 601 m, on a 13.7 % slope falling north-north-west, about 230 m
above Lake Geneva.

**TL;DR — the opposite shape of risk from the alpine version of this model.**
Nothing here is trying to slide, fall or bury the building: no avalanche, no
rockfall, no debris flow, no permafrost, and the surface-runoff map does not
flag the parcel. Two things do matter, and both are about the *building*, not
the site: it sits in **seismic zone Z2 on ground class E** — a soft layer that
amplifies shaking — and it is built of **unreinforced rubble stone masonry**,
which is the most vulnerable structural type there is. Third, the **hail**
climate here is serious enough (3.5 cm at 50 years) to matter for any roof
work or PV plan.

**And one caveat that outranks all of the above:** the canton has **not
assessed** this location for hazards. See the next section before reading the
empty cells in the table as reassurance.

## The cantonal hazard map does not cover this parcel

Querying the harmonised cantonal hazard-map service
(`geodienste.ch/db/gefahrenkarten_v1_3_0`, data owner **VD**) at the building
returns **no danger sector on any process layer** — and the survey-status layer
explains why:

| process | survey status at this parcel |
|---|---|
| flooding, torrential lava overflow, bank erosion | `non_evalue` |
| permanent landslide, spontaneous landslide, mudflow | `non_evalue` |
| rockfall, collapse/rockslide | `non_evalue` |
| subsidence, sinkhole | `non_evalue` |
| flowing avalanche, powder avalanche, snowpack glide | `non_evalue` |
| ice fall | `evaluation_inutile` (assessment unnecessary) |

Note the distinction the data model itself makes: ice fall is marked
*assessment unnecessary*, everything else is marked **not assessed**. So the
blank danger map here is an absence of *data*, not a documented absence of
*hazard*. Any statement below about landslide or flooding rests on federal
indication layers and on the terrain, not on a legally binding cantonal map.

Before any purchase, permit or major works, get an **RDPPF / cadastre extract**
for the parcel and check the cantonal viewer directly — that is the
authoritative source, and it may have been updated since this file was written.

## Processes, point-queried

| process | source | result at this building |
|---|---|---|
| **earthquake** | SIA 261 seismic zones (BAFU) | **zone Z2**, a_gd = 1.0 m/s² |
| **ground class** | SIA 261:2003 (BAFU) | **class E** — soft surface layer 5–20 m over stiffer substrate, S = 1.4 |
| **hail** | MeteoSwiss hail hazard | **3 cm / 20 y · 3.5 cm / 50 y · 4 cm / 100 y** |
| radon | OFSP radon map | **5 %** probability of exceeding 300 Bq/m³ — low |
| surface runoff | BAFU runoff hazard map | not flagged at the point |
| rockfall | SilvaProtect-CH | no process area |
| debris flow | SilvaProtect-CH | no process area |
| avalanche | SilvaProtect-CH | no process area (601 m, no slope above) |
| permafrost | BAFU | none — far below the altitude range |
| lake flooding | terrain | irrelevant: ~230 m above Lake Geneva |
| landslide / flooding | canton VD | **not assessed** — see above |

## Risk over a 50-year horizon

**Earthquake is the one that matters, because of what the building is made of.**
Zone Z2 is the middle of the Swiss range (Z1 0.6 → Z3b 1.6 m/s²), but ground
class E multiplies it by S = 1.4, so the design ground acceleration at the
surface is about **1.4 m/s²**. By definition the SIA 261 design event is the one
with a 475-year return period — i.e. roughly a **10 % chance of being reached or
exceeded in 50 years**.

The exposure is the structure, not the number. **Unreinforced rubble stone
masonry 50–100 cm thick is the single most seismically vulnerable building type
in the Swiss stock**: heavy, brittle, with little tensile capacity and floor
diaphragms that are usually just joists resting in pockets. Walls fail by
out-of-plane overturning long before they fail in shear. This is worth knowing
mainly because it changes what a renovation is for:

- Anything that opens the walls — interior insulation, new services, a window
  enlarged — is the cheap moment to add **wall-to-floor ties and a ring anchor**.
  Retrofitting them later as a standalone job costs several times more.
- Do not cut new large openings in the stone without an engineer. On this
  building the blind north facade is doing structural work.
- The chimney and any heavy stove need anchoring; masonry stacks are the
  classic falling hazard.

**Hail is the underrated one.** A 50-year hailstone here is **3.5 cm**, and
P(≥1 event in 50 years) at that size is by construction **64 %**; the 4 cm
100-year size still carries a **39 %** chance. Standard PV modules are certified
(IEC 61215) against **25 mm** ice balls at 23 m/s — comfortably below the local
50-year size. If the PV in this model gets built, specify hail-resistance class
**HW4/HW5** or an equivalent tested rating, and check that the elemental-damage
cover names the PV installation explicitly. The same figure argues for a
hail-resistant choice when the roof covering is next touched (the roof was
redone around 2000, so it is mid-life).

**Radon needs no action.** A 5 % exceedance probability puts this in the low
band. Worth a cheap measurement anyway if the cellar is ever converted into
living space, since that is where radon accumulates and this building has a
cellar under the whole footprint.

**Landslide is the open question.** The slope is gentle (13.7 %) and nothing in
the federal indication layers flags it, but the canton has not assessed it and
class E ground means soft material at depth. If there is any history of cracking,
settlement or wet cellars, that is worth a geotechnical opinion — not because
the maps say so, but because they are silent.

## Practical implications

- Elemental-damage cover (*dommages naturels*) is mandatory in the ECA Vaud
  fire policy; the exposures that actually apply here are **hail, storm and
  earthquake**. Note that **earthquake is NOT covered** by the standard Swiss
  elemental-damage scheme — Vaud participates in the cantonal earthquake fund,
  but check what the policy on this building actually says.
- Structural strengthening is only economic **during** other works. Sequence the
  renovation so the seismic ties go in with the insulation, not after it.
- Get the RDPPF extract before committing money to anything on this parcel.

## Method (reproducible)

All results above come from point queries at the building coordinate, not from
reading a map by eye:

- **Cantonal hazard map**, harmonised model, via geodienste.ch WMS
  `https://geodienste.ch/db/gefahrenkarten_v1_3_0/fra` — `GetFeatureInfo` on
  `secteur_de_danger_*` (synoptique, eaux, glissement, chute, avalanche), plus
  `zone_de_releve_de_la_cartographie_des_dangers` to establish **survey status**,
  which is the step that turned "no result" into "not assessed".
- **Federal layers** via `wms.geo.admin.ch` `GetFeatureInfo` and
  `api3.geo.admin.ch` `identify`: `ch.bafu.gefahren-gefaehrdungszonen` (SIA 261
  seismic zone), `ch.bafu.gefahren-baugrundklassen` (ground class),
  `ch.bag.radonkarte`, `ch.bafu.gefaehrdungskarte-oberflaechenabfluss`,
  `ch.meteoschweiz.hagelgefaehrdung-korngroesse_{20,50,100}_jahre`,
  `ch.bafu.silvaprotect-{sturz,murgang,lawinen}`.
- **Terrain** from swisstopo swissALTI3D (`api3.geo.admin.ch/rest/services/height`),
  four-point gradient on a 200 m baseline.

Raster layers (radon, hail, runoff) answer to WMS `GetFeatureInfo` but return
HTTP 400 from the `identify` endpoint — use WMS for those.

## Sources

- [Cantonal hazard maps via geodienste.ch](https://www.geodienste.ch/services/gefahrenkarten?locale=fr)
- [Canton VD geoportal](https://www.geo.vd.ch/) — theme *Dangers naturels*
- [Federal viewer map.geo.admin.ch](https://map.geo.admin.ch/) (SIA 261 zones,
  ground classes, radon, hail, surface runoff, SilvaProtect)
- [RDPPF / cadastre extract](https://www.cadastre.ch/fr/service-web-rdppf)
- [ECA Vaud — assurance des bâtiments](https://www.eca-vaud.ch/)
- SIA 261 *Actions sur les structures porteuses*, chapter 16 (seismic zones,
  ground classes, S factors)
- [OFEV — dangers naturels](https://www.bafu.admin.ch/bafu/fr/home/themes/dangers-naturels.html)
