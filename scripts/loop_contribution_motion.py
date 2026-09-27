"""Keep the generated 3D contribution graph moving.

The upstream action plays each rise once. This script turns those motions
into a continuous up-and-down loop and adds a sweep around the language ring.

GitHub renders the graph as an image, so the ring cannot detect the pointer.
The sweep repeats on its own instead.

Safe to run more than once. The daily workflow runs it after generation.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_DIR = ROOT / "profile-3d-contrib"
TOWER_SPLIT = re.compile(
    r'(<g transform="translate\(\d+(?:\.\d+)? \d+(?:\.\d+)?\)">'
    r"<animateTransform\b[^>]*>)"
)
DONUT_GROUP = '<g transform="translate(130, 130)">'
SWEEP = (
    '<circle r="91" fill="none" stroke="#7ee0c3" stroke-width="5" '
    'stroke-linecap="round" stroke-dasharray="48 524" opacity="0.95">'
    '<animateTransform attributeName="transform" type="rotate" '
    'from="0" to="360" dur="2.4s" repeatCount="indefinite"/>'
    "</circle>"
)
RING_PULSE = (
    '<animateTransform attributeName="transform" type="scale" '
    'values="1;1.05;1" dur="2.2s" repeatCount="indefinite"/>'
)


def ping_pong(values: str) -> str:
    parts = [part for part in values.split(";") if part != ""]
    if len(parts) >= 2 and parts[0] != parts[-1]:
        return values + ";" + parts[0]
    return values


def patch_motion(tag: str, phase: float) -> str:
    tag = tag.replace('repeatCount="1"', 'repeatCount="indefinite"')
    tag = re.sub(
        r'values="([^"]*)"',
        lambda match: f'values="{ping_pong(match.group(1))}"',
        tag,
        count=1,
    )
    if "begin=" not in tag:
        tag = tag[:-1] + f' begin="{phase:.2f}s">'
    return tag


def patch_towers(text: str) -> str:
    pieces = TOWER_SPLIT.split(text)
    if len(pieces) == 1:
        return text
    rebuilt = [pieces[0]]
    tower_index = 0
    for delimiter, body in zip(pieces[1::2], pieces[2::2]):
        phase = (tower_index % 10) * 0.3
        tower_index += 1
        delimiter = patch_motion(delimiter, phase)
        head, separator, tail = body.partition("</g>")
        head = re.sub(
            r"<animate\b[^>]*>",
            lambda match, phase=phase: patch_motion(match.group(0), phase),
            head,
        )
        rebuilt.append(delimiter + head + separator + tail)
    return "".join(rebuilt)


def patch_remaining(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        tag = match.group(0)
        if 'attributeName="fill-opacity"' in tag:
            tag = re.sub(r'values="[^"]*"', 'values="0.82;1;0.82"', tag, count=1)
            return tag.replace('repeatCount="1"', 'repeatCount="indefinite"')
        return patch_motion(tag, 0.0)

    text = re.sub(r"<animate\b[^>]*repeatCount=\"1\"[^>]*>", replace, text)
    text = re.sub(
        r"<animateTransform\b[^>]*repeatCount=\"1\"[^>]*>",
        lambda match: patch_motion(match.group(0), 0.0),
        text,
    )
    return text


def patch_ring(text: str) -> str:
    if DONUT_GROUP not in text:
        return text
    if "stroke-dasharray=\"48 524\"" not in text:
        text = text.replace(DONUT_GROUP, DONUT_GROUP + SWEEP, 1)
    for signature in ('d="M0,-117', 'd="M-60.791,-99.967'):
        start = text.find(f"<path {signature}")
        if start < 0:
            start = text.find(f"<path {signature[0:4]}")
        marker = text.find(signature, start if start >= 0 else 0)
        if marker < 0:
            continue
        open_end = text.find(">", marker)
        if open_end < 0:
            continue
        if text.startswith(RING_PULSE, open_end + 1):
            continue
        text = text[: open_end + 1] + RING_PULSE + text[open_end + 1 :]
    return text


def patch_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    if "repeatCount=\"1\"" not in original and "stroke-dasharray=\"48 524\"" in original:
        return False
    updated = patch_ring(patch_remaining(patch_towers(original)))
    if updated == original:
        return False
    path.write_text(updated, encoding="utf-8", newline="\n")
    return True


def main() -> None:
    changed = 0
    for path in sorted(GRAPH_DIR.glob("*.svg")):
        if patch_file(path):
            changed += 1
            print(f"updated {path.name}")
    print(f"{changed} graph file(s) updated")


if __name__ == "__main__":
    main()
