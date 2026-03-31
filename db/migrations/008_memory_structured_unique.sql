-- Unique constraint for upsert on structured memory facts
ALTER TABLE memory_structured
    ADD CONSTRAINT memory_structured_user_cat_key
    UNIQUE (user_id, category, key);
