# Camp Google Sheets Integration Design

## Goal

Export each camp's participant, lecturer, and workshop administration tables to
one administrator-selected Google Spreadsheet without making application writes
wait for Google.

## Scope

Each camp has at most one optional integration. When enabled, it owns complete
snapshots of three tabs: `Uczestnicy`, `Prowadzący`, and `Warsztaty`. The
integration exports all table columns, including hidden and camp-form columns,
but excludes UI-only DataTables control columns.

## Configuration and credentials

`CampGoogleSheetsIntegration` is a one-to-one model owned by `Camp`. It stores
the Google spreadsheet ID, enabled state, the IDs of the three managed sheets,
dirty and worker-claim state, retry metadata, timestamps for the last attempt
and success, and a sanitized actionable error message. It never stores service
account credentials.

The deployment provides the service account JSON through
`GOOGLE_SERVICE_ACCOUNT_JSON`. The application parses it at runtime and uses
Google service-account credentials with the Google Sheets API. Administrators
must share each selected spreadsheet with that service-account address; this is
a deliberate personal-data access decision because exports include profile
answers, email addresses, birth information, and other hidden fields.

## Projection boundary

`wwwapp.sheets.projections` exposes a typed table projection for each managed
tab: ordered column definitions and ordered rows of literal values or links.
The existing views consume the same projection services (or thin view adapters)
so the Sheets and web tables cannot diverge in membership, column order,
dynamic form questions, or display values.

The projections preserve the current membership and ordering rules:

- `Uczestnicy` includes camp participants except profiles that lecture an
  accepted camp workshop.
- `Prowadzący` includes profiles that lecture an accepted camp workshop.
- `Warsztaty` uses the existing camp-scoped counted workshop queryset.

They reproduce human-readable statuses, booleans, dates, percentages, counts,
and ordinary values. Person and workshop values retain hyperlinks; HTML,
icons, popovers, and empty DataTables-control columns are omitted or reduced to
plain values. Dynamic question headers use a deterministic suffix to
disambiguate duplicate-looking names.

## Provisioning and tab ownership

Enabling is an admin operation that validates API access, provisions all three
managed tabs, and marks the integration dirty for its initial snapshot.

For a tab without a stored Google sheet ID, a pre-existing canonical-title tab
is renamed to a unique, clearly labelled backup before the managed replacement
is created. This preserves the prior contents. Once an ID is stored, that ID
is authoritative: a manually renamed managed tab continues to receive writes
under its chosen title and is never renamed back. If a managed tab is deleted,
the worker creates a canonical-title replacement and records its new ID.

All provisioning and publishing operations are idempotent. A retry after a
partial failure resumes from persisted sheet IDs and verifies the resulting
spreadsheet state.

## Durable work scheduling

The integration record is also the durable PostgreSQL-backed work item; no
separate job table or broker exists. Relevant application changes call a
single dirty-marking service through `transaction.on_commit`. This means a
rolled-back transaction makes no sync request.

The service records `dirty=True` and a due time. If it is already dirty,
additional changes do not create more work, thereby coalescing rapid updates.
A standalone `sync_google_sheets` management command is deployed as the one
worker process. It claims due rows with PostgreSQL locking and `skip_locked`,
sets a claim timestamp, and processes one camp at a time. Stale claims expire
so a crash can recover.

Before clearing `dirty` after a successful upload, the worker checks whether a
new dirty request was recorded while it was publishing. If so, it leaves the
record pending for another snapshot. Failures retain dirty state, increment a
bounded retry counter, and schedule exponential backoff. The admin displays
pending state, last success, last attempt, and the last actionable error.

An hourly reconciliation command marks every enabled integration dirty. This
repairs staleness caused by bulk ORM updates, direct SQL, or missed hooks.

## Change coverage

Signals and explicit services cover creates, updates, deletes, and many-to-many
changes for camp participations, workshops, workshop participations, workshop
lecturers and categories, camp forms, form questions/options/answers, users and
profiles, solutions, and camp configuration. Where a profile or form can span
multiple camps, the marker computes all affected enabled integrations and marks
each one only after commit.

## Snapshot publication

Each worker run computes all three fresh projections and replaces all contents
of each managed tab. It clears obsolete rows and columns before writing new
headers and rows. User-supplied strings that Sheets could interpret as formulas
are written as literal data. Links use Sheets hyperlink values rather than HTML.
Manual cell values and formatting in managed tabs are intentionally not
preserved.

## Verification

Tests mock only the Google API boundary and cover projection parity, dynamic
columns, memberships, transaction rollback, coalescing, claim exclusion,
retries and recovery, provisioning collisions, deleted/renamed tabs,
cross-camp fan-out, literal formula safety, no writes after disable, and hourly
reconciliation. Documentation covers configuration, worker and scheduler
deployment, privacy, troubleshooting, and recovery.
