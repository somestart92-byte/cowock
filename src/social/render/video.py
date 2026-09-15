"""Short-form video rendering with ffmpeg.

The pipeline is deliberately simple and dependency-light:

1. Each scene is rendered to a PNG slide by :mod:`.image`.
2. Optional per-scene voiceover is synthesized and concatenated; scene lengths
   stretch to match the narration so text and voice stay in sync.
3. ffmpeg turns the stills into an MP4 — subtle Ken Burns zoom per scene,
   crossfades between scenes, optional music bed ducked under the voice.

ffmpeg is found on PATH, or via the bundled binary from ``imageio-ffmpeg``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from ..generate import Scene, VideoScript
from . import tts
from .image import SIZES, render_slide, save_slides

PRESET_SIZES = {
    "vertical": SIZES["vertical"],
    "square": SIZES["square"],
    "landscape": SIZES["landscape"],
}


class VideoError(RuntimeError):
    pass


def ffmpeg_path() -> str:
    """Return a usable ffmpeg binary path or raise."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - environment dependent
        raise VideoError(
            "ffmpeg not found. Install ffmpeg, or `pip install imageio-ffmpeg`."
        ) from exc


def ffprobe_duration(path: str | Path) -> float:
    """Duration of a media file in seconds (0.0 if it cannot be read)."""
    probe = shutil.which("ffprobe")
    if probe:
        proc = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True,
        )
        if proc.returncode == 0:
            try:
                return float(json.loads(proc.stdout)["format"]["duration"])
            except (KeyError, ValueError):
                pass
    # Fall back to ffmpeg's own report — it always ships with the binary above.
    proc = subprocess.run([ffmpeg_path(), "-i", str(path)], capture_output=True, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            stamp = line.split("Duration:")[1].split(",")[0].strip()
            try:
                h, m, s = stamp.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except ValueError:
                return 0.0
    return 0.0


@dataclass
class VideoSpec:
    """Render settings for one video."""

    preset: str = "vertical"
    fps: int = 30
    seconds_per_scene: float = 3.4
    transition: float = 0.4
    theme: str = "midnight"
    footer: str = ""
    kicker: str = ""
    voiceover: str = "none"
    voice: str = ""
    music: str = ""
    music_gain: float = -20.0
    zoom: bool = True
    backgrounds: list[str] = field(default_factory=list)

    @property
    def size(self) -> tuple[int, int]:
        return PRESET_SIZES.get(self.preset, PRESET_SIZES["vertical"])

    @classmethod
    def from_config(cls, video_cfg: dict, **overrides) -> "VideoSpec":
        known = {f for f in cls.__dataclass_fields__}
        data = {k: v for k, v in (video_cfg or {}).items() if k in known}
        data.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**data)


@dataclass
class RenderedVideo:
    path: Path
    duration: float
    scenes: int
    slides: list[Path]
    voiceover: bool
    width: int
    height: int

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "duration": round(self.duration, 2),
            "scenes": self.scenes,
            "slides": [str(p) for p in self.slides],
            "voiceover": self.voiceover,
            "resolution": f"{self.width}x{self.height}",
        }


def _scene_audio(
    scenes: Sequence[Scene], spec: VideoSpec, workdir: Path
) -> tuple[list[Path | None], list[float]]:
    """Synthesize narration per scene and return (clips, durations)."""
    clips: list[Path | None] = []
    durations: list[float] = []
    for i, scene in enumerate(scenes):
        clip = None
        if spec.voiceover != "none" and scene.voiceover.strip():
            clip = tts.synthesize(
                scene.voiceover,
                workdir / f"vo-{i:02d}.wav",
                provider=spec.voiceover,
                voice=spec.voice,
            )
        clips.append(clip)
        if clip is not None:
            # Leave a short breath after the narration.
            durations.append(max(scene.seconds or 0, ffprobe_duration(clip) + 0.6, 1.5))
        else:
            durations.append(scene.seconds or spec.seconds_per_scene)
    return clips, durations


def _concat_audio(clips: list[Path | None], durations: list[float], workdir: Path) -> Path | None:
    """Join narration clips, padding each to its scene length."""
    if not any(clips):
        return None
    ff = ffmpeg_path()
    padded: list[Path] = []
    for i, (clip, dur) in enumerate(zip(clips, durations)):
        out = workdir / f"pad-{i:02d}.wav"
        if clip is None:
            cmd = [ff, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                   "-t", f"{dur:.3f}", str(out)]
        else:
            cmd = [ff, "-y", "-i", str(clip), "-af",
                   f"apad=whole_dur={dur:.3f},aresample=44100", "-ac", "2",
                   "-t", f"{dur:.3f}", str(out)]
        _run(cmd)
        padded.append(out)

    listing = workdir / "audio.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in padded), encoding="utf-8")
    joined = workdir / "voice.wav"
    _run([ff, "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(joined)],
         cwd=workdir)
    return joined


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-12:])
        raise VideoError(f"ffmpeg failed ({' '.join(cmd[:3])} …):\n{tail}")


def _video_filter(
    slides: list[Path], durations: list[float], spec: VideoSpec
) -> tuple[list[str], str]:
    """Build the ffmpeg filter_complex for zoom + crossfades."""
    w, h = spec.size
    fps = spec.fps
    parts: list[str] = []
    for i, dur in enumerate(durations):
        frames = max(int(dur * fps), 1)
        if spec.zoom:
            # zoompan works on an upscaled still so the slow push stays sharp.
            zoom_dir = 1 if i % 2 == 0 else -1
            if zoom_dir > 0:
                zexpr = f"min(zoom+0.0009,1.12)"
            else:
                zexpr = f"if(lte(zoom,1.0),1.12,max(1.001,zoom-0.0009))"
            parts.append(
                f"[{i}:v]scale={w*2}:{h*2},"
                f"zoompan=z='{zexpr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":s={w}x{h}:fps={fps},setsar=1[v{i}]"
            )
        else:
            parts.append(f"[{i}:v]scale={w}:{h},fps={fps},setsar=1[v{i}]")

    if len(durations) == 1:
        return parts, "v0"

    xfade = max(0.0, min(spec.transition, min(durations) / 2))
    if xfade <= 0:
        parts.append("".join(f"[v{i}]" for i in range(len(durations)))
                     + f"concat=n={len(durations)}:v=1:a=0[vout]")
        return parts, "vout"

    current = "v0"
    offset = durations[0] - xfade
    for i in range(1, len(durations)):
        label = f"x{i}"
        parts.append(
            f"[{current}][v{i}]xfade=transition=fade:duration={xfade:.3f}"
            f":offset={offset:.3f}[{label}]"
        )
        current = label
        offset += durations[i] - xfade
    return parts, current


def render_video(
    script: VideoScript,
    out_path: str | Path,
    spec: VideoSpec | None = None,
    keep_slides_in: str | Path | None = None,
) -> RenderedVideo:
    """Render ``script`` to an MP4 at ``out_path``."""
    spec = spec or VideoSpec()
    scenes = list(script.scenes)
    if not scenes:
        raise VideoError("script has no scenes")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_path()

    with tempfile.TemporaryDirectory(prefix="cowock-video-") as tmp:
        workdir = Path(tmp)
        slide_dir = Path(keep_slides_in) if keep_slides_in else workdir / "slides"
        images = [
            render_slide(
                scene.text,
                theme=spec.theme,
                size=spec.size,
                emphasis=scene.emphasis,
                kicker=spec.kicker if i == 0 else "",
                footer=spec.footer,
                index=i,
                total=len(scenes),
                background=spec.backgrounds[i] if i < len(spec.backgrounds) else None,
            )
            for i, scene in enumerate(scenes)
        ]
        slides = save_slides(images, slide_dir)

        clips, durations = _scene_audio(scenes, spec, workdir)
        voice = _concat_audio(clips, durations, workdir)

        cmd = [ff, "-y"]
        for slide, dur in zip(slides, durations):
            cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(slide)]

        filters, vlabel = _video_filter(slides, durations, spec)
        total = sum(durations) - max(0.0, min(spec.transition, min(durations) / 2)) * (
            len(durations) - 1
        )

        audio_inputs = 0
        music_path = Path(spec.music) if spec.music else None
        if voice is not None:
            cmd += ["-i", str(voice)]
            audio_inputs += 1
        if music_path and music_path.exists():
            cmd += ["-stream_loop", "-1", "-i", str(music_path)]
            audio_inputs += 1

        base = len(slides)
        if audio_inputs == 2:
            filters.append(
                f"[{base}:a]aformat=sample_rates=44100:channel_layouts=stereo[voa];"
                f"[{base+1}:a]volume={spec.music_gain}dB,aformat=sample_rates=44100:"
                f"channel_layouts=stereo[mua];"
                f"[voa][mua]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
            amap = ["-map", "[aout]"]
        elif audio_inputs == 1:
            filters.append(f"[{base}:a]aformat=sample_rates=44100:channel_layouts=stereo[aout]")
            amap = ["-map", "[aout]"]
        else:
            amap = []

        cmd += ["-filter_complex", ";".join(filters), "-map", f"[{vlabel}]"]
        cmd += amap
        cmd += [
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
            "-crf", "20", "-r", str(spec.fps), "-movflags", "+faststart",
            "-t", f"{total:.3f}",
        ]
        if amap:
            cmd += ["-c:a", "aac", "-b:a", "160k", "-shortest"]
        cmd += [str(out)]

        _run(cmd)

        return RenderedVideo(
            path=out,
            duration=ffprobe_duration(out) or total,
            scenes=len(scenes),
            slides=[Path(p) for p in slides] if keep_slides_in else [],
            voiceover=voice is not None,
            width=spec.size[0],
            height=spec.size[1],
        )
