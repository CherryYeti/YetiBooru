CREATE TABLE
  categories (
    id SERIAL PRIMARY KEY,
    label VARCHAR(100) NOT NULL UNIQUE,
    color VARCHAR(100) NOT NULL
  );

CREATE TABLE
  tags (
    id SERIAL PRIMARY KEY,
    label VARCHAR(200) NOT NULL UNIQUE,
    category_id INTEGER NOT NULL REFERENCES categories (id),
    count INTEGER NOT NULL DEFAULT 0
  );

CREATE TABLE
  posts (
    id SERIAL PRIMARY KEY,
    score INTEGER NOT NULL DEFAULT 0,
    type VARCHAR(10) NOT NULL CHECK (type IN ('video', 'image')),
    media_ext VARCHAR(10)
  );

CREATE TABLE
  post_tags (
    post_id INTEGER NOT NULL REFERENCES posts (id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (post_id, tag_id)
  );

CREATE TABLE
  tag_implications (
    parent_tag_id INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    child_tag_id INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (parent_tag_id, child_tag_id),
    CHECK (parent_tag_id != child_tag_id)
  );

CREATE INDEX idx_tags_category_id ON tags (category_id);

CREATE INDEX idx_post_tags_post_id ON post_tags (post_id);

CREATE INDEX idx_post_tags_tag_id ON post_tags (tag_id);

CREATE INDEX idx_tag_implications_parent ON tag_implications (parent_tag_id);

CREATE INDEX idx_tag_implications_child ON tag_implications (child_tag_id);

create table
  "user" (
    "id" text not null primary key,
    "name" text not null,
    "email" text not null unique,
    "emailVerified" boolean not null,
    "image" text,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz default CURRENT_TIMESTAMP not null,
    "role" TEXT NOT NULL DEFAULT 'user',
    "banned" BOOLEAN DEFAULT FALSE,
    "banReason" TEXT,
    "banExpires" TIMESTAMP
  );

create table
  "session" (
    "id" text not null primary key,
    "expiresAt" timestamptz not null,
    "token" text not null unique,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz not null,
    "ipAddress" text,
    "userAgent" text,
    "userId" text not null references "user" ("id") on delete cascade
  );

create table
  "account" (
    "id" text not null primary key,
    "accountId" text not null,
    "providerId" text not null,
    "userId" text not null references "user" ("id") on delete cascade,
    "accessToken" text,
    "refreshToken" text,
    "idToken" text,
    "accessTokenExpiresAt" timestamptz,
    "refreshTokenExpiresAt" timestamptz,
    "scope" text,
    "password" text,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz not null
  );

create table
  "verification" (
    "id" text not null primary key,
    "identifier" text not null,
    "value" text not null,
    "expiresAt" timestamptz not null,
    "createdAt" timestamptz default CURRENT_TIMESTAMP not null,
    "updatedAt" timestamptz default CURRENT_TIMESTAMP not null
  );

create index "session_userId_idx" on "session" ("userId");

create index "account_userId_idx" on "account" ("userId");

create index "verification_identifier_idx" on "verification" ("identifier");