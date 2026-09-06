.PHONY: pdf compile follow wordcount clean

pdf:
	latexmk -pdf -bibtex root.tex

compile: pdf

follow:
	latexmk -pvc -pdf -bibtex -pdflatex="pdflatex --shell-escape %O %S" root.tex

wordcount:
	texcount -utf8 -total -sum root.tex

clean:
	latexmk -c root.tex
