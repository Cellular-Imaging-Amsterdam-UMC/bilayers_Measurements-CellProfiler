# Fully qualified, so engines without short-name resolution (Podman) build it as Docker does
FROM docker.io/cellprofiler/cellprofiler:4.2.6

LABEL org.opencontainers.image.title="bilayers_measurements-cellprofiler" \
      org.opencontainers.image.description="bilayers workflow container for Measurements-CellProfiler (CellProfiler 4.2.6), generated using bilayers-auto-container (https://github.com/NL-BioImaging/bilayers-auto-container)" \
      org.opencontainers.image.source="https://github.com/Cellular-Imaging-Amsterdam-UMC/bilayers_Measurements-CellProfiler" \
      org.opencontainers.image.licenses="Apache-2.0"

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# >>> tool layer: the BIAFLOWS workflow W_Measurements-CellProfiler v1.1.1, as its own Dockerfile installs it
# CellProfiler 4.2.6 is the base image; its Python runs the original wrapper.
RUN python -m pip install --upgrade pip && python -m pip install Cython
RUN python -m pip install 'git+https://github.com/cytomine-uliege/Cytomine-python-client@v2.7.3'
RUN python -m pip install 'git+https://github.com/TorecLuik/biaflows-utilities@v0.10.0'
COPY biaflows/wrapper.py biaflows/FullMeasurementsNucleiCellAggregates.cppipe /app/biaflows/
# the wrapper reads the pipeline from /app
RUN ln -s /app/biaflows/FullMeasurementsNucleiCellAggregates.cppipe /app/FullMeasurementsNucleiCellAggregates.cppipe
# <<< tool layer

# --- bilayers layer: spec parsing, OME-Zarr conversion, RO-Crate ---
# bilayers_auto needs Python >= 3.12, so it gets its own environment next to CellProfiler's;
# the interpreter lives under /opt so it is readable when Singularity runs as another user.
# The base image is Ubuntu 18.04 (glibc 2.27, gcc 7): newer compiled packages only ship wheels
# for glibc >= 2.28 and cannot be built here, so only wheels are used (uv picks the newest versions
# with wheels for this glibc), except for the pure-Python packages that only ship as source.
# openslide-bin has no such wheel at all; biomero-converter only needs OpenSlide for MIRAX slides,
# so it is left out (a uv override that never matches).
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python
RUN python -m pip install uv \
    && echo "openslide-bin; sys_platform == 'never'" > /tmp/uv-overrides.txt \
    && uv venv /opt/bilayers --python 3.12 \
    && uv pip install --no-cache --python /opt/bilayers/bin/python --override /tmp/uv-overrides.txt \
       --only-binary :all: --no-binary bilayers-auto-container --no-binary bilayers-schema \
       --no-binary pytest-logging \
       "bilayers-auto-container @ git+https://github.com/NL-BioImaging/bilayers-auto-container.git" \
    && chmod -R a+rX /opt/bilayers /opt/uv-python

COPY config.yaml wrapper.py /app/
# the descriptor the BIAFLOWS wrapper parses its parameters with, generated from config.yaml
RUN /opt/bilayers/bin/bilayers-auto to-biaflows /app/config.yaml -o /app/biaflows/descriptor.json
RUN mkdir -p /data/in /data/out
WORKDIR /app
ENTRYPOINT ["/opt/bilayers/bin/python", "/app/wrapper.py"]
