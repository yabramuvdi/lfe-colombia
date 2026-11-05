"""Execute the figure notebooks top to bottom, failing on the first error.

Each notebook runs with notebooks/ as its working directory, the way it would
in Jupyter. The executed copies are not saved: the outputs that matter are the
figure files the notebooks write.
"""

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

for path in map(Path, sys.argv[1:]):
    print(f"running {path} ...", flush=True)
    nb = nbformat.read(path, as_version=4)
    NotebookClient(
        nb, timeout=1800, kernel_name="python3",
        resources={"metadata": {"path": str(path.parent.resolve())}},
    ).execute()
    print(f"done    {path}", flush=True)
