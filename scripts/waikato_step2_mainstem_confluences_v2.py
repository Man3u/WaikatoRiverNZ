"""
Waikato River — extract mainstem, source point, and confluence point.

The LINZ River Centrelines layer (data/linz_rivers_waikato.gpkg) turned out to
carry no name attribute (only a t50_fid reference ID) — LINZ stores water
feature names in a separate gazetteer layer, not on the line geometries
themselves. Instead we pull the named Waikato and Waipa rivers directly from
OpenStreetMap (same osmnx approach used in the Hyderabad UHI project), which
tags waterway geometries with real names.

Output (all reprojected to EPSG:2193 to match the LINZ/SRTM data):
    output/waikato_mainstem.gpkg
    output/waipa_tributary.gpkg
    output/waikato_source_point.gpkg
    output/waikato_mouth_point.gpkg
    output/waikato_confluence_point.gpkg
"""

import geopandas as gpd
import osmnx as ox
from shapely.geometry import Point
from shapely.ops import linemerge

NZTM = "EPSG:2193"

# Bounding box covering Lake Taupo outlet -> Ngaruawahia confluence -> Port
# Waikato mouth. Format: (west, south, east, north) in lon/lat.
BBOX = (174.5, -39.0, 176.3, -37.1)

TAGS = {"waterway": "river"}

# The main overpass-api.de endpoint was unreachable from Python (blocked
# locally even though it loaded fine in a browser) -- using a mirror instead.
ox.settings.overpass_url = "https://overpass.kumi.systems/api"

print("Querying OpenStreetMap for waterway=river features in the Waikato bbox...")
try:
    # osmnx >= 1.9
    rivers = ox.features_from_bbox(bbox=BBOX, tags=TAGS)
except TypeError:
    # older osmnx signature: north, south, east, west
    west, south, east, north = BBOX
    rivers = ox.features_from_bbox(north, south, east, west, tags=TAGS)

rivers = rivers[rivers.geometry.type.isin(["LineString", "MultiLineString"])]
print(f"Retrieved {len(rivers)} waterway features")
print("Sample names:", rivers["name"].dropna().unique()[:15])

def extract_named(gdf, target_name):
    parts = gdf[gdf["name"] == target_name]
    if parts.empty:
        raise SystemExit(f"No OSM features named '{target_name}' found in this bbox.")
    merged = linemerge(parts.geometry.union_all())
    return merged, len(parts)

# --- Mainstem ---
mainstem_geom, n_parts = extract_named(rivers, "Waikato River")
mainstem_gdf = gpd.GeoDataFrame({"name": ["Waikato River"]}, geometry=[mainstem_geom], crs="EPSG:4326").to_crs(NZTM)
mainstem_gdf.to_file("output/waikato_mainstem.gpkg", driver="GPKG")
mainstem_line = mainstem_gdf.geometry.iloc[0]
print(f"Mainstem: {n_parts} OSM segments merged, length {mainstem_line.length/1000:.1f} km ({NZTM})")

# --- Tributary (Waipa) ---
waipa_geom, n_parts_w = extract_named(rivers, "Waipa River")
waipa_gdf = gpd.GeoDataFrame({"name": ["Waipa River"]}, geometry=[waipa_geom], crs="EPSG:4326").to_crs(NZTM)
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
# snap to the actual nearest point on the mainstem for a clean map point
confluence_pt = mainstem_line.interpolate(mainstem_line.project(confluence_end))

gpd.GeoDataFrame(
    {"label": ["Confluence - Waipa River joins Waikato River (near Ngaruawahia)"], "gap_m": [dist]},
    geometry=[confluence_pt], crs=NZTM,
).to_file("output/waikato_confluence_point.gpkg", driver="GPKG")
print(f"Confluence point (NZTM): {confluence_pt}, gap to mainstem: {dist:.1f} m")

print("\nDone. Outputs in output/: waikato_mainstem.gpkg, waipa_tributary.gpkg, "
      "waikato_source_point.gpkg, waikato_mouth_point.gpkg, waikato_confluence_point.gpkg")
