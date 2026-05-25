.PHONY: build serve clean

build:
	cd sample-cats && ../bin/docweave

serve:
	cd sample-cats && ../bin/docweave && python3 -m http.server -d .site 8000

clean:
	rm -rf sample-cats/.site/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true