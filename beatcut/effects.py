"""Visual effects for beat-synced video transitions (MoviePy v2 compatible)."""

import numpy as np
from moviepy import VideoClip


def zoom_in_effect(
    clip: VideoClip,
    start_zoom: float = 1.0,
    end_zoom: float = 1.15,
) -> VideoClip:
    """Smooth zoom-in effect over the clip duration."""

    def make_frame(get_frame, t):
        progress = t / clip.duration if clip.duration > 0 else 0
        zoom = start_zoom + (end_zoom - start_zoom) * progress
        frame = get_frame(t)
        h, w = frame.shape[:2]
        new_h, new_w = int(h / zoom), int(w / zoom)
        y_start = (h - new_h) // 2
        x_start = (w - new_w) // 2
        cropped = frame[y_start:y_start + new_h, x_start:x_start + new_w]
        try:
            from scipy.ndimage import zoom as scipy_zoom
            factors = (h / new_h, w / new_w, 1.0)
            return (scipy_zoom(cropped.astype(np.float64), factors, order=1)
                    .clip(0, 255).astype(np.uint8))
        except Exception:
            return frame

    return clip.transform(make_frame)


def slide_transition(
    clip1: VideoClip,
    clip2: VideoClip,
    direction: str = "left",
    duration: float = 0.15,
) -> VideoClip:
    """Slide transition between two clips on a beat."""

    def make_frame(get_frame, t):
        progress = t / duration if duration > 0 else 1
        frame1 = clip1.get_frame(t)
        frame2 = clip2.get_frame(t)

        if progress >= 1:
            return frame2
        if progress <= 0:
            return frame1

        h, w = frame1.shape[:2]
        result = frame1.copy()

        if direction == "left":
            offset = int(w * (1 - progress))
            result[:, :w - offset] = frame1[:, offset:]
            result[:, w - offset:] = frame2[:, :offset]
        elif direction == "right":
            offset = int(w * progress)
            result[:, :offset] = frame2[:, w - offset:]
            result[:, offset:] = frame1[:, :w - offset]
        elif direction == "up":
            offset = int(h * progress)
            result[:offset, :] = frame2[h - offset:, :]
            result[offset:, :] = frame1[:h - offset, :]
        elif direction == "down":
            offset = int(h * (1 - progress))
            result[:h - offset, :] = frame1[offset:, :]
            result[h - offset:, :] = frame2[:offset, :]

        return result

    return clip1.transform(make_frame).with_duration(duration)


def flash_effect(
    clip: VideoClip,
    intensity: float = 0.3,
    duration: float = 0.08,
    color: tuple = (255, 255, 255),
) -> VideoClip:
    """Quick flash effect on beat for visual punch."""

    def make_frame(get_frame, t):
        frame = get_frame(t)
        flash = np.full_like(frame, color)
        return ((1 - intensity) * frame + intensity * flash).astype(np.uint8)

    return clip.transform(make_frame).with_duration(duration)


def shake_effect(
    clip: VideoClip,
    intensity: int = 8,
    duration: float = 0.1,
) -> VideoClip:
    """Camera shake effect on beat for impact."""
    rng = np.random.RandomState(42)

    def make_frame(get_frame, t):
        frame = get_frame(t)
        decay = 1 - (t / duration) if duration > 0 else 0
        dx = int(rng.randint(-intensity, intensity + 1) * decay)
        dy = int(rng.randint(-intensity, intensity + 1) * decay)

        h, w = frame.shape[:2]
        result = np.zeros_like(frame)
        x1, x2 = max(0, dx), min(w, w + dx)
        y1, y2 = max(0, dy), min(h, h + dy)
        fx1, fx2 = max(0, -dx), min(w, w - dx)
        fy1, fy2 = max(0, -dy), min(h, h - dy)

        result[y1:y2, x1:x2] = frame[fy1:fy2, fx1:fx2]
        return result

    return clip.transform(make_frame).with_duration(duration)


def beat_drop_zoom(
    clip: VideoClip,
    zoom_amount: float = 0.08,
    duration: float = 0.12,
) -> VideoClip:
    """Quick punch zoom on heavy beats (bass drops)."""

    def make_frame(get_frame, t):
        progress = t / duration if duration > 0 else 0
        pulse = np.sin(progress * np.pi)
        zoom = 1.0 + zoom_amount * pulse

        frame = get_frame(t)
        h, w = frame.shape[:2]
        new_h, new_w = int(h / zoom), int(w / zoom)
        y_start = (h - new_h) // 2
        x_start = (w - new_w) // 2

        try:
            from scipy.ndimage import zoom as scipy_zoom
            cropped = frame[y_start:y_start + new_h, x_start:x_start + new_w]
            factors = (h / new_h, w / new_w, 1.0)
            return (scipy_zoom(cropped.astype(np.float64), factors, order=1)
                    .clip(0, 255).astype(np.uint8))
        except Exception:
            return frame

    return clip.transform(make_frame).with_duration(duration)


EFFECT_PRESETS = {
    "smooth": {
        "transition": "slide",
        "beat_effect": None,
        "description": "平滑滑动转场，适合日常 vlog",
    },
    "energy": {
        "transition": "slide",
        "beat_effect": "flash",
        "description": "滑动 + 闪白，适合运动/舞蹈视频",
    },
    "heavy": {
        "transition": "cut",
        "beat_effect": "shake",
        "description": "硬切 + 震动，适合电音/嘻哈",
    },
    "cinematic": {
        "transition": "cut",
        "beat_effect": "zoom",
        "description": "硬切 + 缩放脉冲，适合旅行/风景",
    },
}


# ---- New extended effects ----

def glitch_shift(
    clip: VideoClip,
    intensity: int = 20,
    duration: float = 0.08,
) -> VideoClip:
    """Glitch effect: random horizontal slice displacement + black flicker."""
    rng = np.random.RandomState()

    def make_frame(get_frame, t):
        frame = get_frame(t)
        h, w = frame.shape[:2]
        # Flicker: sometimes return black
        if rng.random() < 0.3:
            return np.zeros_like(frame)
        # Random horizontal shift on a band
        band_h = h // 8
        y0 = rng.randint(0, max(1, h - band_h))
        dx = rng.randint(-intensity, intensity + 1)
        shifted = frame.copy()
        if dx > 0:
            shifted[y0:y0 + band_h, dx:w] = frame[y0:y0 + band_h, :w - dx]
            shifted[y0:y0 + band_h, :dx] = 0
        elif dx < 0:
            shifted[y0:y0 + band_h, :w + dx] = frame[y0:y0 + band_h, -dx:w]
            shifted[y0:y0 + band_h, w + dx:] = 0
        return shifted

    return clip.transform(make_frame).with_duration(duration)


def rgb_split(
    clip: VideoClip,
    offset: int = 8,
    duration: float = 0.1,
) -> VideoClip:
    """Retro RGB channel split effect on beat."""
    def make_frame(get_frame, t):
        frame = get_frame(t).astype(np.float64)
        h, w = frame.shape[:2]
        progress = t / duration if duration > 0 else 0
        shift = int(offset * (1 - progress * 2)) if progress < 0.5 else 0
        result = np.zeros_like(frame)
        # Red channel shifted left
        result[:, max(0, -shift):w + min(0, -shift), 0] = frame[:, max(0, shift):w + min(0, shift), 0]
        # Blue channel shifted right
        result[:, max(0, shift):w + min(0, shift), 2] = frame[:, max(0, -shift):w + min(0, -shift), 2]
        # Green stays
        result[:, :, 1] = frame[:, :, 1]
        return result.clip(0, 255).astype(np.uint8)

    return clip.transform(make_frame).with_duration(duration)


def soft_fade_blur(
    clip: VideoClip,
    blur_strength: int = 3,
    duration: float = 0.2,
) -> VideoClip:
    """Dreamy blur fade transition on beat."""
    def make_frame(get_frame, t):
        frame = get_frame(t)
        progress = t / duration if duration > 0 else 0
        if progress < 0.05 or progress > 0.95:
            return frame
        # Simple box blur via downscale/upscale
        h, w = frame.shape[:2]
        factor = max(1, int(blur_strength * (1 - abs(progress - 0.5) * 2)))
        small_h, small_w = max(1, h // factor), max(1, w // factor)
        try:
            from scipy.ndimage import zoom as scipy_zoom
            small = scipy_zoom(frame.astype(np.float64), (small_h / h, small_w / w, 1), order=1)
            result = scipy_zoom(small, (h / small_h, w / small_w, 1), order=1)
            return result.clip(0, 255).astype(np.uint8)
        except Exception:
            return frame

    return clip.transform(make_frame).with_duration(duration)


# Update presets
EFFECT_PRESETS["glitch"] = {
    "transition": "cut",
    "beat_effect": "glitch",
    "description": "故障撕裂 + 黑闪，适合赛博朋克/嘻哈",
}

EFFECT_PRESETS["retro"] = {
    "transition": "cut",
    "beat_effect": "rgb",
    "description": "RGB 色彩分离，适合复古/蒸汽波",
}

EFFECT_PRESETS["dreamy"] = {
    "transition": "fade",
    "beat_effect": "blur",
    "description": "柔焦模糊转场，适合慢节奏/氛围感",
}
