"""生产计划优化：启发式(lot-for-lot) 与 PuLP MILP（CLSP）。

MILP 目标：min 生产 + 持有；约束：库存守恒、周产能上界、需求覆盖。
产能不足以覆盖需求时返回不可行，调用方回退启发式。
"""
from collections import defaultdict

import pulp


def _demand_map(orders, horizon):
    demand = defaultdict(lambda: defaultdict(int))
    for o in orders:
        demand[o["week"]][o["code"]] += o["qty"]
    return demand


def heuristic_plan(demand, product_codes, horizon):
    return {w: {code: demand[w].get(code, 0) for code in product_codes} for w in range(1, horizon + 1)}


def plan_cost(production, demand_map, product_codes, horizon, unit_cost, hold_rate=0.025):
    """按同一目标口径估算(生产+持有)，便于 heuristic/milp 对比。"""
    prod_cost = 0.0
    hold_cost = 0.0
    inv = {c: 0 for c in product_codes}
    for w in range(1, horizon + 1):
        for c in product_codes:
            x = production[w].get(c, 0)
            d = demand_map[w].get(c, 0)
            prod_cost += unit_cost[c] * x
            inv[c] = max(0, inv[c] + x - d)
            hold_cost += hold_rate * unit_cost[c] * inv[c]
    return prod_cost + hold_cost


def milp_plan(demand_map, product_codes, capacity_week, horizon, unit_cost, hold_rate=0.025):
    prob = pulp.LpProblem("CLSP", pulp.LpMinimize)
    X = {}
    I = {}
    for c in product_codes:
        for w in range(1, horizon + 1):
            X[(c, w)] = pulp.LpVariable(f"X_{c}_{w}", lowBound=0)
            I[(c, w)] = pulp.LpVariable(f"I_{c}_{w}", lowBound=0)

    obj = []
    for c in product_codes:
        for w in range(1, horizon + 1):
            obj.append(unit_cost[c] * X[(c, w)] + hold_rate * unit_cost[c] * I[(c, w)])
    prob += pulp.lpSum(obj)

    for c in product_codes:
        for w in range(1, horizon + 1):
            prev = I[(c, w - 1)] if w > 1 else 0
            prob += I[(c, w)] == prev + X[(c, w)] - demand_map[w].get(c, 0)
    for w in range(1, horizon + 1):
        prob += pulp.lpSum(X[(c, w)] for c in product_codes) <= capacity_week

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    st = pulp.LpStatus[status]
    if status != pulp.LpStatusOptimal:
        return None, None, st
    production = {}
    for w in range(1, horizon + 1):
        production[w] = {c: int(round(X[(c, w)].value())) for c in product_codes}
    return production, pulp.value(prob.objective), st