"""Checks of the workflow: config, the Slurm client's arguments, image, and runs compared with reference runs.

Test data (tests/data): ``in`` is a sample job (``sample_data.py``): an RGB OME-TIFF with its nuclei,
cells and aggregates label masks. ``expected`` and ``expected_metric_channels_2`` are the outputs of
the original BIAFLOWS image (cellularimagingcf/w_measurements-cellprofiler:v1.1.1) for it, with
the default parameters and with ``--metric_channels 2``; the pipeline copy is renamed without its
timestamp.
"""
import csv
import shutil
from pathlib import Path, PurePosixPath

import pytest

from bilayers_auto import BilayersSpec
from bilayers_auto.cli import main
from bilayers_auto.compare import compare_outputs
from bilayers_auto.contract import slurm_argv
from bilayers_auto.conversion import TIFF, ZARR, normalize_formats

from sample_data import NAME, SUFFIXES, to_zarr, write_sample

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.yaml"
DATA = Path(__file__).parent / "data"
PIPELINE = "FullMeasurementsNucleiCellAggregates"
CSV_TABLES = {"Nuclei.csv", "Cells.csv", "Cytoplasm.csv", "Aggregates.csv", "Image.csv", "Experiment.csv"}

# Cells that differ from run to run: where the input was read from (also inside the encoded image
# set), timings, the run's time. The MD5Digest_ columns still check that the same pixels were read.
RUN_SPECIFIC_COLUMNS = ("PathName_", "URL_", "ObjectsPathName_", "ObjectsURL_", "ExecutionTime_", "ImageSet_ImageSet")
RUN_SPECIFIC_KEYS = {"Run_Timestamp", "ImageSet_Zip_Dictionary"}
# File names are compared without their TIFF extension: OME-Zarr input is converted to .ome.tiff
FILE_NAME_COLUMNS = ("FileName_", "ObjectsFileName_")
# CellProfiler's digest of each image as loaded: the OME-TIFF converted from OME-Zarr has the same
# pixels (and gives the same measurements) but is TCZYX with singleton axes, which changes the digest
DIGEST_COLUMNS = ("MD5Digest_",)


def _cell(path: Path, column: str, key: str, value: str, skip: tuple) -> str:
    if column.startswith(RUN_SPECIFIC_COLUMNS + skip) or (path.name == "Experiment.csv" and key in RUN_SPECIFIC_KEYS and column == "Value"):
        return ""
    if column.startswith(FILE_NAME_COLUMNS):
        return value.removesuffix(".tiff").removesuffix(".tif")
    return value


def normalized(folder: Path, target: Path, skip: tuple = ()) -> Path:
    """A copy of an output folder without its run-specific cells, the pipeline copy without timestamp."""
    target.mkdir(parents=True)
    for path in folder.iterdir():
        if path.suffix == ".cppipe":
            shutil.copy(path, target / f"{PIPELINE}.cppipe")
        elif path.suffix == ".csv":
            with path.open(newline="") as handle:
                rows = list(csv.reader(handle))
            header = rows[1]  # rows[0]: the OMERO.tables column types
            rows[2:] = [[_cell(path, column, row[0], value, skip) for column, value in zip(header, row)] for row in rows[2:]]
            with (target / path.name).open("w", newline="") as handle:
                csv.writer(handle).writerows(rows)
    return target


def assert_matches_reference(out: Path, expected: Path, tmp_path: Path, skip: tuple = ()):
    results = compare_outputs(normalized(out, tmp_path / "actual", skip), normalized(expected, tmp_path / "expected", skip))
    assert results and all(result.ok for result in results), "\n".join(map(str, results))


def test_config_is_valid_for_bilayers_and_slurm():
    assert main(["validate", str(CONFIG), "--slurm"]) == 0


def test_slurm_arguments_build_the_biaflows_call():
    argv = slurm_argv(CONFIG, PurePosixPath("/"), metric_channels="1,2")
    assert argv == ["--infolder=/data/in", "--outfolder=/data/out", "--metric_channels=1,2"]
    spec = BilayersSpec(CONFIG)
    values = spec.parse_args(argv)
    assert values.params == {"nuclei_mask_suffix": "_Nuclei_Mask", "cells_mask_suffix": "_Cells_Mask",
                             "aggregates_mask_suffix": "_Aggregates_Mask", "metric_channels": "1,2"}
    command = spec.command(values)
    assert command[:2] == ["python", "/app/biaflows/wrapper.py"]


def test_parameters_are_the_biaflows_descriptor_ids():
    """The BIAFLOWS wrapper reads bj.parameters.<id>: the names must stay the descriptor's ids."""
    names = set(BilayersSpec(CONFIG).parameters)
    assert names == {"nuclei_mask_suffix", "cells_mask_suffix", "aggregates_mask_suffix", "metric_channels"}
    wrapper = (ROOT / "biaflows" / "wrapper.py").read_text()
    assert all(f'"{name}"' in wrapper or f".{name}" in wrapper for name in names)


def test_config_accepts_ome_tiff_and_ome_zarr():
    assert normalize_formats(BilayersSpec(CONFIG).inputs["infolder"]["format"]) == {TIFF, ZARR}
    assert 'tool_formats=["tiff"]' in (ROOT / "wrapper.py").read_text()


def _instructions(keyword):
    lines = (ROOT / "Dockerfile").read_text().splitlines()
    return [line.split(None, 1)[1] for line in lines if line.upper().startswith(keyword + " ")]


def test_dockerfile_runs_the_wrapper_as_slurm_expects():
    assert _instructions("ENTRYPOINT")[-1] == '["/opt/bilayers/bin/python", "/app/wrapper.py"]'
    assert all(base.split()[0].startswith("docker.io/") for base in _instructions("FROM"))
    assert _instructions("USER") == []


def test_no_biaflows_descriptor():
    """The Slurm client reads descriptor.json/descriptor.yaml before config.yaml (the image generates its own)."""
    assert not [path for path in ROOT.rglob("descriptor.*") if ".git" not in path.parts]


def test_sample_data_is_stored(tmp_path):
    names = sorted(path.name for path in write_sample(tmp_path))
    assert names == sorted(f"{NAME}{suffix}.ome.tif" for suffix in ("", *SUFFIXES))
    assert names == sorted(path.name for path in (DATA / "in").iterdir())


def test_normalized_reference_runs_differ_only_in_channels(tmp_path):
    """The two reference runs differ, so the comparison detects the channel parameter."""
    results = compare_outputs(normalized(DATA / "expected", tmp_path / "a"),
                              normalized(DATA / "expected_metric_channels_2", tmp_path / "b"))
    assert not all(result.ok for result in results)


def _engine():
    from bilayers_auto.container_test import detect_runtime

    try:
        return detect_runtime()
    except RuntimeError:
        return None


def _zarr_sample(folder: Path) -> Path:
    shutil.copytree(DATA / "in", folder)
    for tiff in sorted(folder.iterdir()):
        to_zarr(tiff, folder)
    return folder


@pytest.mark.container
@pytest.mark.skipif(_engine() is None, reason="Docker is not running")
def test_container_like_slurm(tmp_path):
    """Build the image and run it like the Slurm client on the sample as OME-TIFF and as exported
    OME-Zarr, and with another channel; each must reproduce the original image's results."""
    from bilayers_auto.container_test import container_test

    runs = [("ome-tiff", DATA / "in", {}, DATA / "expected", ()),
            ("ome-zarr", _zarr_sample(tmp_path / "zarr-in"), {}, DATA / "expected", DIGEST_COLUMNS),
            ("channel-2", DATA / "in", {"metric_channels": "2"}, DATA / "expected_metric_channels_2", ())]
    for index, (name, sample, params, expected, skip) in enumerate(runs):
        job = tmp_path / name
        outputs = container_test(CONFIG, sample=sample, params=params, build=index == 0, keep=job)
        names = {path.name for path in outputs}
        assert CSV_TABLES <= names and {"ro-crate-metadata.json", "config.yaml"} <= names
        assert not [path for path in outputs if path.suffix in (".tif", ".zarr")], "no input copies"
        assert_matches_reference(job / "data" / "out", expected, tmp_path / f"compare-{name}", skip)
