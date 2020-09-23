## LaTeX Paper Template

This is Max's LaTeX paper template.

 - `paper.tex` is the main document.
 - The `fig` directory contains all figures as individual TeX files. Most importantly, figures and tables can be compiled separately, which is much faster.
 - The `data` directory contains all data files, i.e. TeX files that contain plot lines, define commands for some key statistics, etc. This often is just a symlink to your "research code" (a hodgepodge of code, jupyter notebooks, and .tex files generated by them). The idea is that you re-run your analysis, which updates the data files, which automatically updates your paper.
 - `publish.py` is a Python script that copies your paper to `dist/`, copies over all files that are actually included, strips all TeX comments, and verifies that the artifact compiled from that is a pixel-perfect copy.


### Why do you do X?

#### `paper.tex`

```latex
% !TeX TXS-program:compile = txs:///pdflatex/[--shell-escape]
```

This magic comment tells TeXstudio (and some other editors) to run pdflatex with `--shell-escape`, which is necessary for some packages. Having this here doesn't require everyone to reconfigure their editor.

```latex
\documentclass[sigconf,nonacm]{acmart}
```

Replace this with the document style wanted by your publication venue.

```latex
\usepackage{standalone}
```

This template uses the [standalone](https://ctan.org/pkg/standalone) package to include figures from seperate files. You probably want to read the documentation at some point, it's really excellent. In a nutshell, `standalone` redefines the `\input` command, which now swallows the preamble of each subdocument. This allows subdocuments to stand on their own.


```latex
\providecommand{\paperroot}{.}
```

This sets the root directory of the paper, which can be used to reference data files in figures (`\input{\paperroot/data/data.tex}`). We need this so that figures can be compiled both individually (with `..` as the root directory) and as part of the main document (with `.` as the root directory).

```latex
Column Width: \the\columnwidth\\
Text Width: \the\textwidth
```

This prints the single column/double column widths for your documentclass, which then need to be hardcoded in each figure's preamble (see below).

#### `fig/figure.tex`

```latex
\documentclass[varwidth=241.14749pt,class=acmart,sigconf,nonacm]{standalone}
%\documentclass[varwidth=506.295pt,class=acmart,sigconf,nonacm]{standalone}
\input{common}
\begin{document}
```

The first four lines are the same for all figures. **You must adjust the first two lines to match your main document's `documentclass`.** First, hardcode the document width to the width of a single/double column when compiled in standalone mode (see above). Second, set `class=` to your main document's style and also pass all options. This ensures that your figures use the same widths and font styles when compiled individually.

If you want to create a double-column figure, comment out the first line, uncomment the second, and swap `figure` with `figure*`.