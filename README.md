# Waikato River: Source to Sea

Reconstructing the full course of New Zealand's longest river from its source at the Lake Taupo outlet, through its confluence with the Waipā River near Ngaruawahia, to its mouth at Port Waikato, using open geospatial data, and visualizing its sediment plume where it discharges into the Tasman Sea.

## What this project does

- Reconstructs a continuous Waikato River mainstem from OpenStreetMap waterway data (LINZ's official river layer carries no name attributes, so it couldn't be used for this step)
- Locates the source, the Waipā confluence, and the river mouth
- Builds a source-to-sea elevation profile using an SRTM DEM
- Visualizes the river's sediment plume at Port Waikato using Sentinel-2 imagery (true color + NDTI turbidity index)
- Produces a final cartographic map in QGIS

## Key results

| Metric | Value |
|---|---|
| Mainstem length (reconstructed) | 350.2 km |
| Documented real-world length (reference) | ~425 km |
| Source elevation (Lake Taupo outlet) | 362 m |
| Mouth elevation (Port Waikato) | 0 m |
| Waipā confluence position | ~239.8 km from source |
| Sentinel-2 scene used | 16 June 2025 |

See `reports/Waikato_River_Report.docx` for full methodology, results, and limitations.

## Notable technical challenge

The Waikato River is split into 15 disconnected fragments in OpenStreetMap (it passes through 8 hydro-lakes where the inundated channel isn't tagged as a river line). Two straightforward approaches to stitching these fragments together produced confidently wrong results, one silently dropped 42% of the river's length, the other produced a non-monotonic path ending 61 m above sea level. The final approach orders fragments by their projection onto a fixed line between two known real-world anchor points (Taupo outlet, Port Waikato mouth), which is robust regardless of gap size. Full writeup in the report.

## Repository structure

```
scripts/    Python processing scripts (data acquisition, mainstem stitching, elevation profile, plume export)
data/       Input data (LINZ layers, OSM export, DEM, Sentinel-2 exports) — not tracked in git
output/     Generated vector layers (mainstem, tributary, reference points) and elevation CSV — not tracked in git
maps/       Final map exports and preview plots
reports/    Technical report (docx)
```

## Data sources

- OpenStreetMap waterway data (via Overpass Turbo)
- USGS SRTM 30m DEM (via Google Earth Engine)
- Copernicus Sentinel-2 Surface Reflectance (via Google Earth Engine)
- LINZ NZ River Centrelines (Topo 1:50k) — background context only

## Tools

Python (geopandas, shapely, rasterio, numpy, pyproj), Google Earth Engine Python API, matplotlib, QGIS 3.x
