"""ashugh: a prosody checker that gives LLM-written lyrics an ear."""

__version__ = "0.1.0"
SOURCE = "git+https://github.com/vitali87/surprise"


def install_hint(extra: str) -> str:
    """The uv command that installs ashugh with an optional extra."""
    return f"uv tool install 'ashugh[{extra}] @ {SOURCE}'"
