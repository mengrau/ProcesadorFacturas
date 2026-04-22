"""Compatibility diagnostic entrypoint.

This script delegates to scripts.diagnostico to keep existing workflows intact.
"""

from scripts.diagnostico import main


if __name__ == "__main__":
    main()
