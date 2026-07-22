-- ============================================================
-- StrokeX — Supabase PostgreSQL Schema
-- Gamified AI Stroke Rehabilitation Platform
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. PATIENT PROFILES
-- ============================================================
CREATE TABLE patient_profiles (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    first_name      TEXT DEFAULT '',
    last_name       TEXT DEFAULT '',
    email           TEXT UNIQUE,
    age             INTEGER DEFAULT 0,
    birth_date      DATE,
    severity_score  INTEGER DEFAULT 5 CHECK (severity_score BETWEEN 1 AND 10),
    current_streak  INTEGER DEFAULT 0,
    last_played_at  DATE,
    avatar_url      TEXT DEFAULT 'https://api.dicebear.com/7.x/avataaars/png?seed=default',
    doctor_name     TEXT DEFAULT 'Dr. Smith',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 2. GAME SESSIONS
-- ============================================================
CREATE TABLE game_sessions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
    mode_name        TEXT NOT NULL,                -- 'Potion Master', 'Shield Defender', 'Rhythm Maestro', 'Rapid Reaction'
    score            INTEGER DEFAULT 0,
    accuracy         REAL DEFAULT 0.0,             -- 0.0 to 1.0
    reported_fatigue REAL DEFAULT 0.0,             -- 0.0 to 1.0
    xp_earned        INTEGER DEFAULT 0,
    star_rating      REAL DEFAULT 0.0,             -- 0.0 to 5.0
    played_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_game_sessions_user_id ON game_sessions(user_id);
CREATE INDEX idx_game_sessions_played_at ON game_sessions(played_at DESC);

-- ============================================================
-- 3. AI PLANS (NSGA-II Generated)
-- ============================================================
CREATE TABLE ai_plans (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES patient_profiles(id) ON DELETE CASCADE,
    potion_reps     INTEGER DEFAULT 0,
    shield_reps     INTEGER DEFAULT 0,
    rhythm_reps     INTEGER DEFAULT 0,
    date            DATE DEFAULT CURRENT_DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ai_plans_user_id ON ai_plans(user_id);
CREATE INDEX idx_ai_plans_date ON ai_plans(date DESC);

-- ============================================================
-- 4. ROW LEVEL SECURITY (RLS)
-- ============================================================

-- Enable RLS on all tables
ALTER TABLE patient_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE game_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_plans ENABLE ROW LEVEL SECURITY;

-- Policies: Users can only read/write their own data
-- (Using Supabase auth.uid() for production; for dev API we bypass via service role)

CREATE POLICY "Users can view own profile"
    ON patient_profiles FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY "Users can update own profile"
    ON patient_profiles FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY "Users can view own sessions"
    ON game_sessions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own sessions"
    ON game_sessions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view own plans"
    ON ai_plans FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own plans"
    ON ai_plans FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- 5. SEED DATA (Demo / Development)
-- ============================================================
INSERT INTO patient_profiles (id, username, password_hash, first_name, last_name, email, age, birth_date, severity_score, current_streak, avatar_url, doctor_name)
VALUES (
    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    'pramot',
    '$2b$12$LJ3dQd2GQk0Rv6K5F8p0aOQx5hVqkGzYf0xFjKWAq5X2L1Y3Z4A5B',  -- hashed 'password123'
    'Pramot',
    'Doe',
    'pramot@strokex.com',
    65,
    '1961-03-15',
    6,
    5,
    'https://api.dicebear.com/7.x/avataaars/png?seed=pramot',
    'Dr. Pop'
);

-- Sample game sessions
INSERT INTO game_sessions (user_id, mode_name, score, accuracy, reported_fatigue, xp_earned, star_rating, played_at) VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'Shield Defender', 2450, 0.92, 0.35, 2450, 4.5, '2026-04-20 15:30:00+07'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'Neuro Quest',    3100, 0.88, 0.42, 3100, 4.0, '2026-04-18 10:15:00+07'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'Rapid Reaction', 1800, 0.78, 0.55, 1800, 3.5, '2026-04-18 17:45:00+07'),
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'Potion Master',  2100, 0.85, 0.30, 2100, 4.0, '2026-04-17 09:00:00+07');

-- Sample AI plan
INSERT INTO ai_plans (user_id, potion_reps, shield_reps, rhythm_reps, date) VALUES
('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 15, 20, 10, CURRENT_DATE);
