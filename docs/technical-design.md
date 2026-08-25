# Technical Design — Mehengaai Mitra

## Goal

Give a household a practical view of local grocery inflation and a personalised, evidence-grounded budget briefing.

## Data flow

1. The user uploads a CSV or uses the bundled demo data.
2. Pandas validates required columns, parses months and numeric values, removes invalid rows, and calculates `monthly_cost = price_inr × quantity`.
3. The dashboard aggregates current and previous month totals for KPI deltas and renders item trends and spend distribution.
4. A scikit-learn linear regression model uses sequential monthly basket totals to estimate the next month. The UI exposes R² and limitations.
5. On explicit user action, the app creates a dynamic Gemini prompt containing only the household profile, forecast, and current item-level data. Gemini returns a concise analysis and actions.

## Design decisions

- **No generic chatbot:** Gemini has one bounded role—Indian household-budget analyst—and receives structured user context.
- **Graceful degradation:** missing API keys do not break the dashboard; the Gemini panel explains setup.
- **Privacy:** no uploaded data is stored by the app. The user triggers the only Gemini request.
- **Reliability:** CSV schema validation and error messages prevent silent incorrect analysis.
