from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence

from rapidfuzz import fuzz, process, utils

from .models import Item


def _token_hit(token: str, key_tokens: list[str]) -> bool:
    if len(token) >= 3:
        return any(token in k for k in key_tokens)
    return any(k.startswith(token) for k in key_tokens)


class ItemIndex:
    """Fuzzy lookup over item names and short names."""

    def __init__(self, items: Sequence[Item]) -> None:
        self._items = items
        self._keys: list[str] = []
        self._owners: list[int] = []
        self._exact: dict[str, list[int]] = defaultdict(list)
        for idx, item in enumerate(items):
            for text in {item.name, item.short}:
                key = utils.default_process(text or "")
                if not key:
                    continue
                self._keys.append(key)
                self._owners.append(idx)
                self._exact[key].append(idx)

    def _adjust(self, idx: int, tokens: list[str]) -> float:
        item = self._items[idx]
        penalty = 0.0
        # Ammo packs and weapon presets shadow the thing people usually mean.
        if "ammoBox" in item.types and "pack" not in tokens:
            penalty -= 12
        if "preset" in item.types and "default" not in tokens:
            penalty -= 2
        return penalty

    def search(
        self,
        query: str,
        limit: int = 10,
        where: Callable[[Item], bool] | None = None,
    ) -> list[tuple[Item, float]]:
        q = utils.default_process(query or "")
        if not q:
            return []
        tokens = q.split()
        total_len = sum(map(len, tokens))
        scores: dict[int, float] = {}

        for idx in self._exact.get(q, ()):
            scores[idx] = 200.0 + self._adjust(idx, tokens)

        for key, score, pos in process.extract(
            q, self._keys, scorer=fuzz.WRatio, limit=max(80, limit * 10), score_cutoff=50
        ):
            idx = self._owners[pos]
            key_tokens = key.split()
            matched = [t for t in tokens if _token_hit(t, key_tokens)]
            # token_set_ratio scores a subset as 100, so "labs card" would match the
            # short name "Labs" perfectly. Only trust it when every query word landed.
            overlap = fuzz.token_set_ratio if len(matched) == len(tokens) else fuzz.token_sort_ratio
            score = max(score, overlap(q, key))
            # Long, distinctive words ("m855a1") matter more than "5" or "56".
            score += 25 * sum(map(len, matched)) / total_len
            if key.startswith(q):
                score += 6
            score += self._adjust(idx, tokens)
            if score > scores.get(idx, 0):
                scores[idx] = score

        ranked = sorted(
            scores.items(),
            key=lambda kv: (-kv[1], len(self._items[kv[0]].name)),
        )
        out: list[tuple[Item, float]] = []
        for idx, score in ranked:
            item = self._items[idx]
            if where is None or where(item):
                out.append((item, score))
                if len(out) >= limit:
                    break
        return out

    def resolve(
        self, query: str, where: Callable[[Item], bool] | None = None
    ) -> tuple[Item | None, list[Item]]:
        """Return a confident match, or ``None`` plus the plausible candidates."""
        hits = self.search(query, limit=8, where=where)
        if not hits:
            return None, []
        if "pack" not in query.lower():
            # "M855A1" should mean the round, not its 50/100-round packs.
            rounds = {item.name for item, _ in hits if "ammoBox" not in item.types}
            hits = [
                (item, score)
                for item, score in hits
                if "ammoBox" not in item.types
                or not any(item.name.startswith(name) for name in rounds)
            ]
        exact = [item for item, score in hits if score >= 200]
        if len(exact) == 1:
            return exact[0], []
        if exact:
            return None, exact
        top_item, top = hits[0]
        runner = hits[1][1] if len(hits) > 1 else 0
        if (top >= 95 and top - runner >= 5) or len(hits) == 1:
            return top_item, []
        return None, [item for item, _ in hits]
