import subprocess
import click
import shutil
import re
import shlex
import sys
from pathlib import Path
from PIL import Image
from PIL import ImageChops
from typing import List, Tuple

here = Path(__file__).parent


def dist_dir(paper: Path) -> Path:
    return paper.parent / "dist"


def src_dir(paper: Path) -> Path:
    return paper.parent


def dist(paper: Path) -> Path:
    return dist_dir(paper) / paper.name


paper_argument = click.argument('paper', default="paper.tex", type=lambda x: Path(x).resolve())


class NaturalOrderGroup(click.Group):
    def list_commands(self, ctx):
        return self.commands.keys()


@click.group(cls=NaturalOrderGroup)
def cli():
    pass


@cli.command()
@paper_argument
@click.option('--clean/--no-clean', default=False)
def run(paper, clean):
    """Run all commands in order."""
    if clean and dist_dir(paper).exists():
        print(f"🗑 Removing {dist_dir(paper)}...")
        shutil.rmtree(dist_dir(paper))

    _init(paper)
    _collect(paper)
    _squash_comments(paper)
    proc, _ = _compile(dist(paper))
    shutil.rmtree(dist_dir(paper) / ".aux" / "diff", ignore_errors=True)
    ok = _compare(
        paper.with_suffix(".pdf"),
        dist(paper).with_suffix(".pdf"),
        dist_dir(paper) / ".aux" / "diff"
    )

    if not ok:
        print("📋 latexmk stdout")
        print(proc.stdout)
        print("📋 latexmk stderr")
        print(proc.stderr)
        print("❗ Failed.")


@cli.command()
@paper_argument
def init(paper):
    """1) Initialize distribution folder."""
    _init(paper)


@cli.command()
@paper_argument
def collect(paper):
    """2) Collect all files."""
    _collect(paper)


@cli.command()
@paper_argument
def squash_comments(paper):
    """3) Squash all comments"""
    _squash_comments(paper)


@cli.command()
@paper_argument
def compile(paper):
    """4) Compile the distribution."""
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


@cli.command()
@paper_argument
@click.option('--src', 'srcfile', type=click.Path(exists=True), help="override source pdf")
@click.option('--dist', 'distfile', type=click.Path(exists=True), help="override dist pdf")
@click.option("--tmpdir", help="override page image directory")
def compare(paper, srcfile, distfile, tmpdir):
    """5) Visually compare PDFs"""
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
        tmpdir = dist_dir(paper) / ".aux" / "diff"

    if tmpdir.exists():
        if tmpdir != dist_dir(paper) / ".aux" / "diff":
            click.confirm(f"Temporary directory {tmpdir} already exists. Delete contents?", abort=True)
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
        f"-aux-directory=.aux",
        str(paper)
    ]
    print(f"🔨 Running {shlex.join(cmd)}...")
    proc = subprocess.run(cmd, cwd=paper.parent, capture_output=True, text=True)

    # newlines may be anywhere in file paths, so we strip them.
    stdout = (proc.stdout + proc.stderr).replace("\n", "")
    missing = sorted(set(
        re.findall(r"LaTeX (?:Error|Warning): File `(.+?)' ?not ?found", stdout)
        + re.findall(r"Failed to find one or more bibliography files:\s*'(.+?)'", stdout)
    ))
    return proc, missing


def _collect(paper: Path) -> None:
    runs = 0
    while True:
        runs += 1
        proc, missing = _compile(dist(paper))
        if missing:
            for file in missing:
                print(f"📄 Copy missing file {file}...")
                (dist_dir(paper) / file).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_dir(paper) / file, dist_dir(paper) / file)
        else:
            log_dir = dist_dir(paper) / ".aux"
            (log_dir / "latexmk-stdout.txt").write_text(proc.stdout)
            (log_dir / "latexmk-stderr.txt").write_text(proc.stderr)
            print(f"✅ latexmk finished after {runs} iterations (logs at {log_dir}).")
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
            print("❗ Visual difference on page {i}!")
            return False

    print("✅ No visual differences found.")
    return True


if __name__ == '__main__':
    cli()
