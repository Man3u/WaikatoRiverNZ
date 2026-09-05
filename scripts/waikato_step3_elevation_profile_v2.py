"""
Waikato River — elevation profile from source (Lake Taupo outlet) to mouth
(Port Waikato), sampled from the SRTM DEM along the mainstem line.

v2 fix: the merged mainstem is a MultiLineString (its 15 OSM segments don't
touch at exactly identical coordinates), and v1 mistakenly kept only the
single longest fragment -- silently dropping ~148 km of river out of the
real 332.9 km mainstem. This version stitches ALL fragments together in
source-to-mouth order (nearest-endpoint chaining) before sampling.

Input:  output/waikato_mainstem.gpkg
        output/waikato_source_point.gpkg
        output/waikato_confluence_point.gpkg
        output/waikato_mouth_point.gpkg
        data/waikato_dem.tif
Output: output/waikato_elevation_profile.csv
        maps/waikato_elevation_profile.png
"""

import csv
import geopandas as gpd
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from shapely.geometry import Point, LineString

DEM_PATH = "data/waikato_dem.tif"
SAMPLE_INTERVAL_M = 500  # sample every 500 m along the river


def stitch_fragments(mls, start_point):
    """Greedily chain a MultiLineString's fragments into one LineString,
    always attaching whichever remaining fragment has an endpoint closest
    to the current chain end, starting near start_point."""
    parts = list(mls.geoms) if mls.geom_type == "MultiLineString" else [mls]
    remaining = parts[:]
    ordered_coords = []
    current_pt = start_point
    total_gap = 0.0

    while remaining:
        best_idx, best_dist, best_flip = None, None, False
        for i, part in enumerate(remaining):
            p0, p1 = Point(part.coords[0]), Point(part.coords[-1])
            d0, d1 = current_pt.distance(p0), current_pt.distance(p1)
            if best_dist is None or d0 < best_dist:
                best_dist, best_idx, best_flip = d0, i, False
            if d1 < best_dist:
                best_dist, best_idx, best_flip = d1, i, True

        part = remaining.pop(best_idx)
        coords = list(part.coords)
        if best_flip:
            coords = coords[::-1]

        if ordered_coords:
            total_gap += best_dist  # distance between chained fragment ends
        ordered_coords.extend(coords)
        current_pt = Point(coords[-1])

    return LineString(ordered_coords), total_gap


mainstem = gpd.read_file("output/waikato_mainstem.gpkg")
source = gpd.read_file("output/waikato_source_point.gpkg")
confluence = gpd.read_file("output/waikato_confluence_point.gpkg")
mouth = gpd.read_file("output/waikato_mouth_point.gpkg")

raw_geom = mainstem.geometry.iloc[0]
source_nztm = source.geometry.iloc[0]

line_nztm, gap_total_m = stitch_fragments(raw_geom, source_nztm)
print(f"Stitched {len(list(raw_geom.geoms)) if raw_geom.geom_type=='MultiLineString' else 1} "
      f"fragments into one path; total inter-fragment gap: {gap_total_m:.1f} m")

total_length_m = line_nztm.length
print(f"Total mainstem length (stitched): {total_length_m/1000:.1f} km")

with rasterio.open(DEM_PATH) as dem:
    dem_crs = dem.crs
    print(f"DEM CRS: {dem_crs}, size: {dem.width}x{dem.height}")

    line_dem_crs = gpd.GeoSeries([line_nztm], crs=mainstem.crs).to_crs(dem_crs).iloc[0]

    n_samples = int(total_length_m // SAMPLE_INTERVAL_M) + 1
    distances_m = np.linspace(0, total_length_m, n_samples)

    sample_points_dem_crs = [
        line_dem_crs.interpolate(d / total_length_m, normalized=True)
        for d in distances_m
    ]
    coords = [(p.x, p.y) for p in sample_points_dem_crs]
    elevations = [val[0] if val[0] != dem.nodata else np.nan for val in dem.sample(coords)]

    confluence_nztm = confluence.geometry.iloc[0]
    confluence_frac = line_nztm.project(confluence_nztm, normalized=True)
    confluence_dist_km = confluence_frac * total_length_m / 1000

elevations = np.array(elevations, dtype=float)
mouth_elev = elevations[-1]
source_elev = elevations[0]

print(f"Source elevation: {source_elev:.1f} m")
print(f"Mouth elevation: {mouth_elev:.1f} m")
print(f"Confluence (Waipa) at ~{confluence_dist_km:.1f} km along the mainstem")

# --- Save CSV ---
with open("output/waikato_elevation_profile.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["distance_km", "elevation_m"])
    for d, e in zip(distances_m, elevations):
        writer.writerow([round(d / 1000, 3), round(e, 1) if not np.isnan(e) else ""])

# --- Plot ---
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
print("\nSaved output/waikato_elevation_profile.csv and maps/waikato_elevation_profile.png")
