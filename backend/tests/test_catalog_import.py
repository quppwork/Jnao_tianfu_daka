import pytest
"""音频目录导入测试"""

from app.services.catalog_import import counts_match_expected, validate_catalog_counts


class TestCatalogImport:
    def test_import_catalog_counts(self, db_session):
        counts = validate_catalog_counts(db_session)
        assert sum(counts.values()) > 0
        assert len(counts) >= 5
