begin;
alter table public.sakura_model_catalogue add column if not exists jio_object_key text;
alter table public.sakura_model_catalogue add column if not exists jio_preview_object_key text;
alter table public.sakura_model_catalogue enable row level security;
revoke all on public.sakura_model_catalogue from anon, authenticated;

create or replace function public.sakura_library_jio_read()
returns jsonb language sql security definer set search_path = '' as $$
  select decrypted_secret::jsonb from vault.decrypted_secrets
  where name='sakura-library-jio-storage' limit 1
$$;
revoke all on function public.sakura_library_jio_read() from public, anon, authenticated;
grant execute on function public.sakura_library_jio_read() to service_role;

create or replace function public.sakura_library_jio_write(payload jsonb)
returns void language plpgsql security definer set search_path = '' as $$
declare secret_id uuid;
begin
  if payload->>'provider' is distinct from 'jio'
     or coalesce(length(payload->'session'->'authToken'->>'accessToken'),0)<10
     or coalesce(length(payload->'session'->>'userId'),0)<1
     or payload->'session'->>'dcGroupCode' not in ('JAWS','JMNG','JMNG2') then
    raise exception 'Expected verified Jio storage connection';
  end if;
  select id into secret_id from vault.secrets where name='sakura-library-jio-storage' limit 1;
  if secret_id is null then
    perform vault.create_secret(payload::text,'sakura-library-jio-storage','Owner-only Jio library storage');
  else
    perform vault.update_secret(secret_id,payload::text);
  end if;
end $$;
revoke all on function public.sakura_library_jio_write(jsonb) from public, anon, authenticated;
grant execute on function public.sakura_library_jio_write(jsonb) to service_role;
commit;
