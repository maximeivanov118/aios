-- 0003 — documents: the company knowledge (SOPs, offers, FAQs, notes) the owner chose to put into the store.
-- Written only by execution/ingest_folder.py ("put <folder> into Supabase", stage 3 of /aios), never on a schedule.
-- One row per file. A folder that needs real rows (a price list, a client list) gets its own migration later.

create table public.documents (
  id           bigint generated always as identity primary key,
  folder       text not null,                      -- AIOS-relative folder given to the ingest, e.g. 'knowledge/sops'
  rel_path     text not null,                      -- file path relative to that folder
  project      text not null,                      -- first path segment(s) of the folder, e.g. 'knowledge/sops'
  kind         text not null,                      -- file extension without the dot: md, txt, json, csv, yaml, html
  title        text,                               -- first Markdown heading, else the file name
  content      text not null,                      -- the file's text, as on disk
  size_bytes   integer not null,
  content_sha  text not null,                      -- sha256 of content: skips unchanged files, verifies the read-back
  file_mtime   timestamptz,
  ingested_at  timestamptz not null default now(),
  search       tsvector generated always as (
                 setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
                 setweight(to_tsvector('simple', replace(rel_path, '/', ' ')), 'B') ||
                 setweight(to_tsvector('simple', content), 'D')
               ) stored,
  unique (folder, rel_path)
);

create index documents_search_idx on public.documents using gin (search);
create index documents_folder_idx on public.documents (folder);

alter table public.documents enable row level security;
create policy "owner can read documents" on public.documents for select to authenticated using ((select private.is_owner()));
grant select on public.documents to authenticated;

create function public.search_documents(q text, half_life_days numeric default 90, max_rows integer default 20)
returns table (id bigint, folder text, rel_path text, title text, kind text, ingested_at timestamptz, rank real)
language sql
stable
set search_path = public
as $$
  select d.id, d.folder, d.rel_path, d.title, d.kind, d.ingested_at,
         (ts_rank_cd(d.search, websearch_to_tsquery('simple', q), 1 | 32)
          * greatest(0.3, exp(-ln(2) * extract(epoch from (now() - d.ingested_at)) / 86400.0 / half_life_days)))::real as rank
  from public.documents d
  where d.search @@ websearch_to_tsquery('simple', q)
  order by rank desc
  limit max_rows;
$$;
revoke all on function public.search_documents(text, numeric, integer) from public, anon;
grant execute on function public.search_documents(text, numeric, integer) to authenticated, service_role;
