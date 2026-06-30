"""
Beat detection module for video beat-sync editing.
Uses scipy + numpy for onset detection and tempo estimation.
No librosa needed — minimal, fast, and Python 3.13 compatible.
"""

import numpy as np
from scipy import signal
from scipy.io import wavfile
from dataclasses import dataclass
from typing import List, Optional
import subprocess
import os
import tempfile


@dataclass
class BeatInfo:
    beat_times: List[float]
    tempo: float
    onset_times: List[float]
    duration: float
    beat_intervals: List[float]


def _load_audio(audio_path: str) -> tuple:
    """Load audio file and return (samples, sample_rate) as mono float32.

    Handles mp3/m4a/etc via ffmpeg pipe, wav directly.
    """
    ext = os.path.splitext(audio_path)[1].lower()

    if ext in (".wav", ".wave"):
        sr, y = wavfile.read(audio_path)
        if y.ndim > 1:
            y = y.mean(axis=1)
        y = y.astype(np.float32) / (np.iinfo(y.dtype).max if np.issubdtype(y.dtype, np.integer) else 1.0)
        return y, sr

    # Use ffmpeg to decode to raw PCM
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-ac", "1", "-ar", "22050",
             "-sample_fmt", "s16", "-f", "wav", tmp_path],
            capture_output=True, check=True,
        )
        sr, y = wavfile.read(tmp_path)
        y = y.astype(np.float32) / 32768.0
        return y, sr
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _onset_strength(y: np.ndarray, sr: int, hop_length: int = 512) -> np.ndarray:
    """Compute onset strength envelope using spectral flux."""
    n_fft = 2048
    # Compute spectrogram
    f, t, Sxx = signal.spectrogram(
        y, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length,
        window="hann", mode="magnitude",
    )
    # Spectral flux: sum of positive differences across frequency
    flux = np.diff(Sxx, axis=1)
    flux = np.maximum(flux, 0).sum(axis=0)
    # Normalize
    if flux.max() > 0:
        flux /= flux.max()
    return flux, t


def _detect_onsets(
    onset_env: np.ndarray,
    times: np.ndarray,
    sr: int,
    hop_length: int = 512,
) -> List[float]:
    """Detect onsets from onset strength envelope using peak picking."""
    # Smooth the envelope
    win = signal.windows.hann(5)
    win /= win.sum()
    onset_smooth = signal.convolve(onset_env, win, mode="same")

    # Adaptive threshold: median + factor * std
    threshold = np.median(onset_smooth) + 0.5 * onset_smooth.std()

    # Find peaks above threshold
    peaks, props = signal.find_peaks(
        onset_smooth,
        height=threshold,
        distance=int(0.1 * sr / hop_length),  # min 100ms apart
    )

    onset_times = times[peaks].tolist() if len(peaks) > 0 else []
    return onset_times


def _estimate_tempo(
    onset_env: np.ndarray,
    sr: int,
    hop_length: int = 512,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
) -> float:
    """Estimate tempo from onset strength using autocorrelation."""
    # Autocorrelation of onset envelope
    ac = np.correlate(onset_env, onset_env, mode="full")
    ac = ac[len(ac) // 2:]  # take positive lags only
    ac = ac / (ac[0] if ac[0] > 0 else 1.0)

    # Convert lags to BPM (skip lag 0)
    lags = np.arange(len(ac))
    bpm_values = np.full_like(lags, np.inf, dtype=float)
    nonzero = lags > 0
    bpm_values[nonzero] = 60.0 * sr / (lags[nonzero] * hop_length)

    # Constrain to plausible BPM range
    mask = (bpm_values >= min_bpm) & (bpm_values <= max_bpm)
    if not mask.any():
        return 120.0  # default fallback

    valid_ac = ac.copy()
    valid_ac[~mask] = -1
    peak_idx = int(np.argmax(valid_ac))
    tempo = float(bpm_values[peak_idx])

    # Double-check: if we have a strong peak at half-tempo, prefer double
    half_mask = (bpm_values >= max(40, min_bpm / 2)) & (bpm_values <= min_bpm)
    if half_mask.any():
        half_idx = int(np.argmax(np.where(half_mask, ac, -1)))
        half_tempo = float(bpm_values[half_idx])
        double_tempo = half_tempo * 2
        if min_bpm <= double_tempo <= max_bpm:
            if ac[half_idx] > valid_ac[peak_idx] * 0.6:
                tempo = double_tempo

    return tempo


def detect_beats(
    audio_path: str,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
    tight: bool = True,
) -> BeatInfo:
    """Detect beat positions from an audio file.

    Args:
        audio_path: Path to audio file (mp3, wav, m4a, etc.)
        min_bpm: Minimum expected tempo
        max_bpm: Maximum expected tempo
        tight: If True, snaps beats to nearest onsets for tighter cuts.

    Returns:
        BeatInfo with beat times, tempo, and metadata.
    """
    hop_length = 512

    # Load audio
    y, sr = _load_audio(audio_path)
    duration = len(y) / sr

    # Resample to 22050 Hz if needed for efficiency
    target_sr = 22050
    if sr != target_sr:
        num_samples = int(len(y) * target_sr / sr)
        y = signal.resample(y, num_samples)
        sr = target_sr

    # Onset detection
    onset_env, times = _onset_strength(y, sr, hop_length)
    onset_times = _detect_onsets(onset_env, times, sr, hop_length)

    # Tempo estimation
    tempo = _estimate_tempo(onset_env, sr, hop_length, min_bpm, max_bpm)

    # Generate beat grid from tempo
    beat_interval = 60.0 / tempo
    beat_times = np.arange(0, duration, beat_interval).tolist()

    # Snap to nearest onsets if tight mode
    if tight and onset_times:
        snapped = []
        for bt in beat_times:
            if onset_times:
                nearest = min(onset_times, key=lambda ot: abs(ot - bt))
                if abs(nearest - bt) < beat_interval * 0.4:
                    snapped.append(nearest)
                else:
                    snapped.append(bt)
            else:
                snapped.append(bt)
        beat_times = snapped

    # Filter out-of-range beats
    beat_times = [t for t in beat_times if 0 <= t <= duration]

    beat_intervals = [
        beat_times[i] - beat_times[i - 1]
        for i in range(1, len(beat_times))
    ]

    return BeatInfo(
        beat_times=beat_times,
        tempo=tempo,
        onset_times=onset_times if onset_times else beat_times,
        duration=duration,
        beat_intervals=beat_intervals,
    )


def select_clip_windows(
    beat_times: List[float],
    video_duration: float,
    min_clip_duration: float = 0.3,
    max_clip_duration: float = 2.0,
    mode: str = "even",
) -> List[tuple]:
    """Map beat times to video clip windows."""
    n_beats = len(beat_times)
    if n_beats < 2:
        return [(0, min(video_duration, beat_times[-1] if beat_times else video_duration))]

    windows = []
    if mode == "even":
        available_video = video_duration
        for i in range(n_beats - 1):
            start_ratio = i / (n_beats - 1)
            end_ratio = (i + 1) / (n_beats - 1)
            start = start_ratio * available_video
            end = min(end_ratio * available_video, video_duration)
            windows.append((start, end))
    elif mode == "random":
        rng = np.random.RandomState(42)
        for i in range(n_beats - 1):
            clip_len = rng.uniform(min_clip_duration, max_clip_duration)
            max_start = max(0, video_duration - clip_len)
            start = rng.uniform(0, max_start)
            windows.append((start, start + clip_len))

    return windows


def detect_interesting_segments(
    video_path: str,
    n_segments: int = 10,
    segment_duration: float = 1.0,
    sample_rate: float = 1.0,
) -> List[tuple]:
    """Find visually interesting segments using frame differencing."""
    try:
        import cv2
    except ImportError:
        from moviepy import VideoFileClip
        with VideoFileClip(video_path) as clip:
            dur = clip.duration
        step = dur / n_segments
        return [(i * step, 0.5) for i in range(n_segments)]

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps if fps > 0 else 0
    if duration == 0:
        return [(0, 0.5) for _ in range(n_segments)]

    sample_interval = int(fps / sample_rate) if fps > 0 else 30
    motion_scores = []
    prev_frame = None
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % sample_interval == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, (160, 90))
            if prev_frame is not None:
                diff = cv2.absdiff(gray, prev_frame)
                score = float(np.mean(diff))
                motion_scores.append((frame_idx / fps, score))
            prev_frame = gray
        frame_idx += 1
    cap.release()

    if not motion_scores:
        step = duration / n_segments
        return [(i * step, 0.5) for i in range(n_segments)]

    motion_scores.sort(key=lambda x: x[1], reverse=True)
    selected = []
    for ts, score in motion_scores:
        start = max(0, ts - segment_duration / 2)
        end = min(duration, ts + segment_duration / 2)
        overlap = any(not (end <= s[0][0] or start >= s[0][1]) for s in selected)
        if not overlap:
            selected.append(((start, end), score, ts))
        if len(selected) >= n_segments:
            break

    return [(seg[0], seg[1]) for seg in selected]
