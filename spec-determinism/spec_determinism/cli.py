"""CLI entry points exposed via pyproject.toml `project.scripts`."""
from spec_determinism.corpus.run_all import main as run_all_main  # noqa: F401
from spec_determinism.corpus.regen_artifacts import main as regen_main  # noqa: F401
from spec_determinism.corpus.verusage_run import main as verusage_main  # noqa: F401
