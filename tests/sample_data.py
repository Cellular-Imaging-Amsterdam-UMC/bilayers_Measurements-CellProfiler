"""Sample job: an RGB image with its nuclei, cells and aggregates label masks.

Written as OME-TIFF (stored in tests/data/in) or OME-Zarr, the two input formats. Usage:
    python tests/sample_data.py <folder> [--zarr]
"""
import argparse
from pathlib import Path

import numpy as np
import tifffile

from bilayers_auto.contract import add_omero_metadata
from bilayers_auto.conversion import ZARR, convert

NAME = "sample"
SUFFIXES = ("_Nuclei_Mask", "_Cells_Mask", "_Aggregates_Mask")


def _disk(shape, center, radius):
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    return (yy - center[0]) ** 2 + (xx - center[1]) ** 2 <= radius ** 2


def make_images(size: int = 128) -> dict:
    """``{file stem: array}``: RGB image (YXC, uint8) and uint16 label masks, two cells."""
    shape = (size, size)
    cells, nuclei, aggregates = (np.zeros(shape, np.uint16) for _ in range(3))
    for label, center in enumerate([(40, 40), (88, 88)], start=1):
        cells[_disk(shape, center, 28)] = label
        nuclei[_disk(shape, center, 12)] = label
        aggregates[_disk(shape, (center[0] + 18, center[1]), 4)] = label
    rng = np.random.default_rng(0)
    image = rng.integers(5, 20, (*shape, 3)).astype(np.uint8)
    image[..., 0][cells > 0] += 60
    image[..., 1][nuclei > 0] += 120
    image[..., 2][aggregates > 0] += 200
    return {NAME: image, **{NAME + suffix: mask for suffix, mask in zip(SUFFIXES, (nuclei, cells, aggregates))}}


def write_sample(folder: Path, as_zarr: bool = False) -> list:
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for stem, data in make_images().items():
        tiff = folder / f"{stem}.ome.tif"
        # the OME name names the converted OME-Zarr (tifffile's default is Image0)
        tifffile.imwrite(tiff, data, photometric="rgb" if data.ndim == 3 else "minisblack", ome=True,
                         metadata={"Name": stem})
        if as_zarr:
            written += to_zarr(tiff, folder)
        else:
            written.append(tiff)
    return written


def to_zarr(tiff: Path, folder: Path) -> list:
    """The OME-TIFF as an exported OME-Zarr (with the omero rendering block), replacing it."""
    stores = convert(tiff, folder, ZARR)
    tiff.unlink()
    for store in stores:
        add_omero_metadata(store)
    return stores


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--zarr", action="store_true", help="write OME-Zarr instead of OME-TIFF")
    args = parser.parse_args()
    for path in write_sample(args.folder, as_zarr=args.zarr):
        print(path)
