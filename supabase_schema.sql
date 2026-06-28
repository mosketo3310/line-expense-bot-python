-- รันใน Supabase SQL Editor
-- ถ้ามีตาราง expenses เดิมอยู่แล้ว ให้ drop ก่อน

drop table if exists expenses;

create table expenses (
  id          bigint generated always as identity primary key,
  day         smallint not null,
  month       smallint not null,
  year        smallint not null,
  time_str    text not null,
  amount      numeric(12,2) default 0,
  slip_url    text,                          -- URL รูปสลิปใน Supabase Storage
  user_id     text,
  created_at  timestamp with time zone default now()
);

create index idx_expenses_year_month on expenses (year, month);
create index idx_expenses_date on expenses (year, month, day);

alter table expenses disable row level security;

-- Storage bucket สำหรับเก็บรูปสลิป
-- รันใน Supabase Dashboard > Storage > New Bucket
-- ชื่อ: slips  | Public: true
-- หรือรัน SQL นี้:
insert into storage.buckets (id, name, public)
values ('slips', 'slips', true)
on conflict (id) do nothing;
