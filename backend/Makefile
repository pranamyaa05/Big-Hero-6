.PHONY: install run test export docker
install:        ; pip install -r requirements-dev.txt
run:            ; uvicorn app.main:app --reload --port 8000
test:           ; python -m pytest -q
export:         ; python -m app.cli export-all -o out
docker:         ; docker build -t reform3d .
