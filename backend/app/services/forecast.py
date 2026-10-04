"""需求预测（statsmodels Holt，缺失时回退线性趋势），读数据库 forecast_history。"""
from collections import OrderedDict

from ..models import ForecastHistory, Product

try:  # statsmodels 可选；缺失时用线性趋势回退，保证可运行
    from statsmodels.tsa.holtwinters import Holt
    HAS_STATS = True
except Exception:  # pragma: no cover
    HAS_STATS = False


def _linear_trend(series, n):
    if len(series) < 3:
        return [series[-1]] * n if series else [0] * n
    m = len(series)
    sx = sum(range(1, m + 1)); sy = sum(series)
    sxx = sum(x * x for x in range(1, m + 1)); sxy = sum(x * y for x, y in zip(range(1, m + 1), series))
    den = m * sxx - sx * sx
    b = (m * sxy - sx * sy) / den if den else 0
    a = (sy - b * sx) / m
    return [int(round(max(0, a + b * (m + i + 1)))) for i in range(n)]


def _holt(series, n):
    if HAS_STATS and len(series) >= 4:
        try:
            fit = Holt(series, damped_trend=False, initialization_method="estimated").fit(optimized=True)
            return [int(round(max(0, v))) for v in fit.forecast(n)]
        except Exception:  # pragma: no cover
            return _linear_trend(series, n)
    return _linear_trend(series, n)


def _holdout_mape(series, k=2):
    if len(series) < k + 3:
        return None
    train = series[:-k]
    test = series[-k:]
    fc = _holt(train, k)
    err = sum(abs(fc[i] - test[i]) / (test[i] or 1) for i in range(k)) / k * 100
    return round(err, 1)


def run_forecast(db, product_ids=None, horizon: int = 4) -> dict:
    q = db.query(Product)
    if product_ids:
        q = q.filter(Product.code.in_(product_ids))
    products = q.all()
    result = OrderedDict()
    for p in products:
        rows = (
            db.query(ForecastHistory)
            .filter(ForecastHistory.product_id == p.id)
            .order_by(ForecastHistory.period.asc())
            .all()
        )
        series = [r.qty for r in rows]
        weeks = _holt(series, horizon) if series else [0] * horizon
        result[p.code] = {
            "weeks": weeks,
            "horizon": horizon,
            "mape": _holdout_mape(series),
            "model": "statsmodels.Holt" if HAS_STATS else "linear-trend(fallback)",
        }
    return result