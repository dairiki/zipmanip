#!/bin/env python3
# © 2025 Geoffrey T. Dairiki <dairiki@dairiki.org>

"""Rewrite a zip file, re- or de- compressing its contents."""

from __future__ import annotations

import argparse
import inspect
import io
import os
import sys
from contextlib import ExitStack, contextmanager, suppress
from pathlib import Path
from shutil import copyfileobj
from tempfile import TemporaryFile, mkstemp
from typing import TYPE_CHECKING, BinaryIO, Final, Protocol, runtime_checkable
from zipfile import ZIP_BZIP2, ZIP_DEFLATED, ZIP_LZMA, ZIP_STORED, ZipFile, ZipInfo

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from _typeshed import StrPath, SupportsRead, SupportsWrite, Unused


@runtime_checkable
class _Seekable(Protocol):
    def seek(self, offset: int, whence: int = 0, /) -> int: ...
    def seekable(self) -> bool: ...
    def tell(self) -> int: ...


_PRESERVED_ZIPINFO_ATTRS: Final = (
    "file_size",
    "comment",
    "extra",
    "create_system",
    "create_version",
    "extract_version",
    "internal_attr",
    "external_attr",
)


def rezip(
    infile: StrPath | BinaryIO,
    outfile: StrPath | BinaryIO,
    *,
    compression: int = ZIP_STORED,
    compresslevel: int | None = None,
) -> None:
    """Rewrite zip file, possibly compressing the files in the output."""
    with ZipFile(infile) as izf, ZipFile(outfile, "w") as ozf:
        for info in izf.infolist():
            outinfo = ZipInfo(info.filename, info.date_time)
            outinfo.compress_type = compression
            if sys.version_info >= (3, 13):
                outinfo.compress_level = compresslevel
            else:
                outinfo._compresslevel = compresslevel  # type: ignore[attr-defined] # noqa: SLF001
            for attr in _PRESERVED_ZIPINFO_ATTRS:
                setattr(outinfo, attr, getattr(info, attr))
            with izf.open(info) as ifp, ozf.open(outinfo, "w") as ofp:
                copyfileobj(ifp, ofp)


def is_seekable(fp: object) -> bool:
    """Determine whether a file object is seekable."""
    return isinstance(fp, _Seekable) and fp.seekable()


@contextmanager
def _buffer_input(
    infp: SupportsRead[bytes],
) -> Generator[io.BufferedRandom, None, None]:
    """Buffer input through a temporary file.

    This, e.g., insures that the file is seekable.

    """
    with TemporaryFile() as tmp:
        copyfileobj(infp, tmp)
        tmp.seek(0)
        yield tmp


@contextmanager
def _buffer_output(
    outfp: SupportsWrite[bytes],
) -> Generator[io.BufferedRandom, None, None]:
    """Buffer output through a temporary file.

    This, e.g., insures that the file is seekable.

    """
    with TemporaryFile() as tmp:
        yield tmp
        tmp.seek(0)
        copyfileobj(tmp, outfp)


@contextmanager
def _atomic_write(dst: StrPath) -> Generator[io.BufferedRandom, None, None]:
    """Overwrite existing file.

    Entry to the context manager returns a temporary file.  Upon successful exit,
    the temporary file is copied to the destination.

    """
    # It seems impossible to read the umask of the current process in
    # a thread-safe way (without actually creating a test file).
    # There is only os.umask(new_umask) which involves briefly setting
    # a new umask.
    os.umask(current_umask := os.umask(0o777))  # NB: Not thread-safe!

    fd, filename = mkstemp(dir=Path(dst).parent, prefix=".", suffix=".zip")
    os.chmod(fd, 0o666 & ~current_umask)
    try:
        with open(fd, "w+b") as fp:
            yield fp
        os.replace(filename, dst)
    except Exception:
        with suppress(OSError):
            os.remove(filename)
        raise


_COMPRESSION_TYPES: Final = {
    "store": ZIP_STORED,
    "deflate": ZIP_DEFLATED,
    "bzip2": ZIP_BZIP2,
    "lzma": ZIP_LZMA,
}


class _CompressionLevelArg(argparse.Action):
    """Implement ``-0`` through ``-9`` style compression level args."""

    def __call__(
        self,
        parser: Unused,  # noqa: ARG002
        namespace: argparse.Namespace,
        values: Unused,  # noqa: ARG002
        option_string: str | None = None,
    ) -> None:
        assert option_string is not None
        assert option_string[0] == "-"
        assert option_string[1:].isdigit()
        compression_level = int(option_string[1:])
        setattr(namespace, self.dest, compression_level)


def main(args: Sequence[str] | None = None) -> None:
    """Write zip file contents to a new zip file, re- or de-compressing its contents.

    This can be used to convert a compressed zip file to one whose
    contents are stored uncompressed, and vice versa.

    """

    parser = argparse.ArgumentParser(description=inspect.getdoc(main))
    parser.add_argument(
        "--output-file",
        "-O",
        help="output file name (default stdout)",
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="""input zip file (default stdin):
        If an explicit input file is named and no explicit output file is set,
        the named zip file will be rewritten IN PLACE.
        """,
    )
    parser.add_argument(
        "--compression-method",
        "-Z",
        choices=_COMPRESSION_TYPES.keys(),
        help="set compression method (default: 'deflate')",
    )
    parser.add_argument(
        "-0",
        "-1",
        "-2",
        "-3",
        "-4",
        "-5",
        "-6",
        "-7",
        "-8",
        "-9",
        nargs=0,
        action=_CompressionLevelArg,
        dest="compression_level",
        help="set compression level",
    )
    parsed = parser.parse_args(args)

    infile = parsed.input_file
    outfile = parsed.output_file
    compression = _COMPRESSION_TYPES.get(parsed.compression_method, ZIP_DEFLATED)
    compresslevel = parsed.compression_level

    with ExitStack() as stack:
        if infile is None:
            # ZipFile wants a seekable input
            assert isinstance(sys.stdin, io.TextIOBase)
            infile = sys.stdin.detach()
            if not is_seekable(infile):
                infile = stack.enter_context(_buffer_input(infile))
            if outfile is None:
                # Make sure ZipFile gets a seekable output file object.
                #
                # ZipFile can write to a non-seekable output (e.g. a
                # pipe), however, when doing so it seems to insert
                # some extra holes in the resulting zip file.
                # (Zipinfo -v reports "There are an extra 16 bytes
                # preceding this file.")
                assert isinstance(sys.stdout, io.TextIOBase)
                outfile = sys.stdout.detach()
                sys.stdout = sys.stderr  # paranoia: insure print() goes to stderr
                if not is_seekable(outfile):
                    outfile = stack.enter_context(_buffer_output(outfile))
        elif outfile is None:
            # overwrite named input file in-place
            outfile = stack.enter_context(_atomic_write(infile))

        rezip(infile, outfile, compression=compression, compresslevel=compresslevel)


if __name__ == "__main__":
    main()  # pragma: NO COVER
