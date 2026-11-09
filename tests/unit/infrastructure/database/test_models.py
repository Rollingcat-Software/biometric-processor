"""Regression tests for the declarative ORM models (issue #189).

``alembic/env.py`` imports ``Base`` from this module for ``target_metadata``.
SQLAlchemy Declarative reserves the attribute name ``metadata``, so a model
that declared ``metadata`` as a mapped attribute made the import (and every
alembic command) fail before any migration ran. The column in the database
is still called ``metadata``; only the Python attribute differs.
"""

import importlib

import pytest


@pytest.mark.parametrize(
    "model_name, table_name",
    [("FaceEmbeddingModel", "face_embeddings"), ("APIKeyModel", "api_keys")],
)
def test_import_WhenModelsModuleLoaded_ShouldMapMetadataColumnUnderNonReservedAttribute(
    model_name: str, table_name: str
) -> None:
    models = importlib.import_module("app.infrastructure.database.models")

    model = getattr(models, model_name)
    table = models.Base.metadata.tables[table_name]

    assert "metadata" in table.c, "the database column must keep its name"
    assert model.meta.property.columns[0] is table.c["metadata"]
