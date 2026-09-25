"""
Audio Analysis Module
=====================

Analyzes the audio track of a video to extract diagnostic signals:
- Transcript with timestamps (Whisper)
- Audio energy curve over time (librosa)
- Silence detection (gaps in audio)
- Voice / music / silence classification per second
- First-3-second "audio hook" analysis

These signals get fed alongside the visual perception into Claude's
diagnostic synthesis, so the diagnosis can reason about audio-visual
sync, silent openings, music drops vs. visual events, etc.

USAGE:
    from analyze_audio import analyze_audio
    audio_report = analyze_audio("/content/samsung_video.mp4")
    # audio_report is a dict with transcript, energy curve, silence
    # segments, and a hook analysis summary
"""

import os
import json
import tempfile
import subprocess
import numpy as np


# ---------------------------------------------------------------------------
# Extract audio from video
# ---------------------------------------------------------------------------

def extract_audio_track(video_path, sample_rate=16000):
    """
    Extracts mono 16kHz wav from a video file using ffmpeg. 16kHz is the
    native rate Whisper expects. Returns path to a temporary wav file.
    """
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn",                          # no video
        "-acodec", "pcm_s16le",         # 16-bit PCM
        "-ac", "1",                     # mono
        "-ar", str(sample_rate),        # sample rate
        "-loglevel", "error",
        tmp_wav,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    return tmp_wav


# ---------------------------------------------------------------------------
# Whisper transcription
# ---------------------------------------------------------------------------

def transcribe_audio(audio_path, model_size="base"):
    """
    Runs Whisper transcription. Returns segments with timestamps and full text.

    Model sizes: tiny (39M, fast), base (74M, balanced), small (244M),
    medium (769M), large (1550M). 'base' is a good default for short videos.
    """
    import whisper
    print(f"  Loading Whisper {model_size}...")
    model = whisper.load_model(model_size)
    print("  Transcribing...")
    result = model.transcribe(audio_path, verbose=False)
    segments = [
        {
            "start": round(seg["start"], 2),
            "end": round(seg["end"], 2),
            "text": seg["text"].strip(),
        }
        for seg in result.get("segments", [])
    ]
    return {
        "language": result.get("language", "unknown"),
        "full_text": result.get("text", "").strip(),
        "segments": segments,
    }


# ---------------------------------------------------------------------------
# Audio signal analysis (librosa)
# ---------------------------------------------------------------------------

def analyze_audio_signals(audio_path):
    """
    Extracts:
      - RMS energy curve (loudness over time)
      - Silence segments
      - First-3-second audio characteristics
      - Overall stats
    """
    import librosa
    y, sr = librosa.load(audio_path, sr=16000)
    duration = len(y) / sr

    # Frame-level RMS energy (loudness) sampled every ~50ms
    hop_length = 800  # ~50ms at 16kHz
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)

    # Normalize RMS to 0-10 for easier interpretation
    rms_max = float(rms.max()) if rms.max() > 0 else 1.0
    rms_norm = 10.0 * rms / rms_max

    # Sample the curve every 0.5s for a compact timeline
    energy_timeline = []
    target_times = np.arange(0, duration, 0.5)
    for t in target_times:
        idx = np.argmin(np.abs(times - t))
        energy_timeline.append({
            "t": round(float(t), 2),
            "energy": round(float(rms_norm[idx]), 2),
        })

    # Silence detection: RMS below threshold for at least 0.3s
    silence_threshold = 0.05 * rms_max  # 5% of peak
    is_silent = rms < silence_threshold
    silence_segments = []
    current_start = None
    for i, silent in enumerate(is_silent):
        t = times[i]
        if silent and current_start is None:
            current_start = t
        elif not silent and current_start is not None:
            if t - current_start >= 0.3:  # only count silences >= 0.3s
                silence_segments.append({
                    "start": round(float(current_start), 2),
                    "end": round(float(t), 2),
                    "duration": round(float(t - current_start), 2),
                })
            current_start = None
    if current_start is not None and duration - current_start >= 0.3:
        silence_segments.append({
            "start": round(float(current_start), 2),
            "end": round(float(duration), 2),
            "duration": round(float(duration - current_start), 2),
        })

    # First 3 seconds analysis
    first_3s_mask = times <= 3.0
    first_3s_rms = rms_norm[first_3s_mask] if first_3s_mask.any() else np.array([0.0])
    first_3s_analysis = {
        "mean_energy": round(float(first_3s_rms.mean()), 2),
        "max_energy": round(float(first_3s_rms.max()), 2),
        "min_energy": round(float(first_3s_rms.min()), 2),
        "starts_silent": bool(first_3s_rms[0] < 1.0) if len(first_3s_rms) > 0 else None,
        "has_loud_moment": bool(first_3s_rms.max() > 6.0),
    }

    # Spectral centroid mean — rough proxy for "speech-like" (lower) vs
    # "music-like" (higher) content. Not perfect, but useful signal.
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
    centroid_mean = float(centroid.mean())

    return {
        "duration_sec": round(float(duration), 2),
        "energy_timeline": energy_timeline,
        "silence_segments": silence_segments,
        "total_silence_sec": round(
            float(sum(s["duration"] for s in silence_segments)), 2
        ),
        "first_3s_analysis": first_3s_analysis,
        "spectral_centroid_mean_hz": round(centroid_mean, 0),
        "audio_character_hint": (
            "speech-like" if centroid_mean < 1500
            else "music-like" if centroid_mean > 2500
            else "mixed"
        ),
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_audio(video_path, whisper_model_size="base"):
    """
    Full audio analysis. Returns a dict with transcript + signal analysis.
    Cleans up the temp wav file when done.
    """
    print(f"Extracting audio from {video_path}...")
    audio_path = extract_audio_track(video_path)
    try:
        signals = analyze_audio_signals(audio_path)
        transcript = transcribe_audio(audio_path, model_size=whisper_model_size)

        # Build first-3s narrative for the diagnostic
        first_3s = signals["first_3s_analysis"]
        first_3s_words = [
            seg["text"] for seg in transcript["segments"]
            if seg["start"] < 3.0
        ]
        signals["first_3s_analysis"]["spoken_in_first_3s"] = (
            " ".join(first_3s_words).strip() or "(no speech detected)"
        )

        return {
            "transcript": transcript,
            "signals": signals,
            "diagnostic_summary": _summarize_for_diagnosis(signals, transcript),
        }
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def _summarize_for_diagnosis(signals, transcript):
    """
    Produces a compact text summary of the audio findings for inclusion in
    Claude's diagnostic prompt. Optimized for signal density, not prose.
    """
    lines = []
    lines.append(f"Duration: {signals['duration_sec']}s")
    lines.append(f"Audio character: {signals['audio_character_hint']} "
                 f"(spectral centroid {signals['spectral_centroid_mean_hz']:.0f} Hz)")
    lines.append(f"Language detected: {transcript['language']}")
    lines.append(f"Total silence: {signals['total_silence_sec']}s "
                 f"across {len(signals['silence_segments'])} segments")

    first_3s = signals["first_3s_analysis"]
    lines.append("\nFirst 3 seconds:")
    lines.append(f"  - Mean energy: {first_3s['mean_energy']}/10 "
                 f"(max {first_3s['max_energy']}, min {first_3s['min_energy']})")
    lines.append(f"  - Starts silent: {first_3s['starts_silent']}")
    lines.append(f"  - Has loud moment: {first_3s['has_loud_moment']}")
    lines.append(f"  - Speech in first 3s: \"{first_3s['spoken_in_first_3s']}\"")

    if signals["silence_segments"]:
        lines.append("\nSilence segments:")
        for s in signals["silence_segments"][:5]:
            lines.append(f"  - {s['start']}s to {s['end']}s ({s['duration']}s)")

    lines.append(f"\nFull transcript: \"{transcript['full_text']}\"")

    # Compact energy timeline (every 0.5s, first 30 points to keep prompt small)
    if signals["energy_timeline"]:
        lines.append("\nAudio energy timeline (0-10 scale, every 0.5s):")
        timeline_str = " ".join(
            f"{p['t']}s={p['energy']:.1f}"
            for p in signals["energy_timeline"][:30]
        )
        lines.append("  " + timeline_str)
        if len(signals["energy_timeline"]) > 30:
            lines.append(f"  ... ({len(signals['energy_timeline'])-30} more points)")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-path", required=True)
    parser.add_argument("--whisper-size", default="base",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--output", default="audio_report.json")
    args = parser.parse_args()

    report = analyze_audio(args.video_path, whisper_model_size=args.whisper_size)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n✅ Saved audio report to {args.output}")
    print("\n=== SUMMARY ===")
    print(report["diagnostic_summary"])
