\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{standalonefigure}[2021/01/29 Standalone Figure]

\newif\if@twocolumn\@twocolumnfalse
\DeclareOption{twocolumn}{\@twocolumntrue}

\DeclareOption*{\PackageWarning{standalonefigure}{Unknown ‘\CurrentOption’}}
\ProcessOptions\relax

\if@twocolumn
	\LoadClass[varwidth=483.6967pt,class=article,USenglish,oneside,twocolumn]{standalone}
\else
	\LoadClass[varwidth=236.1578pt,class=article,USenglish,oneside,twocolumn]{standalone}
\fi

\input{common}
