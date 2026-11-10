#!/usr/bin/env python
"""Wrapper to seed synthetic hospital data via Django management command."""
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
    import django
    django.setup()
    from django.core.management import call_command

    force = "--force" in sys.argv
    call_command("seed_data", force=force)
