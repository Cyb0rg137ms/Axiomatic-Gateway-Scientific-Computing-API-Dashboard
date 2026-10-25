"""Back-compat entry point; see ``python -m app bench``."""

from app.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["bench", *__import__("sys").argv[1:]]))
