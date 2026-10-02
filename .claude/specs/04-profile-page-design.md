# Spec: Profile Page Design

## Overview
This feature replaces the `/profile` stub with a fully designed, login-protected profile page. The page shows the user's account details (name, email, member-since date), a row of summary stats (total spent, number of transactions, top category), a category breakdown, and a recent-transactions table. At this stage the focus is the **page design and layout**: the route passes hardcoded placeholder data to the template so the UI can be built and reviewed in isolation. Wiring the page to real database queries is deferred to a later step. This is also the first page that only logged-in users can reach, so it introduces the login guard and a session-aware navbar (Profile / Sign out for logged-in users, Sign in / Get started for guests).

## Depends on
- Step 01 — Database Setup (`users` and `expenses` tables exist)
- Step 02 — Registration (users can be created)
- Step 03 — Login and Logout (`session["user_id"]` is set on login and cleared on logout)

## Routes
- `GET /profile` — render the profile page with hardcoded placeholder data; redirect guests to `/login` — logged-in

No other new routes.

## Database changes
No database changes. The page uses hardcoded placeholder data in this step; the existing `users` and `expenses` tables already contain every field the design needs (`name`, `email`, `created_at`, `amount`, `category`, `date`, `description`) for when it is wired up later.

## Templates
- **Create:** `templates/profile.html` — extends `base.html`; sections:
  - Profile header card: avatar circle with the user's initials, name, email, "Member since" date
  - Summary stats row: three stat cards — Total spent (₹), Transactions (count), Top category
  - Category breakdown: one row per category showing name, amount (₹), and a horizontal bar sized by its share of total spend (width set via inline `style="width: N%"` computed in Jinja — no JS required)
  - Recent transactions table: columns Date, Description, Category (pill/badge), Amount (₹, right-aligned); an empty-state message if the list is empty
- **Modify:** `templates/base.html` — make the navbar session-aware: if `session.user_id` is set, show "Profile" (`url_for('profile')`) and "Sign out" (`url_for('logout')`); otherwise keep "Sign in" and "Get started". Add a `{% block head %}`-compatible link so `profile.html` can load its own stylesheet.

## Files to change
- `app.py` — replace the `profile()` stub: redirect to `url_for("login")` if `"user_id"` not in session; otherwise build the placeholder `user`, `stats`, `categories`, and `transactions` context and render `profile.html`
- `templates/base.html` — session-aware nav links

## Files to create
- `templates/profile.html` — the profile page
- `static/css/profile.css` — profile-page-only styles (loaded via `{% block head %}` in `profile.html`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (no queries are expected in this step — placeholder data only)
- Passwords hashed with werkzeug (no password handling changes in this step)
- Use CSS variables — never hardcode hex values; reuse the tokens in `static/css/style.css` (`--accent`, `--accent-light`, `--paper-card`, `--border`, `--ink-muted`, `--radius-md`, etc.)
- All templates extend `base.html`
- Page-specific styles go in `static/css/profile.css` — no inline `<style>` tags (inline `style="width: …%"` on breakdown bars is the only allowed inline style)
- Use `url_for()` for every internal link — never hardcode paths
- Guests hitting `/profile` must be redirected with `redirect(url_for("login"))`, not shown an error string
- Placeholder data lives in the `profile()` route as plain Python dicts/lists — do not add DB helpers in this step
- Currency is displayed as ₹ with two decimal places (use a Jinja format filter, e.g. `"%.2f"|format(amount)`)
- Placeholder categories must come from the existing set: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- Layout must be responsive: stat cards stack to a single column below ~640px; the transactions table scrolls horizontally rather than overflowing the page
- Vanilla JS only — the page should need no JavaScript at all

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` then visiting `/profile` renders the profile page (no stub string)
- [ ] The profile header shows initials avatar, name, email, and a "Member since" date
- [ ] Three stat cards show Total spent (₹), Transactions count, and Top category
- [ ] The category breakdown lists categories with ₹ amounts and bars whose widths reflect their share of the total
- [ ] The recent transactions table shows Date, Description, Category badge, and right-aligned ₹ amount
- [ ] While logged in, the navbar shows "Profile" and "Sign out"; while logged out it shows "Sign in" and "Get started"
- [ ] Clicking "Sign out" logs the user out and the navbar reverts to guest links
- [ ] `static/css/profile.css` contains no hardcoded hex colour values (`grep -E "#[0-9a-fA-F]{3,6}" static/css/profile.css` returns nothing)
- [ ] `profile.html` contains no `<style>` tags and no hardcoded internal URLs
- [ ] At a narrow (~375px) browser width, stat cards stack vertically and nothing overflows the page horizontally
