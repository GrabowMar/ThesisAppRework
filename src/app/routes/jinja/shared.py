"""
Shared Jinja Route Utilities
=============================

Shared utility classes and functions for Jinja template routes.

This module provides common utilities used across multiple Jinja route handlers:
- SimplePagination: Lightweight pagination helper compatible with Jinja templates
- Template-compatible pagination that mirrors Flask-SQLAlchemy's Pagination API

These utilities enable consistent pagination patterns across the application without
requiring Flask-SQLAlchemy's heavy Pagination class.
"""

from __future__ import annotations

from typing import Any


class SimplePagination:
    """Lightweight pagination helper compatible with Jinja templates.

    Provides a drop-in replacement for Flask-SQLAlchemy's Pagination class
    with minimal overhead, suitable for manual pagination of query results.

    Attributes:
        page: Current page number (1-indexed)
        per_page: Items per page
        total: Total number of items across all pages
        items: Items on the current page
    """

    def __init__(self, page: int, per_page: int, total: int, items: list[Any]):
        """Initialize pagination helper.

        Args:
            page: Current page number (1-indexed)
            per_page: Number of items per page
            total: Total count of items
            items: List of items for the current page
        """
        self.page = page
        self.per_page = per_page
        self.total = total
        self.items = items

    @property
    def pages(self) -> int:
        """Total number of pages.

        Returns:
            Total page count (minimum 1)
        """
        if self.per_page <= 0:
            return 1
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        """Check if there's a previous page.

        Returns:
            True if current page > 1
        """
        return self.page > 1

    @property
    def has_next(self) -> bool:
        """Check if there's a next page.

        Returns:
            True if current page < total pages
        """
        return self.page < self.pages

    @property
    def prev_num(self) -> int:
        """Get previous page number.

        Returns:
            Previous page number (minimum 1)
        """
        return max(1, self.page - 1)

    @property
    def next_num(self) -> int:
        """Get next page number.

        Returns:
            Next page number (maximum: total pages)
        """
        return min(self.pages, self.page + 1)

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 2,
        right_edge: int = 2,
    ):
        """Yield page numbers for pagination controls with ellipses as None.

        Mirrors Flask-SqlAlchemy Pagination.iter_pages signature so templates
        like `for page_num in pagination.iter_pages()` work unchanged.
        """
        last = 0
        total_pages = self.pages
        for num in range(1, total_pages + 1):
            if (
                num <= left_edge
                or (num >= self.page - left_current and num <= self.page + right_current)
                or num > total_pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num
