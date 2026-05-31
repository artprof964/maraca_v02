"""Executable backend smoke helpers."""

__all__ = ["build_demo_repository", "run_keyword_manual"]


def __getattr__(name: str):
    if name in __all__:
        from . import manual

        return getattr(manual, name)
    raise AttributeError(name)
