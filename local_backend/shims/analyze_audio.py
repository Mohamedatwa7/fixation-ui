"""Functional reimplementation of analyze_audio.py (original lives only on the
currently-unreachable Modal volume).

Reproduces the output contract consumed by diagnose_video_v5.run_diagnosis and
cognitive_kpis:
  - "signals": {
        "energy_timeline": [{"t": <sec>, "energy": <0-10>}],
        "first_3s_analysis": {"has_loud_moment", "starts_silent", "mean_energy"},
    }
  - "diagnostic_summary": str  (fed to the Claude diagnosis prompt)
  - "transcript": str (Whisper)

Energy is per-second RMS scaled 0-10 against the clip's 95th percentile, so
the pattern-interrupt (>3.0 jumps) and hook (mean/2.0) thresholds in
cognitive_kpis stay meaningful. Swap the original back in once the Modal
volume is recovered.
"""

import os
import subprocess
import tempfile

import numpy as np

_SILENCE_THRESHOLD = 0.5   # on the 0-10 energy scale
_LOUD_THRESHOLD = 7.0


def _extract_wav(video_path):
    wav = os.path.join(tempfile.gettempdir(), f"f1x8_audio_{os.getpid()}_{abs(hash(video_path)) % 99999}.wav")
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", wav],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not os.path.exists(wav) or os.path.getsize(wav) < 1024:
        return None
    return wav


def _no_audio_report(video_path, note):
    return {
        "video_path": video_path,
        "has_audio": False,
        "transcript": "",
        "language": None,
        "signals": {
            "energy_timeline": [],
            "first_3s_analysis": {"has_loud_moment": False, "starts_silent": True,
                                  "mean_energy": 0.0},
            "silence_seconds": 0,
            "mean_energy": 0.0,
            "peak_energy": 0.0,
        },
        "diagnostic_summary": f"(no usable audio track: {note})",
    }


def analyze_audio(video_path, whisper_model_size="base"):
    wav = _extract_wav(video_path)
    if wav is None:
        return _no_audio_report(video_path, "extraction failed or silent stream")

    try:
        import librosa
        y, sr = librosa.load(wav, sr=16000, mono=True)
        duration = len(y) / sr
        if duration < 0.25 or float(np.abs(y).max()) < 1e-4:
            return _no_audio_report(video_path, "empty or near-silent")

        # Per-second RMS, scaled 0-10 against the clip's own p95.
        seconds = int(np.ceil(duration))
        rms = []
        for s in range(seconds):
            seg = y[s * sr:(s + 1) * sr]
            rms.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
        ref = float(np.percentile(rms, 95)) or 1e-8
        energies = [min(10.0, 10.0 * v / ref) for v in rms]
        energy_timeline = [{"t": float(s), "energy": round(e, 2)}
                           for s, e in enumerate(energies)]

        first3 = energies[:3]
        first_3s = {
            "mean_energy": round(float(np.mean(first3)), 2) if first3 else 0.0,
            "starts_silent": bool(energies[0] < _SILENCE_THRESHOLD) if energies else True,
            "has_loud_moment": bool(any(e >= _LOUD_THRESHOLD for e in first3)),
        }
        silence_seconds = sum(1 for e in energies if e < _SILENCE_THRESHOLD)

        tempo_bpm = None
        try:
            tempo = librosa.feature.rhythm.tempo(y=y, sr=sr)
            tempo_bpm = round(float(np.atleast_1d(tempo)[0]), 1)
        except Exception:
            try:  # older librosa API
                tempo_bpm = round(float(np.atleast_1d(librosa.beat.tempo(y=y, sr=sr))[0]), 1)
            except Exception:
                pass

        transcript, language = "", None
        try:
            import torch
            import whisper
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = whisper.load_model(whisper_model_size, device=device)
            tr = model.transcribe(wav, fp16=(device == "cuda"))
            transcript = (tr.get("text") or "").strip()
            language = tr.get("language")
            del model
            if device == "cuda":
                torch.cuda.empty_cache()
        except Exception as e:
            print(f"[analyze_audio] whisper failed: {e}")

        lines = [
            f"Audio duration: {duration:.1f}s. Mean energy {np.mean(energies):.1f}/10, "
            f"peak {max(energies):.1f}/10 ({silence_seconds}s near-silent).",
            f"First 3s: mean energy {first_3s['mean_energy']}/10, "
            f"{'starts silent' if first_3s['starts_silent'] else 'sound from the first second'}, "
            f"{'contains a loud moment' if first_3s['has_loud_moment'] else 'no loud moment'}.",
        ]
        if tempo_bpm:
            lines.append(f"Estimated tempo: {tempo_bpm} BPM.")
        if transcript:
            lines.append(f"Transcript ({language or 'unknown'}): {transcript[:1200]}")
        else:
            lines.append("No speech transcribed (music/SFX only, or Whisper unavailable).")
        energy_str = " ".join(f"{p['t']:.0f}s={p['energy']:.1f}" for p in energy_timeline[:40])
        lines.append(f"Per-second energy (0-10): {energy_str}")

        return {
            "video_path": video_path,
            "has_audio": True,
            "duration_sec": round(duration, 2),
            "transcript": transcript,
            "language": language,
            "signals": {
                "energy_timeline": energy_timeline,
                "first_3s_analysis": first_3s,
                "silence_seconds": silence_seconds,
                "mean_energy": round(float(np.mean(energies)), 2),
                "peak_energy": round(float(max(energies)), 2),
                "tempo_bpm": tempo_bpm,
            },
            "diagnostic_summary": "\n".join(lines),
        }
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
