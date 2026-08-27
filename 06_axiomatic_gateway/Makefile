.PHONY: test install run clean

PYTHON=D:\project\attachments\thinkingLLM\python311\tools\python.exe

install:
	$(PYTHON) -m pip install -r backend/requirements.txt

test:
	set PYTHONPATH=backend&& $(PYTHON) -m pytest backend/tests/ -v

run:
	set PYTHONPATH=backend&& $(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

clean:
	rmdir /s /q backend\app\__pycache__ 2>nul || exit 0
	rmdir /s /q backend\tests\__pycache__ 2>nul || exit 0
	rmdir /s /q .pytest_cache 2>nul || exit 0
