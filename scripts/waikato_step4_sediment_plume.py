"""
Port Waikato river mouth — sediment plume visualization using Sentinel-2.

A sediment plume is a transient feature (it appears/disappears with river
flow, tides, and recent rainfall), so unlike the DEM or nightlights work
earlier, we deliberately do NOT use a median composite here -- that would
average the plume away. Instead we pick the single least-cloudy Sentinel-2
scene available over the coastal AOI and export true-color RGB plus an NDTI
(turbidity) index.

Run with: python3 waikato_step4_sediment_plume.py
Requires: earthengine-api authenticated (same as the DEM export script)
"""

import ee

ee.Initialize(project="floodmapping-506505")

# Coastal AOI around the Waikato River mouth at Port Waikato
AOI = ee.Geometry.Rectangle([174.55, -37.45, 174.85, -37.25])

s2 = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(AOI)
    .filterDate("2023-01-01", "2026-09-01")
    .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 10))
    .sort("CLOUDY_PIXEL_PERCENTAGE")
)

count = s2.size().getInfo()
print(f"Found {count} Sentinel-2 scenes with <10% cloud cover over the AOI")
if count == 0:
    raise SystemExit("No low-cloud scenes found -- widen the date range or cloud threshold.")

best = ee.Image(s2.first())
date_str = best.date().format("YYYY-MM-dd").getInfo()
cloud_pct = best.get("CLOUDY_PIXEL_PERCENTAGE").getInfo()
print(f"Selected scene date: {date_str}, cloud cover: {cloud_pct:.1f}%")

rgb = best.select(["B4", "B3", "B2"]).divide(10000).clip(AOI)

# NDTI (Normalized Difference Turbidity Index) = (Red - Green) / (Red + Green)
# Higher values = more suspended sediment / turbid water
ndti = best.normalizedDifference(["B4", "B3"]).rename("NDTI").clip(AOI)

task_rgb = ee.batch.Export.image.toDrive(
    image=rgb.multiply(255).toByte(),
    description="Waikato_Mouth_RGB",
    folder="WaikatoRiverExports",
    fileNamePrefix=f"waikato_mouth_rgb_{date_str}",
    region=AOI,
    scale=10,
    maxPixels=1e9,
)
task_rgb.start()

task_ndti = ee.batch.Export.image.toDrive(
    image=ndti,
    description="Waikato_Mouth_NDTI",
    folder="WaikatoRiverExports",
    fileNamePrefix=f"waikato_mouth_ndti_{date_str}",
    region=AOI,
    scale=10,
    maxPixels=1e9,
)
task_ndti.start()

print(f"Started exports: waikato_mouth_rgb_{date_str}.tif, waikato_mouth_ndti_{date_str}.tif")
print("Check progress at https://code.earthengine.google.com/tasks")
