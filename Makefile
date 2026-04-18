VENV := .venv
BIN := $(VENV)/bin

.PHONY: dev install clean uninstall

$(VENV):
	python3 -m venv $(VENV)

dev: $(VENV)
	$(BIN)/pip install -e .
	ln -sf $(CURDIR)/$(BIN)/appimage-install ~/.local/bin/appimage-install

install: $(VENV)
	$(BIN)/pip install .
	ln -sf $(CURDIR)/$(BIN)/appimage-install ~/.local/bin/appimage-install

uninstall:
	rm -f ~/.local/bin/appimage-install
	$(BIN)/pip uninstall -y appimage-install 2>/dev/null || true

clean:
	rm -rf $(VENV) build/ dist/ *.egg-info src/*.egg-info
	rm -f ~/.local/bin/appimage-install
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
