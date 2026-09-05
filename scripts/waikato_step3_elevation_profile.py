"""
Waikato River — elevation profile from source (Lake Taupo outlet) to mouth
(Port Waikato), sampled from the SRTM DEM along the mainstem line.

Input:  output/waikato_mainstem.gpkg
        output/waikato_source_point.gpkg
        output/waikato_confluence_point.gpkg
        output/waikato_mouth_point.gpkg
        waikato_dem.tif  (from Task 2's GEE export)
Output: output/waikato_elevation_profile.csv
        maps/waikato_elevation_profile.png
"""

import geopandas as gpd
import numpy as np
import rasterio
import matplotlib.pyplot as plt
from shapely.geometry import Point

DEM_PATH = "data/waikato_dem.tif"
SAMPLE_INTERVAL_M = 500  # sample every 500 m along the river

mainstem = gpd.read_file("output/waikato_mainstem.gpkg")
source = gpd.read_file("output/waikato_source_point.gpkg")
confluence = gpd.read_file("output/waikato_confluence_point.gpkg")
mouth = gpd.read_file("output/waikato_mouth_point.gpkg")

line = mainstem.geometry.iloc[0]
if line.geom_type == "MultiLineString":
    line = max(line.geoms, key=lambda l: l.length)

with rasterio.open(DEM_PATH) as dem:
    dem_crs = dem.crs
    print(f"DEM CRS: {dem_crs}, size: {dem.width}x{dem.height}")

    # Reproject the mainstem + reference points to the DEM's CRS for sampling
    line_dem_crs = gpd.GeoSeries([line], crs=mainstem.crs).to_crs(dem_crs).iloc[0]
    source_dem = gpd.GeoSeries(source.geometry, crs=source.crs).to_crs(dem_crs).iloc[0]
    confluence_dem = gpd.GeoSeries(confluence.geometry, crs=confluence.crs).to_crs(dem_crs).iloc[0]
    mouth_dem = gpd.GeoSeries(mouth.geometry, crs=mouth.crs).to_crs(dem_crs).iloc[0]

    # Make sure we walk the line from source -> mouth. Compare line's start
    # point (in original NZTM CRS, where distances are meaningful metres) to
    # the known source point; flip if needed.
    line_nztm = mainstem.geometry.iloc[0]
    if line_nztm.geom_type == "MultiLineString":
        line_nztm = max(line_nztm.geoms, key=lambda l: l.length)
    start_pt = Point(line_nztm.coords[0])
    source_nztm = source.geometry.iloc[0]
    if start_pt.distance(source_nztm) > Point(line_nztm.coords[-1]).distance(source_nztm):
        line_nztm = line_nztm.reverse()
        line_dem_crs = line_dem_crs.reverse()

    total_length_m = line_nztm.length
    n_samples = int(total_length_m // SAMPLE_INTERVAL_M) + 1
    distances_m = np.linspace(0, total_length_m, n_samples)

    # Sample points along the line in NZTM (for correct distance-along-line),
    # then get the matching point in DEM CRS by fractional position.
    sample_points_dem_crs = [
        line_dem_crs.interpolate(d / total_length_m, normalized=True)
        for d in distances_m
    ]

    coords = [(p.x, p.y) for p in sample_points_dem_crs]
    elevations = [val[0] if val[0] != dem.nodata else np.nan for val in dem.sample(coords)]

    # Find approximate distance-along-line of the confluence point (project
    # onto the NZTM line, express as fraction, apply to distances_m range)
    confluence_nztm = confluence.geometry.iloc[0]
    confluence_frac = line_nztm.project(confluence_nztm, normalized=True)
    confluence_dist_km = confluence_frac * total_length_m / 1000

mouth_elev = elevations[-1]
source_elev = elevations[0]

print(f"Total mainstem length: {total_length_m/1000:.1f} km")
print(f"Source elevation: {source_elev:.1f} m")
print(f"Mouth elevation: {mouth_elev:.1f} m")
print(f"Confluence (Waipa) at ~{confluence_dist_km:.1f} km along the mainstem")

# --- Save CSV ---
import csv
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
ax.text(confluence_dist_km, max(np.nanmax(elevations) * 0.92, 10), "Waipā\nconfluence",
        color="#c0392b", ha="center", fontsize=9)

ax.scatter([0], [source_elev], color="#2e8b57", zorder=5, s=40)
ax.text(0, source_elev + max(elevations) * 0.04, "Source\n(Lake Taupo outlet)", ha="left", fontsize=9, color="#2e8b57")

ax.scatter([distances_km[-1]], [mouth_elev], color="#8e44ad", zorder=5, s=40)
ax.text(distances_km[-1], mouth_elev + max(elevations) * 0.04, "Mouth\n(Port Waikato)", ha="right", fontsize=9, color="#8e44ad")

ax.set_xlabel("Distance along mainstem (km)")
ax.set_ylabel("Elevation (m)")
ax.set_title("Waikato River — Elevation Profile, Source to Sea")
ax.grid(alpha=0.25)
plt.tight_layout()
plt.savefig("maps/waikato_elevation_profile.png", dpi=200)
print("\nSaved output/waikato_elevation_profile.csv and maps/waikato_elevation_profile.png")
