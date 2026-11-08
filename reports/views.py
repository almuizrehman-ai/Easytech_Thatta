"""
Views for the reports application.

Access: Principal only (financial reports are sensitive).

Routes:
    /reports/                    -> collection_report (filters + table)
    /reports/export/excel/       -> export_excel (POST -> file download)
    /reports/export/pdf/         -> export_pdf (POST -> file download)
"""
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import principal_required

from .forms import CollectionReportForm
from .services import build_collection_report, get_report_rows_for_export


# ============================================================
# COLLECTION REPORT LIST
# ============================================================

@principal_required
@require_http_methods(["GET"])
def collection_report(request):
    """
    Main collection reports page.

    Reads filter params from GET; builds report; renders paginated table
    (via iterator limit — full export handles unlimited).
    """
    form = CollectionReportForm(request.GET or None)
    filters_valid = form.is_valid()

    # Resolve date range even if form invalid (fallback to this month)
    start_date, end_date = form.resolved_range()
    range_label = form.range_label()

    # Extract filters (only from cleaned data if valid)
    course = batch = staff = None
    payment_method = None
    search = ''

    if filters_valid:
        course = form.cleaned_data.get('course')
        batch = form.cleaned_data.get('batch')
        staff = form.cleaned_data.get('staff')
        payment_method = form.cleaned_data.get('payment_method') or None
        search = form.cleaned_data.get('search', '')

    report = build_collection_report(
        start_date=start_date,
        end_date=end_date,
        course=course,
        batch=batch,
        staff=staff,
        payment_method=payment_method,
        search=search,
    )

    # On-page display limit (exports not affected)
    preview_limit = 200
    rows = list(get_report_rows_for_export(report['queryset'], limit=preview_limit))

    context = {
        'page_title': 'Collection Reports',
        'page_subtitle': 'Fee collection details filtered by date, course, and staff.',
        'active_menu': 'reports',
        'form': form,
        'filters_valid': filters_valid,
        'rows': rows,
        'total': report['total'],
        'count': report['count'],
        'by_method': report['by_method'],
        'range_label': range_label,
        'start_date': start_date,
        'end_date': end_date,
        'preview_limit': preview_limit,
        'is_truncated': report['count'] > preview_limit,
        'crumbs': [
            {'label': 'Home', 'url': reverse('accounts:redirect_after_login')},
            {'label': 'Reports', 'url': reverse('reports:collection')},
            {'label': 'Collection'},
        ],
    }
    return render(request, 'reports/collection_report.html', context)


# ============================================================
# EXPORT — EXCEL
# ============================================================

@principal_required
@require_POST
def export_excel(request):
    """
    POST -> generate Excel file + return as download.

    Accepts same filter params as GET (form fields in POST).
    """
    form = CollectionReportForm(request.POST or None)

    if not form.is_valid():
        messages.error(request, "Export filters sahi nahi hain. Dobara koshish karein.")
        return redirect('reports:collection')

    start_date, end_date = form.resolved_range()
    report = build_collection_report(
        start_date=start_date,
        end_date=end_date,
        course=form.cleaned_data.get('course'),
        batch=form.cleaned_data.get('batch'),
        staff=form.cleaned_data.get('staff'),
        payment_method=form.cleaned_data.get('payment_method') or None,
        search=form.cleaned_data.get('search', ''),
    )

    from .exporters import generate_excel_report  # lazy import

    try:
        file_bytes = generate_excel_report(
            rows=list(get_report_rows_for_export(report['queryset'])),
            report_meta={
                'range_label': form.range_label(),
                'total': report['total'],
                'count': report['count'],
                'generated_by': request.user.get_full_name(),
            },
        )
    except Exception as exc:
        messages.error(request, f"Excel generate nahi hua: {exc}")
        return redirect('reports:collection')

    filename = f"collection_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        file_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================================
# EXPORT — PDF
# ============================================================

@principal_required
@require_POST
def export_pdf(request):
    """POST -> generate PDF file + return as download."""
    form = CollectionReportForm(request.POST or None)

    if not form.is_valid():
        messages.error(request, "Export filters sahi nahi hain. Dobara koshish karein.")
        return redirect('reports:collection')

    start_date, end_date = form.resolved_range()
    report = build_collection_report(
        start_date=start_date,
        end_date=end_date,
        course=form.cleaned_data.get('course'),
        batch=form.cleaned_data.get('batch'),
        staff=form.cleaned_data.get('staff'),
        payment_method=form.cleaned_data.get('payment_method') or None,
        search=form.cleaned_data.get('search', ''),
    )

    from .exporters import generate_pdf_report  # lazy import

    try:
        file_bytes = generate_pdf_report(
            rows=list(get_report_rows_for_export(report['queryset'])),
            report_meta={
                'range_label': form.range_label(),
                'total': report['total'],
                'count': report['count'],
                'generated_by': request.user.get_full_name(),
            },
        )
    except Exception as exc:
        messages.error(request, f"PDF generate nahi hua: {exc}")
        return redirect('reports:collection')

    filename = f"collection_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    response = HttpResponse(file_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response