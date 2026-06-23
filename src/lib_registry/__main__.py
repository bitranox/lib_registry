"""Module entry point for python -m execution.

Provide the ``python -m lib_registry`` path mandated by the
project's packaging guidelines. This delegates to the CLI main function
ensuring consistent behavior between module execution and console scripts.

Note:
    Lives in the adapters layer. It bridges CPython's module execution entry
    point to the shared CLI helper defined in cli.py.

"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
