#!/usr/bin/env python3
"""Align approved sentence text to whisper.cpp -ojf/-sow output.

sentences.json is {"paragraphs": [["Sentence one.", "Sentence two."], ...]}.
The result is JSON with `sentenceTimings`, ready for LISTENING_PLAYER_CONFIG.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


def parse_time(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def normal_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower().replace("’", "'"))


def whisper_words(data: dict) -> list[dict]:
    words, current = [], None
    for segment in data.get("transcription", []):
        for token in segment.get("tokens", []):
            raw = token.get("text", "")
            if raw.startswith("[_") or not raw.strip():
                continue
            begins_word = raw[0].isspace()
            text = raw.strip()
            if begins_word and current:
                words.append(current)
                current = None
            stamp = token.get("timestamps", {})
            if current is None:
                current = {"text": text, "start": parse_time(stamp["from"]), "end": parse_time(stamp["to"])}
            else:
                current["text"] += text
                current["end"] = parse_time(stamp["to"])
    if current:
        words.append(current)
    return [word for word in words if normal_words(word["text"])]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--whisper-json", required=True, type=Path)
    parser.add_argument("--sentences-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-coverage", type=float, default=.45,
                        help="Fail if a sentence has fewer exact reference-word matches; default .45")
    args = parser.parse_args()

    paragraphs = json.loads(args.sentences_json.read_text(encoding="utf-8"))["paragraphs"]
    reference, sentence_ranges = [], []
    for paragraph_index, sentences in enumerate(paragraphs):
        for sentence_index, sentence in enumerate(sentences):
            start = len(reference)
            reference.extend(normal_words(sentence))
            sentence_ranges.append((paragraph_index, sentence_index, start, len(reference)))
    heard = whisper_words(json.loads(args.whisper_json.read_text(encoding="utf-8")))
    heard_tokens = [normal_words(word["text"])[0] for word in heard]
    matcher = difflib.SequenceMatcher(None, reference, heard_tokens, autojunk=False)
    matched = {}
    for ref_start, heard_start, length in matcher.get_matching_blocks():
        for offset in range(length):
            matched[ref_start + offset] = heard_start + offset

    timings = [[None for _ in sentences] for sentences in paragraphs]
    report = []
    failures = []
    for paragraph_index, sentence_index, start, end in sentence_ranges:
        positions = [matched[index] for index in range(start, end) if index in matched]
        total = max(1, end - start)
        coverage = len(positions) / total
        if not positions or coverage < args.min_coverage:
            failures.append(f"P{paragraph_index + 1} S{sentence_index + 1}: {coverage:.0%} exact-word coverage")
            continue
        timings[paragraph_index][sentence_index] = [
            round(heard[min(positions)]["start"], 3), round(heard[max(positions)]["end"], 3)
        ]
        report.append({"paragraph": paragraph_index, "sentence": sentence_index,
                       "coverage": round(coverage, 3), "timing": timings[paragraph_index][sentence_index]})

    if failures:
        raise SystemExit("Alignment needs review; do not emit partial player data:\n" + "\n".join(failures))
    args.output.write_text(json.dumps({"sentenceTimings": timings, "report": report}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Aligned {len(sentence_ranges)} sentences to {args.output}")


if __name__ == "__main__":
    main()
