.PHONY: build serve clean

build:
	cd sample-cats && python3 ../build.py

serve:
	cd sample-cats && python3 ../build.py && python3 -m http.server -d .site 8000

clean:
	rm -rf sample-cats/.site/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true