"""生产计划优化：启发式(lot-for-lot) 与 PuLP MILP（CLSP + 加班 + 积压）。

产能不足时不再不可行：
- 加班 O_t：t 周超出常规产能后的额外可用产能，单位成本 otc（加班溢价）；
- 积压 B_{c,t}：t 周未能满足、推迟到后续满足的需求，单位罚金 bpen；
- 期末积压清零 → 所有需求在计划期结束前都必须生产，总量=总需求，与 MRP 口径一致。

这样在产能紧张时 MILP 可给出"可行且更省"的方案：通过提前投产（囤库存）
或小幅积压来规避高峰周的加班溢价；基线为"按需投产但不提前囤货"的简单做法。
"""
from collections import defaultdict

import pulp

DEFAULT_HOLD = 0.025   # 单位成本×周 的持有费率
DEFAULT_OTC = 30.0     # 每单位加班产能的溢价成本（元）
DEFAULT_BPEN = 80.0    # 每单位积压罚金（元）
DEFAULT_OMAX = 0.6     # 周加班上限 = 常规产能 × OMAX


def _demand_map(orders, horizon):
    demand = defaultdict(lambda: defaultdict(int))
    for o in orders:
        demand[o["week"]][o["code"]] += o["qty"]
    return demand


def heuristic_plan(demand, product_codes, horizon):
    """lot-for-lot：每周恰好按需求生产（不提前囤货、不积压的简单基线）。"""
    return {w: {code: demand[w].get(code, 0) for code in product_codes} for w in range(1, horizon + 1)}


def plan_cost(production, demand_map, product_codes, horizon, unit_cost, hold_rate=DEFAULT_HOLD):
    """按同一口径估算(生产+持有)，便于 heuristic/milp 对比（不含加班）。"""
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


def _week_overflow(demand_map, product_codes, week, capacity_week):
    dsum = sum(demand_map[week].get(c, 0) for c in product_codes)
    return max(0, dsum - capacity_week)


def heuristic_cost_ot(demand_map, product_codes, horizon, unit_cost, capacity_week,
                      otc=DEFAULT_OTC):
    """产能感知基线成本：按需投产(lot-for-lot)，周需求超出产能的部分用加班补。

    该基线不提前囤货也不积压，是"不做时序优化"的简单生产方式；
    MILP 通过提前投产/积压来降低高峰加班，因此可比此基线与启发式都更省。
    """
    prod_cost = 0.0
    ot_cost = 0.0
    for w in range(1, horizon + 1):
        for c in product_codes:
            prod_cost += unit_cost[c] * demand_map[w].get(c, 0)
        ot_cost += otc * _week_overflow(demand_map, product_codes, w, capacity_week)
    return prod_cost + ot_cost


def milp_plan(demand_map, product_codes, capacity_week, horizon, unit_cost,
              hold_rate=DEFAULT_HOLD, otc=DEFAULT_OTC, bpen=DEFAULT_BPEN, omax=DEFAULT_OMAX):
    """CLSP + 加班 + 积压 的 MILP。返回 (production, cost, status, overtime)。"""
    prob = pulp.LpProblem("CLSP_OT", pulp.LpMinimize)
    X, I, B, O = {}, {}, {}, {}
    for c in product_codes:
        for w in range(1, horizon + 1):
            X[(c, w)] = pulp.LpVariable(f"X_{c}_{w}", lowBound=0)
            I[(c, w)] = pulp.LpVariable(f"I_{c}_{w}", lowBound=0)
            B[(c, w)] = pulp.LpVariable(f"B_{c}_{w}", lowBound=0)
    for w in range(1, horizon + 1):
        O[w] = pulp.LpVariable(f"O_{w}", lowBound=0)

    obj = []
    for c in product_codes:
        for w in range(1, horizon + 1):
            obj.append(unit_cost[c] * X[(c, w)] + hold_rate * unit_cost[c] * I[(c, w)] + bpen * B[(c, w)])
    for w in range(1, horizon + 1):
        obj.append(otc * O[w])
    prob += pulp.lpSum(obj)

    # 物料守恒（含积压）：(I-B) 期初 + 生产 - 需求 = (I-B) 期末
    for c in product_codes:
        for w in range(1, horizon + 1):
            iv = I[(c, w - 1)] if w > 1 else 0
            bv = B[(c, w - 1)] if w > 1 else 0
            prob += (I[(c, w)] - B[(c, w)]) == (iv - bv) + X[(c, w)] - demand_map[w].get(c, 0)
    # 期末积压清零：所有需求在计划期末前必须满足（保证总产量=总需求）
    for c in product_codes:
        prob += B[(c, horizon)] == 0

    # 产能：常规 + 加班；加班有上限
    for w in range(1, horizon + 1):
        prob += pulp.lpSum(X[(c, w)] for c in product_codes) <= capacity_week + O[w]
        prob += O[w] <= omax * capacity_week

    status = prob.solve(pulp.PULP_CBC_CMD(msg=False))
    st = pulp.LpStatus[status]
    if status != pulp.LpStatusOptimal:
        return None, None, st, None

    production = {}
    overtime = {}
    for w in range(1, horizon + 1):
        production[w] = {c: int(round(X[(c, w)].value())) for c in product_codes}
        otv = O[w].value()
        overtime[w] = int(round(otv)) if otv is not None else 0
    return production, pulp.value(prob.objective), st, overtime


if __name__ == "__main__":
    # 自测示例：模拟一个"前周有余量、后两周高峰"的需求
    dm = _demand_map([{"week": 1, "code": "P-A", "qty": 2470},
                      {"week": 2, "code": "P-A", "qty": 2700},
                      {"week": 3, "code": "P-A", "qty": 2790},
                      {"week": 4, "code": "P-A", "qty": 2840}], 4)
    umc = {"P-A": 40}
    for cap in [2900, 2700, 2500]:
        prod, cost, st, ot = milp_plan(dm, ["P-A"], cap, 4, umc)
        hcost = heuristic_cost_ot(dm, ["P-A"], 4, umc, cap)
        saving = hcost - cost if cost is not None else None
        print(f"cap={cap} status={st} milp={cost} 基线={hcost} 节省={saving} 加班={ot}")