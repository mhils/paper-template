import random

with open("data2.tex", "w") as f:
	f.write("\\providecommand{\\samplesize}{%d}" % random.randint(1,3))
