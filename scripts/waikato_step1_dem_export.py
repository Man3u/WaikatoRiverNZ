import ee

ee.Initialize(project="floodmapping-506505")

# Waikato catchment AOI: from Lake Taupo (source region) down to Port Waikato
# (mouth), covering the full mainstem and the Waipa River confluence at
# Ngaruawahia
AOI = ee.Geometry.Rectangle([175.0, -39.1, 176.5, -37.2])

dem = ee.Image("USGS/SRTMGL1_003").select("elevation").clip(AOI)
hillshade = ee.Terrain.hillshade(dem)

task_dem = ee.batch.Export.image.toDrive(
    image=dem,
    description="Waikato_DEM",
    folder="WaikatoRiverExports",
    fileNamePrefix="waikato_dem",
    region=AOI,
    scale=30,
    maxPixels=1e10,
)
task_dem.start()

task_hs = ee.batch.Export.image.toDrive(
    image=hillshade,
    description="Waikato_Hillshade",
    folder="WaikatoRiverExports",
    fileNamePrefix="waikato_hillshade",
    region=AOI,
    scale=30,
    maxPixels=1e10,
)
task_hs.start()

print("Started exports: Waikato_DEM, Waikato_Hillshade")
print("Done. Check https://code.earthengine.google.com/tasks")
