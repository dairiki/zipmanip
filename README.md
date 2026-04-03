# zipmanip

[![Latest version badge](https://img.shields.io/pypi/v/zipmanip)](https://pypi.org/project/zipmanip/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/zipmanip)


This is a command line utility that rewrites a zip file. It attempts
to leave the archive contents metadata and ordering as unchanged as
is possible, but re-compresses or decompresses the contents.

This was written to use as a git smudge/clean filter to use when using
git to keep a history of zip files. (See below for more on that.)
Note that various programs store their native project files as zip files.

- [FreeCAD]'s [`.FCStd`][FCStd] files are zip archives, as are *some*
  `.amf` and `.3mf` files.  (Being able to reasonably version-control
  FreeCAD drawings was my motivation for writing this.)

- Many formats written by Open/LibreOffice and Microsoft Office
  programs are zip-based. These include `.odt`, `.ods`, `.odp`, `odg`,
  `.docx`, `.xlsx`, and `.pptx` files.  (It's still untested
  how well they work with this, but they may well do.)

- Java's `.jar` and `.war` files are zip archives. (Though these may
  be digitally signed.  At present, I'm unsure how those signatures
  may interact with the techniques used here.)

- The `.epub` e-book format is zip-based.

This program may be useful in other non-git-related purposes as well.

## Installation

The recommended method of installation is to install the distribution from
[PyPI](https://pypi.org/project/zipmanip/) using, e.g. [pipx].

1. Install `pipx`.
2. Run `pipx install zipmanip`.

Any standard python installation method (e.g. installing to a
virtual environment using `pip`) should work.

### Quick and Dirty method

At present, there are no external dependencies and the code is all
contained in a single file, so you could just copy the
[`zipmanip.py`](https://raw.githubusercontent.com/dairiki/zipmanip/refs/heads/master/zipmanip.py)
file to some location in your PATH, and make it executable.

## Usage

```shell

$ zipmanip -h
usage: zipmanip [-h] [--output-file OUTPUT_FILE]
                [--compression-method {store,deflate,bzip2,lzma}] [-0]
                [input_file]

Write zip file contents to a new zip file, re- or de-compressing its contents. This can be
used to convert a compressed zip file to one whose contents are stored uncompressed, and
vice versa.

positional arguments:
  input_file            input zip file (default stdin): If an explicit input file is named
                        and no explicit output file is set, the named zip file will be
                        rewritten IN PLACE.

options:
  -h, --help            show this help message and exit
  --output-file OUTPUT_FILE, -O OUTPUT_FILE
                        output file name (default stdout)
  --compression-method {store,deflate,bzip2,lzma}, -Z {store,deflate,bzip2,lzma}
                        set compression method (default: 'deflate')
  -0, -1, -2, -3, -4, -5, -6, -7, -8, -9
                        set compression level
```

For example, `zipmanip --compression-method=store` will read a zip
archive from *stdin*, and write an zip archive with the same contents,
all of which is stored uncompressed to *stdout*.

The "inverse" operation (not exactly, see
[below](#on-round-trip-idempotency)) would be `zipmanip` to
compress the contents using the default settings (or `zipmanip -9` to
turn the deflate compression to max).

## Usage with Git

`Zipmanip` can be used as a clean/smudge filter with `git` so that zip
archives are stored uncompressed in the git index.

(The motivation is that if the zip contents are not compressed, git
should be able to more efficiently pack the deltas between revisions.)

To set this up:

```shell
git config filter.zipmanip.clean "zipmanip --compression-method=store"
git config filter.zipmanip.smudge "zipmanip -9"
# optionally, for diff formatting
git config diff.unzip.textconv "unzip -c -a"
```

Then, edit [`.gitattributes`][gitattributes] to set the
`filter=zipmanip` (and, optionally `diff=unzip`) on any zip files that
you want to store uncompressed.  E.g.


```
*.FCStd binary filter=zipmanip diff=unzip
*.3mf binary filter=zipmanip diff=unzip
*.amf binary filter=zipmanip diff=unzip
```

## Bugs

### On Round-trip Idempotency

Currently if a zip archive is round tripped — converted to
uncompressed, then re-compressed — the result will not be byte-wise
identical to the original. This is due to (at least) a couple of issues.

#### Differing compression algorithm and parameters

It may be possible to improve this situation, at least partially, by
storing information on the original compression type in the
uncompressed archives.

Note that data on compression level may be available from bits 1, 2
and possibly 4 of the ``ZipInfo.flags``.
(See section 4.4.4 of [PKZIP Application Note][AppNote].)

#### Differing use of "zip64" extended header

Also the use of "extended local header" is not preserved. (This
manifests in `.3mf` files written by PrusaSlicer. PrusaSlicer always
writes extended headers.  (This, I think could be fixed with
appropriate use of the `force_zip64` parameters to `ZipFile.open`.)


## Author

Jeff Dairiki <dairiki@dairiki.org>


[AppNote]: https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT (PKZIP Application Note)
[gitattributes]: https://git-scm.com/docs/gitattributes
[FreeCAD]: https://www.freecad.org/
[FCStd]: https://wiki.freecad.org/File_Format_FCStd
[pipx]: https://pipx.pypa.io/stable/docs/
