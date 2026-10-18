"""Shared setup for auto import tests."""

from tests._helpers.db import _import_all_models

# Building ORM instances configures every mapper, so all models must be loaded.
_import_all_models()
