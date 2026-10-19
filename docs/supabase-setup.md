# Supabase setup

One-time setup. Passwords go only into `.env`, never into code, chat or git.

## 1. Create the project

1. Sign in at https://supabase.com/dashboard and click **New project**.
2. Name: e.g. `vlstat-analyse`. **Region: an EU region** (Frankfurt or Stockholm), since the data is about Danish lifters (GDPR).
3. Generate a strong database password and store it in your password manager.
4. Wait until the project shows as ready (about 2 minutes).

## 2. Fill in the admin connection

1. In the project, click **Connect** (top bar) → **Session pooler**. Use the pooler: the direct connection is IPv6-only and often fails on home networks.
2. Copy the URI. It looks like
   `postgresql://postgres.abcdefghijkl:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`
3. In the project folder, copy `.env.example` to `.env` (already done if `.env` exists) and set `DATABASE_URL_ADMIN` to that URI with your password filled in.
   If the password has special characters (`@ : / ? #`), URL-encode them, or generate one with letters and digits only.

## 3. Run the migrations

```bash
uv run python -m db.migrate
uv run python -m db.check
```

This creates schema `vl` with the tables, the `v_entry_result` view, the Sinclair coefficients and the group roles `vl_read` / `vl_write`.
`db.check` should show `[ok] admin (postgres): read+write, 4 Sinclair rows`.

## 4. Create the login users

In the dashboard: **SQL Editor** → New query. Replace the two passwords with new, different ones (letters and digits only), then run:

```sql
CREATE ROLE vl_writer LOGIN PASSWORD 'replace-me-1' IN ROLE vl_write;
CREATE ROLE vl_reader LOGIN PASSWORD 'replace-me-2' IN ROLE vl_read;
```

Then fill in `DATABASE_URL_WRITE` and `DATABASE_URL_READ` in `.env`. Same host and port as the admin URI, but the user is `vl_writer.PROJECT_REF` / `vl_reader.PROJECT_REF` (the pooler needs the `.PROJECT_REF` suffix).

Run `uv run python -m db.check` again. All three lines should be `[ok]`, and the reader must say `read-only`.

## Notes

- The `vl` schema is **not** exposed through Supabase's REST API. Don't add it under *Settings → API → Exposed schemas*: the app connects to Postgres directly.
- Free-tier projects pause after a week without activity. Unpause from the dashboard if connections suddenly time out.
