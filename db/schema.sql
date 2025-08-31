-- Schéma & tables pour Chessscore (Supabase/Postgres)
create schema if not exists chessscore;
set search_path to chessscore, public;

create table if not exists games(
  id bigserial primary key,
  date date not null,
  white text not null check (length(trim(white)) > 0),
  black text not null check (length(trim(black)) > 0),
  result real not null check (result in (0, 0.5, 1))
);

create table if not exists players(
  id bigserial primary key,
  name text unique not null,
  alias text
);

create index if not exists games_date_idx  on games(date);
create index if not exists games_white_idx on games(white);
create index if not exists games_black_idx on games(black);
create unique index if not exists games_uniq_triplet on games(date, white, black);
