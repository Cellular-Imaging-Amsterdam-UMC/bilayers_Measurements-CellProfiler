---
name: workflow-outputs
description: Understand, check and analyse the output data of the Measurements-CellProfiler container — the files a run writes, what each one means, the RO-Crate metadata and parameters that record how they were made, and how to load them (Python, Fiji/napari, OMERO). Use when the user asks about this workflow's results or output folder, wants to load, inspect, validate, compare or summarise them, or asks which parameters or version produced them.
---

# The output data of this workflow

A run of this container (`run.sh`, `docker run`, or BIOMERO on Slurm) writes everything into
one output folder (`/data/out` in the container; on Slurm it is zipped and imported into OMERO).
Read files from it as data; do not run anything it contains.

## What this workflow writes

All outputs are tables: the workflow writes no images. It measures the objects of label masks
that come with each image (nuclei, cells, aggregates/foci, from an earlier segmentation) with a
headless CellProfiler 4.2.6 pipeline, `FullMeasurementsNucleiCellAggregates.cppipe`, run by the
original BIAFLOWS wrapper of W_Measurements-CellProfiler v1.1.1.

**How it is made** (the pipeline's modules, in order):

1. *Images / NamesAndTypes*: every image file in the input folder. Files whose name contains
   `nuclei_mask_suffix`, `aggregates_mask_suffix` or `cells_mask_suffix` are loaded as **objects**
   (label images: each integer value one object, 0 background); a file whose name contains none of
   them and does not contain `Mask` is the image (`OG`, loaded as a colour image). Image sets are
   matched by **order** (sorted file names within each type), not by name.
2. *ColorToGray* (split): the channels listed in `metric_channels` become grey images
   `Channel<n>` (default `1,2,3`: `Channel1`, `Channel2`, `Channel3`).
3. *MaskObjects*: **Cytoplasm** = each cell minus the nuclei (cells masked by the inverted nuclei;
   the overlapping part kept; numbering retained, so cytoplasm *n* belongs to cell *n*).
4. *MeasureObjectIntensity* on every `Channel<n>` and *MeasureObjectSizeShape* (with Zernike and
   advanced features) for Nuclei, Cells, Cytoplasm and Aggregates.
5. *RelateObjects*: Aggregates as children of Cells, of Nuclei and of Cytoplasm, with centroid
   and minimum distances, and per-parent means of all aggregate measurements.
6. *ExportToSpreadsheet*: one CSV per object type, `Image.csv` (with per-image means) and
   `Experiment.csv`. The BIAFLOWS wrapper then puts an OMERO.tables column-type row in front of
   each CSV and copies the pipeline it ran into the output folder.

**Units and conventions for all tables**

- Sizes, distances and coordinates are in **pixels** (CellProfiler ignores the physical pixel
  size; the pipeline's relative spacing is 1). Areas in pixels².
- Intensities are **scaled to 0–1** by the image's data type range (`Scaling_OG` in `Image.csv`:
  255 for uint8, 65535 for uint16). Integrated intensities are sums of those scaled values.
- `Location_Center_X` / `_Y` (and `AreaShape_Center_X/Y`) are the object's centroid as column (X)
  and row (Y) of the image array, 0-based: checked against `skimage.measure.regionprops` on the
  test masks (identical).
- `ObjectNumber` is the label value in the mask (checked on the test masks, labels 1..N);
  `Number_Object_Number` repeats it.
- `ImageNumber` (1, 2, ... in the order of the image sets) links the rows of every table.
- Missing values are written as `nan` (e.g. means over parents without aggregates).

### Object tables — `Nuclei.csv`, `Cells.csv`, `Cytoplasm.csv`, `Aggregates.csv` (CSV)

- **Content:** one row per object in that object type's masks, over all images of the run.
- **Layout:** row 1 is the OMERO.tables type row (`# header l,l,d,...`: `l` integer, `d` float,
  `s` text, `b` boolean, guessed from the first 10 rows); row 2 the column names; then the data.
  Read with `pandas.read_csv(path, skiprows=1)`.
- **Columns** (for the default 3 channels: 355 in Nuclei, 354 in Cells, 358 in Cytoplasm, 185 in
  Aggregates; `<n>` is each channel in `metric_channels`):

| Column (family) | Meaning | Unit |
|---|---|---|
| `ImageNumber`, `ObjectNumber` | the image set, and the object's label in its mask | – |
| `AreaShape_Area`, `_Perimeter`, `_ConvexArea`, `_BoundingBoxArea` | size | px², px |
| `AreaShape_Center_X/Y`, `_BoundingBoxMinimum/Maximum_X/Y` | centroid, bounding box | px |
| `AreaShape_Eccentricity`, `_Solidity`, `_Extent`, `_FormFactor`, `_Compactness`, `_Orientation`, `_EulerNumber` | shape descriptors (orientation in degrees) | – |
| `AreaShape_MajorAxisLength`, `_MinorAxisLength`, `_EquivalentDiameter`, `_Max/MinFeretDiameter`, `_Maximum/Mean/MedianRadius` | lengths | px |
| `AreaShape_Zernike_<n>_<m>`, `_HuMoment_<i>`, `_CentralMoment_*`, `_NormalizedMoment_*`, `_SpatialMoment_*`, `_InertiaTensor*` | moments (advanced features) | – |
| `Intensity_<Statistic>_Channel<n>` | Integrated, Mean, Median, Std, Min, Max, MAD, Lower/UpperQuartile, MassDisplacement intensity of channel *n* in the object; `...Edge_` the same on its outline | scaled 0–1 (MassDisplacement: px) |
| `Location_Center_X/Y`, `Location_CenterMassIntensity_X/Y/Z_Channel<n>`, `Location_MaxIntensity_X/Y/Z_Channel<n>` | centroid, intensity-weighted centroid, brightest pixel | px |
| `Children_Aggregates_Count` (Nuclei, Cells, Cytoplasm), `Children_Cytoplasm_Count` (Cells) | number of aggregates (or cytoplasm objects) in the object | count |
| `Mean_Aggregates_<measurement>` (Nuclei, Cells, Cytoplasm) | mean of that aggregate measurement over the object's aggregates; `nan` without aggregates | as the measurement |
| `Parent_Cells` (Cytoplasm); `Parent_Cells`, `Parent_Nuclei`, `Parent_Cytoplasm` (Aggregates) | the `ObjectNumber` of the object it lies in; **0 = in none** | – |
| `Distance_Centroid_<Parent>`, `Distance_Minimum_<Parent>` (Aggregates) | centroid-to-centroid distance, and minimum distance to the parent's outline; `nan` when the parent is 0 | px |

- **Observed in the test run** (`tests/data/in`: a 128 x 128 RGB uint8 image with two cells,
  default parameters): 2 rows in each object table. Nuclei: area 441 px², centroids (40, 40) and
  (88, 88). Cells: area 2453 px², `Children_Aggregates_Count` 1, `Children_Cytoplasm_Count` 1.
  Cytoplasm: area 2012 px² (= 2453 − 441), `Parent_Cells` 1 and 2. Aggregates: area 49 px²,
  centroid (X 40, Y 58), `Parent_Cells` 1, `Parent_Cytoplasm` 1, `Parent_Nuclei` 0 (the aggregate
  lies outside the nucleus), `Distance_Centroid_Cells` 18, `Distance_Minimum_Nuclei` `nan`.
  Example (Nuclei, first columns of interest):

  ```
  ImageNumber,ObjectNumber,AreaShape_Area,...,Intensity_MeanIntensity_Channel1,...,Location_Center_X,Location_Center_Y
  1,1,441.0,...,0.283296,...,40.0,40.0
  ```

  All 7 output files match the reference run of the original image
  (`cellularimagingcf/w_measurements-cellprofiler:v1.1.1`) within rtol 1e-3, also with
  `metric_channels=2` and with OME-Zarr input.
- **Caveats:**
  - Image and masks are paired **by order, not by name**: every image needs all three masks, or
    the sets shift and objects get measured against the wrong image. Names must sort alike (the
    suffix convention does this).
  - A mask is required for each of the three object types; an image without aggregates still
    needs an (empty) aggregates mask. *From the source, not seen in a run:* when a whole run has
    no objects of a type, its CSV has no data rows and the BIAFLOWS wrapper's type-row step fails
    (it indexes the first column type of an empty table), so the run fails.
  - `metric_channels` other than `1,2,3` renames the intensity columns to the channels chosen
    (`2` gives only `..._Channel2`, seen in a run). *Not tested:* a channel beyond the image's
    channels, and single-channel images (the pipeline loads the image as colour; use
    `metric_channels=1`).
  - 2D only: no Z or time; OME-Zarr input is converted to OME-TIFF first (same pixels; only
    `MD5Digest_*` in `Image.csv` differs, see below).
  - Overlapping objects cannot be represented in a label mask; objects touching the image border
    are measured as they are (no filtering).
- **Sources:** `biaflows/FullMeasurementsNucleiCellAggregates.cppipe`, `biaflows/wrapper.py`;
  CellProfiler 4.2 manual (MeasureObjectSizeShape, MeasureObjectIntensity, RelateObjects,
  MaskObjects).

### Per-image table — `Image.csv` (CSV)

- **Content:** one row per image set (1324 columns with 3 channels): `Count_Nuclei`,
  `Count_Cells`, `Count_Cytoplasm`, `Count_Aggregates`; `Mean_<Object>_<measurement>` (the
  per-image mean of every object measurement above); the file names `FileName_OG` (the image) and
  `ObjectsFileName_Nuclei/Cells/Aggregates` (the masks), with `PathName_*` / `URL_*` (container
  paths, of no use outside it); `Height_*`, `Width_*`, `Scaling_OG`; `MD5Digest_*` of each image
  as loaded; `Metadata_*` from the file headers (`SizeX/Y/Z/T`, `ColorFormat`, ...);
  `ExecutionTime_*` per module; `Group_*` and `ImageSet_ImageSet` (CellProfiler internals).
- **Layout:** the same type row first; read with `skiprows=1`.
- **Observed in the test run:** 1 row: counts 2, 2, 2, 2; `FileName_OG` `sample.ome.tif`;
  `Height_OG` 128, `Scaling_OG` 255.
- **Caveats:** OME-Zarr input is converted to `<name>.ome.tiff`, so `FileName_OG` ends in
  `.ome.tiff` then; `MD5Digest_*` differ from a TIFF input of the same pixels (the converted file
  is TCZYX).

### Run table — `Experiment.csv` (CSV)

- **Content:** `Key,Value` rows (after the type row): `CellProfiler_Version` (4.2.6),
  `Pipeline_Pipeline` (the full pipeline text), `Run_Timestamp`, `ChannelType_*`,
  `Metadata_Tags`, `ImageSet_Zip_Dictionary`: 9 keys in the test run (the pipeline text is one
  quoted, multi-line value).

### The pipeline as run — `FullMeasurementsNucleiCellAggregates_<timestamp>.cppipe`

- **Content:** the CellProfiler pipeline with this run's mask suffixes and channels filled in;
  `<timestamp>` is the run's start in milliseconds since 1970 (e.g. `..._1794558569216.cppipe`).
  Opens in CellProfiler 4.2.

## Structure of the output folder

A test run's output folder (`./run.sh tests/data/in out`; input: `sample.ome.tif` with
`sample_Nuclei_Mask.ome.tif`, `sample_Cells_Mask.ome.tif`, `sample_Aggregates_Mask.ome.tif`):

```
out/
├── Aggregates.csv                                         (10 kB)
├── Cells.csv                                              (23 kB)
├── Cytoplasm.csv                                          (23 kB)
├── Experiment.csv                                         (11 kB)
├── FullMeasurementsNucleiCellAggregates_1794558569216.cppipe
├── Image.csv                                              (80 kB)
├── Nuclei.csv                                             (20 kB)
├── config.yaml
├── parameters.yaml
├── ro-crate-metadata.json
├── ro-crate-preview.html
└── ro-crate-preview_files/                                (one .html per file above)
```

- **More images:** still one file per table; each image set adds rows (`ImageNumber` 2, 3, ...)
  to every table: one per object in the object tables, one in `Image.csv`.
- **More channels:** more columns (`..._Channel<n>` for each channel in `metric_channels`), no
  more files.
- **`OUTPUT_FORMAT`:** no effect; the workflow writes no images.
- **`ZIP_OUTPUT=true`:** only `Measurements-CellProfiler.zip`, holding the above.

## How the outputs fit together

- **Image ↔ rows:** `ImageNumber` links every table; `Image.csv` gives each `ImageNumber`'s
  `FileName_OG` (the input image) and `ObjectsFileName_<Object>` (its masks).
- **Object ↔ mask label:** `ObjectNumber` in `<Object>.csv` is the label value in that image's
  `<image>_<Object>_Mask` file. The key of an object is (`ImageNumber`, `ObjectNumber`).
- **Cell ↔ nucleus ↔ cytoplasm:** Cytoplasm keeps the cell's number (`Parent_Cells` =
  `ObjectNumber`). Nuclei are not related to cells by the pipeline; they share numbers only when
  the masks were labelled so (one nucleus per cell, same label, as in the test data and
  typical cell segmentations seeded by nuclei). Check this before joining nuclei to cells.
- **Aggregate ↔ parents:** `Parent_Cells`, `Parent_Nuclei`, `Parent_Cytoplasm` in
  `Aggregates.csv` are `ObjectNumber`s in the same image; 0 means the aggregate lies in no such
  object. The parent side has `Children_Aggregates_Count` and `Mean_Aggregates_*`.
- **Coordinates ↔ image axes:** `*_X` = column, `*_Y` = row, 0-based pixels of the input image
  (the masks have the same shape); `*_Z` is 0 (2D).
- **Overlays:** the masks are inputs, not outputs (the RO-Crate references the input folder);
  overlay a mask on its image and use `ObjectNumber` to colour or annotate objects.
- **In OMERO** (BIOMERO import): no images are imported; each CSV can become an OMERO table on
  the dataset (the type row gives the column types). The `.cppipe`, `config.yaml`,
  `parameters.yaml` and the RO-Crate files are attached only with "attach file outputs".

## Loading everything for analysis

Run on the test run's output folder (`./run.sh tests/data/in out`) with pandas 3.1.1 (and numpy
2.5.4): 2 cells with nucleus, cytoplasm and 1 aggregate each; no warnings.

```python
from pathlib import Path

import pandas as pd

OBJECTS = ("Nuclei", "Cells", "Cytoplasm", "Aggregates")


def read_cp_table(path):
    """A CellProfiler table of this workflow; its first row holds the OMERO.tables column types (`# header ...`)."""
    return pd.read_csv(path, skiprows=1)


def load_run(output):
    """One run's tables: per image (with its file name), per object type (with the image's file name), and the run."""
    output = Path(output)
    images = read_cp_table(output / "Image.csv")
    names = images[["ImageNumber", "FileName_OG"]].rename(columns={"FileName_OG": "image"})
    objects = {name: read_cp_table(output / f"{name}.csv").merge(names, on="ImageNumber")
               for name in OBJECTS if (output / f"{name}.csv").exists()}
    experiment = read_cp_table(output / "Experiment.csv").set_index("Key")["Value"]
    return {"images": images, "objects": objects, "experiment": experiment}


def per_cell(run):
    """One row per cell, with its nucleus and cytoplasm (same ObjectNumber: the label in the cells mask)
    and its number of aggregates."""
    objects = run["objects"]
    key = ["ImageNumber", "ObjectNumber"]
    cells = objects["Cells"].set_index(key)
    nuclei = objects["Nuclei"].set_index(key).drop(columns="image").add_prefix("Nucleus_")
    cytoplasm = objects["Cytoplasm"].set_index(key).drop(columns="image").add_prefix("Cytoplasm_")
    return pd.concat([cells, nuclei, cytoplasm], axis=1).copy().reset_index()


def aggregates_in_cells(run):
    """One row per aggregate, with the measurements of the cell it lies in (Parent_Cells; 0 = outside every cell)."""
    aggregates = run["objects"]["Aggregates"]
    cells = run["objects"]["Cells"].drop(columns="image").add_prefix("Cell_")
    return aggregates.merge(cells, how="left", left_on=["ImageNumber", "Parent_Cells"],
                            right_on=["Cell_ImageNumber", "Cell_ObjectNumber"])


run = load_run("out")
cells = per_cell(run)            # e.g. cells[["image", "ObjectNumber", "AreaShape_Area", "Children_Aggregates_Count"]]
aggregates = aggregates_in_cells(run)
```

`per_cell` joins nuclei to cells by number (see above): only valid when the masks are labelled
that way.

The notebook `notebooks/read-outputs.ipynb` does all of this for a run's output folder:
provenance, the folder tree, every image (OME-Zarr 0.4, 0.5 and 0.6, TIFF) and table, a first
look, and this loader with an example analysis. Start from it for post-processing.

## The rest of the folder: provenance

The output folder is a [Workflow RO-Crate](https://w3id.org/workflowhub/workflow-ro-crate/):

| File | What it holds |
|---|---|
| `ro-crate-metadata.json` | JSON-LD: the run (`#run`, a `CreateAction` with name, start and end time), the workflow (`config.yaml`, `mainEntity`, language Bilayers), the software (container image and version), the input (by file URI, not copied, unless `RO_CRATE_INPUT=copy`) and every output, with EDAM formats |
| `config.yaml` | the bilayers spec of the workflow version that ran: inputs, outputs, parameters with defaults, tool command, citations |
| `parameters.yaml` | the values this run used, every parameter (defaults included), grouped by the config's `section_id`s; BIAFLOWS-style extras under `extra` |
| `ro-crate-preview.html` (+ `ro-crate-preview_files/`) | a human-readable view of the crate (open in a browser) |

With `ZIP_OUTPUT=true` the folder holds only `<algorithm_folder_name>.zip` (stored, not
compressed) with all of the above inside; unzip it first.

To answer "how was this made": the image and version are in `ro-crate-metadata.json` (the
software) and `config.yaml` (`docker_image`); the values in `parameters.yaml`; the tool and its
citation in `config.yaml` (`citations`) and the repository `README.md`.

```python
import json, yaml
crate = json.load(open("out/ro-crate-metadata.json"))
graph = {e["@id"]: e for e in crate["@graph"]}
run = graph["#run"]            # CreateAction: instrument (workflow), object (input), result (outputs)
params = yaml.safe_load(open("out/parameters.yaml"))
```

## Loading the images

- **OME-Zarr** (`*.ome.zarr`, `*.zarr` folders), version 0.4 (Zarr v2), 0.5 or 0.6 (Zarr v3,
  metadata under `ome` in `zarr.json`; `OMEZARR_VERSION` picks the one written): read with
  `zarr>=3`. The `multiscales` metadata lists the resolution levels, full resolution first by
  its `path`, e.g. `0` or `s0`. In 0.4 and 0.5 the axes are in `multiscales[].axes` and the
  pixel sizes in each dataset's `scale`. In 0.6 (RFC-5) the axes are in
  `multiscales[].coordinateSystems[].axes`, and each dataset has one transformation, a scale or
  a `sequence`, with `input`/`output`. `ome-zarr-py` does not read 0.6 yet; the notebook's
  `open_image` reads all three. Viewers: napari (`napari-ome-zarr`), Fiji (OME-Zarr reader /
  BigDataViewer).
- **TIFF / OME-TIFF**: `tifffile.imread(...)` (and `tifffile.TiffFile(...).ome_metadata`), Fiji.
- **Label images** (integer, one value per object, 0 = background): count objects with
  `len(numpy.unique(labels)) - 1`, measure them with `skimage.measure.regionprops_table`.
- Images keep the input's pixel sizes and axes where the tool keeps them; check before
  measuring in physical units.

## Checking results

- Every output listed above is present and non-empty; image outputs have the input's
  dimensions (unless the workflow changes them) and the declared format.
- Compare with expected results: `bilayers-auto compare <output folder> <expected folder>`
  (from `requirements-dev.txt`): label images by foreground Dice and object count, other
  images and CSV/TSV numbers within a relative tolerance, other files identical.
- Results that look wrong: first compare `parameters.yaml` with what was intended, and the
  image version with the one tested; then see the `update-workflow` skill.
