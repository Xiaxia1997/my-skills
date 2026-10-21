#!/usr/bin/env python3
"""Download English YouTube subtitles and normalize a selected VTT time range."""

from __future__ import annotations

import argparse
import html
import importlib.util
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable, List, NamedTuple, Optional, Sequence, Tuple
import uuid


TIMING_RE = re.compile(
    r"(?P<start>\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)\s+-->\s+"
    r"(?P<end>\d{1,3}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?)"
)
TAG_RE = re.compile(r"<[^>]+>")
INLINE_TIMESTAMP_RE = re.compile(r"<\d{1,3}:\d{2}(?::\d{2})?[.,]\d{1,3}>")


class Cue(NamedTuple):
    start: float
    end: float
    caption: str
    has_inline_timestamps: bool
    first_line: str


def parse_timestamp(value: str) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS into non-negative seconds."""
    raw = value.strip().replace(",", ".")
    if not raw or raw.startswith("-"):
        raise ValueError(f"invalid non-negative timestamp: {value!r}")

    parts = raw.split(":")
    if len(parts) > 3:
        raise ValueError(f"invalid timestamp: {value!r}")

    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) == 2:
            minutes = int(parts[0])
            trailing_seconds = float(parts[1])
            if minutes < 0 or not 0 <= trailing_seconds < 60:
                raise ValueError
            seconds = minutes * 60 + trailing_seconds
        else:
            hours = int(parts[0])
            minutes = int(parts[1])
            trailing_seconds = float(parts[2])
            if hours < 0 or not 0 <= minutes < 60 or not 0 <= trailing_seconds < 60:
                raise ValueError
            seconds = hours * 3600 + minutes * 60 + trailing_seconds
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid timestamp: {value!r}") from exc

    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"invalid non-negative timestamp: {value!r}")
    return seconds


def _clean_caption(lines: Iterable[str]) -> str:
    joined = " ".join(line.strip() for line in lines if line.strip())
    without_tags = TAG_RE.sub("", joined)
    decoded = html.unescape(without_tags).replace("\u200b", "")
    return re.sub(r"\s+", " ", decoded).strip()


def _token_key(token: str) -> str:
    return re.sub(r"[^\w]+", "", token, flags=re.UNICODE).casefold()


def _append_without_overlap(accumulated: List[str], current: Sequence[str]) -> None:
    if not current:
        return
    max_overlap = min(len(accumulated), len(current))
    overlap = 0
    for size in range(max_overlap, 0, -1):
        left = [_token_key(token) for token in accumulated[-size:]]
        right = [_token_key(token) for token in current[:size]]
        if left == right:
            overlap = size
            break
    accumulated.extend(current[overlap:])


def _iter_cues(vtt: str) -> Iterable[Cue]:
    normalized = vtt.replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n\s*\n", normalized):
        lines = block.splitlines()
        timing_index = next(
            (index for index, line in enumerate(lines) if "-->" in line),
            None,
        )
        if timing_index is None:
            continue
        match = TIMING_RE.search(lines[timing_index])
        if not match:
            continue
        caption_lines = lines[timing_index + 1 :]
        caption = _clean_caption(caption_lines)
        if caption:
            first_line = next(
                (
                    cleaned
                    for line in caption_lines
                    if (cleaned := _clean_caption((line,)))
                ),
                "",
            )
            yield Cue(
                parse_timestamp(match.group("start")),
                parse_timestamp(match.group("end")),
                caption,
                any(INLINE_TIMESTAMP_RE.search(line) for line in caption_lines),
                first_line,
            )


def _token_keys(text: str) -> List[str]:
    return [_token_key(token) for token in text.split()]


def _is_rolling_continuation(previous: Cue, current: Cue) -> bool:
    if current.start > previous.end + 0.05:
        return False

    previous_tokens = _token_keys(previous.caption)
    if current.has_inline_timestamps and _token_keys(current.first_line) == previous_tokens:
        return True

    current_tokens = _token_keys(current.caption)
    is_short_bridge = current.end - current.start <= 0.05
    return (
        previous.has_inline_timestamps
        and not current.has_inline_timestamps
        and is_short_bridge
        and len(current_tokens) <= len(previous_tokens)
        and previous_tokens[-len(current_tokens) :] == current_tokens
    )


def extract_text(
    vtt: str,
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> str:
    """Extract and de-duplicate caption text overlapping the selected range."""
    if start is not None and start < 0:
        raise ValueError("start time must be non-negative")
    if end is not None and end < 0:
        raise ValueError("end time must be non-negative")
    if start is not None and end is not None and end <= start:
        raise ValueError("end time must be greater than start time")

    normalized_words: List[str] = []
    selected_words: List[str] = []
    previous_cue: Optional[Cue] = None
    for cue in _iter_cues(vtt):
        caption_words = cue.caption.split()
        previous_length = len(normalized_words)
        should_deduplicate = previous_cue is not None and (
            cue.start < previous_cue.end
            or _is_rolling_continuation(previous_cue, cue)
        )
        if should_deduplicate:
            _append_without_overlap(normalized_words, caption_words)
        else:
            normalized_words.extend(caption_words)

        new_words = normalized_words[previous_length:]
        if not (start is not None and cue.end <= start) and not (
            end is not None and cue.start >= end
        ):
            selected_words.extend(new_words)
        previous_cue = cue
    return " ".join(selected_words).strip()


def build_download_attempts(
    url: str,
    output_stem: Path,
    launcher: Optional[Sequence[str]] = None,
) -> List[List[str]]:
    """Build manual-first yt-dlp commands for testability and clear fallback order."""
    executable = list(launcher or ("yt-dlp",))
    def command(flag: str, label: str) -> List[str]:
        return executable + [
            flag,
            "--skip-download",
            "--sub-format",
            "vtt",
            "--sub-langs",
            "en.*,en",
            "--no-playlist",
            "-o",
            f"{output_stem}-{label}.%(ext)s",
            url,
        ]

    return [
        command("--write-subs", "manual"),
        command("--write-auto-subs", "automatic"),
    ]


def _yt_dlp_launcher() -> List[str]:
    executable = shutil.which("yt-dlp")
    if executable:
        return [executable]
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    raise RuntimeError(
        "yt-dlp was not found. Install it first: "
        "macOS `brew install yt-dlp`; macOS/Linux `python3 -m pip install yt-dlp`; "
        "Windows `py -3 -m pip install yt-dlp`."
    )


def _subtitle_rank(path: Path) -> Tuple[int, str]:
    name = path.name.casefold()
    if name.endswith(".en.vtt"):
        return (0, name)
    if ".en-us." in name or ".en-gb." in name:
        return (1, name)
    return (2, name)


def download_subtitle(url: str, output_dir: Path) -> Tuple[Path, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    launcher = _yt_dlp_launcher()
    diagnostics: List[str] = []

    with tempfile.TemporaryDirectory(prefix=".dictation-download-", dir=output_dir) as temp_name:
        temp_dir = Path(temp_name)
        attempts = build_download_attempts(url, temp_dir / "source", launcher=launcher)
        for label, command in zip(("manual", "automatic"), attempts):
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            candidates = sorted(temp_dir.glob(f"source-{label}*.vtt"), key=_subtitle_rank)
            if candidates:
                source_path = candidates[0]
                language_suffix = "".join(source_path.suffixes) or ".vtt"
                final_path = output_dir / (
                    f"source-{label}-{uuid.uuid4().hex[:8]}{language_suffix}"
                )
                source_path.replace(final_path)
                return final_path, label
            detail = (completed.stderr or completed.stdout).strip()
            diagnostics.append(f"{label}: {detail[-800:] or 'no VTT file produced'}")

    raise RuntimeError(
        "No English VTT subtitles were produced. The video may have no English captions, "
        "may be private, or may block yt-dlp.\n" + "\n".join(diagnostics)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download manual English subtitles (or automatic fallback) and normalize VTT text."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("--start", help="Start at seconds, MM:SS, or HH:MM:SS")
    parser.add_argument("--end", help="Stop at seconds, MM:SS, or HH:MM:SS")
    parser.add_argument(
        "--output-dir",
        default=".",
        type=Path,
        help="Directory for the retained VTT and transcript.txt (default: current directory)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        start = parse_timestamp(args.start) if args.start is not None else None
        end = parse_timestamp(args.end) if args.end is not None else None
        if start is not None and end is not None and end <= start:
            raise ValueError("end time must be greater than start time")

        subtitle_path, subtitle_type = download_subtitle(args.url, args.output_dir)
        transcript = extract_text(
            subtitle_path.read_text(encoding="utf-8-sig"),
            start=start,
            end=end,
        )
        if not transcript:
            raise RuntimeError("The selected time range contains no subtitle text.")

        transcript_path = args.output_dir / "transcript.txt"
        transcript_path.write_text(transcript + "\n", encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"subtitle_type={subtitle_type}")
    print(f"vtt={subtitle_path.resolve()}")
    print(f"transcript={transcript_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
