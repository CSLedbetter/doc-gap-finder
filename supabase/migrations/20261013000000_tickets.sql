-- The helpdesk inbox, in Postgres. Same columns as the SQLite version in inbox.py.
create table if not exists public.tickets (
  id          text primary key,
  received_at timestamptz not null,
  channel     text not null,
  from_name   text,
  from_email  text,
  plan        text,
  subject     text not null,
  body        text not null,
  status      text not null default 'new' check (status in ('new', 'open', 'solved'))
);

create index if not exists tickets_status_received on public.tickets (status, received_at);

-- RLS on with no policies: the public anon key can't read or write anything.
-- Only inbox.py, run locally with the secret key, touches this table.
alter table public.tickets enable row level security;
