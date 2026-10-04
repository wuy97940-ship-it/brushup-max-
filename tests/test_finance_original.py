"""原创财管内容核验：独立金融模型复算，而非复用生成器的答案或演算函数。"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, localcontext
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "data/banks/finance-original-v02.json"
AUDIT = ROOT / ".qa/finance-original-audit.json"
D = Decimal


def present_value(flows: list[Decimal], rate: Decimal) -> Decimal:
    """从最后一期向前递推，独立于题解的逐项现值加总。"""
    value = D(0)
    for cash in reversed(flows):
        value = (value + cash) / (1 + rate)
    return value


def annuity(value: Decimal, rate: Decimal, years: int) -> Decimal:
    return present_value([value] * years, rate)


def derive_case(q: dict) -> dict[str, Decimal]:
    """只读题干附带的原始参数；结果不依赖answer、reference或numeric_checks.value。"""
    p = q["source_ref"]["parameters"]
    x = lambda key: D(str(p[key]))
    a = lambda key: [D(v) for v in p[key]]
    c, n = map(int, re.search(r"orig-cg-(\d+)-case-(\d+)", q["id"]).groups())
    if (c, n) == (1, 1):
        return {"1.npv_a": present_value(a("a"), x("discount")) - x("initial"),
                "2.npv_b": present_value(a("b"), x("discount")) - x("initial")}
    if (c, n) == (1, 2):
        noa = x("operating_assets") - x("operating_liabilities")
        net_debt = x("debt") - x("financial_assets")
        return {"1.noa": noa, "1.net_debt": net_debt, "1.equity": noa - net_debt,
                "2.fcfe_received": x("dividend") + x("repurchase") - x("issue")}
    if (c, n) == (2, 1):
        return {"1.margin": x("profit") / x("sales") * 100,
                "1.turnover": x("sales") / x("assets"),
                "2.multiplier": x("assets") / x("equity"),
                "2.roe": x("profit") / x("equity") * 100}
    if (c, n) == (2, 2):
        future_sales = x("sales") * (1 + x("growth"))
        delta_sales = future_sales - x("sales")
        need = delta_sales * (x("asset_ratio") - x("liability_ratio"))
        profit = future_sales * x("margin")
        retained = profit * x("retention")
        return {"1.delta_sales": delta_sales, "1.asset_need": need,
                "2.profit": profit, "2.retained": retained, "2.efn": need - retained}
    if (c, n) == (3, 1):
        pv = annuity(x("payment"), x("discount"), p["years"])
        return {"1.pv": pv, "2.extra_cost": pv - x("cash_price")}
    if (c, n) == (3, 2):
        w, sigma, beta = a("w"), a("sigma"), a("beta")
        # 协方差矩阵的二次型，与题解显式方差展开相互验证。
        covariance = [[sigma[0] ** 2, x("rho") * sigma[0] * sigma[1]],
                      [x("rho") * sigma[0] * sigma[1], sigma[1] ** 2]]
        variance = sum(w[i] * w[j] * covariance[i][j] for i in (0, 1) for j in (0, 1))
        bp = sum(wi * bi for wi, bi in zip(w, beta))
        return {"1.expected": sum(wi * ri for wi, ri in zip(w, a("returns"))) * 100,
                "1.sigma": variance.sqrt() * 100, "2.beta": bp,
                "2.required": (x("rf") + bp * (x("rm") - x("rf"))) * 100}
    if (c, n) == (4, 1):
        dividend = x("dividend0") * (1 + x("growth"))
        ke = dividend / x("price") + x("growth")
        kd = x("debt_cost") * (1 - x("tax"))
        return {"1.dividend": dividend, "1.ke": ke * 100, "2.kd": kd * 100,
                "2.wacc": (x("debt_weight") * kd + (1 - x("debt_weight")) * ke) * 100}
    if (c, n) == (4, 2):
        asset_beta = x("beta_equity") / (1 + (1 - x("tax")) * x("comparable_de"))
        equity_beta = asset_beta * (1 + (1 - x("tax")) * x("target_de"))
        ke = x("rf") + equity_beta * x("premium")
        equity_weight = 1 / (1 + x("target_de"))
        return {"1.beta_asset": asset_beta, "1.beta_equity": equity_beta, "2.ke": ke * 100,
                "2.wacc": (equity_weight * ke + (1 - equity_weight) * x("debt_cost") * (1 - x("tax"))) * 100}
    if (c, n) == (5, 1):
        dep = x("equipment") / p["years"]
        ebit = x("sales") - x("cash_cost") - dep
        ocf = ebit - ebit * x("tax") + dep
        flows = [ocf] * p["years"]
        flows[-1] += x("nwc")
        initial = -x("equipment") - x("nwc")
        return {"1.dep": dep, "1.ocf": ocf, "2.initial": initial,
                "2.terminal": flows[-1], "2.npv": initial + present_value(flows, x("discount"))}
    if (c, n) == (5, 2):
        net_sale = x("old_sale") - (x("old_sale") - x("old_basis")) * x("tax")
        initial = net_sale - x("new_price")
        old_ebit = -x("old_cash_cost") - x("old_dep")
        new_dep = x("new_price") / p["years"]
        new_ebit = -x("new_cash_cost") - new_dep
        old_ocf = old_ebit * (1 - x("tax")) + x("old_dep")
        new_ocf = new_ebit * (1 - x("tax")) + new_dep
        delta = new_ocf - old_ocf
        return {"1.net_sale": net_sale, "1.initial": initial, "2.delta_ocf": delta,
                "2.npv": initial + annuity(delta, x("discount"), p["years"])}
    if (c, n) == (6, 1):
        up = max(x("up") - x("strike"), D(0))
        down = max(x("down") - x("strike"), D(0))
        delta = (up - down) / (x("up") - x("down"))
        # 用股票+债券复制组合确定期权价，题解主要使用风险中性期望。
        bond_today = (down - delta * x("down")) / (1 + x("rate"))
        probability = ((1 + x("rate")) * x("spot") - x("down")) / (x("up") - x("down"))
        return {"1.c_up": up, "1.c_down": down, "1.delta": delta,
                "2.p": probability, "2.c0": delta * x("spot") + bond_today}
    if (c, n) == (6, 2):
        put = x("call") + x("strike") / (1 + x("rate")) - x("spot")
        return {"1.put": put,
                "2.call_profit": max(x("call_terminal_spot") - x("strike"), D(0)) - x("call"),
                "2.put_profit": max(x("strike") - x("put_terminal_spot"), D(0)) - put}
    if (c, n) == (7, 1):
        flows = a("fcff")
        terminal = flows[-1] * (1 + x("growth")) / (x("discount") - x("growth"))
        flows[-1] += terminal
        enterprise = present_value(flows, x("discount"))
        return {"1.terminal": terminal, "2.enterprise": enterprise, "2.equity": enterprise - x("net_debt")}
    if (c, n) == (7, 2):
        fcff = x("nopat") + x("dep") - x("capex") - x("delta_nwc")
        fcfe = fcff - x("interest") * (1 - x("tax")) + x("net_borrowing")
        equity = fcfe * (1 + x("growth")) / (x("ke") - x("growth"))
        return {"1.fcff": fcff, "1.fcfe": fcfe, "2.equity": equity, "2.price": equity / x("shares")}
    if (c, n) == (8, 1):
        contribution = x("sales") - x("variable")
        ebit = contribution - x("fixed")
        ebt = ebit - x("interest")
        new_ebit = contribution * (1 - x("sales_decline")) - x("fixed")
        eps = (new_ebit - x("interest")) * (1 - x("tax")) / x("shares")
        old_eps = ebt * (1 - x("tax")) / x("shares")
        return {"1.ebit": ebit, "1.dol": contribution / ebit, "1.dfl": ebit / ebt,
                "1.dtl": contribution / ebt, "2.eps": eps, "2.decline": (old_eps - eps) / old_eps * 100}
    if (c, n) == (8, 2):
        new_shares = x("funding") / x("issue_price")
        debt_interest = x("old_interest") + x("funding") * x("debt_rate")
        total_shares = x("shares") + new_shares
        point = (debt_interest * total_shares - x("old_interest") * x("shares")) / new_shares
        return {"1.indifference": point,
                "2.debt_eps": (x("ebit") - debt_interest) * (1 - x("tax")) / x("shares"),
                "2.equity_eps": (x("ebit") - x("old_interest")) * (1 - x("tax")) / total_shares}
    if (c, n) == (9, 1):
        coupon = x("face") * x("coupon_rate")
        flows = [coupon] * p["years"]
        flows[-1] += x("face")
        price0 = present_value(flows, x("yield"))
        price1 = present_value(flows[1:], x("yield"))
        return {"1.price": price0, "2.price": price1, "2.return": (coupon + price1 - price0) / price0 * 100}
    if (c, n) == (9, 2):
        depreciation = x("buy") / p["years"]
        buy = x("buy") - annuity(depreciation * x("tax"), x("discount"), p["years"])
        lease = annuity(x("rent") * (1 - x("tax")), x("discount"), p["years"])
        return {"1.buy_pv": buy, "1.lease_pv": lease, "2.lease_advantage": buy - lease}
    if (c, n) == (10, 1):
        retained = x("investment") * x("equity_weight")
        dividend = x("profit") - retained
        return {"1.retained": retained, "1.dividend": dividend,
                "2.payout": dividend / x("profit") * 100, "2.dps": dividend / x("shares")}
    if (c, n) == (10, 2):
        shares = x("shares") - x("repurchase") / x("price")
        eps = x("profit") / shares
        return {"1.shares": shares, "1.eps": eps,
                "1.growth": (eps / (x("profit") / x("shares")) - 1) * 100,
                "2.price": x("price") / x("split"), "2.eps": x("profit") / (x("shares") * x("split"))}
    if (c, n) == (11, 1):
        continuous = (2 * x("demand") * x("order_cost") / x("holding")).sqrt()
        cost = lambda amount: x("demand") / amount * x("order_cost") + amount / 2 * x("holding")
        lower = continuous.to_integral_value(rounding=ROUND_FLOOR)
        upper = continuous.to_integral_value(rounding=ROUND_CEILING)
        integer = min([lower, upper], key=cost)
        return {"1.eoq": continuous, "1.integer_q": integer, "2.orders": x("demand") / integer,
                "2.cost": cost(integer) + x("safety") * x("holding")}
    if (c, n) == (11, 2):
        period = D(p["credit_day"] - p["discount_day"])
        principal = x("invoice") * (1 - x("discount"))
        interest = principal * x("borrowing_rate") * period / p["year_days"]
        return {"1.forgone_cost": x("discount") / (1 - x("discount")) * p["year_days"] / period * 100,
                "2.interest": interest, "2.saving": x("invoice") - principal - interest}
    if (c, n) == (12, 1):
        variable = (x("high_y") - x("low_y")) / (x("high_x") - x("low_x"))
        fixed = x("low_y") - x("low_x") * variable
        estimate = lambda amount: fixed + variable * amount + (x("extra_fixed") if amount > x("threshold") else 0)
        return {"1.variable": variable, "1.fixed": fixed,
                "2.cost_3500": estimate(x("q1")), "2.cost_5500": estimate(x("q2"))}
    if (c, n) == (12, 2):
        revenue = x("sales_units") * x("price")
        manufacture_per_unit = x("unit_variable_manufacturing") + x("fixed_manufacturing") / x("production")
        absorption = revenue - manufacture_per_unit * x("sales_units") - x("unit_variable_selling") * x("sales_units") - x("fixed_selling")
        variable = revenue - (x("unit_variable_manufacturing") + x("unit_variable_selling")) * x("sales_units") - x("fixed_manufacturing") - x("fixed_selling")
        return {"1.absorption_profit": absorption, "2.variable_profit": variable, "2.difference": absorption - variable}
    if (c, n) == (13, 1):
        material_eq = x("finished") + x("end_units")
        conversion_eq = x("finished") + x("end_units") * x("end_conversion")
        material_rate = (x("begin_material") + x("current_material")) / material_eq
        conversion_rate = (x("begin_conversion") + x("current_conversion")) / conversion_eq
        finished = x("finished") * (material_rate + conversion_rate)
        remaining = x("end_units") * material_rate + x("end_units") * x("end_conversion") * conversion_rate
        return {"1.material_eq": material_eq, "1.conversion_eq": conversion_eq,
                "1.material_rate": material_rate, "1.conversion_rate": conversion_rate,
                "2.finished": finished, "2.wip": remaining}
    if (c, n) == (13, 2):
        end_eq = x("end_units") * x("end_progress")
        finish_old = x("begin_units") * (1 - x("begin_progress"))
        new_finished = x("finished") - x("begin_units")
        eq = finish_old + new_finished + end_eq
        rate = x("current_cost") / eq
        return {"1.equivalent": eq, "1.rate": rate,
                "2.finished_conversion": x("begin_cost") + (finish_old + new_finished) * rate,
                "2.end_conversion": end_eq * rate}
    if (c, n) == (14, 1):
        mq = x("material_actual_quantity")
        ms = x("output") * x("material_per_unit")
        mh = (mq - ms) * x("material_standard_price")
        mp = mq * (x("material_actual_price") - x("material_standard_price"))
        lh = x("labor_actual_hours")
        ls = x("output") * x("labor_per_unit")
        le = (lh - ls) * x("labor_standard_rate")
        lr = lh * (x("labor_actual_rate") - x("labor_standard_rate"))
        return {"1.material_price": mp, "1.material_quantity": mh,
                "1.material_total": mq * x("material_actual_price") - ms * x("material_standard_price"),
                "2.labor_rate": lr, "2.labor_efficiency": le,
                "2.labor_total": lh * x("labor_actual_rate") - ls * x("labor_standard_rate")}
    if (c, n) == (14, 2):
        rate = x("budget") / x("capacity")
        standard_hours = x("output") * x("standard_hours_per_unit")
        return {"1.rate": rate, "1.spending": x("actual_fixed") - x("budget"),
                "1.idle": (x("capacity") - x("actual_hours")) * rate,
                "1.efficiency": (x("actual_hours") - standard_hours) * rate,
                "2.volume": x("budget") - standard_hours * rate,
                "2.total": x("actual_fixed") - standard_hours * rate}
    if (c, n) == (15, 1):
        rates = [D(row["cost"]) / D(row["total_driver"]) for row in p["pools"]]
        alpha = sum(rate * D(row["a_driver"]) for rate, row in zip(rates, p["pools"]))
        total = sum(D(row["cost"]) for row in p["pools"])
        return {"1.order_rate": rates[0], "1.setup_rate": rates[1], "1.inspection_rate": rates[2],
                "1.a_cost": alpha, "2.a_unit": alpha / x("a_units"), "2.b_unit": (total - alpha) / x("b_units")}
    if (c, n) == (15, 2):
        target = x("price") * (1 - x("target_margin"))
        current = sum(a("costs"))
        revised = current + x("design_add") - x("production_saving") - x("service_saving")
        return {"1.target": target, "1.current": current, "1.gap": current - target,
                "2.revised": revised, "2.margin": (x("price") - revised) / x("price") * 100}
    if (c, n) == (16, 1):
        contribution = x("price") - x("variable")
        break_even = x("fixed") / contribution
        return {"1.break_even": break_even, "1.safety": (x("sales_units") - break_even) / x("sales_units") * 100,
                "1.profit": x("sales_units") * contribution - x("fixed"),
                "2.target_units": (x("fixed") + x("target_after_tax") / (1 - x("tax"))) / contribution}
    if (c, n) == (16, 2):
        rate_a = 1 - x("a_variable") / x("a_price")
        rate_b = 1 - x("b_variable") / x("b_price")
        rate = x("a_weight") * rate_a + (1 - x("a_weight")) * rate_b
        sales = (x("fixed") + x("target_profit")) / rate
        new_rate = x("new_a_weight") * rate_a + (1 - x("new_a_weight")) * rate_b
        return {"1.margin": rate * 100, "1.break_even": x("fixed") / rate,
                "2.target_sales": sales, "2.a_units": sales * x("a_weight") / x("a_price"),
                "2.b_units": sales * (1 - x("a_weight")) / x("b_price"), "2.new_break_even": x("fixed") / new_rate}
    if (c, n) == (17, 1):
        free = x("capacity") - x("normal_units")
        q1, q2 = a("order_quantities")
        normal_cm = x("normal_price") - x("normal_variable")
        opportunity = max(q2 - free, D(0)) * normal_cm
        profit = lambda quantity: quantity * (x("order_price") - x("order_variable")) - x("tooling") - max(quantity - free, D(0)) * normal_cm
        return {"1.profit": profit(q1), "2.profit": profit(q2),
                "2.minimum_price": x("order_variable") + (x("tooling") + opportunity) / q2}
    if (c, n) == (17, 2):
        make_avoidable = x("units") * x("make_variable") + x("avoidable_fixed")
        buy = x("units") * x("buy_price")
        return {"1.make_cost": make_avoidable + x("rental"), "1.buy_cost": buy,
                "2.profit_increase": make_avoidable - buy + x("rental")}
    if (c, n) == (18, 1):
        sales = a("sales")
        end1 = sales[1] * x("finished_ratio")
        end2 = sales[2] * x("finished_ratio")
        prod1 = sales[0] + end1 - x("begin_finished")
        prod2 = sales[1] + end2 - end1
        usage = prod1 * x("material_per_unit")
        purchase = usage + prod2 * x("material_per_unit") * x("material_ratio") - x("begin_material")
        return {"1.q1_production": prod1, "1.q2_production": prod2, "2.usage": usage,
                "2.purchase": purchase, "2.amount": purchase * x("material_price")}
    if (c, n) == (18, 2):
        sales, purchases = a("sales"), a("purchases")
        rc, pc = x("receipt_current"), x("payment_current")
        r1 = sales[1] * rc + sales[0] * (1 - rc)
        paid1 = purchases[1] * pc + purchases[0] * (1 - pc)
        cash1 = x("begin_cash") + r1 - paid1 - x("operating_paid") - x("january_capex")
        borrowing = max(x("minimum") - cash1, D(0))
        interest = borrowing * x("monthly_rate")
        r2 = sales[2] * rc + sales[1] * (1 - rc)
        paid2 = purchases[2] * pc + purchases[1] * (1 - pc)
        cash2 = cash1 + borrowing + r2 - paid2 - x("operating_paid") - x("february_dividend") - interest
        repaid = min(max(cash2 - x("minimum"), D(0)), borrowing)
        return {"1.receipts": r1, "1.purchases_paid": paid1, "1.borrow": borrowing,
                "2.interest": interest, "2.repayment": repaid, "2.ending_cash": cash2 - repaid}
    if (c, n) == (19, 1):
        combined_assets = x("assets") + x("project_assets")
        combined_profit = x("profit") + x("project_profit")
        return {"1.roi": x("profit") / x("assets") * 100,
                "1.ri": x("profit") - x("assets") * x("required"),
                "2.project_roi": x("project_profit") / x("project_assets") * 100,
                "2.combined_roi": combined_profit / combined_assets * 100,
                "2.combined_ri": combined_profit - combined_assets * x("required")}
    if (c, n) == (19, 2):
        free = x("capacity") - x("external_units")
        displaced = max(x("internal_units") - free, D(0))
        opportunity = displaced * (x("external_price") - x("variable") - x("external_delivery"))
        return {"1.displaced": displaced, "1.opportunity": opportunity,
                "2.minimum": x("variable") + opportunity / x("internal_units"),
                "2.maximum": x("outside_delivered_price") - x("internal_transport")}
    if (c, n) == (20, 1):
        nopat = x("nopat") + (x("rd_expense") - x("rd_amortization")) * (1 - x("tax"))
        capital = x("average_capital") + x("average_rd_adjustment")
        charge = capital * x("wacc")
        return {"1.nopat": nopat, "1.capital": capital, "2.capital_charge": charge, "2.eva": nopat - charge}
    if (c, n) == (20, 2):
        return {"1.delivery": x("on_time") / x("orders") * 100,
                "1.retention": x("retained") / x("begin_customers") * 100,
                "1.certification": x("certified") / x("employees") * 100,
                "2.eva": x("nopat") - x("capital") * x("wacc")}
    raise AssertionError(f"缺少独立复算模型：{q['id']}")


def audit_cases(questions: dict) -> list[dict]:
    evidence = []
    with localcontext() as context:
        context.prec = 70
        for q in sorted(questions.values(), key=lambda row: row["id"]):
            if q.get("options"):
                continue
            results = derive_case(q)
            checks = q["numeric_checks"]
            if set(results) != {item["key"] for item in checks}:
                raise AssertionError((q["id"], "复算模型覆盖与检查点不同"))
            values = []
            for item in checks:
                raw = results[item["key"]]
                expected = D(item["value"])
                places = item["decimals"]
                if item["exact"]:
                    if raw != expected:
                        raise AssertionError((q["id"], item["key"], raw, expected))
                    rounded = raw
                else:
                    precision = D(1).scaleb(-places)
                    rounded = raw.quantize(precision, rounding=ROUND_HALF_UP)
                    if rounded != expected:
                        raise AssertionError((q["id"], item["key"], raw, rounded, expected))
                values.append(dict(key=item["key"], independently_calculated=str(raw),
                                   rounded=str(rounded), reference=item["value"], unit=item["unit"],
                                   precision=places, exact=item["exact"], status="passed"))
            evidence.append(dict(id=q["id"], parameters=q["source_ref"]["parameters"],
                                 method="独立Decimal模型与原始参数复算，现值使用倒序递推，不调用生成器答案函数",
                                 values=values, status="passed"))
    return evidence


def numeric_objective_models() -> dict[tuple[int, int], tuple[Decimal, int, str]]:
    """独立编辑复算常数来自题面，所有终值在此现算；不读取生成器ROWS中的答案/解释。"""
    models = {}
    def add(c, n, value, places=2, token=""):
        models[(c, n)] = (D(value), places, token)
    # 第1—5章：报表、利率与资本预算。金额单位与题面一致。
    add(1, 11, D(900) - 260)
    add(1, 12, D(80) + 20 - 50)
    for n, value in {
        1: D(360)/180, 2: (D(500)-180-20)/200, 3: D(240)/60,
        4: D(1200)/((D(180)+220)/2), 5: D(360)/(D(900)/150),
        6: 1/(1-D('.4')), 7: D('.08')*D('1.5')*2*100,
        9: D(350)-70, 10: D(400)*(D('.6')-D('.15')),
        11: D(180)-90*D('.6'), 12: (D('.2')*D('.5'))/(1-D('.2')*D('.5'))*100,
        13: D(96)/800*100, 14: (D('.15')+(D('.15')-D('.06'))*1)*100,
    }.items(): add(2, n, value)
    for n, value in {
        1: D(10000)*D('1.1')**2, 2: D(12100)/D('1.1')**2,
        3: D(1000)*D('2.4869'), 4: D(1000)*D('2.4869')*D('1.1'),
        5: D(2000)/D('.08'), 6: D(1000)*D('2.4869')*D('.7513'),
        7: ((1+D('.12')/12)**12-1)*100,
        8: (D('1.08')/D('1.03')-1)*100,
        9: (D('.2')*D('.3')+D('.05')*D('.7'))*100,
        12: (D('.4')*D('.08')+D('.6')*D('.13'))*100,
        13: D('.018')/D('.012'), 14: (D('.03')+D('1.2')*(D('.09')-D('.03')))*100,
    }.items(): add(3, n, value)
    for n, value in {
        1: D(8)*(1-D('.25')), 2: D(7), 3: (D(2)*D('1.05')/40+D('.05'))*100,
        4: (D(3)/(50-2)+D('.04'))*100, 5: D(6)/75*100,
        6: D(300)/(300+700)*100,
        7: (D('.4')*D('.06')*(1-D('.25'))+D('.6')*D('.12'))*100,
        8: D(10)-4, 9: D('1.4')/(1+(1-D('.2'))*D('.5')),
        10: D('.8')*(1+(1-D('.2'))*D('.75')),
    }.items(): add(4, n, value)
    for n, value in {
        2: D(80), 3: (D(300)-180-40)*(1-D('.25'))+40,
        4: D(30)-8, 5: D(18)-(18-10)*D('.25'),
        6: D(115)/D('1.1')-100, 7: D(230)/200,
        8: (D(120)/100-1)*100, 9: D(150)/50,
    }.items(): add(5, n, value)
    # 第6—10章：期权复制、估值、杠杆和证券筹资。
    for n, value in {
        1: max(D(62)-50, D(0)), 2: max(D(40)-31, D(0)),
        3: max(D(36)-30,D(0))-4, 5: D(8)-max(D(55)-50,D(0)),
        6: D(50)+4-45, 8: D('.625')*20/D('1.05'),
        9: (D(20)-0)/(120-80), 13: D(50), 14: D(50)-40,
    }.items(): add(6, n, value)
    add(6, 7, (D('1.05')-D('.8'))/(D('1.2')-D('.8')), 3)
    for n, value in {
        2: D(180)-70, 3: D(200)+30-80-20, 4: D(150)-30+20,
        7: D(100)*D('1.03')/(D('.08')-D('.03')), 8: D(1331)/D('1.1')**3,
        9: D(1000)-250+50, 10: D(12)*D('2.5'), 12: D(20)*D('.15')/D('.10'),
    }.items(): add(7, n, value)
    for n, value in {
        1: (D(1000)-600)/(1000-600-200), 2: D(300)/(300-100),
        3: D(2)*D('1.5')*10, 4: (D(160)-40)*(1-D('.25'))/60,
        5: ((D(200)-40)*(1-D('.25'))-20)/50,
        6: (D(20)*100-D(0)*80)/(100-80), 10: D(800)+D('.25')*200,
        14: D(400)/600,
    }.items(): add(8, n, value)
    for n, value in {
        1: annuity(D(60),D('.06'),2)+D(1000)/D('1.06')**2,
        2: D(1210)/D('1.1')**2, 4: D(1000)*D('.08')/2,
        5: D(100)-3, 6: D(1000)/25, 7: D(40)*30, 9: D(1000)*D(2)/10,
    }.items(): add(9, n, value)
    for n, value in {
        1: D(120)-100*D('.6'), 3: D(200)*D('.4'), 5: D(20)-1,
        6: D(1000)*(1+D(2)/10), 7: D(30)/(1+D(5)/10),
        9: D(200)/10, 10: D(100)/(100-20), 11: (1-D('.3'))*100,
    }.items(): add(10, n, value)
    # 第11—15章：营运、产品成本、差异与作业。
    for n, value in {
        1: D(50)+35-20, 2: (2*D(10000)*50/4).sqrt(), 3: D(12000)/600,
        4: D(1000)/2+100, 5: D(40)*5,
        6: D('.02')/(1-D('.02'))*360/30*100, 7: D(2)+3*3,
        9: D(3600)/360*30*D('.6'), 10: D(50)-8-5-2,
        13: D(10)/(100-10)*100, 14: D(100)*D('.08')/80*100,
    }.items(): add(11, n, value)
    for n, value in {
        2: D(10000)/2000, 3: D(1000)+2*500, 4: (D(9000)-7000)/(1000-600),
        5: D(9000)-5*1000, 13: (D(1000)-800)*D(10000)/1000,
    }.items(): add(12, n, value)
    for n, value in {
        3: D(60000)/3000*1200, 4: D(9000)*200/(200+100),
        5: D(800)+D(200)*D('.4'), 6: D(800)+200, 7: D(26400)/880,
        8: D(100)*(1-D('.5'))+(800-100)+200*D('.4'),
        9: D(200)*D('.4')*30, 10: D(12000)*3000/(3000+1000),
    }.items(): add(13, n, value)
    for n, value in {
        1: (D(6)-5)*220, 2: (D(220)-100*2)*5, 3: D(220)*6-200*5,
        4: (D(24)-20)*110, 5: (D(110)-100)*20,
        6: D(690)-115*5, 7: (D(115)-100)*5, 8: D(10800)-10000,
        9: (D(1000)-900)*10, 10: (D(900)-800)*10, 11: (D(1000)-800)*10,
    }.items(): add(14, n, value, token="不利")
    add(14, 14, D(120)*2)
    for n, value in {
        1: D(60000)/300, 2: D(80000)/40*12, 7: D(300)*(1-D('.3')),
        8: D(240)/(1+D('.2')), 9: sum(map(D,[20,80,10,8,2])),
    }.items(): add(15, n, value)
    # 第16—20章：CVP、经营、预算、责任与EVA。
    for n, value in {
        1: D(100)-60, 2: (D(80)-50)/80*100, 3: D(100000)/(100-60),
        4: D(64000)/D('.32'), 5: (D(100000)+50000)/(100-60),
        6: (D(100000)+D(37500)/(1-D('.25')))/(100-60),
        7: D(4000)-2500, 8: (D(4000)-2500)/4000*100,
        9: D('.4')*D('.3')*100, 10: D(1000)*80*D('.1'),
        11: D(40000)*D('.1')/(60000-40000)*100, 12: D(80000)/20000*5,
        13: (D('.6')*D('.4')+D('.4')*D('.2'))*100,
        14: D(70000)/(2*20+3*10),
    }.items(): add(16, n, value)
    for n, value in {
        1: D(100)*(70-50), 2: D(8000)-5000-4000,
        7: D(16000)-10000-4000, 9: D(35000)-30000,
        10: D(60), 11: D(130), 12: D(45)+5,
    }.items(): add(17, n, value)
    for n, value in {
        2: D(1000)+200-120, 3: D(1080)*3+500-300, 4: D(3440)*5,
        5: D(1200)*D('.5')*20, 6: D(100)*D('.6')+80*D('.4'),
        7: D(70)*D('.5')+50*D('.5'), 8: D(8)-(10+50-55),
        9: D(30)-6, 10: D(5)*1000+20000, 13: D(40)+100-90,
    }.items(): add(18, n, value)
    for n, value in {
        4: D(100)/500*100, 5: D(100)-500*D('.12'), 7: D(30)-200*D('.12'),
        8: D(30), 9: D(30)+20, 10: D(55),
    }.items(): add(19, n, value)
    for n, value in {
        1: D(120)-1000*D('.08'), 3: D(160)*(1-D('.25')),
        4: D(500)*D('.10'), 5: D(600)-80,
        6: D(100)+(20-5)*(1-D('.25')), 7: D(30)-200*D('.10'),
    }.items(): add(20, n, value)
    return models


def audit_numeric_objectives(questions: dict) -> list[dict]:
    evidence = []
    with localcontext() as context:
        context.prec = 70
        for (chapter, number), (expected, places, required_token) in numeric_objective_models().items():
            qid = f"orig-cg-{chapter:02d}-{number:02d}"
            q = questions[qid]
            rounded = expected.quantize(D(1).scaleb(-places), rounding=ROUND_HALF_UP)
            matched = []
            for letter, option in q["options"].items():
                normalized = option.replace("−", "-").replace(",", "").replace("，", "")
                match = re.search(r"[+-]?\d+(?:\.\d+)?", normalized)
                if match and D(match[0]) == rounded and required_token in option:
                    matched.append(letter)
            if len(matched) != 1 or matched[0] != q["answer"]:
                raise AssertionError((qid, "独立模型未匹配唯一正确选项", expected, matched, q["answer"]))
            evidence.append(dict(id=qid, stem=q["stem"], independently_calculated=str(expected),
                                 rounded=str(rounded), selected_option=matched[0],
                                 required_semantic_token=required_token, status="passed"))
    return evidence


class FinanceOriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = json.loads(BANK.read_text(encoding="utf-8"))
        cls.questions = cls.bank["questions"]

    def test_distribution_and_source_identity(self):
        self.assertEqual(len(self.questions), 440)
        for chapter in range(1, 21):
            rows = [q for q in self.questions.values() if q["chapter_no"] == chapter]
            self.assertEqual(Counter(q["type"] for q in rows), {"单选题": 14, "多选题": 6, "计算分析题": 2})
            for q in rows:
                self.assertEqual(q["book_id"], "cg_original_v02")
                self.assertEqual(q["source_ref"]["kind"], "project_original")
                self.assertEqual(q["source_id"], "project_finance_original")

    def test_unique_choices_and_specific_rationales(self):
        for q in self.questions.values():
            if not q["options"]:
                continue
            with self.subTest(q=q["id"]):
                self.assertEqual(set(q["options"]), set("ABCD"))
                self.assertEqual(len(set(q["options"].values())), 4)
                self.assertTrue(set(q["answer"]).issubset(q["options"]))
                self.assertEqual(len(q["answer"]), 1) if q["type"] == "单选题" else self.assertGreaterEqual(len(q["answer"]), 2)
                explanations = q["analysis"]["option_analysis"]
                self.assertEqual(set(explanations), set("ABCD"))
                self.assertEqual(len(set(explanations.values())), 4)
                for option, rationale in explanations.items():
                    self.assertTrue(rationale.startswith("正确。" if option in q["answer"] else "错误。"))
                    self.assertGreater(len(rationale), 6)
                self.assertTrue(q["analysis"]["principle"])
                self.assertTrue(q["analysis"]["pitfalls"])
                self.assertTrue(q["analysis"]["memory"])

    def test_subquestion_check_integrity(self):
        for q in self.questions.values():
            if q["options"]:
                continue
            keys = {item["key"] for item in q["numeric_checks"]}
            self.assertEqual(keys, {key for sub in q["subquestions"] for key in sub["checks"]})
            self.assertEqual(len(keys), len(q["numeric_checks"]))
            self.assertGreaterEqual(len(q["subquestions"]), 2)
            for sub in q["subquestions"]:
                self.assertTrue(sub["process_checklist"])
                self.assertTrue(sub["reference"])

    def test_all_40_cases_independent_recalculation(self):
        evidence = audit_cases(self.questions)
        self.assertEqual(len(evidence), 40)
        self.assertEqual(sum(len(case["values"]) for case in evidence), 168)
        audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {}
        audit["case_recalculations"] = evidence
        audit["independent_case_check_count"] = 168
        AUDIT.parent.mkdir(parents=True, exist_ok=True)
        AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_numeric_objectives_independent_models(self):
        evidence = audit_numeric_objectives(self.questions)
        self.assertGreaterEqual(len(evidence), 160)
        self.assertEqual({q["chapter_no"] for q in self.questions.values() if q["id"] in {e["id"] for e in evidence}}, set(range(1, 21)))
        audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {}
        audit["objective_recalculations"] = evidence
        audit["independent_objective_check_count"] = len(evidence)
        AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_generation_deterministic_and_reusable(self):
        path = ROOT / "tools/create_finance_original_bank.py"
        spec = importlib.util.spec_from_file_location("original_finance_generator_test", path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        generated = generator.objectives(generator.parse_cards()) + generator.CASES
        self.assertEqual(set(self.questions), {q["id"] for q in generated})
        for q in generated:
            saved = dict(self.questions[q["id"]])
            candidate = dict(q)
            saved.pop("authorship", None)
            candidate.pop("authorship", None)
            self.assertEqual(saved, candidate)

    def test_formula_cards_complete_structured(self):
        path = ROOT / "tools/create_finance_original_bank.py"
        spec = importlib.util.spec_from_file_location("original_finance_knowledge_test", path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        chapters = generator.parse_cards()
        self.assertEqual(len(chapters), 20)
        for chapter in chapters:
            self.assertEqual(chapter["cards"], chapter["formulas"])
            self.assertGreaterEqual(len(chapter["formulas"]), 3)
            for card in chapter["formulas"]:
                for key in ("name", "expression", "symbols", "conditions", "pitfalls"):
                    self.assertTrue(card[key])


if __name__ == "__main__":
    unittest.main()
