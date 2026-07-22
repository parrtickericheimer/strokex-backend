from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from supabase import create_client, Client
from models import GameSessionCreate, DailyPrescription
from ai_engine import calculate_next_prescription
from datetime import date

load_dotenv()

app = FastAPI(title="StrokeX AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "your-anon-key")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "Welcome to StrokeX Backend"}

@app.post("/sessions/")
def create_game_session(session: GameSessionCreate):
    """ Record a patient's game session results """
    data = session.model_dump()
    response = supabase.table("game_sessions").insert(data).execute()
    return {"status": "success", "data": response.data}

@app.post("/generate-plan/{patient_id}")
def generate_daily_plan(patient_id: str):
    """ Fetch past 3 days of sessions and run NSGA-II to prescribe new plan """
    # Fetch recent sessions from Supabase
    res = supabase.table("game_sessions").select("*").eq("patient_id", patient_id).order("created_at", desc=True).limit(20).execute()
    sessions = res.data

    # Group sessions by game
    game_stats = {}
    for s in sessions:
        game_id = s['game_id']
        if game_id not in game_stats:
            game_stats[game_id] = {'success_sum': 0, 'pain_sum': 0, 'count': 0, 'current_level': s['level']}
        game_stats[game_id]['success_sum'] += s['success_rate']
        game_stats[game_id]['pain_sum'] += s['pain_level']
        game_stats[game_id]['count'] += 1

    # Calculate averages
    past_data = {}
    for g, stats in game_stats.items():
        past_data[g] = {
            'avg_success': stats['success_sum'] / stats['count'],
            'avg_pain': stats['pain_sum'] / stats['count'],
            'current_level': stats['current_level']
        }

    # If no data, use defaults
    if not past_data:
        past_data = {
            "potion": {"avg_success": 0.8, "avg_pain": 2, "current_level": 1},
            "shield": {"avg_success": 0.8, "avg_pain": 2, "current_level": 1},
            "rhythm": {"avg_success": 0.8, "avg_pain": 2, "current_level": 1},
            "rapid": {"avg_success": 0.8, "avg_pain": 2, "current_level": 1},
        }

    # Run AI NSGA-II
    plan = calculate_next_prescription(past_data)

    # Ensure all games have a plan (if user hasn't played one yet, give baseline)
    for g in ["potion", "shield", "rhythm", "rapid"]:
        if g not in plan:
            plan[g] = {"reps": 15, "level": 1, "target_rom": 1.0}

    # Save to DB
    new_prescription = {
        "patient_id": patient_id,
        "date": str(date.today()),
        "potion_reps": plan["potion"]["reps"],
        "potion_level": plan["potion"]["level"],
        "potion_target_rom": plan["potion"].get("target_rom", 1.0),
        "shield_reps": plan["shield"]["reps"],
        "shield_level": plan["shield"]["level"],
        "rhythm_reps": plan["rhythm"]["reps"],
        "rhythm_level": plan["rhythm"]["level"],
        "rapid_reps": plan["rapid"]["reps"],
        "rapid_level": plan["rapid"]["level"],
    }

    try:
        supabase.table("daily_prescriptions").insert(new_prescription).execute()
    except Exception as e:
        # Ignore unique constraint error if plan already generated today, or update it
        pass

    return {"status": "success", "plan": plan}
