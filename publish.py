#!/usr/bin/env python3
"""
Usage:
    - pip install click pillow
    - ./publish.py --help
"""

from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import List, Tuple

import click
from PIL import Image, ImageChops

here = Path(__file__).parent

AUXDIR = "tmp"

def dist_dir(paper: Path) -> Path:
    return paper.parent / "dist"


def src_dir(paper: Path) -> Path:
    return paper.parent


def dist(paper: Path) -> Path:
    return dist_dir(paper) / paper.name


paper_argument = click.option(
    "--paper",
    default="paper.tex",
    metavar="PATH",
    type=lambda x: Path(x).resolve(),
    show_default=True,
    help="override main document",
)


class NaturalOrderGroup(click.Group):
    def list_commands(self, ctx):
        return self.commands.keys()


@click.group(cls=NaturalOrderGroup)
def cli():
    """
    This script prepares papers for distribution to conferences. It moves your
    main TeX document and included subdocuments into a dist/ folder, strips
    all TeX comments, and then checks that the PDF produced from that matches
    the original PDF.

    Run `publish.py <command> --help` to see what each command does.
    """
    pass


@cli.command()
@paper_argument
@click.option(
    "--clean/--no-clean",
    default=True,
    show_default=True,
    help="Delete a previously existing distribution folder.",
)
def run(paper, clean):
    """Run all commands in order."""
    if clean and dist_dir(paper).exists():
        print(f"🗑 Removing {dist_dir(paper)}...")
        shutil.rmtree(dist_dir(paper))

    _init(paper)
    _collect(paper)
    _squash_comments(paper)
    proc, _ = _compile(dist(paper))
    shutil.rmtree(dist_dir(paper) / AUXDIR / "diff", ignore_errors=True)
    ok = _compare(
        paper.with_suffix(".pdf"),
        dist(paper).with_suffix(".pdf"),
        dist_dir(paper) / AUXDIR / "diff",
    )

    if not ok:
        print("📋 latexmk stdout")
        print(proc.stdout)
        print("📋 latexmk stderr")
        print(proc.stderr)
        print("❗ Failed.")


@cli.command(short_help="1. Initialize distribution folder")
@paper_argument
def init(paper):
    """
    This step doesn't do much, it just creates a `dist` folder and copies over the main document.
    """
    _init(paper)


@cli.command(short_help="2. Collect all included files")
@paper_argument
def collect(paper):
    """
    This step tries to compile the distribution,
    detects error messages complaining about missing files,
    copies them over, and then tries again. This makes sure
    that no unused files are included in the final distribution,
    which would otherwise be common if your data folder also includes code.
    """
    _collect(paper)


@cli.command(short_help="3. Squash all comments")
@paper_argument
def squash_comments(paper):
    """
    This step removes all comments from TeX files in the distribution folder.
    """
    _squash_comments(paper)


@cli.command(short_help="4. Compile the distribution")
@paper_argument
def compile(paper):
    """
    This step runs latexmk on dist/paper.tex again
    after comments have been stripped in the previous step.
    """
    proc, missing = _compile(dist(paper))

    print("📋 latexmk stdout")
    print(proc.stdout)
    print("📋 latexmk stderr")
    print(proc.stderr)

    if missing:
        print("❗ Missing the following files:")
        for x in missing:
            print(f" - {x}")
    else:
        print("✅ No missing files")


@cli.command(short_help="5. Compare generated PDFs")
@paper_argument
@click.option(
    "--src", "srcfile", type=click.Path(exists=True), help="override source pdf"
)
@click.option(
    "--dist", "distfile", type=click.Path(exists=True), help="override dist pdf"
)
@click.option("--tmpdir", help="override page image directory", type=click.Path())
def compare(paper, srcfile, distfile, tmpdir):
    """
    This step renders both your source PDF and the distribution PDF
    into PNG files and compares them visually. This ensures that the
    distribution reproduces your paper exactly.
    """
    if srcfile:
        a = Path(srcfile)
    else:
        a = paper.with_suffix(".pdf")
    if distfile:
        b = Path(distfile)
    else:
        b = dist(paper).with_suffix(".pdf")

    if tmpdir:
        tmpdir = Path(tmpdir)
    elif srcfile or distfile:
        tmpdir = here / "diff"
    else:
        tmpdir = dist_dir(paper) / AUXDIR / "diff"

    if tmpdir.exists():
        if tmpdir != dist_dir(paper) / AUXDIR / "diff":
            click.confirm(
                f"Temporary directory {tmpdir} already exists. Delete contents?",
                abort=True,
            )
        shutil.rmtree(tmpdir)

    _compare(a, b, tmpdir)


def _init(paper: Path) -> None:
    dist_dir(paper).mkdir(exist_ok=True)
    if not dist(paper).exists():
        shutil.copy(paper, dist(paper))
    print(f"✅ Initialized {dist_dir(paper)}.")


def _compile(paper: Path) -> Tuple[subprocess.CompletedProcess, List[str]]:
    cmd = [
        "latexmk",
        "-pdf",
        "-recorder-",
        "-shell-escape",
        "-interaction=nonstopmode",
        f"-aux-directory={AUXDIR}",
        paper.name,
    ]
    print(f"🔨 Running {shlex.join(cmd)}...")
    proc = subprocess.run(cmd, cwd=paper.parent, capture_output=True, text=True)

    log_dir = paper.parent / AUXDIR
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "latexmk-stdout.txt").write_text(proc.stdout)
    (log_dir / "latexmk-stderr.txt").write_text(proc.stderr)

    # newlines may be anywhere in file paths, so we strip them.
    stdout = (proc.stdout + proc.stderr).replace("\n", "")
    missing = sorted(
        set(
            re.findall(r"LaTeX (?:Error|Warning): File `(.+?)' ?not ?found", stdout)
            + re.findall(
                r"Failed to find one or more bibliography files:\s*'(.+?)'", stdout
            )
            + re.findall(
                r"Missing input file: '`?(.+?)'", stdout
            )
        )
    )
    return proc, missing


def _collect(paper: Path) -> None:
    runs = 0

    while True:
        runs += 1
        proc, missing = _compile(dist(paper))
        if missing:
            for file in missing:
                src_file = src_dir(paper) / file
                dst_file = dist_dir(paper) / file
                if not src_file.exists():
                    for src_file in src_file.parent.glob(f"{src_file.name}.*"):
                        # file extension missing
                        if not src_file.is_file():
                            continue
                        dst_file = dst_file.with_name(src_file.name)
                        if not dst_file.exists():
                            break
                print(f"📄 Copy missing file {src_file.relative_to(src_dir(paper))}...")
                    
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_file, dst_file)
        else:
            print(f"✅ latexmk finished after {runs} iterations.")
            return


def _squash_comments(paper: Path) -> None:
    tex_files = list(dist_dir(paper).glob("**/*.tex"))
    print(f"🧹 Removing comments from {len(tex_files)} tex files...")
    total = 0
    for file in tex_files:
        contents = file.read_text()
        contents, n = re.subn(r"(?<!\\)((?:\\\\)*%).+", r"\1", contents)
        file.write_text(contents)
        total += n
    print(f"✅ Removed {total} comments.")


def _compare(a: Path, b: Path, tmpdir: Path) -> bool:
    print("🔍 Comparing PDFs for visual differences...")
    (tmpdir / "a").mkdir(parents=True, exist_ok=True)
    (tmpdir / "b").mkdir(parents=True, exist_ok=True)

    print(f"⚙️ Converting {a} to PNGs...")
    subprocess.run(["pdftoppm", "-png", a, tmpdir / "a" / "page"])
    print(f"⚙️ Converting {b} to PNGs...")
    subprocess.run(["pdftoppm", "-png", b, tmpdir / "b" / "page"])

    a_pages = sorted(list((tmpdir / "a").glob("*")))
    b_pages = sorted(list((tmpdir / "b").glob("*")))

    if len(a_pages) != len(b_pages):
        print(f"❗ {a} has {len(a_pages)} pages, {b} has {len(b_pages)} pages.")
        return False

    for i, (page_a, page_b) in enumerate(zip(a_pages, b_pages)):
        image_a = Image.open(page_a)
        image_b = Image.open(page_b)
        diff = ImageChops.difference(image_a, image_b)
        if image_a.size == image_b.size and diff.getbbox() is None:
            pass
        else:
            print(f"❗ Visual difference on page {i}!")
            return False

    print("✅ No visual differences found.")
    return True


if __name__ == "__main__":
    cli()
