# /// script
# dependencies = ["nox"]
# ///
import nox

nox.options.default_venv_backend = "uv|venv"

PYPROJECT = nox.project.load_toml("pyproject.toml")
TESTS_DEPENDENCIES = nox.project.dependency_groups(PYPROJECT, "tests")
TYPING_DEPENDENCIES = nox.project.dependency_groups(PYPROJECT, "typing")
STYLE_DEPENDENCIES = nox.project.dependency_groups(PYPROJECT, "style")
PYTHON_VERSIONS = nox.project.python_versions(PYPROJECT, max_version="3.14")


@nox.session(python=PYTHON_VERSIONS, requires=["cover_clean"])
def tests(session: nox.Session) -> None:
    """Run python tests"""
    session.install(".", "coverage", *TESTS_DEPENDENCIES)
    session.run("coverage", "run", "-p", "-m", "pytest", "tests", "-ra")


@nox.session
def typing(session: nox.Session) -> None:
    """Check type annotations"""
    session.install(*TYPING_DEPENDENCIES)
    session.run("mypy")


@nox.session
def style(session: nox.Session) -> None:
    """Check style (lint and format)"""
    session.install(*STYLE_DEPENDENCIES)
    session.run("ruff", "check")
    session.run("ruff", "format", "--check")


@nox.session(default=False)
def cover_clean(session: nox.Session) -> None:
    """Clear existing code coverage stats."""
    session.install("coverage")
    session.run("coverage", "erase")


@nox.session(requires=["tests"])
def cover_report(session: nox.Session) -> None:
    """Combine and report code coverage."""
    session.install("coverage")
    session.run("coverage", "combine", success_codes=(0, 1))
    session.run("coverage", "report", "--show-missing", "--fail-under=100")


if __name__ == "__main__":
    nox.main()
