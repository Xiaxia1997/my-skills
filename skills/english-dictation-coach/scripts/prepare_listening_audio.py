#!/usr/bin/env python3
"""Package an exact listening range as a local, browser-friendly MP3.

Examples:
  prepare_listening_audio.py --youtube-url URL --start 0:00 --end 6:36 --output clip.mp3
  prepare_listening_audio.py --input-file talk.m4a --start 12:10 --end 18:00 --output clip.mp3
  prepare_listening_audio.py --audio-url https://example.com/talk.mp3 --start 0 --end 396 --output clip.mp3
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path


def seconds(value: str) -> float:
    parts = value.strip().split(":")
    try:
        values = [float(part) for part in parts]
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"Invalid time: {value}") from error
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return values[0] * 60 + values[1]
    if len(values) == 3:
        return values[0] * 3600 + values[1] * 60 + values[2]
    raise argparse.ArgumentTypeError(f"Invalid time: {value}")


def run(command: list[str], timeout: float = 300) -> None:
    # Terminate downloader children too, so a timed-out yt-dlp cannot leave ffmpeg running.
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=os.name == "posix") as process:
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait()
            raise SystemExit(f"Media preparation timed out after {timeout:g}s; existing output was preserved")
        if returncode:
            raise subprocess.CalledProcessError(returncode, command)


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise SystemExit(f"Missing required program: {binary}")
    return path


def probe_duration(ffprobe: str, source: str) -> float:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", source],
        check=True, capture_output=True, text=True, timeout=20,
    )
    return float(result.stdout.strip())


def validate_audio(ffmpeg: str, ffprobe: str, path: Path, expected: float) -> float:
    duration = probe_duration(ffprobe, str(path))
    # MP3 frame/encoder padding is normally a few hundredths of a second.
    if not math.isfinite(duration) or abs(duration - expected) > 0.12:
        raise ValueError(f"Audio duration {duration:.3f}s does not match requested {expected:.3f}s")
    run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-xerror",
         "-i", str(path), "-map", "0:a:0", "-f", "null", "-"], timeout=max(60, expected))
    return duration


def reuse_audio(args: argparse.Namespace, source_value: str, ffmpeg: str, ffprobe: str) -> float:
    manifest_path = args.output.with_suffix(args.output.suffix + ".json")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("source") != source_value or data.get("audio") != args.output.name:
        raise ValueError("Existing audio has a different source or filename")
    for key, value in (("start_seconds", args.start), ("end_seconds", args.end)):
        if not math.isclose(float(data[key]), value, rel_tol=0, abs_tol=1e-6):
            raise ValueError("Existing audio covers a different time range")
    if data.get("bitrate", "128k") != args.bitrate:
        raise ValueError("Existing audio uses a different bitrate")
    if args.input_file:
        stat = Path(source_value).stat()
        if data.get("source_size") != stat.st_size or data.get("source_mtime_ns") != stat.st_mtime_ns:
            raise ValueError("Local source changed, or its identity is absent from the old manifest")
    duration = validate_audio(ffmpeg, ffprobe, args.output, args.end - args.start)
    if not math.isclose(float(data["duration_seconds"]), duration, rel_tol=0, abs_tol=.01):
        raise ValueError("Existing audio does not match its recorded duration")
    return duration


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--youtube-url", help="Public YouTube URL; downloaded with yt-dlp")
    source.add_argument("--audio-url", help="Direct public audio/video URL readable by ffmpeg")
    source.add_argument("--input-file", help="Existing local audio/video file")
    parser.add_argument("--start", required=True, type=seconds, help="Clip start, e.g. 1:30")
    parser.add_argument("--end", required=True, type=seconds, help="Clip end, e.g. 6:36")
    parser.add_argument("--output", required=True, type=Path, help="Destination .mp3 next to the HTML page")
    parser.add_argument("--bitrate", default="128k", help="MP3 bitrate; default: 128k mono")
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    parser.add_argument("--no-manifest", action="store_true", help="Do not write the adjacent provenance JSON")
    args = parser.parse_args()
    if not all(math.isfinite(value) for value in (args.start, args.end)) or args.start < 0 or args.end <= args.start:
        parser.error("Times must be finite, with 0 <= --start < --end")

    ffmpeg = require("ffmpeg")
    ffprobe = require("ffprobe")
    source_value = str(Path(args.input_file).resolve()) if args.input_file else args.audio_url or args.youtube_url
    if args.output.exists() and not args.force:
        try:
            duration = reuse_audio(args, source_value, ffmpeg, ffprobe)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
            parser.error(f"Existing output preserved: {error}. Use another output path or --force to replace it")
        print(f"Reused {args.output} ({duration:.2f}s); no download or transcode needed")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    expected_duration = args.end - args.start
    manifest = args.output.with_suffix(args.output.suffix + ".json")

    with tempfile.TemporaryDirectory(prefix=".listening-audio-", dir=args.output.parent) as temp_dir:
        source_path = source_value
        clip_start = args.start
        if args.youtube_url:
            ytdlp = require("yt-dlp")
            template = str(Path(temp_dir) / "source.%(ext)s")
            run([ytdlp, "--ignore-config", "--no-playlist", "--no-progress",
                 "--socket-timeout", "20", "--retries", "1", "--fragment-retries", "1",
                 "--extractor-retries", "1", "--file-access-retries", "1",
                 "--abort-on-unavailable-fragments", "-f", "bestaudio/best",
                 "--download-sections", f"*{args.start}-{args.end}", "--force-keyframes-at-cuts",
                 "--downloader-args", "ffmpeg_i:-rw_timeout 20000000",
                 "-o", template, args.youtube_url], timeout=max(300, expected_duration * 3))
            files = [path for path in Path(temp_dir).glob("source.*") if path.suffix not in {".part", ".ytdl"}]
            if len(files) != 1:
                raise SystemExit("yt-dlp did not produce exactly one complete audio section")
            source_path = str(files[0])
            # yt-dlp's section is already cut at the requested source time. Its local timeline starts at zero.
            clip_start = 0

        staged_audio = Path(temp_dir) / "clip.mp3"
        input_options = ["-rw_timeout", "20000000"] if args.audio_url else []
        # Keep output-side seeking for direct/local input to preserve exact sentence boundaries.
        run([
            ffmpeg, "-nostdin", "-y" if args.force else "-n", "-hide_banner", "-loglevel", "error",
            *input_options, "-i", source_path, "-ss", str(clip_start), "-t", str(expected_duration),
            "-map", "0:a:0", "-vn", "-ac", "1", "-c:a", "libmp3lame", "-b:a", args.bitrate,
            str(staged_audio),
        ], timeout=max(300, expected_duration * 3))

        duration = validate_audio(ffmpeg, ffprobe, staged_audio, expected_duration)
        metadata = {
            "source": source_value, "start_seconds": args.start, "end_seconds": args.end,
            "duration_seconds": duration, "audio": args.output.name, "bitrate": args.bitrate,
        }
        if args.input_file:
            stat = Path(source_value).stat()
            metadata.update(source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns)
        staged_manifest = Path(temp_dir) / "clip.mp3.json"
        if not args.no_manifest:
            staged_manifest.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.output.exists() and not args.force:
            raise SystemExit("Output appeared during preparation; it was preserved. Use another path or --force")
        staged_audio.replace(args.output)
        if not args.no_manifest:
            staged_manifest.replace(manifest)
        elif manifest.exists():
            manifest.unlink()  # Do not leave stale provenance after an explicit --force replacement.
    print(f"Created {args.output} ({duration:.2f}s)")


if __name__ == "__main__":
    main()
