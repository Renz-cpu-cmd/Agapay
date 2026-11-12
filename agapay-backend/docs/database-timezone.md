# PostgreSQL time-zone policy (R2)

## What the code does

- **Columns.** All 118 timestamp columns in migrations 0001–0008 are `timestamp with time zone`.
  There are no naive timestamp or date columns.
- **Writes.** The application writes timezone-aware UTC values (`utc_now()`). Every comparison
  normalizes through `utc()`. No query uses database-side `now()`, `date_trunc` or similar.
- **Sessions.** `app/database.py` opens every PostgreSQL connection with `TimeZone=UTC`, whatever
  the server or database default. Values read back are therefore rendered in UTC, and a naive
  literal can never be shifted by a local offset.
- **Offline transfer.** `app/transfer_database.py` also sets `TIME ZONE 'UTC'` for its writer.

## Production configuration (all three levels)

1. **Server:** `timezone = 'UTC'` and `log_timezone = 'UTC'` in `postgresql.conf`.
2. **Database:** `ALTER DATABASE <agapay database> SET TimeZone = 'UTC';`
3. **Connection:** enforced by the application (above). Other tools such as psql, backups and
   reporting should also set `PGTZ=UTC`.

Verify with `SHOW TimeZone;` from the application role, and from a plain client after step 2.

## Evidence

`tests/test_postgres_timezone.py` ran on real PostgreSQL 16. The server was set to
`Asia/Kuala_Lumpur` (+08), as the drill instance was; every earlier PostgreSQL suite run also used
that non-UTC default. The tests cover:

- **Defaults overridden.** A database-level `Asia/Manila` default applies to plain clients, while
  application sessions still report UTC.
- **Same instants and ordering in every zone.** Readings ingested through the API keep identical
  instants and identical ordering (telemetry and alert transitions) when read from Manila,
  Kiritimati (+14), Adak (−10) and New York sessions.
- **Boundary instants round-trip unchanged.** Checked for the UTC year end, local midnight in
  Manila/Kuala Lumpur, the New York DST fold and the New York DST gap, including writes made from
  foreign-zone sessions.
- **Expiry decisions are zone independent.** Exercise-session expiry and recovery-generation
  activation times come out the same after foreign-zone writes.
- **The removed hazard is real.** A naive literal shifts by exactly 8 hours in a Manila session,
  and does not in an application session.

**Finding.** In a New York session, a value inside the DST fold comes back as an ambiguous local
wall time. Python never treats that as equal to the same instant in another zone. The stored
value is correct; this is a client-side hazard that UTC sessions avoid. Reports and exports
should use UTC sessions.
