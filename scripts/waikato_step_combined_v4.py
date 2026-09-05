"""
Waikato River — mainstem stitching, source/mouth/confluence points, and
elevation profile, all in one consistent pipeline.

Why this replaces the earlier two scripts: the Waikato mainstem is broken
into 15 disconnected OSM fragments -- NOT because of a chaining error, but
because the river passes through a chain of hydroelectric lakes (Karapiro,
Arapuni, Maraetai, Waipapa, Atiamuri, Ohakuri, Aratiatia, etc.), and OSM
tags the inundated sections as lake polygons rather than continuing the
waterway=river line through them. Greedy "nearest fragment" stitching can
jump to the WRONG next fragment when gaps are large and multiple fragments
are within similar distance of each other, producing a non-monotonic path
(which is why the previous run's "mouth" elevation of 61 m was wrong --
sea level should be ~0-5 m).

Fix: order fragments using two known, fixed real-world anchor points
(Lake Taupo outlet and Port Waikato river mouth) and a straight-line
projection, which is robust to any number/size of gaps because it doesn't
depend on fragment-to-fragment distances at all.

Input:  data/waikato_waipa_rivers_osm.geojson
        data/waikato_dem.tif
Output: output/waikato_mainstem.gpkg          (overwritten, now correct)
        output/waikato_source_point.gpkg      (overwritten)
        output/waikato_mouth_point.gpkg       (overwritten)
        output/waikato_confluence_point.gpkg  (overwritten)
        output/waikato_elevation_profile.csv
        maps/waikato_elevation_profile.png
"""

import csv
import geopandas as gpd
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import Point, LineString

GEOJSON_PATH = "data/waikato_waipa_rivers_osm.geojson"
DEM_PATH = "data/waikato_dem.tif"
NZTM = "EPSG:2193"
SAMPLE_INTERVAL_M = 500

# Known real-world anchors (approximate, just used to establish direction)
TAUPO_OUTLET_LONLAT = (176.0702, -38.6857)   # Taupo township, Lake Taupo outlet
PORT_WAIKATO_LONLAT = (174.6980, -37.3833)   # Port Waikato, river mouth

transformer = Transformer.from_crs("EPSG:4326", NZTM, always_xy=True)
taupo_xy = transformer.transform(*TAUPO_OUTLET_LONLAT)
mouth_xy = transformer.transform(*PORT_WAIKATO_LONLAT)
ref_dx, ref_dy = mouth_xy[0] - taupo_xy[0], mouth_xy[1] - taupo_xy[1]


def projection(pt):
    """Scalar position of pt along the Taupo -> Port Waikato direction."""
    dx, dy = pt.x - taupo_xy[0], pt.y - taupo_xy[1]
    return dx * ref_dx + dy * ref_dy


def order_and_stitch(mls):
    """Order every fragment by its projection onto the known source->mouth
    direction (orienting each fragment source-ward-first), then concatenate.
    Robust to large/uneven gaps since it never relies on fragment-to-fragment
    distance."""
    parts = list(mls.geoms) if mls.geom_type == "MultiLineString" else [mls]
    oriented = []
    for part in parts:
        p0, p1 = Point(part.coords[0]), Point(part.coords[-1])
        if projection(p0) > projection(p1):
            part = LineString(list(part.coords)[::-1])
        oriented.append(part)
    oriented.sort(key=lambda ln: projection(Point(ln.coords[0])))

    coords = []
    gap_total = 0.0
    for part in oriented:
        c = list(part.coords)
        if coords:
            gap_total += Point(coords[-1]).distance(Point(c[0]))
            if coords[-1] == c[0]:
                c = c[1:]
        coords.extend(c)
    return LineString(coords), gap_total


# --- Load OSM data ---
gdf = gpd.read_file(GEOJSON_PATH)
if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")

def extract_named(gdf, exact_name):
    parts = gdf[gdf["name"] == exact_name]
    if parts.empty:
        raise SystemExit(f"No features named exactly '{exact_name}' found.")
    return parts

waikato_parts = extract_named(gdf, "Waikato River").to_crs(NZTM)
waipa_parts = extract_named(gdf, "Waipā River").to_crs(NZTM)

from shapely.ops import linemerge
waikato_merged = linemerge(waikato_parts.geometry.union_all())
waipa_merged = linemerge(waipa_parts.geometry.union_all())

mainstem_line, gap_total_m = order_and_stitch(waikato_merged)
print(f"Mainstem: {len(waikato_parts)} OSM segments -> stitched, "
      f"length {mainstem_line.length/1000:.1f} km, inter-fragment gap total {gap_total_m/1000:.1f} km")

waipa_line, waipa_gap_m = order_and_stitch(waipa_merged)
print(f"Waipa tributary: {len(waipa_parts)} OSM segments -> stitched, "
      f"length {waipa_line.length/1000:.1f} km, inter-fragment gap total {waipa_gap_m/1000:.1f} km")

source_pt = Point(mainstem_line.coords[0])
mouth_pt = Point(mainstem_line.coords[-1])
print(f"Source point (NZTM): {source_pt}")
print(f"Mouth point (NZTM):  {mouth_pt}")

# Confluence = whichever end of the Waipa line is closest to the mainstem
w_end_a, w_end_b = Point(waipa_line.coords[0]), Point(waipa_line.coords[-1])
confluence_end = min([w_end_a, w_end_b], key=lambda p: mainstem_line.distance(p))
confluence_gap = mainstem_line.distance(confluence_end)
confluence_pt = mainstem_line.interpolate(mainstem_line.project(confluence_end))
print(f"Confluence point (NZTM): {confluence_pt}, gap to mainstem: {confluence_gap:.1f} m")

# --- Save corrected outputs ---
gpd.GeoDataFrame({"name": ["Waikato River"]}, geometry=[mainstem_line], crs=NZTM)\
    .to_file("output/waikato_mainstem.gpkg", driver="GPKG")
gpd.GeoDataFrame({"name": ["Waipa River"]}, geometry=[waipa_line], crs=NZTM)\
    .to_file("output/waipa_tributary.gpkg", driver="GPKG")
gpd.GeoDataFrame({"label": ["Source - Lake Taupo outlet, Taupo township"]}, geometry=[source_pt], crs=NZTM)\
    .to_file("output/waikato_source_point.gpkg", driver="GPKG")
gpd.GeoDataFrame({"label": ["Mouth - Port Waikato / Tasman Sea"]}, geometry=[mouth_pt], crs=NZTM)\
    .to_file("output/waikato_mouth_point.gpkg", driver="GPKG")
gpd.GeoDataFrame({"label": ["Confluence - Waipa River joins Waikato River (near Ngaruawahia)"]},
                 geometry=[confluence_pt], crs=NZTM)\
    .to_file("output/waikato_confluence_point.gpkg", driver="GPKG")

# --- Elevation profile ---
with rasterio.open(DEM_PATH) as dem:
    dem_crs = dem.crs
    print(f"\nDEM CRS: {dem_crs}, size: {dem.width}x{dem.height}")

    line_dem_crs = gpd.GeoSeries([mainstem_line], crs=NZTM).to_crs(dem_crs).iloc[0]
    total_length_m = mainstem_line.length
    n_samples = int(total_length_m // SAMPLE_INTERVAL_M) + 1
    distances_m = np.linspace(0, total_length_m, n_samples)

    sample_points_dem_crs = [line_dem_crs.interpolate(d / total_length_m, normalized=True) for d in distances_m]
    coords = [(p.x, p.y) for p in sample_points_dem_crs]
    elevations = np.array(
        [val[0] if val[0] != dem.nodata else np.nan for val in dem.sample(coords)], dtype=float
    )

    confluence_frac = mainstem_line.project(confluence_pt, normalized=True)
    confluence_dist_km = confluence_frac * total_length_m / 1000

source_elev, mouth_elev = elevations[0], elevations[-1]
print(f"Source elevation: {source_elev:.1f} m")
print(f"Mouth elevation: {mouth_elev:.1f} m")
print(f"Confluence at ~{confluence_dist_km:.1f} km along the mainstem")

with open("output/waikato_elevation_profile.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["distance_km", "elevation_m"])
    for d, e in zip(distances_m, elevations):
        writer.writerow([round(d / 1000, 3), round(e, 1) if not np.isnan(e) else ""])

distances_km = distances_m / 1000
fig, ax = plt.subplots(figsize=(12, 5))
ax.plot(distances_km, elevations, color="#1f6fb2", linewidth=1.8)
ax.fill_between(distances_km, elevations, min(np.nanmin(elevations), 0), color="#1f6fb2", alpha=0.12)

ax.axvline(confluence_dist_km, color="#c0392b", linestyle="--", linewidth=1.2)
ax.text(confluence_dist_km, np.nanmax(elevations) * 0.92, "Waipā\nconfluence",
        color="#c0392b", ha="center", fontsize=9)

ax.scatter([0], [source_elev], color="#2e8b57", zorder=5, s=40)
ax.text(0, source_elev + np.nanmax(elevations) * 0.04, "Source\n(Lake Taupo outlet)",
        ha="left", fontsize=9, color="#2e8b57")

ax.scatter([distances_km[-1]], [mouth_elev], color="#8e44ad", zorder=5, s=40)
ax.text(distances_km[-1], mouth_elev + np.nanmax(elevations) * 0.04, "Mouth\n(Port Waikato)",
        ha="right", fontsize=9, color="#8e44ad")

ax.set_xlabel("Distance along mainstem (km)")
ax.set_ylabel("Elevation (m)")
ax.set_title("Waikato River — Elevation Profile, Source to Sea")
ax.grid(alpha=0.25)
plt.tight_layout()
plt.savefig("maps/waikato_elevation_profile.png", dpi=200)
print("\nSaved corrected mainstem/source/mouth/confluence gpkg files, "
      "output/waikato_elevation_profile.csv, and maps/waikato_elevation_profile.png")
