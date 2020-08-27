from typing import List, Iterator

from .models import Category


def build_category(item: dict) -> Category:
    """Create a Category object with children from its json representation."""
    cat = Category(
        id=int(item['id']),
        urlname=item['urlname'],
        position=int(item['position']),
        name=item['name'],
        is_readonly=bool(int(item['readonly'])),
        parent=None,
        children=list(map(build_category, item.get('categories', []))),
    )
    for child in cat.children:
        # Category dataclass is frozen, so this hack is required here
        child.__dict__['parent'] = cat
    return cat


class Categories:
    """
    Category container.
    Supports iteration over categories and querying them.
    """

    def __init__(self, data: List[dict]):
        categories = list(map(build_category, data))
        self._categories = categories[:]
        for cat in categories:
            self._categories += cat.children
        self._categories.sort(key=lambda x: x.id)
        self._by_id = {c.id: c for c in self._categories}
        self._by_urlname = {c.urlname: c for c in self._categories}
        self._by_name = {c.name.lower(): c for c in self._categories}

    def __iter__(self) -> Iterator[Category]:
        return iter(self._categories)

    def __len__(self) -> int:
        return len(self._categories)

    def __repr__(self) -> str:
        return repr(self._categories)

    def by_id(self, category_id: int) -> Category:
        """Get a category by id."""
        return self._by_id.get(category_id)

    def by_urlname(self, urlname: str) -> Category:
        """Get a category by its urlname."""
        return self._by_urlname.get(urlname)

    def by_name(self, name: str) -> Category:
        """
        Get a category by its human-readable name.
        :param name: case-insensitive category name
        """
        return self._by_name.get(name.lower())
