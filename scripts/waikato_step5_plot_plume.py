"""
Quick preview plot of the Port Waikato sediment plume: true-color RGB next
to the NDTI turbidity index, side by side.

Update RGB_PATH / NDTI_PATH below to match whatever filenames Google Drive
actually gave your downloaded files (they include the scene date, e.g.
waikato_mouth_rgb_2026-03-14.tif).
"""

import glob
import rasterio
import numpy as np
import matplotlib.pyplot as plt

rgb_matches = glob.glob("data/waikato_mouth_rgb_*.tif")
ndti_matches = glob.glob("data/waikato_mouth_ndti_*.tif")

if not rgb_matches or not ndti_matches:
    raise SystemExit(
        f"Could not find the exported files in data/. Found RGB: {rgb_matches}, "
        f"NDTI: {ndti_matches}. Make sure both .tif files from Google Drive are "
        f"saved into data/ with their original names."
    )

RGB_PATH = rgb_matches[0]
NDTI_PATH = ndti_matches[0]
print(f"Using RGB: {RGB_PATH}")
print(f"Using NDTI: {NDTI_PATH}")

with rasterio.open(RGB_PATH) as src:
    rgb = src.read([1, 2, 3]).astype(float) / 255.0
    rgb = np.transpose(rgb, (1, 2, 0))

with rasterio.open(NDTI_PATH) as src:
    ndti = src.read(1)
    ndti = np.where(ndti == src.nodata, np.nan, ndti)

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

axes[0].imshow(rgb)
axes[0].set_title("True Color — Port Waikato River Mouth")
axes[0].axis("off")

im = axes[1].imshow(ndti, cmap="YlOrBr", vmin=-0.3, vmax=0.3)
axes[1].set_title("NDTI (Turbidity Index) — brighter = more sediment")
axes[1].axis("off")
plt.colorbar(im, ax=axes[1], fraction=0.04, label="NDTI")

plt.tight_layout()
plt.savefig("maps/waikato_sediment_plume_preview.png", dpi=200)
print("Saved maps/waikato_sediment_plume_preview.png")
