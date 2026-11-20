-- 문서 질문 챗봇용 Supabase 설정 (llm 스키마)
-- Supabase 대시보드 → SQL Editor에 전체를 붙여 넣고 Run 하세요.
-- 여러 번 실행해도 안전하게 작성했습니다.
-- 실행 후: Project Settings → Data API → Exposed schemas 에 llm 이 있어야 합니다.

create schema if not exists llm;

-- ---------- 승인된 사용자 ----------
create table if not exists llm.approved_users (
  user_id uuid primary key references auth.users (id) on delete cascade,
  created_at timestamptz not null default now()
);

-- 현재 로그인한 사용자가 승인됐는지 확인합니다.
create or replace function llm.is_approved()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1 from llm.approved_users where user_id = auth.uid()
  );
$$;

-- ---------- 문서 ----------
create table if not exists llm.documents (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users (id) on delete cascade default auth.uid(),
  filename text not null,
  content text not null,
  created_at timestamptz not null default now()
);
-- 예전에 만든 documents 테이블에도 필요한 열을 추가합니다.
alter table llm.documents
  add column if not exists user_id uuid references auth.users (id) on delete cascade default auth.uid();
alter table llm.documents
  add column if not exists created_at timestamptz not null default now();
-- 같은 사용자 안에서만 파일 이름이 겹치지 않게 합니다.
create unique index if not exists documents_user_filename_key
  on llm.documents (user_id, filename);

-- ---------- 채팅방 ----------
create table if not exists llm.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade default auth.uid(),
  title text not null default '새 채팅',
  created_at timestamptz not null default now()
);

-- ---------- 질문·답변 ----------
create table if not exists llm.chat_turns (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references llm.chat_sessions (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade default auth.uid(),
  question text not null,
  answer text not null,
  sources text[] not null default '{}',
  created_at timestamptz not null default now()
);
create index if not exists chat_turns_session_idx
  on llm.chat_turns (session_id, created_at);

-- ---------- 권한 ----------
grant usage on schema llm to anon, authenticated, service_role;
grant select on llm.approved_users to authenticated;
grant select, insert on llm.documents to authenticated;
grant select, insert on llm.chat_sessions to authenticated;
grant select, insert on llm.chat_turns to authenticated;
grant all on all tables in schema llm to service_role;
grant execute on function llm.is_approved() to authenticated;
-- 로그인하지 않은 사용자(anon)는 테이블을 읽을 수 없습니다.
revoke all on all tables in schema llm from anon;

-- ---------- RLS ----------
alter table llm.approved_users enable row level security;
alter table llm.documents enable row level security;
alter table llm.chat_sessions enable row level security;
alter table llm.chat_turns enable row level security;

-- 예전에 만든 정책(예: 누구나 문서 읽기)을 모두 지우고 아래 정책만 남깁니다.
do $$
declare p record;
begin
  for p in
    select policyname, tablename from pg_policies
    where schemaname = 'llm'
      and tablename in ('approved_users', 'documents', 'chat_sessions', 'chat_turns')
  loop
    execute format('drop policy %I on llm.%I', p.policyname, p.tablename);
  end loop;
end $$;

-- 자기 승인 행만 볼 수 있습니다. 승인 추가는 관리자가 SQL로 합니다.
create policy "read own approval" on llm.approved_users
  for select to authenticated using (user_id = auth.uid());

-- 승인된 사용자는 자기 문서와 공용 샘플 문서(user_id가 비어 있음)를 읽습니다.
create policy "read own and shared documents" on llm.documents
  for select to authenticated
  using (llm.is_approved() and (user_id = auth.uid() or user_id is null));
create policy "add own documents" on llm.documents
  for insert to authenticated
  with check (llm.is_approved() and user_id = auth.uid());

create policy "read own chats" on llm.chat_sessions
  for select to authenticated
  using (llm.is_approved() and user_id = auth.uid());
create policy "add own chats" on llm.chat_sessions
  for insert to authenticated
  with check (llm.is_approved() and user_id = auth.uid());

create policy "read own turns" on llm.chat_turns
  for select to authenticated
  using (llm.is_approved() and user_id = auth.uid());
create policy "add own turns" on llm.chat_turns
  for insert to authenticated
  with check (
    llm.is_approved()
    and user_id = auth.uid()
    and exists (
      select 1 from llm.chat_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );

-- ---------- 사용자 승인 예시 ----------
-- insert into llm.approved_users (user_id)
-- select id from auth.users where lower(email) = lower('승인할@이메일')
-- on conflict (user_id) do nothing;
