.PHONY: build serve clean build-cats

build:
	cd sample-knowledge && ../bin/docweave

serve:
	cd sample-knowledge && ../bin/docweave && python3 -m http.server -d .site 8000

build-cats:
	cd sample-cats && ../bin/docweave

clean:
	rm -rf sample-knowledge/.site/* sample-cats/.site/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true