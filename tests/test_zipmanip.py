# ruff: noqa: TRY003, EM101
from __future__ import annotations

import io
from contextlib import suppress
from typing import TYPE_CHECKING, Any, BinaryIO
from unittest.mock import ANY, Mock
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZIP_STORED, ZipFile

import pytest

from zipmanip import (
    _atomic_write,
    _buffer_input,
    _buffer_output,
    is_seekable,
    main,
    rezip,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from _typeshed import Unused


@pytest.mark.parametrize("compression", [ZIP_BZIP2, ZIP_STORED, ZIP_DEFLATED])
def test_rezip(compression: int) -> None:
    infile = io.BytesIO()
    with ZipFile(infile, "w") as zf:
        zf.writestr("somefile", b"some content")
    infile.seek(0)

    outfile = io.BytesIO()
    rezip(infile, outfile, compression=compression)
    outfile.seek(0)

    with ZipFile(outfile) as zf:
        assert zf.testzip() is None
        assert zf.namelist() == ["somefile"]
        assert zf.getinfo("somefile").compress_type == compression
        assert zf.read("somefile") == b"some content"


class _NonseekableBytesIO(io.BytesIO):
    def seek(self, offset: int, whence: int = 0, /) -> int:  # noqa: ARG002
        raise OSError("Not seekable")  # pragma: NO COVER

    def seekable(self) -> bool:
        return False  # pragma: NO COVER

    def tell(self) -> int:
        raise OSError("Not seekable")  # pragma: NO COVER


def test_is_seekable_true() -> None:
    assert is_seekable(io.BytesIO())


def test_is_seekable_false() -> None:
    assert not is_seekable(_NonseekableBytesIO())


def test_buffer_input() -> None:
    fp = _NonseekableBytesIO(b"test text")
    with _buffer_input(fp) as sfp:
        assert sfp is not fp
        assert sfp.read() == b"test text"
        sfp.seek(5)
        assert sfp.read() == b"text"


def test_buffer_output() -> None:
    fp = _NonseekableBytesIO()
    with _buffer_output(fp) as sfp:
        assert sfp is not fp
        sfp.write(b"one")
        sfp.seek(0)
        sfp.write(b"two")
    assert fp.getvalue() == b"two"


def test_atomic_write(tmp_path: Path) -> None:
    target = tmp_path / "test.txt"
    target.write_bytes(b"content")
    with open(target, "rb") as ifp, _atomic_write(target) as ofp:
        ofp.write(b"X")
        ofp.write(ifp.read())
        ofp.write(b"Y")
        assert target.read_bytes() == b"content"
    assert target.read_bytes() == b"XcontentY"
    assert set(tmp_path.iterdir()) == {target}


def test_atomic_failed_write(tmp_path: Path) -> None:
    target = tmp_path / "test.txt"
    with suppress(RuntimeError), _atomic_write(target) as ofp:
        ofp.write(b"X")
        raise RuntimeError

    assert not target.exists()
    assert set(tmp_path.iterdir()) == set()


@pytest.mark.parametrize(
    ("args", "opts"),
    [
        ((), {"compression": ZIP_DEFLATED, "compresslevel": None}),
        (("-4",), {"compression": ZIP_DEFLATED, "compresslevel": 4}),
        (("-Z", "store"), {"compression": ZIP_STORED, "compresslevel": None}),
        (
            ("--compression-method=bzip2", "-9"),
            {"compression": ZIP_BZIP2, "compresslevel": 9},
        ),
    ],
)
def test_main_options(
    monkeypatch: pytest.MonkeyPatch, args: Sequence[str], opts: Mapping[str, Any]
) -> None:
    mock_rezip = Mock(spec=rezip)
    monkeypatch.setattr("zipmanip.rezip", mock_rezip)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO()))
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(io.BytesIO()))

    main(args)
    mock_rezip.assert_called_once_with(ANY, ANY, **opts)


def test_main_makes_streams_seekable(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = _NonseekableBytesIO(b"input")
    stdout = _NonseekableBytesIO()
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(stdin))
    monkeypatch.setattr("sys.stdout", io.TextIOWrapper(stdout))

    def mock_rezip(infile: BinaryIO, outfile: BinaryIO, **_opts: Unused) -> None:
        assert infile.read() == b"input"
        infile.seek(0)
        assert infile.read() == b"input"

        outfile.write(b"output")

    monkeypatch.setattr("zipmanip.rezip", mock_rezip)

    main([])

    assert stdout.getvalue() == b"output"


def test_main_rewrite_in_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    filepath = tmp_path / "file"

    def mock_rezip(infile: str, outfile: BinaryIO, **_opts: Unused) -> None:
        assert infile == str(filepath)
        outfile.write(b"output")

    monkeypatch.setattr("zipmanip.rezip", mock_rezip)

    filepath.write_bytes(b"input")
    main([str(filepath)])
    assert filepath.read_bytes() == b"output"
