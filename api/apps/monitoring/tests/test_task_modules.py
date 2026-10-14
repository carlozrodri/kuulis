import re
from pathlib import Path

from kuulis.tasks import TASK_MODULES

ENTRYPOINT = Path(__file__).resolve().parents[3] / "docker" / "entrypoint.sh"


def test_the_container_loads_every_task_module():
    """A module missing from the entrypoint never starts its loop in QA or production."""
    script = ENTRYPOINT.read_text()
    for command in ("taskiq worker kuulis.tasks:broker", "taskiq scheduler kuulis.tasks:scheduler"):
        line = next(x for x in script.splitlines() if command in x)
        listed = re.findall(r"apps\.[\w.]+", line)
        assert listed == TASK_MODULES, command
