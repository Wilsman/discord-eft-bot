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
        if selected_mode == "pve":
            cost = it.get("pvePrice")
            if not isinstance(cost, int) or cost <= 0:
                continue
            candidates.append({
                "name": it.get("name") or it.get("shortName") or "Unknown",
                "value": value,
                "cost": cost,
                "link": it.get("link"),
            })
        else:  # PvP uses trader buy offers (buyFor)
            cost = it.get("traderBuyPrice")
            if not isinstance(cost, int) or cost <= 0:
                continue
            vendor = it.get("traderBuyVendor")
            min_level = it.get("traderMinLevel")
            buy_limit = it.get("traderBuyLimit")
            # Clamp limit between 1 and max_items (if missing, treat as unlimited up to max_items)
            if isinstance(buy_limit, int) and buy_limit > 0:
                cap = min(buy_limit, max_items)
            else:
                cap = max_items
            vendor_label = f"{vendor} L{min_level if isinstance(min_level, int) else '?'}" if vendor else "unknown L?"
            candidates.append({
                "name": it.get("name") or it.get("shortName") or "Unknown",
                "value": value,
                "cost": cost,
                "link": it.get("link"),
                "vendor": vendor,
                "vendor_label": vendor_label,
                "cap": cap,
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

    if selected_mode == "pve":
        # Unbounded DP (original logic)
        dp = [[INF] * (vb_max + 1) for _ in range(K + 1)]
        prevV = [[-1] * (vb_max + 1) for _ in range(K + 1)]
        prevI = [[-1] * (vb_max + 1) for _ in range(K + 1)]
        dp[0][0] = 0

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
    else:
        # PvP: bounded by buyLimit. Convert to 0/1 DP over expanded units.
        # Expand each candidate into cap "units" so each can be taken at most once.
        units: List[Dict[str, Any]] = []
        for idx, c in enumerate(candidates):
            cap = c.get("cap", K)
            cap = max(1, min(K, cap))
            for _ in range(cap):
                units.append({
                    "idx": idx,
                    "vb": c["vb"],
                    "cost": c["cost"],
                })

        dp = [[INF] * (vb_max + 1) for _ in range(K + 1)]
        prevV = [[-1] * (vb_max + 1) for _ in range(K + 1)]
        prevU = [[-1] * (vb_max + 1) for _ in range(K + 1)]  # unit index used
        dp[0][0] = 0

        for u_idx, u in enumerate(units):
            ivb = u["vb"]
            icost = u["cost"]
            for ccount in range(K, 0, -1):  # descending for 0/1
                for vb in range(vb_max, ivb - 1, -1):
                    pv = vb - ivb
                    if dp[ccount - 1][pv] == INF:
                        continue
                    new_cost = dp[ccount - 1][pv] + icost
                    if new_cost < dp[ccount][vb]:
                        dp[ccount][vb] = new_cost
                        prevV[ccount][vb] = pv
                        prevU[ccount][vb] = u_idx

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
    if selected_mode == "pve":
        while ccount > 0 and vb >= 0:
            idx = prevI[ccount][vb]
            pv = prevV[ccount][vb]
            if idx is None or idx < 0 or pv < 0:
                break
            counts[idx] = counts.get(idx, 0) + 1
            vb = pv
            ccount -= 1
    else:
        # Aggregate by candidate index via used units
        while ccount > 0 and vb >= 0:
            u_idx = prevU[ccount][vb]
            pv = prevV[ccount][vb]
            if u_idx is None or u_idx < 0 or pv < 0:
                break
            cand_idx = units[u_idx]["idx"]
            counts[cand_idx] = counts.get(cand_idx, 0) + 1
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
        if selected_mode == "pvp":
            vendor_lbl = item.get("vendor_label") or ""
            sel_lines.append(
                f"x{cnt} — {name_disp} | value {item['value']:,}₽ | cost {item['cost']:,}₽ | {vendor_lbl}"
            )
        else:
            sel_lines.append(
                f"x{cnt} — {name_disp} | value {item['value']:,}₽ | cost {item['cost']:,}₽"
            )

    return {
        "total_value": total_value,
        "total_cost": best_cost,
        "sel_lines": sel_lines,
    }
