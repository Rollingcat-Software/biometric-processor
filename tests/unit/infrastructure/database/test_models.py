"""Regression tests for the declarative ORM models (issue #189).

SQLAlchemy Declarative reserves the attribute name ``metadata``, so a model
that declared ``metadata`` as a mapped attribute made this module (and, while
``alembic/env.py`` imported it for ``target_metadata``, every alembic command)
fail on import. The mapped column is still called ``metadata``; only the
Python attribute differs. ``api_keys.metadata`` exists in the migrated
schema; ``face_embeddings`` has no such column (see ``FaceEmbeddingModel``).
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
