"""
Waikato River — extract mainstem, source point, and confluence point.

Reads the Waikato/Waipa river geometries from a GeoJSON exported manually
from Overpass Turbo (https://overpass-turbo.eu/), since live Overpass API
calls from this machine were unreliable (blocked/overloaded).

Input:  data/waikato_waipa_rivers_osm.geojson
Output: output/waikato_mainstem.gpkg
        output/waipa_tributary.gpkg
        output/waikato_source_point.gpkg
        output/waikato_mouth_point.gpkg
        output/waikato_confluence_point.gpkg
"""

import geopandas as gpd
from shapely.geometry import Point
from shapely.ops import linemerge

NZTM = "EPSG:2193"
GEOJSON_PATH = "data/waikato_waipa_rivers_osm.geojson"

gdf = gpd.read_file(GEOJSON_PATH)
print(f"Loaded {len(gdf)} features, CRS: {gdf.crs}")
print("Columns:", list(gdf.columns))

# Overpass Turbo GeoJSON exports usually flatten tags directly into
# properties, so "name" should just be a column. Handle the rare case where
# it's nested under a "tags" dict instead.
if "name" not in gdf.columns and "tags" in gdf.columns:
    gdf["name"] = gdf["tags"].apply(lambda t: t.get("name") if isinstance(t, dict) else None)

if "name" not in gdf.columns:
    raise SystemExit(f"No 'name' field found. Columns available: {list(gdf.columns)}")

print("Unique names:", gdf["name"].dropna().unique())

if gdf.crs is None:
    gdf = gdf.set_crs("EPSG:4326")

def extract_named(gdf, exact_name):
    # Exact match (case-sensitive, including macrons) -- a broad substring
    # match pulled in unrelated rivers worldwide (Waipara, Waipaoa, even a
    # Rio Waiparu in South America), so we match precisely instead.
    parts = gdf[gdf["name"] == exact_name]
    if parts.empty:
        raise SystemExit(
            f"No features named exactly '{exact_name}' found. "
            f"Check the unique names list printed above for the correct spelling."
        )
    merged = linemerge(parts.geometry.union_all())
    return merged, len(parts)

# --- Mainstem ---
mainstem_geom, n_parts = extract_named(gdf, "Waikato River")
mainstem_gdf = gpd.GeoDataFrame({"name": ["Waikato River"]}, geometry=[mainstem_geom], crs=gdf.crs).to_crs(NZTM)
mainstem_gdf.to_file("output/waikato_mainstem.gpkg", driver="GPKG")
mainstem_line = mainstem_gdf.geometry.iloc[0]
print(f"Mainstem: {n_parts} OSM segments merged, length {mainstem_line.length/1000:.1f} km ({NZTM})")

# --- Tributary (Waipa) ---
waipa_geom, n_parts_w = extract_named(gdf, "Waipā River")
waipa_gdf = gpd.GeoDataFrame({"name": ["Waipa River"]}, geometry=[waipa_geom], crs=gdf.crs).to_crs(NZTM)
waipa_gdf.to_file("output/waipa_tributary.gpkg", driver="GPKG")
waipa_line = waipa_gdf.geometry.iloc[0]
print(f"Waipa tributary: {n_parts_w} OSM segments merged, length {waipa_line.length/1000:.1f} km ({NZTM})")

# --- Source / mouth points ---
# In NZTM, northing increases northward. Taupo (source) is south of Port
# Waikato (mouth), so source = endpoint with the smaller northing.
def get_endpoints(line):
    if line.geom_type == "MultiLineString":
        parts = sorted(line.geoms, key=lambda l: l.length, reverse=True)
        line = parts[0]
    return Point(line.coords[0]), Point(line.coords[-1])

p1, p2 = get_endpoints(mainstem_line)
source_pt, mouth_pt = (p1, p2) if p1.y < p2.y else (p2, p1)

gpd.GeoDataFrame({"label": ["Source - Lake Taupo outlet, Taupo township"]}, geometry=[source_pt], crs=NZTM)\
    .to_file("output/waikato_source_point.gpkg", driver="GPKG")
gpd.GeoDataFrame({"label": ["Mouth - Port Waikato / Tasman Sea"]}, geometry=[mouth_pt], crs=NZTM)\
    .to_file("output/waikato_mouth_point.gpkg", driver="GPKG")
print(f"Source point (NZTM): {source_pt}")
print(f"Mouth point  (NZTM): {mouth_pt}")

# --- Confluence point (Waipa joins Waikato near Ngaruawahia) ---
w1, w2 = get_endpoints(waipa_line)
confluence_end = min([w1, w2], key=lambda p: mainstem_line.distance(p))
dist = mainstem_line.distance(confluence_end)
confluence_pt = mainstem_line.interpolate(mainstem_line.project(confluence_end))

gpd.GeoDataFrame(
    {"label": ["Confluence - Waipa River joins Waikato River (near Ngaruawahia)"], "gap_m": [dist]},
    geometry=[confluence_pt], crs=NZTM,
).to_file("output/waikato_confluence_point.gpkg", driver="GPKG")
print(f"Confluence point (NZTM): {confluence_pt}, gap to mainstem: {dist:.1f} m")

print("\nDone. Outputs in output/: waikato_mainstem.gpkg, waipa_tributary.gpkg, "
      "waikato_source_point.gpkg, waikato_mouth_point.gpkg, waikato_confluence_point.gpkg")
