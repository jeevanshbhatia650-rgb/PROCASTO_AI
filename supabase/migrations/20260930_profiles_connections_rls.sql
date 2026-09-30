-- Applied to project duaaijaftvrvkluhjxxo on 2026-09-30 (migration "profiles_connections_rls").

-- One profile per user, created by a trigger when they sign up.
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  display_name text not null default '' check (char_length(display_name) <= 60),
  home_name text not null default 'My home' check (char_length(home_name) between 1 and 60),
  onboarded boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Smart-home accounts a user linked. The token is encrypted by the app server before it is stored.
create table public.connections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  provider text not null check (provider in ('smartthings')),
  status text not null default 'connected' check (status in ('connected', 'error')),
  account_label text not null default '' check (char_length(account_label) <= 120),
  token_ciphertext text check (char_length(token_ciphertext) <= 8192),
  connected_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, provider)
);

alter table public.profiles enable row level security;
alter table public.connections enable row level security;

create policy "Users read their own profile" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "Users update their own profile" on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

create policy "Users read their own connections" on public.connections
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "Users add their own connections" on public.connections
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "Users update their own connections" on public.connections
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Users remove their own connections" on public.connections
  for delete to authenticated using ((select auth.uid()) = user_id);

-- Nobody signed out can touch either table, even by accident.
revoke all on public.profiles, public.connections from anon;

create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, left(coalesce(new.raw_user_meta_data ->> 'display_name', ''), 60));
  return new;
end;
$$;
revoke execute on function public.handle_new_user() from public, anon, authenticated;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

create function public.touch_updated_at() returns trigger
language plpgsql set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
revoke execute on function public.touch_updated_at() from public, anon, authenticated;

create trigger profiles_touch_updated_at before update on public.profiles
  for each row execute function public.touch_updated_at();
create trigger connections_touch_updated_at before update on public.connections
  for each row execute function public.touch_updated_at();

-- Lets a signed-in user delete their own account; profiles and connections cascade.
-- (The Supabase advisor flags any signed-in-callable SECURITY DEFINER function; this one is intentional.)
create function public.delete_my_account() returns void
language plpgsql security definer set search_path = ''
as $$
begin
  if (select auth.uid()) is null then
    raise exception 'not signed in';
  end if;
  delete from auth.users where id = (select auth.uid());
end;
$$;
revoke execute on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
