"""
Cached wrappers around expensive dashboard analytics.

Live queries in analytics.py are correct but slow for large datasets.
Caching for 5 minutes dramatically improves dashboard load time.

Trade-off:
    - Data may be up to 5 minutes stale on dashboards.
    - Collection dashboard (Phase 6) uses live data — always fresh.

Usage:
    from dashboard.analytics_cached import get_principal_dashboard_kpis_cached
    kpis = get_principal_dashboard_kpis_cached()
"""
from django.core.cache import cache

from . import analytics


# Cache TTL in seconds
DASHBOARD_CACHE_TTL = 300  # 5 minutes
CHART_CACHE_TTL = 600      # 10 minutes


# ============================================================
# KPIs
# ============================================================
def get_staff_dashboard_kpis_cached(user):
    """
    Cached staff KPI dict. Key per-user (staff-specific data).

    Cache key:
        dash:staff_kpis:<user_pk>
    """
    key = f'dash:staff_kpis:{user.pk}'
    data = cache.get(key)
    if data is None:
        data = analytics.get_staff_dashboard_kpis(user)
        cache.set(key, data, DASHBOARD_CACHE_TTL)
    return data


def get_principal_dashboard_kpis_cached():
    """
    Cached principal KPI dict (institute-wide).

    Cache key:
        dash:principal_kpis
    """
    key = 'dash:principal_kpis'
    data = cache.get(key)
    if data is None:
        data = analytics.get_principal_dashboard_kpis()
        cache.set(key, data, DASHBOARD_CACHE_TTL)
    return data


# ============================================================
# Charts
# ============================================================
def get_fee_status_chart_cached():
    """Cached fee status distribution — expensive loop over all obligations."""
    key = 'dash:chart:fee_status'
    data = cache.get(key)
    if data is None:
        data = analytics.get_fee_status_chart()
        cache.set(key, data, CHART_CACHE_TTL)
    return data


def get_course_distribution_chart_cached():
    """Cached course distribution."""
    key = 'dash:chart:course'
    data = cache.get(key)
    if data is None:
        data = analytics.get_course_distribution_chart()
        cache.set(key, data, CHART_CACHE_TTL)
    return data


def get_batch_distribution_chart_cached(limit=8):
    """Cached batch distribution (limit as part of cache key)."""
    key = f'dash:chart:batch:{limit}'
    data = cache.get(key)
    if data is None:
        data = analytics.get_batch_distribution_chart(limit=limit)
        cache.set(key, data, CHART_CACHE_TTL)
    return data


def get_daily_collection_chart_cached(days=30, user=None):
    """
    Cached daily collection chart. Keyed by days + user (staff).
    """
    user_part = user.pk if user else 'all'
    key = f'dash:chart:daily:{days}:{user_part}'
    data = cache.get(key)
    if data is None:
        data = analytics.get_daily_collection_chart(days=days, user=user)
        cache.set(key, data, CHART_CACHE_TTL)
    return data


def get_monthly_revenue_chart_cached(months=6):
    """Cached monthly revenue chart."""
    key = f'dash:chart:monthly:{months}'
    data = cache.get(key)
    if data is None:
        data = analytics.get_monthly_revenue_chart(months=months)
        cache.set(key, data, CHART_CACHE_TTL)
    return data


# ============================================================
# Cache invalidation helpers
# ============================================================
def invalidate_dashboard_cache():
    """
    Manually invalidate all dashboard caches.

    Called by:
        - After payment recorded (optional — for real-time feel)
        - After student created/updated
        - Management command `python manage.py clear_dashboard_cache`
        - Cron job as safety net

    Note: cache.delete_pattern is Redis-specific. For LocMem we
    delete known keys individually.
    """
    keys_to_delete = [
        'dash:principal_kpis',
        'dash:chart:fee_status',
        'dash:chart:course',
    ]
    for k in keys_to_delete:
        cache.delete(k)

    # Dynamic keys — chart batch/daily/monthly
    # LocMem can't iterate; Redis can.
    # For LocMem, TTL expiry (5-10 min) handles cleanup naturally.
    # For Redis, use delete_pattern:
    try:
        cache.delete_pattern('dash:chart:batch:*')
        cache.delete_pattern('dash:chart:daily:*')
        cache.delete_pattern('dash:chart:monthly:*')
        cache.delete_pattern('dash:staff_kpis:*')
    except (AttributeError, NotImplementedError):
        pass  # LocMem backend doesn't support pattern delete