"""
Waikato River — extract mainstem, source point, and confluence points.

Input:  data/linz_rivers_waikato.gpkg  (LINZ NZ River Centrelines, clipped/
        exported to the Waikato catchment)
Output: output/waikato_mainstem.gpkg
        output/waikato_source_point.gpkg
        output/waikato_confluence_points.gpkg
"""

import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import linemerge

RIVERS_PATH = "data/linz_rivers_waikato.gpkg"

# Tributaries whose confluence with the mainstem we want to mark.
# Add/remove names to match whatever the LINZ "name" field actually
# contains in your download (print unique names first if unsure).
TRIBUTARIES_OF_INTEREST = ["Waipa River", "Waikato River"]

rivers = gpd.read_file(RIVERS_PATH)
print(f"Loaded {len(rivers)} river features, CRS: {rivers.crs}")
print("Columns:", list(rivers.columns))

# LINZ layers use different name-column labels across exports/versions.
NAME_CANDIDATES = ["name", "name_ascii", "name1", "namelabel", "river_name", "GAZETTED_NAME"]
NAME_COL = next((c for c in NAME_CANDIDATES if c in rivers.columns), None)
if NAME_COL is None:
    raise SystemExit(
        f"Could not find a name column automatically. Columns available: "
        f"{list(rivers.columns)}\nTell me which column holds the river name "
        f"and I'll update NAME_CANDIDATES."
    )
print(f"Using name column: '{NAME_COL}'")
print("Unique names sample:", rivers[NAME_COL].dropna().unique()[:20])

# --- 1. Extract and merge the Waikato River mainstem ---
mainstem_parts = rivers[rivers[NAME_COL] == "Waikato River"]
if mainstem_parts.empty:
    raise SystemExit(
        f"No features named 'Waikato River' found in column '{NAME_COL}' — "
        "check the unique names printed above and adjust the filter."
    )

merged = linemerge(mainstem_parts.geometry.union_all())
mainstem_gdf = gpd.GeoDataFrame(
    {"name": ["Waikato River"]}, geometry=[merged], crs=rivers.crs
)
mainstem_gdf.to_file("output/waikato_mainstem.gpkg", driver="GPKG")
print(f"Mainstem merged: {len(mainstem_parts)} segments -> 1 line, "
      f"length {merged.length/1000:.1f} km (in {rivers.crs})")

# --- 2. Identify the source point ---
# The Waikato's true source is Lake Taupo's outlet at Taupo township, which
# is the northern/upper end of the mainstem line. Compare the two endpoint
# latitudes and take the southernmost (closest to Taupo, ~38.68S) as source,
# northernmost (closest to Port Waikato, ~37.38S) as mouth.
if merged.geom_type == "MultiLineString":
    lines = list(merged.geoms)
    lines.sort(key=lambda l: l.length, reverse=True)
    endpoints = [Point(lines[0].coords[0]), Point(lines[0].coords[-1])]
else:
    endpoints = [Point(merged.coords[0]), Point(merged.coords[-1])]

source_pt, mouth_pt = sorted(endpoints, key=lambda p: p.y, reverse=False)
# southernmost latitude (most negative... actually NZ is negative lat, so
# "southernmost" = more negative = smaller y). Taupo (~ -38.68) is south of
# Port Waikato (~ -37.38), so the source has the SMALLER (more negative) y.
source_pt, mouth_pt = min(endpoints, key=lambda p: p.y), max(endpoints, key=lambda p: p.y)

source_gdf = gpd.GeoDataFrame(
    {"label": ["Source (Lake Taupo outlet, near Taupo township)"]},
    geometry=[source_pt], crs=rivers.crs,
)
mouth_gdf = gpd.GeoDataFrame(
    {"label": ["Mouth (Port Waikato / Tasman Sea)"]},
    geometry=[mouth_pt], crs=rivers.crs,
)
source_gdf.to_file("output/waikato_source_point.gpkg", driver="GPKG")
mouth_gdf.to_file("output/waikato_mouth_point.gpkg", driver="GPKG")
print(f"Source point: {source_pt}")
print(f"Mouth point:  {mouth_pt}")

# --- 3. Identify confluence points ---
# A confluence = where a tributary's endpoint touches the mainstem line.
confluences = []
for trib_name in TRIBUTARIES_OF_INTEREST:
    if trib_name == "Waikato River":
        continue
    trib_parts = rivers[rivers[NAME_COL] == trib_name]
    if trib_parts.empty:
        print(f"  (no features found for tributary '{trib_name}', skipping)")
        continue
    trib_merged = linemerge(trib_parts.geometry.union_all())
    trib_lines = list(trib_merged.geoms) if trib_merged.geom_type == "MultiLineString" else [trib_merged]
    # longest segment = main tributary channel
    trib_lines.sort(key=lambda l: l.length, reverse=True)
    main_trib_line = trib_lines[0]
    for end in [Point(main_trib_line.coords[0]), Point(main_trib_line.coords[-1])]:
        dist = merged.distance(end)
        if dist < 50:  # within 50m (CRS units) of the mainstem = confluence
            confluences.append({"tributary": trib_name, "geometry": end, "distance_m": dist})

if confluences:
    conf_gdf = gpd.GeoDataFrame(confluences, crs=rivers.crs)
    conf_gdf.to_file("output/waikato_confluence_points.gpkg", driver="GPKG")
    print(f"Found {len(confluences)} confluence point(s):")
    for c in confluences:
        print(f"  {c['tributary']} joins mainstem at distance {c['distance_m']:.1f} m")
else:
    print("No confluence points found — check TRIBUTARIES_OF_INTEREST names "
          "against the 'name' column values printed above.")

print("\nDone. Outputs written to output/waikato_mainstem.gpkg, "
      "output/waikato_source_point.gpkg, output/waikato_mouth_point.gpkg, "
      "output/waikato_confluence_points.gpkg")
