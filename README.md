# Café platform

Websites for small cafés: a public site (menu, opening hours, directions) and a
phone-friendly dashboard where the owner keeps the menu and hours up to date.
One installation serves many cafés; each lives at `/<cafe-slug>/`.

Built with Django 5.2 (LTS), PostgreSQL and HTMX.

## What's in Phase 1

**Public site** (`/bean-house/`, `/bean-house/menu/`, `/bean-house/visit/`)
- "Open now / Closed now" using the café's own timezone, including hours past midnight and one-off closures
- Menu by section, with prices, photos, vegetarian tags and "sold out today"
- Opening hours, map, directions, call / WhatsApp / Instagram links

**Owner dashboard** (`/dashboard/`)
- Log in (Argon2-hashed passwords, lockout after repeated failed attempts)
- Add, edit and delete menu sections and items, upload photos
- One tap to mark an item sold out or available again
- Set weekly hours and special closure days
- Edit café details, logo, cover photo and brand colour (owners only; staff can't)

**Platform admin** (`/admin/`): create cafés and link owner/staff logins.

### Safety built in
- Every dashboard query is scoped to the logged-in user's café; trying another café's
  page or item returns "not found". Covered by tests.
- Database constraints back up the form rules (one hours row per day, open days need times).
- CSRF protection, secure cookies, HSTS, no-sniff and clickjacking headers in production.
- Secrets only come from environment variables.

## Run it locally

You need Python 3.12+ and PostgreSQL 16.

```bash
# 1. Database
createuser -P cafe            # password: cafe (local only)
createdb -O cafe cafe_platform

# 2. Code
python3 -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env          # then: export $(cat .env | xargs)   (or set the variables another way)

# 3. Set up and start
python manage.py migrate
python manage.py createcachetable
python manage.py seed_demo --owner-password "pick-a-password"
python manage.py createsuperuser   # your platform admin login
python manage.py runserver
```

Then open http://localhost:8000/bean-house/ and log in at http://localhost:8000/dashboard/
as `demo-owner`.

## Tests and checks

```bash
python manage.py test        # 43 tests: hours logic, public pages, access control, login lockout
ruff check . && ruff format --check .
```

GitHub Actions runs all of this against a real PostgreSQL on every push and pull request.

## Deploying (Render)

`render.yaml` sets up a web service and a PostgreSQL database (about $13/month).

1. In Render choose **New → Blueprint** and pick this repository.
2. Render asks for two passwords: `DJANGO_SUPERUSER_PASSWORD` (your `admin` login for `/admin/`)
   and `DEMO_OWNER_PASSWORD` (the `demo-owner` login for the Bean House demo dashboard).
3. Click **Apply**. Every push to `main` deploys automatically after that.

The build creates the admin and the demo café on the first deploy only. To skip the
demo café, leave `DEMO_OWNER_PASSWORD` empty.

Uploaded photos need S3-compatible storage in production (Cloudflare R2 is cheapest),
because Render's disk is wiped on each deploy. Set the `MEDIA_*` variables from `.env.example`.

## Next phases

2. Online ordering with pay-at-pickup and a live order screen
3. Online payments (M-Pesa, cards)
4. Café self-signup, custom domains, subscriptions
5. Loyalty, promo codes, QR table ordering
