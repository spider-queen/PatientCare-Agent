from pathlib import Path


SOURCE_ROOTS = (
    Path("app"),
    Path("frontend/src"),
    Path("tests"),
)
SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".css", ".md"}
MOJIBAKE_MARKERS = tuple(chr(code) for code in (0x9369, 0x7487, 0x93AE, 0x93C8, 0x9225))


def test_source_files_are_utf8_and_do_not_contain_common_mojibake_markers():
    checked_files = []
    failed_files = []

    for root in SOURCE_ROOTS:
        for path in root.rglob("*"):
            if path.suffix not in SOURCE_SUFFIXES or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            checked_files.append(path)
            if any(marker in text for marker in MOJIBAKE_MARKERS):
                failed_files.append(str(path))

    assert checked_files
    assert failed_files == []
