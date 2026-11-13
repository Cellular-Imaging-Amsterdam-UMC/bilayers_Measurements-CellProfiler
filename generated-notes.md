# Notes

## Creation as a bilayers container

This repository was created from the BIAFLOWS workflow
[W_Measurements-CellProfiler](https://github.com/Cellular-Imaging-Amsterdam-UMC/W_Measurements-CellProfiler)
at release `v1.1.1` (commit `7019b0b`; a `descriptor.json` of schema `cytomine-0.1` and a
`BiaflowsJob` wrapper running a CellProfiler 4.2.6 pipeline), following the
`create-bilayers-container` procedure of
[bilayers-auto-container](https://github.com/NL-BioImaging/bilayers-auto-container), with AI
assistance (Claude Code). The source repository is unchanged. Unlike an earlier in-place conversion
(WB_Measurements-CellProfiler), the original wrapper is not ported: it runs unchanged, called
BIAFLOWS style.

### Tasks performed

| Change | What it does |
|---|---|
| `biaflows/wrapper.py`, `biaflows/FullMeasurementsNucleiCellAggregates.cppipe` | The source's wrapper and pipeline at `v1.1.1`, byte for byte (same checksums as in the published `cellularimagingcf/w_measurements-cellprofiler:v1.1.1` image). |
| `descriptor.json` (not copied) | The Slurm client reads `descriptor.json` before `config.yaml`, so the repository has none. The BIAFLOWS wrapper still needs one in local mode to parse its parameters: the image generates `/app/biaflows/descriptor.json` from `config.yaml` (`bilayers-auto to-biaflows`), so `config.yaml` is the only source of the parameters. |
| `config.yaml` (new) | Drafted with `bilayers-auto from-biaflows` from the source's descriptor, then completed: one `image` input (`ometiff`, `omezarr`; color, grayscale and label images, 2D), a `measurement` output (`csv`), the four descriptor parameters with their ids (the wrapper reads `bj.parameters.<id>`) in sections `masks`/`measurements`, citations (this workflow, Apache-2.0; CellProfiler 4, BSD-3-Clause), image `cellularimagingcf/bilayers_measurements-cellprofiler:v1.0.0`. |
| `wrapper.py` (new) | Entrypoint: `bilayers_auto.run(spec=CONFIG, tool=..., tool_formats=["tiff"])`. The tool calls `python /app/biaflows/wrapper.py --descriptor /app/biaflows/descriptor.json` with `bilayers_auto.biaflows.biaflows_args` (`--infolder --outfolder --gtfolder --local -nmc --<id> <value>`), with `HOME` set to the run's work folder: the BIAFLOWS wrapper keeps its temporary files under `$HOME`. OME-Zarr input is converted to OME-TIFF, which CellProfiler reads. |
| `Dockerfile` (new) | `FROM docker.io/cellprofiler/cellprofiler:4.2.6`. Tool layer as in the source's Dockerfile: Cython, Cytomine Python client `v2.7.3`, biaflows-utilities `v0.10.0`, the `biaflows/` files (the pipeline also linked at `/app`, where the wrapper reads it). bilayers layer: `bilayers_auto` from GitHub in its own Python 3.12 environment (`/opt/bilayers`, the entrypoint), wheels only for the base image's glibc 2.27 except the pure-Python source-only packages (`bilayers-auto-container`, `bilayers-schema`, `pytest-logging`), `openslide-bin` left out (only for MIRAX slides). OCI labels with the generated-with notice. |
| `tests/` | `sample_data.py` (the sample job of the earlier conversion, on `bilayers_auto`), `data/in` (the sample as OME-TIFF), `data/expected*` (reference runs, below), `test_workflow.py`: config validation, the Slurm client's arguments and the tool command, parameter ids, input formats, Dockerfile checks, no descriptor in the repository, and a `container` test. `pytest.ini`, `requirements-dev.txt`. |
| `.github/workflows/` | `ci.yml` (validate + `pytest`, including the container test; pip cache on `requirements-dev.txt`) and the template's `docker-image.yml` (image tag from `config.yaml`, on release). |
| `README.md`, `LICENSE`, `.gitattributes`, `.gitignore`, `.dockerignore` | README with the generated-with notice, inputs, outputs, parameters, BIOMERO registration, Docker use, credits. The source's Apache-2.0 license. LF line endings. |
| `.github/workflows/release.yml`, `.claude/skills/` (from the template's `workflow-files/`) | Replace `docker-image.yml`: the Release workflow (run by hand with a version) sets `docker_image.tag`, validates and tests, builds the image (pushes it when `PUBLISH` is `"true"`), and only then pushes the commit, tag and GitHub release. Skills `update-workflow` and `release-workflow` for working on this repository; `.claude` kept out of the image. |

### Regeneration with the current skill (2026-11-13)

Brought up to date with the `create-bilayers-container` skill of bilayers-auto-container `384d2a2`,
with AI assistance (Claude Code). The source, `config.yaml`, `wrapper.py`, `Dockerfile`, tests
and test data were already what the current skill produces and are unchanged.

| Change | What it does |
|---|---|
| `run.sh` (new, executable), `.gitattributes` (`*.sh text eol=lf`) | From the skill's `references/run.sh`, flags `--infolder`/`--outfolder`: runs the image on a folder with Docker, Podman or Apptainer/Singularity, without BIOMERO or Slurm. |
| `README.md` | "Run it yourself" (get the image, `run.sh`, plain `docker`/`apptainer` commands, parameter table, `params.yaml`, inputs/outputs, settings) replaces "Running it with Docker"; the new files in the development table. |
| `.claude/skills/workflow-outputs/SKILL.md` (new) | From the skill's `references/outputs-skill.md`: every output table and its columns, units (pixels; intensities scaled 0–1), the pipeline's steps, caveats (images and masks paired by order), the output tree, how tables join (`ImageNumber`, `ObjectNumber` = mask label, `Parent_*`), and a tested pandas loader. |
| `notebooks/read-outputs.ipynb` (new) | From the skill's `references/read-outputs.ipynb`, with the loader and an example analysis (cells with aggregates per image; aggregates vs. cell area; nucleus vs. cytoplasm intensity). Committed without outputs. |
| `.github/workflows/release.yml`, `.claude/skills/update-workflow/SKILL.md` | The template's current `workflow-files/` (Node 24 action versions; `run.sh`, outputs skill and notebook in the update procedure); `PUBLISH` stays `"true"`. |
| `.github/workflows/ci.yml` | `actions/checkout@v7`, `actions/setup-python@v7`, as the template. |
| `.dockerignore` | Also keeps `notebooks` out of the image. |

The template got one more fix, uncommitted in bilayers-auto-container: the notebook's generic
`read_table` skips the OMERO.tables `# header ...` type row, which it otherwise read as the column
names.

The earlier template fix, now pushed (bilayers-auto-container `cfec6a3`): `bilayers_auto.compare.compare_tables` treated
NaN cells as different from NaN (CellProfiler writes `nan` for measurements of objects without
children). The fix and a test are uncommitted in bilayers-auto-container.

### Test data

From the source's workflow, as no test data comes with it: the sample job of the
earlier WB_Measurements-CellProfiler conversion (`tests/sample_data.py`): a 128 x 128 RGB uint8 image with two cells,
and its nuclei, cells and aggregates uint16 label masks (two objects each), as OME-TIFF in
`tests/data/in` (150 kB).

Expected outputs are **reference runs of the original image**,
`cellularimagingcf/w_measurements-cellprofiler:v1.1.1`
(`sha256:637b851498b7fc54108a639220f9cd9ea5ab3cd36d5eec2262985bf649c58a05`), run directly as
BIAFLOWS local mode (`--infolder /data/in --outfolder /data/out --gtfolder /data/gt --local -nmc`):
`tests/data/expected` (default parameters) and `tests/data/expected_metric_channels_2`
(`--metric_channels 2`). The pipeline copy is stored without its timestamp.

The container test runs the image like the Slurm client three times and compares every output
with the reference (CSV numbers within `rtol` 1e-3, text equal, the pipeline copy identical):

| Run | Input | Result |
|---|---|---|
| ome-tiff | `tests/data/in` | all 7 files match, including CellProfiler's `MD5Digest_*` of each image |
| ome-zarr | the sample converted to exported OME-Zarr (with `omero` metadata) | all 7 files match; `MD5Digest_*` left out (see below) |
| channel-2 | `tests/data/in`, `metric_channels=2` | all 7 files match `expected_metric_channels_2` |

Left out of the comparison as run-specific: the input's folder and URLs (`PathName_*`, `URL_*`,
`ObjectsPathName_*`, `ObjectsURL_*`, and the encoded `ImageSet_ImageSet`; the container reads the
input from its staging folder), `ExecutionTime_*`, and `Run_Timestamp` and
`ImageSet_Zip_Dictionary` in `Experiment.csv`. File names are compared without their TIFF extension,
as converted OME-Zarr becomes `.ome.tiff`. For the OME-Zarr run, CellProfiler's `MD5Digest_*`
differ: the converted OME-TIFF has the same pixels (checked: identical arrays and dtype) but is
TCZYX with singleton axes, which changes the digest. All measurements still match.

### Verified

- `bilayers-auto validate config.yaml --slurm`: no issues.
- `bilayers-auto command config.yaml`: the Slurm client's arguments give
  `python /app/biaflows/wrapper.py --infolder ... --outfolder ... --<id> <value>`.
- `pytest`: 9 passed locally on Windows (Docker 29.9.3, Linux containers), including the container
  test above, with the template's NaN fix installed locally.
- `bilayers-auto container-test config.yaml --sample tests/data/in`: passed. Without
  `--expected`: its comparison does not leave out the run-specific cells; the pytest test does.
- Outputs: the CSV tables (with the OMERO.tables type row), the pipeline copy,
  `ro-crate-metadata.json` (config, parameters by section, the CSVs with EDAM format, the input by
  `file:///data/in/`), no copy of the input, not zipped.
- A run as a non-root user (uid 12345) with a read-only root filesystem, `/tmp` as tmpfs and
  `HOME=/nonexistent`, as under Singularity: completed with all outputs.
- Regeneration (2026-11-13; Docker 29.9.3, template `384d2a2` from GitHub): `validate --slurm`
  no issues; `command` gives the BIAFLOWS call; `pytest` 9 passed, including the three container
  runs against the reference runs (image rebuilt). `./run.sh tests/data/in <out>`: the same 7 files,
  all matching `tests/data/expected`; `./run.sh ... --params params.yaml` (`metric_channels: "1,2"`)
  gives the two channels. The outputs skill's loader and the notebook (all cells, nbconvert)
  ran on that output folder; `ObjectNumber` = mask label and X/Y = column/row checked against
  `regionprops` on the test masks.

### Still to verify

- CI on GitHub after this push (the template's NaN fix is now on GitHub).
- `run.sh` with Podman and Apptainer/Singularity (only Docker run).
- A run on real images and masks (only the synthetic sample so far).
- A run through BIOMERO on Slurm (Singularity) after release `v1.0.0` and registration.
