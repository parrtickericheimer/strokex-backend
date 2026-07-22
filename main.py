from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from supabase import create_client, Client
from models import GameSessionCreate, DailyPrescription
from ai_engine import calculate_next_prescription
from datetime import date
from pydantic import BaseModel
from fastapi.responses import HTMLResponse

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

@app.get("/camera", response_class=HTMLResponse)
def get_camera_html():
    return """
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
      <style>
        body { margin: 0; padding: 0; overflow: hidden; background-color: #000; }
        #output_canvas { width: 100vw; height: 100vh; object-fit: cover; transform: scaleX(-1); }
        #input_video { display: none; }
      </style>
      <script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js" crossorigin="anonymous"></script>
      <script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js" crossorigin="anonymous"></script>
      <script src="https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js" crossorigin="anonymous"></script>
    </head>
    <body>
      <video id="input_video" autoplay playsinline></video>
      <canvas id="output_canvas"></canvas>
      <script>
        const videoElement = document.getElementById('input_video');
        const canvasElement = document.getElementById('output_canvas');
        const canvasCtx = canvasElement.getContext('2d');

        function sendToApp(data) {
          window.ReactNativeWebView.postMessage(JSON.stringify(data));
        }

        // We determine mode via URL params: ?mode=hands or ?mode=pose
        const urlParams = new URLSearchParams(window.location.search);
        const mode = urlParams.get('mode') || 'hands';

        if (mode === 'hands') {
            const hands = new Hands({locateFile: (file) => {
              return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
            }});
            hands.setOptions({
              maxNumHands: 2,
              modelComplexity: 1,
              minDetectionConfidence: 0.5,
              minTrackingConfidence: 0.5
            });

            hands.onResults((results) => {
              canvasElement.width = videoElement.videoWidth;
              canvasElement.height = videoElement.videoHeight;
              canvasCtx.save();
              canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
              canvasCtx.drawImage(results.image, 0, 0, canvasElement.width, canvasElement.height);
              canvasCtx.restore();
              
              if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
                sendToApp({ type: 'hands', landmarks: results.multiHandLandmarks });
              } else {
                sendToApp({ type: 'hands', landmarks: [] });
              }
            });

            const camera = new Camera(videoElement, {
              onFrame: async () => {
                await hands.send({image: videoElement});
              },
              width: 640,
              height: 480,
              facingMode: "user"
            });
            camera.start();
        } else {
            const pose = new Pose({locateFile: (file) => {
              return `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`;
            }});
            pose.setOptions({
              modelComplexity: 1,
              smoothLandmarks: true,
              minDetectionConfidence: 0.5,
              minTrackingConfidence: 0.5
            });

            pose.onResults((results) => {
              canvasElement.width = videoElement.videoWidth;
              canvasElement.height = videoElement.videoHeight;
              canvasCtx.save();
              canvasCtx.clearRect(0, 0, canvasElement.width, canvasElement.height);
              canvasCtx.drawImage(results.image, 0, 0, canvasElement.width, canvasElement.height);
              canvasCtx.restore();
              
              if (results.poseLandmarks) {
                sendToApp({ type: 'pose', landmarks: results.poseLandmarks });
              } else {
                sendToApp({ type: 'pose', landmarks: null });
              }
            });

            const camera = new Camera(videoElement, {
              onFrame: async () => {
                await pose.send({image: videoElement});
              },
              width: 640,
              height: 480,
              facingMode: "user"
            });
            camera.start();
        }

        window.onload = () => {
           sendToApp({ type: 'ready' });
        };
      </script>
    </body>
    </html>
    """

@app.post("/sessions/")
def create_game_session(session: GameSessionCreate):
    """ Record a patient's game session results """
    data = session.model_dump()
    response = supabase.table("game_sessions").insert(data).execute()
    return {"status": "success", "data": response.data}

@app.get("/sessions/recent/{patient_id}")
def get_recent_sessions(patient_id: str):
    """ Fetch the patient's recent game sessions """
    res = supabase.table("game_sessions").select("*").eq("patient_id", patient_id).order("created_at", desc=True).limit(10).execute()
    return {"status": "success", "data": res.data}

@app.get("/sessions/stats/{patient_id}")
def get_session_stats(patient_id: str):
    """ Calculate aggregated stats for the patient """
    res = supabase.table("game_sessions").select("*").eq("patient_id", patient_id).order("created_at", desc=True).limit(20).execute()
    sessions = res.data
    if not sessions:
        return {"status": "success", "data": {"rom": 0, "accuracy": 0, "fatigue": 0}}
    
    avg_score = sum(s.get("performance_score", 0) for s in sessions) / len(sessions)
    # Estimate stats based on performance score for the MVP demo
    rom = min(0.95, avg_score / 1000.0) 
    accuracy = min(0.98, avg_score / 800.0)
    fatigue = max(0.1, 1.0 - (avg_score / 1200.0))
    
    return {"status": "success", "data": {"rom": rom, "accuracy": accuracy, "fatigue": fatigue}}

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
