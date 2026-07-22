from pydantic import BaseModel, Field
from typing import Optional
from datetime import date

# Game Session Model (Request from App)
class GameSessionCreate(BaseModel):
    patient_id: str
    game_id: str
    level: int
    max_rom: Optional[float] = None
    success_rate: float = Field(..., ge=0.0, le=1.0)
    reaction_time_ms: Optional[float] = None
    pain_level: int = Field(..., ge=0, le=10)

# Daily Prescription Model (Response to App)
class DailyPrescription(BaseModel):
    date: date
    potion_reps: int
    potion_level: int
    potion_target_rom: float
    shield_reps: int
    shield_level: int
    rhythm_reps: int
    rhythm_level: int
    rapid_reps: int
    rapid_level: int
