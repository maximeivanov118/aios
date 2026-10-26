-- 0002 — Where data comes from (sources) and the data itself (items): mail, calendar events, messages, meetings.
-- Written by collectors (n8n or a script) with the secret key. Read by the owner (app, MCP) through RLS.
-- Nothing is collected until stage 4 of /aios connects a tool; these tables can stay empty until then.

create table public.sources (
  id              text primary key,                       -- 'gmail_inbox', 'google_calendar', 'outlook', 'slack_general', ...
  kind            text not null check (kind in ('mail', 'calendar', 'chat', 'meeting', 'crm', 'drive', 'other')),
  account         text,                                   -- the mailbox / calendar / workspace, human readable
  last_success_at timestamptz,                            -- heartbeat: set by the collector after a successful run
  last_error      text,                                   -- last failure text, cleared on success
  last_count      integer,                                -- items seen on the last run
  updated_at      timestamptz not null default now()
);

create table public.items (
  id           bigint generated always as identity primary key,
  source_id    text not null references public.sources (id),
  external_id  text not null,                             -- the provider's id (message id, event id, ...)
  kind         text not null check (kind in ('mail', 'event', 'message', 'meeting', 'task', 'record', 'other')),
  occurred_at  timestamptz not null,                      -- sent / starts at
  author       text,
  title        text,                                      -- subject / event title
  body_text    text,                                      -- plain text; how long it is kept is the owner's decision
  raw          jsonb,                                     -- the normalised item as the collector saw it
  summary      text,                                      -- one sentence, model-written (later)
  atoms        text[] not null default '{}',              -- exact facts: amounts, deadlines, decisions (later)
  questions    text[] not null default '{}',              -- questions this item answers (later)
  bucket       text check (bucket in ('needs_you', 'reply_owed', 'fyi', 'unclassified')),
  created_at   timestamptz not null default now(),
  -- 'simple' config: no stemming, so every language is tokenised the same way.
  search       tsvector generated always as (
                 setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
                 setweight(array_to_tsvector(atoms), 'A') ||
                 setweight(to_tsvector('simple', coalesce(summary, '')), 'B') ||
                 setweight(to_tsvector('simple', coalesce(author, '')), 'C') ||
                 setweight(to_tsvector('simple', coalesce(body_text, '')), 'D')
               ) stored,
  unique (source_id, external_id)                         -- collectors upsert with ON CONFLICT DO NOTHING
);

create index items_search_idx   on public.items using gin (search);
create index items_occurred_idx on public.items (occurred_at desc);
create index items_source_idx   on public.items (source_id);

alter table public.sources enable row level security;
alter table public.items   enable row level security;
create policy "owner can read sources" on public.sources for select to authenticated using ((select private.is_owner()));
create policy "owner can read items"   on public.items   for select to authenticated using ((select private.is_owner()));
grant select on public.sources, public.items to authenticated;

-- Full-text search with recency weighting: rank x exp decay (half-life in days), floored at 0.3
-- so old but exact matches still surface.
create function public.search_items(q text, half_life_days numeric default 30, max_rows integer default 20)
returns table (
  id bigint, source_id text, kind text, occurred_at timestamptz,
  author text, title text, summary text, bucket text, rank real
)
language sql
stable
set search_path = public
as $$
  select i.id, i.source_id, i.kind, i.occurred_at, i.author, i.title, i.summary, i.bucket,
         (ts_rank_cd(i.search, websearch_to_tsquery('simple', q), 1 | 32)
          * greatest(0.3, exp(-ln(2) * extract(epoch from (now() - i.occurred_at)) / 86400.0 / half_life_days)))::real as rank
  from public.items i
  where i.search @@ websearch_to_tsquery('simple', q)
  order by rank desc
  limit max_rows;
$$;
revoke all on function public.search_items(text, numeric, integer) from public, anon;
grant execute on function public.search_items(text, numeric, integer) to authenticated, service_role;
