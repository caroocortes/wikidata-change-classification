ALTER TABLE  revision_sample_30
ADD COLUMN IF NOT EXISTS user_type VARCHAR DEFAULT NULL;

-- user type column: bot / anonymous / human
UPDATE revision_sample_30
SET user_type = 
    CASE
        WHEN username ILIKE '%bot%' THEN 'bot'
        WHEN user_id = '' and username = '' THEN 'anonymous'
        ELSE 'human'
    END;


