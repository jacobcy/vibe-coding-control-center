"""Tests for ensuring docstrings and __all__ stay in sync for key modules."""

import re

import vibe3.agents


def test_agents_docstring_all_sync() -> None:
    """Verify that all symbols in agents.__all__ are documented in the docstring.

    This test enforces the pattern where the package-level docstring serves as
    the primary Public API reference, listing every symbol exported via __all__.
    """
    module = vibe3.agents
    all_symbols = set(module.__all__)
    doc = module.__doc__ or ""

    missing_in_doc = []
    for symbol in all_symbols:
        # Check for ``symbol`` pattern which is used for Sphinx/reST cross-references
        if f"``{symbol}``" not in doc:
            missing_in_doc.append(symbol)

    assert not missing_in_doc, (
        f"Symbols exported in vibe3.agents.__all__ are missing from its docstring: "
        f"{sorted(missing_in_doc)}\n\n"
        "Please update the docstring in src/vibe3/agents/__init__.py to include them."
    )


def test_agents_doc_mentions_exist_in_all() -> None:
    """Verify that symbols in agents docstring are in __all__."""
    module = vibe3.agents
    all_symbols = set(module.__all__)
    doc = module.__doc__ or ""

    # Find all ``symbol`` occurrences in doc
    # This pattern matches symbols wrapped in double backticks
    mentions = re.findall(r"``([^`]+)``", doc)

    # Filter to valid Python identifiers only (avoid descriptive text)
    # and de-duplicate to avoid repeated failures
    valid_identifier_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    symbol_mentions = {
        mention for mention in mentions if valid_identifier_pattern.match(mention)
    }

    # Check that all documented symbols are exported
    missing_in_all = []
    for symbol in sorted(symbol_mentions):
        if symbol not in all_symbols:
            missing_in_all.append(symbol)

    assert not missing_in_all, (
        f"Symbols documented in vibe3.agents docstring are missing from __all__: "
        f"{missing_in_all}\n\n"
        "Ensure all documented Public API symbols are exported."
    )
