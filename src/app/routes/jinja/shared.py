"""
Shared utilities for Flask routes
=================================="""

from __future__ import annotations

from typing import Any


class SimplePagination:
    """Lightweight pagination helper compatible with templates."""

    def __init__(self, page: int, per_page: int, total: int, items: list[Any]):
        self.page = page
        self.per_page = per_page
        self.total = total
        self.items = items

    @property
    def pages(self) -> int:
        if self.per_page <= 0:
            return 1
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev_num(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_num(self) -> int:
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
