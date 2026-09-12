# Backend Code Map
## Main layers
- `routers/`: HTTP/WebSocket entry points and dependency enforcement.
- `database/schemas/`: Pydantic request and response contracts.
- `services/`: reusable business logic and transactional operations.
- `database/models/`: SQLAlchemy persistence models.
- `core/`: security, tenancy, realtime, notifications, audit and error monitoring.
- `alembic/versions/`: ordered database schema history.
- `docker/maintenance.py`: maintenance loop and midnight trigger.
## `accounting.py`
10 operations: GET, PATCH, POST. See `catalogs/api_routes.csv`.

## `audit.py`
1 operations: GET. See `catalogs/api_routes.csv`.

## `auth.py`
12 operations: DELETE, GET, POST, PUT. See `catalogs/api_routes.csv`.

## `billing.py`
9 operations: DELETE, GET, POST, PUT. See `catalogs/api_routes.csv`.

## `borrower.py`
6 operations: DELETE, GET, POST, PUT. See `catalogs/api_routes.csv`.

## `borrower_registration.py`
1 operations: POST. See `catalogs/api_routes.csv`.

## `branches.py`
8 operations: DELETE, GET, PATCH, POST, PUT. See `catalogs/api_routes.csv`.

## `chat.py`
10 operations: DELETE, GET, PATCH, POST. See `catalogs/api_routes.csv`.

## `company.py`
10 operations: DELETE, GET, PATCH, POST, PUT. See `catalogs/api_routes.csv`.

## `company_registration.py`
1 operations: POST. See `catalogs/api_routes.csv`.

## `company_staff.py`
6 operations: DELETE, GET, POST, PUT. See `catalogs/api_routes.csv`.

## `employees.py`
8 operations: GET, PATCH, POST, PUT. See `catalogs/api_routes.csv`.

## `files.py`
5 operations: DELETE, GET, POST. See `catalogs/api_routes.csv`.

## `loan_offers.py`
6 operations: DELETE, GET, PATCH, POST. See `catalogs/api_routes.csv`.

## `loan_products.py`
8 operations: DELETE, GET, PATCH, POST, PUT. See `catalogs/api_routes.csv`.

## `loan_request.py`
10 operations: DELETE, GET, PATCH, POST. See `catalogs/api_routes.csv`.

## `loans.py`
4 operations: GET, POST. See `catalogs/api_routes.csv`.

## `marketplace.py`
3 operations: GET, POST. See `catalogs/api_routes.csv`.

## `notifications.py`
6 operations: DELETE, GET, PATCH. See `catalogs/api_routes.csv`.

## `payments.py`
3 operations: GET, POST. See `catalogs/api_routes.csv`.

## `performance.py`
1 operations: GET. See `catalogs/api_routes.csv`.

## `person.py`
7 operations: DELETE, GET, POST, PUT. See `catalogs/api_routes.csv`.

## `reports.py`
7 operations: DELETE, GET, PATCH, POST. See `catalogs/api_routes.csv`.

## `system_errors.py`
3 operations: GET, PATCH. See `catalogs/api_routes.csv`.

## `ws.py`
1 operations: WEBSOCKET. See `catalogs/api_routes.csv`.

## Backend change rule

A business feature normally changes the router, Pydantic schema and service. Change the SQLAlchemy model only when persistence changes. When a model changes, create and review an Alembic revision, then run migration checks against a backup/staging database.
