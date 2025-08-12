from typing import Any, Dict, List
import math
import random as _rand


def compute_cultist_selection(
    items_data: Dict[str, Any],
    threshold: int,
    max_items: int,
    mode: str,
    randomize: bool,
) -> Dict[str, Any]:
    """
    Unbounded (repetition allowed) DP to pick up to `max_items` items whose
    total base value >= `threshold` with minimum total cost.

    - value = basePrice
    - cost = traderSellPrice (PvP) or pvePrice (PvE)
    - ties: lower cost, then fewer items, then lower overshoot
    Returns: { total_value, total_cost, sel_lines }
    """
    if not items_data or "items" not in items_data:
        raise ValueError("Missing items data")

    selected_mode = mode or "pvp"

    # Build candidate list
    candidates: List[Dict[str, Any]] = []
    for it in items_data["items"]:
        value = it.get("basePrice")
        if not isinstance(value, int) or value <= 0:
            continue
        cost = it.get("pvePrice") if selected_mode == "pve" else it.get("traderSellPrice")
        if not isinstance(cost, int) or cost <= 0:
            continue
        candidates.append({
            "name": it.get("name") or it.get("shortName") or "Unknown",
            "value": value,
            "cost": cost,
            "link": it.get("link"),
        })

    if not candidates:
        raise ValueError("No valid candidates")

    if randomize:
        _rand.shuffle(candidates)

    # DP parameters
    STEP = 500
    MAX_OVER = 50_000
    K = max(1, max_items)
    tb = math.ceil(threshold / STEP)
    vb_max = math.ceil((threshold + MAX_OVER) / STEP)

    # Precompute value buckets
    for c in candidates:
        c["vb"] = min(math.ceil(c["value"] / STEP), vb_max)

    INF = 10**18
    dp = [[INF] * (vb_max + 1) for _ in range(K + 1)]
    prevV = [[-1] * (vb_max + 1) for _ in range(K + 1)]
    prevI = [[-1] * (vb_max + 1) for _ in range(K + 1)]
    dp[0][0] = 0

    # Transition (unbounded via count dimension)
    for ccount in range(1, K + 1):
        for vb in range(0, vb_max + 1):
            best_cost = dp[ccount][vb]
            best_prev_v = -1
            best_prev_i = -1
            base_prev = dp[ccount - 1]
            for idx, it in enumerate(candidates):
                ivb = it["vb"]
                pv = vb - ivb
                if pv < 0:
                    continue
                cost_prev = base_prev[pv]
                if cost_prev == INF:
                    continue
                new_cost = cost_prev + it["cost"]
                if new_cost < best_cost:
                    best_cost = new_cost
                    best_prev_v = pv
                    best_prev_i = idx
            if best_cost < dp[ccount][vb]:
                dp[ccount][vb] = best_cost
                prevV[ccount][vb] = best_prev_v
                prevI[ccount][vb] = best_prev_i

    # Collect feasible solutions
    options = []  # (cost, count, vb)
    for ccount in range(1, K + 1):
        for vb in range(tb, vb_max + 1):
            cost = dp[ccount][vb]
            if cost < INF:
                options.append((cost, ccount, vb))

    if not options:
        raise ValueError("No feasible selection for given constraints")

    # Pick by min cost, then fewer items, then lower vb (least overshoot)
    options.sort(key=lambda t: (t[0], t[1], t[2]))
    best_cost, best_count, best_vb = options[0]

    # Reconstruct
    counts: Dict[int, int] = {}
    ccount, vb = best_count, best_vb
    while ccount > 0 and vb >= 0:
        idx = prevI[ccount][vb]
        pv = prevV[ccount][vb]
        if idx is None or idx < 0 or pv < 0:
            break
        counts[idx] = counts.get(idx, 0) + 1
        vb = pv
        ccount -= 1

    # Aggregate output
    sel_lines: List[str] = []
    total_value = 0
    total_cost = 0
    for idx, cnt in sorted(counts.items(), key=lambda x: (-candidates[x[0]]["value"], candidates[x[0]]["cost"])):
        item = candidates[idx]
        total_value += item["value"] * cnt
        total_cost += item["cost"] * cnt
        name_disp = f"[{item['name']}]({item['link']})" if item.get("link") else item["name"]
        sel_lines.append(f"x{cnt} — {name_disp} | value {item['value']:,}₽ | cost {item['cost']:,}₽")

    return {
        "total_value": total_value,
        "total_cost": best_cost,
        "sel_lines": sel_lines,
    }
