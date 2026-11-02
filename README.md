# Task Manager API

A REST API where a user can sign up, log in, and manage their own to-do tasks.
It is a learning and portfolio project built for a SIWES report. There is no
frontend: you use it through an API client, curl, or the built-in `/docs` page.

Built with FastAPI, SQLAlchemy, Pydantic, passlib (bcrypt), python-jose (JWT), and pytest.

## Project structure

```
app/
  main.py          Creates the app; request logging and the catch-all error handler
  config.py        Settings read from environment variables
  database.py      Database engine, sessions, and the get_db dependency
  models.py        SQLAlchemy models: the User and Task tables
  schemas.py       Pydantic schemas: what requests and responses look like
  auth.py          Password hashing, JWT tokens, and the get_current_user dependency
  routes/
    auth.py        POST /auth/signup and /auth/login
    tasks.py       The /tasks CRUD routes
tests/             Automated tests
.env.example       Template for your local .env file
```

## Data model

One user has many tasks. Each task belongs to exactly one user.

| User              | Notes                  |
| ----------------- | ---------------------- |
| `id`              | Primary key            |
| `email`           | Unique, required       |
| `hashed_password` | bcrypt hash            |
| `created_at`      | Set automatically      |

| Task          | Notes                  |
| ------------- | ---------------------- |
| `id`          | Primary key            |
| `title`       | Required, 1-200 characters |
| `description` | Optional               |
| `is_done`     | Defaults to `false`    |
| `owner_id`    | Foreign key to `User.id` |
| `created_at`  | Set automatically      |

## Install and run

You need Python 3.11 or newer. Run these from the project folder.

**1. Create and activate a virtual environment**

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

**2. Install the dependencies**

```bash
pip install -r requirements.txt
```

**3. Create your `.env` file**

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env
```

Then generate a secret key and paste it after `SECRET_KEY=` in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The app will not start without a `SECRET_KEY` of at least 32 characters.

**4. Start the server**

```bash
uvicorn app.main:app --reload
```

The API is now at <http://127.0.0.1:8000>. The tables are created automatically
the first time it starts.

The easiest way to try it is the interactive page at <http://127.0.0.1:8000/docs>.
Log in there, then paste the token into the **Authorize** button.

## Configuration

Settings come from environment variables, or from `.env` for local development.

| Variable                      | Required | Default                       | Purpose                     |
| ----------------------------- | -------- | ----------------------------- | --------------------------- |
| `SECRET_KEY`                  | Yes      | None                          | Signs the login tokens      |
| `DATABASE_URL`                | No       | `sqlite:///./task_manager.db` | Which database to use       |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No       | `30`                          | How long a login token lasts |

### Using Postgres

No code changes are needed, but two things have to be right:

1. Install the Postgres driver, which is not in `requirements.txt` because local
   development doesn't need it: `pip install "psycopg[binary]"`
2. Set `DATABASE_URL` to a URL starting with `postgresql://`. Some hosts hand out
   URLs starting with `postgres://`, which SQLAlchemy rejects, so change that part
   if yours does.

## Endpoints

| Method   | URL            | Auth | Purpose                                     | Success |
| -------- | -------------- | ---- | ------------------------------------------- | ------- |
| `POST`   | `/auth/signup` | No   | Create a user                               | `201`   |
| `POST`   | `/auth/login`  | No   | Get an access token                         | `200`   |
| `POST`   | `/tasks`       | Yes  | Create a task                               | `201`   |
| `GET`    | `/tasks`       | Yes  | List your tasks, with optional `?is_done=`  | `200`   |
| `GET`    | `/tasks/{id}`  | Yes  | Get one task                                | `200`   |
| `PUT`    | `/tasks/{id}`  | Yes  | Replace a task                              | `200`   |
| `DELETE` | `/tasks/{id}`  | Yes  | Delete a task                               | `204`   |

### Example requests

These use bash syntax. On Windows, run them in Git Bash, or use the `/docs` page,
because PowerShell treats `curl` and the quotes differently.

**Sign up**

```bash
curl -X POST http://127.0.0.1:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "ann@example.com", "password": "correct-password"}'
```

```json
{"id": 1, "email": "ann@example.com", "created_at": "2026-11-02T10:00:00"}
```

**Log in**

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "ann@example.com", "password": "correct-password"}'
```

```json
{"access_token": "eyJhbGciOi...", "token_type": "bearer"}
```

Save the token so the next commands can use it:

```bash
TOKEN="paste-your-access-token-here"
```

**Create a task**

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write report", "description": "SIWES chapter 3"}'
```

```json
{"id": 1, "title": "Write report", "description": "SIWES chapter 3", "is_done": false, "owner_id": 1, "created_at": "2026-11-02T10:01:00"}
```

**List tasks** (remove `?is_done=false` to get all of them)

```bash
curl "http://127.0.0.1:8000/tasks?is_done=false" -H "Authorization: Bearer $TOKEN"
```

**Get one task**

```bash
curl http://127.0.0.1:8000/tasks/1 -H "Authorization: Bearer $TOKEN"
```

**Update a task**

`PUT` replaces the whole task, so `title` and `is_done` are both required, and
leaving out `description` clears it.

```bash
curl -X PUT http://127.0.0.1:8000/tasks/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Write report", "description": "SIWES chapter 3", "is_done": true}'
```

**Delete a task** (returns `204` with no body)

```bash
curl -X DELETE http://127.0.0.1:8000/tasks/1 -H "Authorization: Bearer $TOKEN"
```

### Error responses

Errors are JSON with a `detail` field.

| Status | When                                                                       |
| ------ | -------------------------------------------------------------------------- |
| `401`  | Wrong email or password; token missing, invalid, or expired                |
| `404`  | The task doesn't exist, or belongs to another user                         |
| `409`  | Signing up with an email that is already registered                        |
| `422`  | Invalid input, such as an empty title, short password, or malformed email  |
| `500`  | Unexpected server error. The client gets a generic message; details are logged |

The API never returns `403`. Someone else's task gets a `404` instead, as if it
didn't exist, so users can't discover which task ids are in use.

## Running the tests

```bash
pytest
```

The tests use a temporary in-memory database and their own settings, so they don't
need a `.env` file and never touch your development data.

## Logging

Logs are written to the console using Python's `logging` module:

- Every request, with its method, path, status code, and duration
- Sign-ups, logins, failed logins, rejected tokens, and task changes
- Full details of unexpected errors, including the stack trace

Request bodies and headers are never logged, so passwords and tokens stay out of the logs.

```
2026-11-02 10:01:00,123 INFO [app.routes.tasks] Task created: id=1 owner_id=1
2026-11-02 10:01:00,124 INFO [app.main] POST /tasks -> 201 (4.2 ms)
```

## Where each concept is demonstrated

| Concept                                       | Where                                         |
| --------------------------------------------- | --------------------------------------------- |
| HTTP methods and status codes                 | `app/routes/`                                 |
| Backend separate from any client              | The whole project: a JSON API with no frontend |
| REST design, resources as URLs                | `/tasks`, `/tasks/{id}`                       |
| Path params, query params, JSON bodies        | `app/routes/tasks.py`                         |
| FastAPI routing                               | `APIRouter` in `app/routes/`, included in `app/main.py` |
| Database CRUD                                 | `app/routes/tasks.py`                         |
| Primary keys, foreign key, one-to-many        | `app/models.py`                               |
| ORM models and session-based queries          | `app/models.py`, `app/database.py`            |
| Authentication and authorization              | `app/auth.py`, `get_owned_task` in `app/routes/tasks.py` |
| Validation and error handling                 | `app/schemas.py`, `app/main.py`               |
| Environment configuration                     | `app/config.py`, `.env.example`               |
| Automated tests                               | `tests/`                                      |
| Logging and observability                     | `app/main.py`, plus a logger in each module   |

## Possible future improvements

These were left out on purpose to keep the project focused:

- Database migrations with Alembic. Tables are currently only created if missing,
  so later changes to a model won't update an existing table.
- Pagination for `GET /tasks`
- Refresh tokens and logout
- Password reset and email verification
- Rate limiting on the login route
- A health check endpoint for hosting platforms
- A `PATCH` route for partial task updates
