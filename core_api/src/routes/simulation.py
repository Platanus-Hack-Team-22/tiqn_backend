import asyncio
import logging
import random
import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from ..core import process_text_chunk, end_session

router = APIRouter()
logger = logging.getLogger("simulation")


class SimulationRequest(BaseModel):
    duration_mode: Literal["short", "medium", "long"]
    dispatcher_id: str = "js7crtvfa7c5ctm6j09q8n16sh7vwrtk"  # Default fallback
    session_id: str | None = None


# Scenarios
SCENARIO_CHUNKS = [
    "Hola, necesito ayuda urgente. Mi padre se desmayó.",
    "No reacciona, creo que no está respirando bien.",
    "Estamos en Avenida Apoquindo 4500, Las Condes.",
    "Es un hombre de 74 años, tiene marcapasos.",
    "El departamento es el 304, torre B.",
    "Por favor apúrense, se está poniendo morado.",
]


async def run_simulation(session_id: str, dispatcher_id: str, duration_mode: str):
    logger.info(f"Starting simulation {session_id} with mode {duration_mode}")

    # Determine timing
    if duration_mode == "short":
        target_duration = 10
        chunks = SCENARIO_CHUNKS[:3]  # Fewer chunks for short
    elif duration_mode == "medium":
        target_duration = 30
        chunks = SCENARIO_CHUNKS
    else:  # long
        target_duration = 60
        # Repeat/extend chunks for long to fill time if needed, or just spread them out
        chunks = SCENARIO_CHUNKS + [
            "Sigue inconsciente.",
            "Estamos esperando en el lobby.",
        ]

    num_chunks = len(chunks)
    if num_chunks == 0:
        return

    # Calculate average delay
    # We want total time to be target_duration.
    # We have num_chunks intervals? No, num_chunks calls.
    # Delay happens *between* calls or *before* calls?
    # Let's say we space them out evenly.
    avg_delay = target_duration / num_chunks

    for i, chunk in enumerate(chunks):
        # Add randomness to delay: +/- 20%
        delay = avg_delay * random.uniform(0.8, 1.2)

        # Sleep before processing (except maybe first one? no, let's sleep to simulate real time flow)
        logger.info(
            f"Simulation {session_id}: Sleeping {delay:.2f}s before chunk {i+1}"
        )
        await asyncio.sleep(delay)

        try:
            logger.info(
                f"Simulation {session_id}: Processing chunk {i+1}/{num_chunks}: '{chunk}'"
            )
            await process_text_chunk(
                chunk_text=chunk,
                session_id=session_id,
                dispatcher_id=dispatcher_id,
                update_convex=True,
            )
        except Exception as e:
            logger.error(f"Simulation {session_id}: Error processing chunk: {e}")

    # End session
    logger.info(f"Simulation {session_id}: Ending session")
    try:
        end_session(
            session_id=session_id, save_to_convex=True, dispatcher_id=dispatcher_id
        )
    except Exception as e:
        logger.error(f"Simulation {session_id}: Error ending session: {e}")

    logger.info(f"Simulation {session_id}: Completed")


@router.post("/test/simulate-call")
async def start_simulation(req: SimulationRequest, background_tasks: BackgroundTasks):
    """
    Start a simulated call to test Convex data creation.

    Args:
        req: SimulationRequest with duration_mode (short, medium, long)
    """
    session_id = req.session_id or f"sim-{uuid.uuid4().hex[:8]}"

    background_tasks.add_task(
        run_simulation,
        session_id=session_id,
        dispatcher_id=req.dispatcher_id,
        duration_mode=req.duration_mode,
    )

    return {
        "status": "started",
        "session_id": session_id,
        "mode": req.duration_mode,
        "message": "Simulation started in background. Watch logs/Convex for updates.",
    }
