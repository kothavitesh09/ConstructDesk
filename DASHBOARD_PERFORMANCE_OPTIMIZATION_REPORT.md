# Dashboard Performance Optimization Report

## Files Changed

- `routes/dashboard.py`
  - Replaced broad collection loads with targeted MongoDB aggregations.
  - Added faceted aggregate queries for flat, booking, receipt, and customer dashboard data.
  - Reused query results for dashboard stats, tower summaries, pending collections, and recent activity.
  - Limited list queries to the records actually displayed by the dashboard.

## Before Architecture

- Loaded all matching flats, bookings, receipts, customers, projects, and towers through service calls.
- Filtered bookings, receipts, pending collections, registrations, and activity lists in Python.
- Loaded all receipts with an empty query, then filtered them in memory.
- Queried projects and towers more than once during the same request.
- Built dashboard totals by iterating over full document lists.

## After Architecture

- Flat totals, status counts, registered counts, and tower flat counts are produced by one `$facet` aggregation.
- Booking totals, outstanding totals, pending customer counts, top pending bookings, and recent bookings are produced by one `$facet` aggregation.
- Receipt totals, registration counts, recent registrations, and recent receipts are produced by one `$facet` aggregation.
- Customer total and recent customer activity are produced by one `$facet` aggregation.
- Tower performance reuses grouped flat, booking, and receipt metrics instead of scanning full lists in Python.
- Project and tower dropdown data are fetched once with only the fields needed by the UI.

## Risks

- Date filtering is now pushed into MongoDB for ISO date strings and datetime values. Non-ISO historical date strings may not match as broadly as the previous Python parser.
- Receipt scoping now uses receipt fields such as `project_id`, `tower_id`, and `customer_name` instead of loading receipts and comparing every booking id in Python.
- Each app process still runs these aggregations independently, so very large datasets may need supporting indexes on dashboard filter fields.

## Expected Performance Improvement

- Fewer MongoDB round trips for dashboard rendering.
- Less memory use in Flask because full booking, receipt, flat, and customer lists are no longer loaded for summary cards.
- Faster dashboard response time on larger datasets due to server-side grouping and counting.
- Lower Python CPU work because sums, counts, distinct grouping, and top lists are handled by MongoDB.
