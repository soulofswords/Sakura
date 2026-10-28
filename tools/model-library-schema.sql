-- Run once in the Sakura Supabase project. No user passwords are stored here.
begin;
create table if not exists public.sakura_model_catalogue (
  id text primary key check (id ~ '^[a-zA-Z0-9_-]{1,100}$'),
  name text not null check (length(name) between 1 and 200),
  format text not null check (format in ('live2d', 'pmx', 'vrm')),
  bytes bigint not null check (bytes between 1 and 536870912),
  sha256 text not null check (sha256 ~ '^[a-f0-9]{64}$'),
  version text not null,
  mobile_compatible boolean not null default false,
  published boolean not null default false,
  drive_file_id text,
  storage_path text,
  preview_storage_path text,
  preview_drive_file_id text,
  created_at timestamptz not null default now()
);
-- Safe to re-run on the existing project before deploying the updated function.
alter table public.sakura_model_catalogue add column if not exists preview_storage_path text;
alter table public.sakura_model_catalogue add column if not exists preview_drive_file_id text;
alter table public.sakura_model_catalogue enable row level security;
-- All reads pass through the authenticated function. Private file IDs stay private.
revoke all on public.sakura_model_catalogue from anon, authenticated;
commit;
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where n.nspname='public' and c.relname='sakura_model_catalogue';

-- Dedicated publisher-created Drive files, encrypted by Supabase Vault.
-- No secret values belong in this schema or migration history.
create or replace function public.sakura_library_storage_read()
returns jsonb language sql security definer set search_path = '' as $$
  select decrypted_secret::jsonb from vault.decrypted_secrets
  where name='sakura-library-drive-storage' limit 1
$$;
revoke all on function public.sakura_library_storage_read() from public,anon,authenticated;
grant execute on function public.sakura_library_storage_read() to service_role;

create or replace function public.sakura_library_storage_write(payload jsonb)
returns void language plpgsql security definer set search_path = '' as $$
declare secret_id uuid;
begin
  if payload->>'scope' is distinct from 'https://www.googleapis.com/auth/drive.file'
     or length(coalesce(payload->>'refresh_token','')) < 20 then
    raise exception 'Expected isolated Drive-file authorization';
  end if;
  select id into secret_id from vault.secrets where name='sakura-library-drive-storage' limit 1;
  if secret_id is null then
    perform vault.create_secret(payload::text,'sakura-library-drive-storage','Dedicated publisher-created Drive files only');
  else
    perform vault.update_secret(secret_id,payload::text);
  end if;
end $$;
revoke all on function public.sakura_library_storage_write(jsonb) from public,anon,authenticated;
grant execute on function public.sakura_library_storage_write(jsonb) to service_role;
