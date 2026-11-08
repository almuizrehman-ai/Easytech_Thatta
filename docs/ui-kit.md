# EASYTECH THATTA — UI Kit Documentation

**Version:** 1.0 (Phase 2)
**Last Updated:** Phase 2

---

## 1. Design Tokens

All tokens live in `static/css/design-system.css` under `:root`.
**Never hardcode colors, spacing, shadows, or radii in templates.** Use tokens.

### Colors
| Token | Value | Use |
|-------|-------|-----|
| `--navy-900` | `#0b1736` | Sidebar bg, headings |
| `--navy-700` | `#16295c` | Gradient endpoints |
| `--accent` | `#2563eb` | Primary actions, links |
| `--success` | `#10b981` | Paid status, positive KPIs |
| `--warning` | `#f59e0b` | Pending status |
| `--danger` | `#ef4444` | Overdue status, errors |
| `--info` | `#0ea5e9` | Info banners |
| `--bg-body` | `#f5f7fb` | Page background |
| `--bg-card` | `#ffffff` | Card background |
| `--border` | `#e5e9f2` | Card borders, dividers |
| `--text-primary` | `#0f172a` | Body text |
| `--text-secondary` | `#64748b` | Labels, hints |

### Spacing Scale
`--sp-1` (4px) · `--sp-2` (8px) · `--sp-3` (12px) · `--sp-4` (16px) · `--sp-5` (20px) · `--sp-6` (24px) · `--sp-8` (32px) · `--sp-10` (40px)

### Radius
`--radius-xs` (6px) · `--radius-sm` (8px) · `--radius-md` (12px) · `--radius-lg` (16px) · `--radius-xl` (20px)

### Shadows
`--shadow-xs` · `--shadow-sm` · `--shadow-md` · `--shadow-lg` · `--shadow-xl`

### Typography
Font: **Inter** (loaded from Google Fonts in `base.html`).
Scale: 11px · 12px · 13px · 14px · 15px · 16px · 18px · 20px · 22px · 24px · 28px · 32px

---

## 2. Component Inventory

### Layout
- `page-header.html` — Page title, description, action buttons
- `breadcrumbs.html` — Hierarchical navigation
- `notifications.html` — Bell dropdown with item list
- `search.html` — Global search bar

### Data
- `_data_table.html` — Standard table with header, rows, empty state
- `pagination.html` — Page navigation with count
- `empty-state.html` — Friendly "no data" state with icon

### Forms
- `_form_field.html` — Label + input + help text + errors
- `_card.html` — Card container with optional header/footer

### Feedback
- `toast-container.html` — Live region for JS toasts
- `confirm-modal.html` — Reusable confirmation dialog
- `.alert-*` — Django messages (from Phase 1)