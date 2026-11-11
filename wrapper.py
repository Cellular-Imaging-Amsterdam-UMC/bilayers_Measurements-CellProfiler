"""bilayers container entrypoint.

Resolves the values the Slurm client passes (see config.yaml), converts OME-Zarr input to OME-TIFF
for CellProfiler, runs the original BIAFLOWS wrapper (/app/biaflows/wrapper.py, unchanged, with
CellProfiler's own Python) BIAFLOWS style and writes RO-Crate metadata; see bilayers_auto.
"""
import os
import shlex
import subprocess
from pathlib import Path

from bilayers_auto import run
from bilayers_auto.biaflows import biaflows_args

CONFIG = Path(__file__).with_name("config.yaml")
# The BIAFLOWS wrapper reads its parameters from a descriptor in local mode; the image generates it
# from config.yaml (bilayers-auto to-biaflows), so the repository has none for the Slurm client to pick.
COMMAND = ["python", "/app/biaflows/wrapper.py", "--descriptor", "/app/biaflows/descriptor.json"]


def biaflows_tool(ctx):
    """Like bilayers_auto.biaflows.biaflows_tool, with HOME in the work folder: the BIAFLOWS wrapper
    keeps its temporary files under $HOME, which need not be writable (Singularity) or roomy."""
    argv = COMMAND + biaflows_args(ctx)
    print("Running BIAFLOWS workflow:", shlex.join(argv), flush=True)
    subprocess.run(argv, check=True, env={**os.environ, "HOME": str(ctx.workdir)})


if __name__ == "__main__":
    # config.yaml accepts OME-TIFF and OME-Zarr; CellProfiler reads only the TIFF
    raise SystemExit(run(spec=CONFIG, tool=biaflows_tool, tool_formats=["tiff"]))
