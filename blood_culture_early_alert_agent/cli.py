"""Compatibility CLI wrapper for the blood-culture analysis utilities."""

from blood_culture_sentinel import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
