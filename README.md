# bilayers_Measurements-CellProfiler

> This bilayers workflow container was generated with AI assistance (Claude Code, using the
> `create-bilayers-container` skill) using
> [bilayers-auto-container](https://github.com/NL-BioImaging/bilayers-auto-container) from
> [W_Measurements-CellProfiler](https://github.com/Cellular-Imaging-Amsterdam-UMC/W_Measurements-CellProfiler)
> (a BIAFLOWS workflow, v1.1.1). It runs on Slurm, is described by a
> [bilayers](https://github.com/bilayer-containers/bilayers) spec (`config.yaml`), and adds OME-Zarr
> conversion and RO-Crate metadata. See [generated-notes.md](generated-notes.md) for how it was made.

Batch feature extraction for 2D fluorescence images using **CellProfiler 4.2.6**, for datasets that
already have three pre-segmented object masks: nuclei, cells, and sub-cellular aggregates or foci.

The workflow runs a headless CellProfiler pipeline (`FullMeasurementsNucleiCellAggregates.cppipe`)
and writes per-object CSV tables with morphology features (area, perimeter, shape descriptors,
Zernike) and per-channel intensity statistics for every nucleus, cell, cytoplasm and aggregate, with
aggregates related to their parent cells, nuclei and cytoplasm. The original BIAFLOWS wrapper of
W_Measurements-CellProfiler runs unchanged inside this container.

## What you need

- **Input images**: 2D fluorescence images, as OME-TIFF or OME-Zarr (also mixed). OME-Zarr is
  converted to OME-TIFF for CellProfiler, keeping the file names, so the suffixes still match.
- **A nuclei mask per image**: a greyscale label image where each nucleus is a distinct integer
  value (e.g. from a segmentation workflow). Its name is the image's base name plus the nuclei
  suffix (default `_Nuclei_Mask`).
- **A cell mask per image**: same convention, cells suffix (default `_Cells_Mask`).
- **An aggregates/foci mask per image**: same convention, aggregates suffix (default `_Aggregates_Mask`).

All four (image + three masks) go in the same input folder, e.g. `img1.ome.tif`,
`img1_Nuclei_Mask.ome.tif`, `img1_Cells_Mask.ome.tif`, `img1_Aggregates_Mask.ome.tif`.

## Outputs

| File | Contents |
|---|---|
| `Nuclei.csv`, `Cells.csv`, `Cytoplasm.csv`, `Aggregates.csv` | One row per object: shape, size and intensity per channel; parent/child relations |
| `Image.csv` | Per-image counts and mean object measurements |
| `Experiment.csv` | Run metadata (CellProfiler version, pipeline) |
| `FullMeasurementsNucleiCellAggregates_<timestamp>.cppipe` | The pipeline as run, with the parameters filled in |
| `ro-crate-metadata.json`, `config.yaml`, `parameters.yaml` | [Workflow RO-Crate](https://w3id.org/workflowhub/workflow-ro-crate/1.1) describing the run: the workflow spec, its values, the input and every output |

Each CSV starts with a `# header ...` row of column types, so OMERO.tables can import it.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `nuclei_mask_suffix` | `_Nuclei_Mask` | File name suffix of the nuclei masks |
| `cells_mask_suffix` | `_Cells_Mask` | File name suffix of the cell masks |
| `aggregates_mask_suffix` | `_Aggregates_Mask` | File name suffix of the aggregates/foci masks |
| `metric_channels` | `1,2,3` | Comma-separated, 1-based channels of the image to measure intensities in (`1` for a single channel, `1,2,3,4` for four) |

## Running it with BIOMERO (Slurm)

The Slurm client ([BIOMERO](https://github.com/NL-BioImaging/biomero) 2.x) reads `config.yaml` from
this repository at a release tag, shows the parameters in OMERO, runs the image on Slurm
(converted to Singularity/Apptainer) and imports the CSV tables back (as OMERO tables when chosen).
Register it in BIOMERO's `slurm-config.ini`:

```ini
[WORKFLOWS]
measurements_cellprofiler=measurements_cellprofiler
measurements_cellprofiler_repo=https://github.com/Cellular-Imaging-Amsterdam-UMC/bilayers_Measurements-CellProfiler/tree/v1.0.0
measurements_cellprofiler_image=cellularimagingcf/bilayers_measurements-cellprofiler
```

The release tag must equal `docker_image.tag` in `config.yaml`; publishing the release builds and
pushes the image (`.github/workflows/docker-image.yml`).

## Running it with Docker

Lay out a job folder like the Slurm client's (`<job>/data/in` with the images and masks, an empty
`<job>/data/out`) and mount `data`:

```
docker build -t cellularimagingcf/bilayers_measurements-cellprofiler:v1.0.0 .
docker run --rm -v ./job/data:/data cellularimagingcf/bilayers_measurements-cellprofiler:v1.0.0 \
    --infolder=/data/in --outfolder=/data/out --metric_channels=1,2,3
```

## Development

| File | Role |
|---|---|
| `config.yaml` | bilayers spec: input, output, parameters, citations, image |
| `wrapper.py` | image entrypoint: `bilayers_auto.run` with the original BIAFLOWS wrapper as the tool, CellProfiler reading TIFF |
| `biaflows/` | the original `wrapper.py` and `FullMeasurementsNucleiCellAggregates.cppipe` of W_Measurements-CellProfiler v1.1.1, unchanged |
| `Dockerfile` | CellProfiler 4.2.6 with the BIAFLOWS utilities (tool layer) and `bilayers_auto` in its own Python 3.12 environment |
| `tests/` | config, Slurm-argument and Dockerfile checks; a container test against reference runs of the original image |

```
pip install -r requirements-dev.txt
pytest -m "not container"        # quick checks
pytest                           # also builds the image and runs it like the Slurm client (Docker)
```

## Credits and license

- Pipeline and BIAFLOWS wrapper: [W_Measurements-CellProfiler](https://github.com/Cellular-Imaging-Amsterdam-UMC/W_Measurements-CellProfiler),
  Cellular Imaging, Amsterdam UMC; Apache-2.0 (see `LICENSE`).
- CellProfiler: Stirling et al. (2021), *CellProfiler 4: improvements in speed, utility and
  usability*, BMC Bioinformatics 22, 433, [doi:10.1186/s12859-021-04344-9](https://doi.org/10.1186/s12859-021-04344-9) (BSD-3-Clause).
- BIAFLOWS utilities ([TorecLuik/biaflows-utilities](https://github.com/TorecLuik/biaflows-utilities) v0.10.0)
  and the Cytomine Python client v2.7.3, as the original workflow uses them.
