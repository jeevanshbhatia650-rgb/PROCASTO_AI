-- Applied to project duaaijaftvrvkluhjxxo on 2026-09-30 (migrations "delete_account_needs_recent_sign_in" and
-- "delete_account_uses_sign_in_time"). Deleting an account needs a real sign-in from the last 10 minutes, so an
-- old or stolen session can't do it. The token's iat resets on every automatic refresh; amr keeps when the person
-- actually signed in.
create or replace function public.delete_my_account() returns void
language plpgsql security definer set search_path = ''
as $$
declare
  signed_in_at bigint := coalesce((
    select max((entry ->> 'timestamp')::bigint)
    from jsonb_array_elements(coalesce((select auth.jwt()) -> 'amr', '[]'::jsonb)) as entry
    where entry ->> 'method' <> 'token_refresh'
  ), 0);
begin
  if (select auth.uid()) is null then
    raise exception 'not signed in';
  end if;
  if signed_in_at < extract(epoch from now()) - 600 then
    raise exception 'recent sign-in required' using errcode = '42501';
  end if;
  delete from auth.users where id = (select auth.uid());
end;
$$;
revoke execute on function public.delete_my_account() from public, anon;
grant execute on function public.delete_my_account() to authenticated;
