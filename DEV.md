# Development information

## Project structure

- `wwwapp/` contains the main Django models, forms, views, URL routes, management commands, and
  app-local tests.
- `wwwforms/` contains reusable form models, forms, admin integration, and tests.
- `gallery/` contains gallery models, views, templates, and tests.
- `templates/` contains Django templates shared by the applications.
- `frontend/` contains the TypeScript and stylesheet sources built by Webpack.
- `static/dist/` contains generated Webpack output and must not be edited directly.

## Costs and invoice documents

Invoice records and their attachment fields are defined in `wwwapp/models.py`. Costs views are in
`wwwapp/views.py`, their routes are in `wwwapp/urls.py`, and costs view tests are in
`wwwapp/tests/test_costs_views.py`.

The custom costs administration page is `templates/costs_admin.html`. It requires the
`wwwapp.view_all_costs` permission. Its invoice archive endpoint uses the same permission. The
endpoint selects all invoices for the requested camp. Python reads each attachment through Django's
configured file storage and streams it into a temporary ZIP file. Django streams that file in the
response without nginx sendfile handling.

ZIP members use the same names as individual invoice downloads. A numbered invoice uses its
internal number plus the stored file extension. An unnumbered invoice uses the basename stored in
its attachment field. Members are placed at the ZIP root; no directory hierarchy is added. When two
names collide, later members receive ` (2)`, ` (3)`, and higher suffixes before the extension.
