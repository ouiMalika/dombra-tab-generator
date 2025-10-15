# main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from tempfile import NamedTemporaryFile
import numpy as np, json, mido, os
from basic_pitch.inference import predict_and_save
from music21 import converter, instrument, note, stream
from basic_pitch.inference import predict_and_save, ICASSP_2022_MODEL_PATH
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dombra tuning (2 strings): string 1 = D4 (MIDI 62), string 2 = G3 (MIDI 55)
DOMBRA_TUNING = [62, 55]  # [string1_high, string2_low]
MAX_FRET = 20

def midi_single_melody(midi_path:str) -> list[dict]:
    """Return monophonic melody as list of {pitch, start, end} (seconds)."""
    s = converter.parse(midi_path)
    s.insert(0, instrument.Piano())
    flat = s.flat.notes.stream()
    # Take top voice by highest pitch at any time (simple heuristic)
    events = []
    for n in flat:
        if isinstance(n, note.Note):
            events.append({"pitch": n.pitch.midi, "start": float(n.offset), "end": float(n.offset + n.quarterLength)})
    # Sort & thin to one note at a time (keep highest when overlaps)
    events.sort(key=lambda x: (x["start"], -x["pitch"]))
    mono, last_end = [], -1.0
    for e in events:
        if not mono or e["start"] >= mono[-1]["end"] - 1e-3:
            mono.append(e)
        else:
            # Overlap: keep the higher pitch (already sorted)
            mono[-1] = e
    return mono

def map_to_dombra_tabs(melody:list[dict]) -> list[dict]:
    """Greedy mapper: choose a playable string+fret minimizing jumps."""
    tabs, last = [], None
    for ev in melody:
        best = None
        for si, open_midi in enumerate(DOMBRA_TUNING, start=1):
            fret = ev["pitch"] - open_midi
            if 0 <= fret <= MAX_FRET:
                cost = 0 if last is None else abs(fret - last["fret"]) + (0 if si == last["string"] else 1)
                cand = {"pitch": ev["pitch"], "start": ev["start"], "end": ev["end"], "string": si, "fret": int(fret), "cost": cost}
                if best is None or cand["cost"] < best["cost"]: best = cand
        # if out of range, try octave shift (±12) once
        if best is None:
            for shift in [-12, 12]:
                for si, open_midi in enumerate(DOMBRA_TUNING, start=1):
                    fret = ev["pitch"]+shift - open_midi
                    if 0 <= fret <= MAX_FRET:
                        cost = 5  # penalty for octave shift
                        cand = {"pitch": ev["pitch"]+shift, "start": ev["start"], "end": ev["end"], "string": si, "fret": int(fret), "cost": cost}
                        if best is None or cand["cost"] < best["cost"]: best = cand
        if best is None: continue
        last = best; best.pop("cost")
        tabs.append(best)
    return tabs

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    with NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[-1]) as tmp:
        tmp.write(await file.read())
        audio_path = tmp.name

    out_dir = audio_path + "_out"
    os.makedirs(out_dir, exist_ok=True)

    predict_and_save(
        [audio_path],
        out_dir,
        save_midi=True,
        save_notes=True,
        sonify_midi=False,
        save_model_outputs=False,
        model_or_model_path=ICASSP_2022_MODEL_PATH,
    )

    # ---  Read the generated MIDI file  ---
    midi_path = os.path.join(out_dir, os.path.basename(audio_path).split(".")[0] + "_basic_pitch.mid")

    # Parse the MIDI and extract notes
    s = converter.parse(midi_path)
    melody = []
    for n in s.flat.notes:
        if isinstance(n, note.Note):
            melody.append({
                "pitch": n.pitch.midi,
                "start": float(n.offset),
                "end": float(n.offset + n.quarterLength)
            })

    # --- Convert to simple dombra tab ---
    tabs = []
    DOMBRA_TUNING = [62, 55]  # string1=D4, string2=G3
    MAX_FRET = 20
    for ev in melody:
        best = None
        for si, open_midi in enumerate(DOMBRA_TUNING, start=1):
            fret = ev["pitch"] - open_midi
            if 0 <= fret <= MAX_FRET:
                best = {"string": si, "fret": fret}
                break
        if best:
            tabs.append(best)

    return JSONResponse({"status": "ok", "tabs": tabs})
