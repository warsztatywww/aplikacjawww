# Repository Guidelines

## Scope and project layout

This is a Django application for managing registrations for a scientific summer
school. Webpack builds the JavaScript and stylesheet bundles that Django serves.

- `wwwapp/`: main application: models, views, forms, authentication, management
  commands, and tests.
- `wwwforms/`: reusable form models, admin integration, forms, and tests.
- `gallery/`: gallery models, views, templates, and tests.
- `frontend/`: Webpack entry points and frontend source assets.
- `templates/` and `static/`: Django templates and static assets. Webpack writes
  bundles to `static/dist/`.
- `assets/`: branding and reference assets.

Place tests in the owning app, using `test_*.py` names (for example,
`wwwapp/tests/test_auth.py`). Do not place application tests in a new top-level
test directory.

## Local setup and daily commands

Use the project's existing Python and Node toolchains; do not introduce a new
package manager or build system without discussion.

- `pip install -r requirements.txt`: install Python dependencies in an active
  virtual environment.
- `npm ci`: install JavaScript dependencies from the lockfile. Use `npm install`
  only when intentionally updating dependencies and the lockfile.
- `./manage.py migrate`: apply local database migrations.
- `./manage.py runserver`: start the Django development server.
- `./manage.py populate_with_test_data`: add development fixture data to the
  local database. Run migrations first; never run this against a production or
  shared database.

## Frontend assets

Webpack has three entry points: `frontend/index.ts`, `frontend/datatables.ts`,
and `frontend/tinymce.ts`. It emits JavaScript and extracted CSS into
`static/dist/`, which Django serves directly during development.

After changing JavaScript, TypeScript, SCSS, CSS, or a frontend dependency, run
one of the following before checking the change in Django:

- `npm run build-dev`: development build; faster and unminified. Use this for a
  one-off local rebuild.
- `npm run watch`: development build that rebuilds on changes during active
  frontend work.
- `npm run build`: optimized production build. Use this when validating the
  production asset output.

Do not edit generated files in `static/dist/`; update their sources under
`frontend/` and rebuild them instead.

## Testing and verification

Start with the narrowest relevant check, then expand only when the change
warrants it.

- `./manage.py test wwwapp.tests.test_auth`: run a focused Django test module.
- `./manage.py test -v 2`: run the full Django test suite.
- `./manage.py makemigrations --check --dry-run`: confirm model changes do not
  leave migrations missing.

`coverage.sh` and `type_check.sh` are experimental tools and are not part of the
supported verification flow. Coverage is incomplete, and type annotations cover
only part of the project; `type_check.sh` currently fails when run for the full
project. Use Django's test runner (`./manage.py test -v 2`) for supported test
verification.

For behavior changes, add or update a focused test. Exercise error and boundary
cases when the modified code handles them. For model changes, run the migration
check; create and commit the migration when Django reports one is needed.

## Code and template conventions

- Follow the existing Python style: 4-space indentation, `snake_case` for
  functions and variables, and `PascalCase` for classes.
- Prefer clear, explicit names and small, focused changes over refactors that
  are unrelated to the requested work.
- Keep Django view, form, and model behavior covered by app-local tests.
- Render Django forms and formsets with django-crispy-forms.
- Keep frontend entry-point changes in `frontend/`; do not hand-edit build
  output.
- Never commit secrets, local databases, uploaded media, virtual environments,
  or `node_modules/`. Use environment-specific settings for credentials.

## Working-tree and Git practices

- Inspect `git status` before editing and preserve unrelated user changes.
- Keep commits focused and use an imperative subject of 72 characters or fewer.
- Before committing, review the diff and run the relevant targeted tests and
  checks above. Include test evidence and migration notes in pull requests.
- Do not push directly to the default branch; use a feature branch and pull
  request.
