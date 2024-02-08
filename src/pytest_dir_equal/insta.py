from pathlib import Path
from typing import Any

from pytest_insta import Fmt


class FmtDir(Fmt[Path]):
    extension = ".dir"

    def load(self, path: Path) -> Path:
        return (path / "left.txt").read_text(), (path / "right.txt").read_text()

    def dump(self, path: Path, value: Path):
        path.mkdir(exist_ok=True)
        # (path / "left.txt").write_text(value[0])
        # (path / "right.txt").write_text(value[1])


def test_dir(snapshot: Any, tmp_path: Path):
    assert snapshot("dir") == tmp_path
