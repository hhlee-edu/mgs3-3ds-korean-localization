#!/usr/bin/env python3
"""Compatibility wrapper for mgs3d_gcx_font_tool.py plan-capacity."""

from __future__ import annotations

import sys

from mgs3d_gcx_font_tool import main


if __name__ == "__main__":
    sys.argv.insert(1, "plan-capacity")
    raise SystemExit(main())
