# Development notes

`wwwapp/sheets/projections.py` supplies the canonical participant, lecturer, and workshop tables.
`queue.py` stores dirty state, leases work for ten minutes, and retries failures with capped backoff.
`google.py` owns the Google API boundary and replaces complete tab snapshots. `publisher.py` invokes
it without holding a database transaction; `sync_google_sheets` is the worker. Signals request work
only after data writes commit.

Each integration stores Google tab IDs, so manually renamed managed tabs remain owned. Deleted tabs
are recreated. Reconciliation (`sync_google_sheets --reconcile`) queues all enabled camps, while a
normal worker (`sync_google_sheets`) processes due work. Inspect the Camp admin inline for claim,
retry, success, and error state.
