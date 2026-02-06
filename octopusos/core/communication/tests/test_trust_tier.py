"""Test trust tier determination and validation.

This module tests the Evidence Trust Model that distinguishes between
search results (candidate sources) and verified information sources.

Critical principle: Search ≠ Truth
"""

import pytest
from unittest.mock import Mock

from agentos.core.communication.evidence import EvidenceLogger
from agentos.core.communication.models import ConnectorType, TrustTier


class TestTrustTierDetermination:
    """Test automatic trust tier determination."""

    @pytest.fixture
    def evidence_logger(self):
        """Create evidence logger with mock storage."""
        mock_storage = Mock()
        return EvidenceLogger(storage=mock_storage)

    def test_search_result_always_lowest_tier(self, evidence_logger):
        """Search results should ALWAYS be SEARCH_RESULT tier.

        Critical: Search engines are candidate generators, not truth sources.
        """
        urls = [
            "https://www.google.com/search?q=test",
            "https://duckduckgo.com/?q=test",
            "https://bing.com/search?q=test",
            "https://any-domain.com/search",
        ]

        for url in urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_SEARCH,
            )
            assert trust_tier == TrustTier.SEARCH_RESULT, (
                f"Search results must be SEARCH_RESULT tier, not {trust_tier}. "
                f"URL: {url}"
            )

    def test_government_domains_authoritative(self, evidence_logger):
        """Government domains (.gov) should be AUTHORITATIVE_SOURCE."""
        gov_urls = [
            "https://www.whitehouse.gov/briefing",
            "https://www.nih.gov/health-information",
            "https://www.cdc.gov/coronavirus",
            "https://www.sec.gov/edgar",
            "https://www.gov.cn/policies",  # Chinese government
        ]

        for url in gov_urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier == TrustTier.AUTHORITATIVE_SOURCE, (
                f"Government domain should be AUTHORITATIVE_SOURCE, not {trust_tier}. "
                f"URL: {url}"
            )

    def test_academic_domains_authoritative(self, evidence_logger):
        """Academic institutions (.edu) should be AUTHORITATIVE_SOURCE."""
        edu_urls = [
            "https://www.mit.edu/research",
            "https://www.stanford.edu/publications",
            "https://www.harvard.edu/studies",
            "https://www.berkeley.edu/labs",
            "https://www.oxford.ac.uk/research",  # UK academia
            "https://www.cambridge.ac.uk/studies",
        ]

        for url in edu_urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier == TrustTier.AUTHORITATIVE_SOURCE, (
                f"Academic domain should be AUTHORITATIVE_SOURCE, not {trust_tier}. "
                f"URL: {url}"
            )

    def test_authoritative_domains_from_list(self, evidence_logger):
        """Domains in AUTHORITATIVE_DOMAINS list should be authoritative."""
        auth_urls = [
            "https://www.who.int/health-topics",
            "https://www.un.org/en/documents",
            "https://www.w3.org/standards",
            "https://www.ietf.org/rfc",
            "https://www.nature.com/articles",
            "https://www.science.org/research",
        ]

        for url in auth_urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier == TrustTier.AUTHORITATIVE_SOURCE, (
                f"Authoritative domain should be AUTHORITATIVE_SOURCE, not {trust_tier}. "
                f"URL: {url}"
            )

    def test_primary_source_domains(self, evidence_logger):
        """Official documentation sites should be PRIMARY_SOURCE."""
        primary_urls = [
            "https://docs.python.org/3/library/os.html",
            "https://docs.microsoft.com/en-us/windows",
            "https://developer.apple.com/documentation",
            "https://developer.mozilla.org/en-US/docs",
            "https://docs.github.com/en/get-started",
            "https://kubernetes.io/docs",
            "https://www.reuters.com/article/world-news",
            "https://apnews.com/article/politics",
        ]

        for url in primary_urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier == TrustTier.PRIMARY_SOURCE, (
                f"Primary source should be PRIMARY_SOURCE, not {trust_tier}. "
                f"URL: {url}"
            )

    def test_external_source_default(self, evidence_logger):
        """Unknown domains should default to EXTERNAL_SOURCE."""
        external_urls = [
            "https://random-blog.com/article",
            "https://some-company.com/products",
            "https://news-aggregator.com/story",
            "https://social-media.com/post",
            "https://en.wikipedia.org/wiki/Topic",  # Even Wikipedia needs verification!
        ]

        for url in external_urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier == TrustTier.EXTERNAL_SOURCE, (
                f"Unknown domain should be EXTERNAL_SOURCE, not {trust_tier}. "
                f"URL: {url}"
            )

    def test_www_prefix_removed_for_matching(self, evidence_logger):
        """www. prefix should be removed for domain matching."""
        # Test both with and without www.
        pairs = [
            ("https://www.nih.gov/health", "https://nih.gov/health"),
            ("https://www.docs.python.org/3/", "https://docs.python.org/3/"),
        ]

        for url_with_www, url_without_www in pairs:
            trust_tier_www = evidence_logger.determine_trust_tier(
                url=url_with_www,
                connector_type=ConnectorType.WEB_FETCH,
            )
            trust_tier_no_www = evidence_logger.determine_trust_tier(
                url=url_without_www,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier_www == trust_tier_no_www, (
                f"www. prefix should not affect trust tier. "
                f"Got {trust_tier_www} vs {trust_tier_no_www}"
            )

    def test_port_numbers_ignored(self, evidence_logger):
        """Port numbers should not affect trust tier determination."""
        url_with_port = "https://www.nih.gov:443/health"
        url_without_port = "https://www.nih.gov/health"

        trust_tier_port = evidence_logger.determine_trust_tier(
            url=url_with_port,
            connector_type=ConnectorType.WEB_FETCH,
        )
        trust_tier_no_port = evidence_logger.determine_trust_tier(
            url=url_without_port,
            connector_type=ConnectorType.WEB_FETCH,
        )

        assert trust_tier_port == trust_tier_no_port == TrustTier.AUTHORITATIVE_SOURCE

    def test_invalid_url_defaults_to_external(self, evidence_logger):
        """Invalid URLs should default to EXTERNAL_SOURCE."""
        invalid_urls = [
            "not-a-url",
            "",
            "htp://malformed.com",  # Typo in scheme
        ]

        for url in invalid_urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier == TrustTier.EXTERNAL_SOURCE, (
                f"Invalid URL should default to EXTERNAL_SOURCE, not {trust_tier}. "
                f"URL: {url}"
            )


class TestTrustTierConfiguration:
    """Test trust tier domain list configuration."""

    @pytest.fixture
    def evidence_logger(self):
        """Create evidence logger with mock storage."""
        mock_storage = Mock()
        return EvidenceLogger(storage=mock_storage)

    def test_add_custom_authoritative_domain(self, evidence_logger):
        """Test adding custom authoritative domain at runtime."""
        # Initially not authoritative
        url = "https://custom-authority.com/document"
        trust_tier = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_FETCH,
        )
        assert trust_tier == TrustTier.EXTERNAL_SOURCE

        # Add to authoritative list
        evidence_logger.authoritative_domains.add("custom-authority.com")

        # Now should be authoritative
        trust_tier = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_FETCH,
        )
        assert trust_tier == TrustTier.AUTHORITATIVE_SOURCE

    def test_add_custom_primary_source_domain(self, evidence_logger):
        """Test adding custom primary source domain at runtime."""
        # Initially external
        url = "https://company-docs.example.com/api"
        trust_tier = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_FETCH,
        )
        assert trust_tier == TrustTier.EXTERNAL_SOURCE

        # Add to primary source list
        evidence_logger.primary_source_domains.add("company-docs.example.com")

        # Now should be primary source
        trust_tier = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_FETCH,
        )
        assert trust_tier == TrustTier.PRIMARY_SOURCE

    def test_domain_lists_are_independent(self, evidence_logger):
        """Ensure domain lists don't interfere with each other."""
        auth_count = len(evidence_logger.authoritative_domains)
        primary_count = len(evidence_logger.primary_source_domains)

        # Add to authoritative
        evidence_logger.authoritative_domains.add("test-auth.com")

        # Should not affect primary sources
        assert len(evidence_logger.authoritative_domains) == auth_count + 1
        assert len(evidence_logger.primary_source_domains) == primary_count


class TestTrustTierHierarchy:
    """Test trust tier hierarchy and comparison."""

    def test_trust_tier_ordering(self):
        """Test that trust tiers have correct ordering."""
        # Lowest to highest
        tiers = [
            TrustTier.SEARCH_RESULT,
            TrustTier.EXTERNAL_SOURCE,
            TrustTier.PRIMARY_SOURCE,
            TrustTier.AUTHORITATIVE_SOURCE,
        ]

        # Test string values match expected order
        assert tiers[0].value == "search_result"
        assert tiers[1].value == "external_source"
        assert tiers[2].value == "primary_source"
        assert tiers[3].value == "authoritative"

    def test_can_use_for_decision_making(self):
        """Test which tiers are suitable for decision-making."""
        # Helper function (would be in BrainOS)
        def can_use_for_decision(trust_tier: TrustTier) -> bool:
            return trust_tier in [
                TrustTier.PRIMARY_SOURCE,
                TrustTier.AUTHORITATIVE_SOURCE,
            ]

        # Test each tier
        assert not can_use_for_decision(TrustTier.SEARCH_RESULT)
        assert not can_use_for_decision(TrustTier.EXTERNAL_SOURCE)
        assert can_use_for_decision(TrustTier.PRIMARY_SOURCE)
        assert can_use_for_decision(TrustTier.AUTHORITATIVE_SOURCE)

    def test_can_store_in_knowledge_base(self):
        """Test which tiers are suitable for knowledge base storage."""
        # Helper function (would be in BrainOS)
        def can_store_in_kb(trust_tier: TrustTier) -> bool:
            return trust_tier in [
                TrustTier.PRIMARY_SOURCE,
                TrustTier.AUTHORITATIVE_SOURCE,
            ]

        # SEARCH_RESULT should NEVER be stored
        assert not can_store_in_kb(TrustTier.SEARCH_RESULT)

        # EXTERNAL_SOURCE needs verification
        assert not can_store_in_kb(TrustTier.EXTERNAL_SOURCE)

        # PRIMARY_SOURCE and AUTHORITATIVE_SOURCE can be stored
        assert can_store_in_kb(TrustTier.PRIMARY_SOURCE)
        assert can_store_in_kb(TrustTier.AUTHORITATIVE_SOURCE)


class TestSearchVsFetch:
    """Test critical distinction between search and fetch operations."""

    @pytest.fixture
    def evidence_logger(self):
        """Create evidence logger with mock storage."""
        mock_storage = Mock()
        return EvidenceLogger(storage=mock_storage)

    def test_same_url_different_trust_for_search_vs_fetch(self, evidence_logger):
        """The same URL should have different trust tiers for search vs fetch.

        Critical test: This demonstrates that search results are ALWAYS
        SEARCH_RESULT tier, even if the URL itself would be authoritative.
        """
        url = "https://www.nih.gov/health-information"

        # When used as search result
        search_trust = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_SEARCH,
        )

        # When actually fetched
        fetch_trust = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_FETCH,
        )

        # Search should be SEARCH_RESULT
        assert search_trust == TrustTier.SEARCH_RESULT, (
            "Search results must always be SEARCH_RESULT tier, "
            "even for authoritative domains"
        )

        # Fetch should be AUTHORITATIVE_SOURCE (it's .gov)
        assert fetch_trust == TrustTier.AUTHORITATIVE_SOURCE, (
            "Fetched .gov content should be AUTHORITATIVE_SOURCE"
        )

        # They should be different!
        assert search_trust != fetch_trust, (
            "Search and fetch must have different trust tiers. "
            "Search ≠ Truth!"
        )

    def test_search_never_equals_truth(self, evidence_logger):
        """Fundamental principle: Search results are NOT truth sources."""
        # Test with various authoritative URLs
        authoritative_urls = [
            "https://www.whitehouse.gov/policy",
            "https://www.mit.edu/research",
            "https://www.who.int/health",
        ]

        for url in authoritative_urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_SEARCH,
            )

            # Even authoritative URLs are SEARCH_RESULT when from search
            assert trust_tier == TrustTier.SEARCH_RESULT, (
                f"Search results from {url} must be SEARCH_RESULT tier. "
                "Search engines provide candidates, not verified truth."
            )


class TestEdgeCases:
    """Test edge cases in trust tier determination."""

    @pytest.fixture
    def evidence_logger(self):
        """Create evidence logger with mock storage."""
        mock_storage = Mock()
        return EvidenceLogger(storage=mock_storage)

    def test_subdomain_matching(self, evidence_logger):
        """Test trust tier for subdomains of authoritative domains."""
        # Subdomain of .gov should be authoritative
        url = "https://subdomain.nih.gov/health"
        trust_tier = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_FETCH,
        )
        assert trust_tier == TrustTier.AUTHORITATIVE_SOURCE

        # Subdomain of primary source
        url = "https://api.github.com/repos"
        trust_tier = evidence_logger.determine_trust_tier(
            url=url,
            connector_type=ConnectorType.WEB_FETCH,
        )
        # Should still be primary source (github.com is in the list)
        assert trust_tier == TrustTier.PRIMARY_SOURCE

    def test_case_insensitive_matching(self, evidence_logger):
        """Domain matching should be case-insensitive."""
        urls = [
            "https://WWW.NIH.GOV/health",
            "https://www.nih.gov/health",
            "https://Www.Nih.Gov/health",
        ]

        trust_tiers = [
            evidence_logger.determine_trust_tier(url, ConnectorType.WEB_FETCH)
            for url in urls
        ]

        # All should be authoritative
        assert all(t == TrustTier.AUTHORITATIVE_SOURCE for t in trust_tiers)

    def test_non_http_urls(self, evidence_logger):
        """Test trust tier for non-HTTP URLs."""
        # FTP, file, etc. should default to EXTERNAL_SOURCE
        urls = [
            "ftp://ftp.example.com/file.txt",
            "file:///etc/passwd",
            "gopher://old-protocol.com",
        ]

        for url in urls:
            trust_tier = evidence_logger.determine_trust_tier(
                url=url,
                connector_type=ConnectorType.WEB_FETCH,
            )
            assert trust_tier == TrustTier.EXTERNAL_SOURCE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
