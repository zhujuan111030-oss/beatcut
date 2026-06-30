
"""Video editing engine for beat-synced video creation.

Orchestrates beat detection, clip selection, transition effects,
and final rendering into a beat-synchronized music video.
"""

import os
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Callable

import numpy as np
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    CompositeAudioClip,
    concatenate_videoclips,
    ColorClip,
    vfx,
)
from moviepy.video.fx import FadeIn, FadeOut

from .beat_detector import detect_beats, BeatInfo, select_clip_windows
from .effects import (
    zoom_in_effect,
    slide_transition,
    flash_effect,
    shake_effect,
    beat_drop_zoom,
    glitch_shift,
    rgb_split,
    soft_fade_blur,
    EFFECT_PRESETS,
)


def create_beat_video(
    video_path: str,
    audio_path: Optional[str] = None,
    output_path: str = "output_beatcut.mp4",
    preset: str = "energy",
    output_fps: int = 30,
    output_resolution: tuple = (1080, 1920),  # vertical video default
    max_duration: Optional[float] = None,
    progress_callback: Optional[Callable] = None,
    keep_original_audio: bool = False,
    trim_to_video: bool = False,
    transition_duration: float = 0.1,
) -> str:
    """Create a beat-synced music video.

    Main pipeline:
    1. Detect beats from audio
    2. Load and analyze video
    3. Map video clips to beat windows
    4. Apply transition effects on beats
    5. Composite and render

    Args:
        video_path: Path to input video file
        audio_path: Path to music file (uses video audio if None)
        output_path: Output video path
        preset: Effect preset name ("smooth", "energy", "heavy", "cinematic")
        output_fps: Output frame rate
        output_resolution: (width, height) tuple
        max_duration: Maximum output duration (trims audio)
        progress_callback: Optional callback(progress: float) for progress
        keep_original_audio: Keep video's original audio as background
        transition_duration: Duration of transition between clips

    Returns:
        Path to the output video file.
    """
    preset_config = EFFECT_PRESETS.get(preset, EFFECT_PRESETS["energy"])

    # ---- Step 1: Detect beats ----
    if progress_callback:
        progress_callback(0.05)

    audio_to_analyze = audio_path if audio_path else video_path
    beat_info = detect_beats(audio_to_analyze, tight=True)

    print(f"  Detected {len(beat_info.beat_times)} beats at {beat_info.tempo:.1f} BPM")
    print(f"  Audio duration: {beat_info.duration:.1f}s")

    # Trim to max_duration if specified
    if max_duration and beat_info.duration > max_duration:
        beat_info.beat_times = [t for t in beat_info.beat_times if t <= max_duration]
        beat_info.duration = max_duration

    n_beats = len(beat_info.beat_times)
    if n_beats < 4:
        raise ValueError(f"Not enough beats detected ({n_beats}). Try different music.")

    # ---- Step 2: Load video ----
    if progress_callback:
        progress_callback(0.10)

    video_clip = VideoFileClip(video_path)
    video_duration = video_clip.duration
    print(f"  Video duration: {video_duration:.1f}s")

    # ---- Step 3: Trim audio to video length if requested ----
    total_audio_raw = beat_info.beat_times[-1]

    if trim_to_video and video_duration < total_audio_raw:
        print(f"  ✂️  Trimming audio to video length: {video_duration:.1f}s")
        beat_info.beat_times = [t for t in beat_info.beat_times if t <= video_duration]
        beat_info.duration = video_duration
        total_audio_raw = beat_info.beat_times[-1]
        n_beats = len(beat_info.beat_times)
        if n_beats < 4:
            raise ValueError("Not enough beats after trimming. Try a longer video or shorter max_duration.")

    # ---- Step 4: Map video to beat windows ----
    if progress_callback:
        progress_callback(0.15)

    # Select clip windows based on beat count and video length
    # If video is shorter than audio, loop or distribute
    total_audio = beat_info.beat_times[-1]

    # Assign each beat interval a video segment
    clip_segments = []
    video_segments_needed = n_beats - 1  # segments between beats

    if video_duration >= total_audio:
        # Distribute video evenly across beats
        for i in range(video_segments_needed):
            ratio_start = i / video_segments_needed
            ratio_end = (i + 1) / video_segments_needed
            start = ratio_start * total_audio * (video_duration / total_audio)
            end = ratio_end * total_audio * (video_duration / total_audio)
            start = start % video_duration
            end = min(end % video_duration, video_duration)
            if start >= end:
                end = min(start + 0.5, video_duration)
            clip_segments.append((start, end))
    else:
        # Video is shorter: loop with variation
        loop_count = int(np.ceil(total_audio / video_duration))
        for i in range(video_segments_needed):
            ratio = i / video_segments_needed
            abs_time = ratio * total_audio
            loop_offset = (int(abs_time / video_duration) * 0.3) % video_duration
            start = (abs_time + loop_offset) % video_duration
            end = min(start + (total_audio / video_segments_needed), video_duration)
            if start >= end - 0.1:
                start = max(0, end - 0.5)
            clip_segments.append((start, end))

    # ---- Step 4: Create beat-synced clips ----
    if progress_callback:
        progress_callback(0.20)

    beat_clips = []
    directions = ["left", "right", "up", "down"]

    for i in range(video_segments_needed):
        beat_start = beat_info.beat_times[i]
        beat_end = beat_info.beat_times[i + 1]
        seg_start, seg_end = clip_segments[i]
        seg_duration = seg_end - seg_start

        if seg_duration <= 0:
            continue

        # Extract and resize clip segment
        try:
            sub_clip = video_clip.subclipped(seg_start, seg_end)
        except Exception:
            continue

        # Resize to target resolution
        sub_clip = sub_clip.resized(output_resolution)

        # Stretch or compress to fit beat interval
        beat_duration = beat_end - beat_start
        speed_factor = seg_duration / beat_duration
        if 0.5 <= speed_factor <= 2.0:
            sub_clip = sub_clip.with_speed_scaled(speed_factor)
        else:
            sub_clip = sub_clip.with_duration(beat_duration)

        # Skip continuous zoom (bottleneck) # for dynamic feel
        # sub_clip = zoom_in_effect(sub_clip, 1.0, 1.08)

        # Apply beat effect if configured
        if preset_config["beat_effect"] == "flash":
            flash = flash_effect(sub_clip, intensity=0.25, duration=0.06)
            sub_clip = concatenate_videoclips([flash, sub_clip.subclipped(0.06, beat_duration)])
            sub_clip = sub_clip.with_duration(beat_duration)
        elif preset_config["beat_effect"] == "shake":
            shake = shake_effect(sub_clip, intensity=6, duration=0.08)
            sub_clip = concatenate_videoclips([shake, sub_clip.subclipped(0.08, beat_duration)])
            sub_clip = sub_clip.with_duration(beat_duration)
        elif preset_config["beat_effect"] == "zoom":
            pulse = beat_drop_zoom(sub_clip, zoom_amount=0.06, duration=0.10)
            sub_clip = concatenate_videoclips([pulse, sub_clip.subclipped(0.10, beat_duration)])
            sub_clip = sub_clip.with_duration(beat_duration)
        elif preset_config["beat_effect"] == "glitch":
            glitch = glitch_shift(sub_clip, intensity=20, duration=0.08)
            sub_clip = concatenate_videoclips([glitch, sub_clip.subclipped(0.08, beat_duration)])
            sub_clip = sub_clip.with_duration(beat_duration)
        elif preset_config["beat_effect"] == "rgb":
            split = rgb_split(sub_clip, offset=10, duration=0.12)
            sub_clip = concatenate_videoclips([split, sub_clip.subclipped(0.12, beat_duration)])
            sub_clip = sub_clip.with_duration(beat_duration)
        elif preset_config["beat_effect"] == "blur":
            blur = soft_fade_blur(sub_clip, blur_strength=4, duration=0.20)
            sub_clip = concatenate_videoclips([blur, sub_clip.subclipped(0.20, beat_duration)])
            sub_clip = sub_clip.with_duration(beat_duration)

        # Position at beat time
        sub_clip = sub_clip.with_start(beat_start)
        beat_clips.append(sub_clip)

        if progress_callback and i % max(1, video_segments_needed // 10) == 0:
            progress_callback(0.20 + 0.40 * (i / video_segments_needed))

    if not beat_clips:
        raise ValueError("No valid clips generated. Check your video and audio files.")

    # ---- Step 5: Composite ----
    if progress_callback:
        progress_callback(0.65)

    # Black background
    bg = ColorClip(
        size=output_resolution,
        color=(0, 0, 0),
    ).with_duration(total_audio)

    composite = CompositeVideoClip([bg] + beat_clips, size=output_resolution)

    # ---- Step 6: Audio ----
    if progress_callback:
        progress_callback(0.75)

    # Load and trim audio to match video
    audio_clip = AudioFileClip(audio_to_analyze).subclipped(0, total_audio)

    if keep_original_audio:
        # Mix original video audio (quiet) with music
        try:
            video_audio = video_clip.audio
            if video_audio is not None:
                video_audio = video_audio.subclipped(0, min(total_audio, video_duration))
                video_audio = video_audio.with_volume_scaled(0.15)
                mixed = CompositeAudioClip([audio_clip.with_volume_scaled(0.85), video_audio])
                composite = composite.with_audio(mixed)
            else:
                composite = composite.with_audio(audio_clip)
        except Exception:
            composite = composite.with_audio(audio_clip)
    else:
        composite = composite.with_audio(audio_clip)

    # ---- Step 7: Render ----
    if progress_callback:
        progress_callback(0.80)

    print(f"  Rendering to {output_path}...")
    composite.write_videofile(
        output_path,
        fps=output_fps,
        codec="libx264",
        audio_codec="aac",
        preset="ultrafast",
        threads=0,
        logger=None,
    )

    if progress_callback:
        progress_callback(1.0)

    # Clean up
    video_clip.close()
    composite.close()

    print(f"  Done! Output: {output_path}")
    return output_path


def batch_create(
    video_path: str,
    audio_paths: List[str],
    output_dir: str = "output",
    preset: str = "energy",
    output_resolution: tuple = (1080, 1920),
) -> List[str]:
    """Create multiple beat videos for different songs.

    Args:
        video_path: Single video to use for all outputs
        audio_paths: List of music files
        output_dir: Output directory
        preset: Effect preset
        output_resolution: Output resolution

    Returns:
        List of output paths
    """
    os.makedirs(output_dir, exist_ok=True)
    outputs = []

    for i, audio_path in enumerate(audio_paths):
        song_name = Path(audio_path).stem
        output_path = os.path.join(output_dir, f"beatcut_{i:02d}_{song_name}.mp4")
        print(f"\n[{i+1}/{len(audio_paths)}] {song_name}")

        result = create_beat_video(
            video_path=video_path,
            audio_path=audio_path,
            output_path=output_path,
            preset=preset,
            output_resolution=output_resolution,
        )
        outputs.append(result)

    return outputs
