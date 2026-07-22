-- Supabase SQL Schema for StrokeX

-- 1. Table: patients
CREATE TABLE IF NOT EXISTS public.patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    baseline_rom JSONB, -- e.g. {"wrist_flexion": 30, "finger_abduction_ratio": 0.5}
    current_level INT DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 2. Table: game_sessions
CREATE TABLE IF NOT EXISTS public.game_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES public.patients(id) ON DELETE CASCADE,
    game_id TEXT NOT NULL, -- "potion", "shield", "rhythm", "rapid"
    level INT NOT NULL,
    max_rom FLOAT,
    success_rate FLOAT NOT NULL, -- 0.0 to 1.0 (or percentage)
    reaction_time_ms FLOAT,
    pain_level INT CHECK (pain_level >= 0 AND pain_level <= 10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 3. Table: daily_prescriptions
CREATE TABLE IF NOT EXISTS public.daily_prescriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES public.patients(id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    potion_reps INT,
    potion_level INT,
    potion_target_rom FLOAT,
    shield_reps INT,
    shield_level INT,
    rhythm_reps INT,
    rhythm_level INT,
    rapid_reps INT,
    rapid_level INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    UNIQUE(patient_id, date)
);

-- Set up Row Level Security (RLS)
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.game_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_prescriptions ENABLE ROW LEVEL SECURITY;

-- Policies for Authenticated Users (assuming Supabase Auth)
-- Allow users to read their own data
CREATE POLICY "Users can view own patient data" ON public.patients FOR SELECT USING (auth.uid() = id);
CREATE POLICY "Users can update own patient data" ON public.patients FOR UPDATE USING (auth.uid() = id);

CREATE POLICY "Users can view own game sessions" ON public.game_sessions FOR SELECT USING (auth.uid() = patient_id);
CREATE POLICY "Users can insert own game sessions" ON public.game_sessions FOR INSERT WITH CHECK (auth.uid() = patient_id);

CREATE POLICY "Users can view own prescriptions" ON public.daily_prescriptions FOR SELECT USING (auth.uid() = patient_id);
