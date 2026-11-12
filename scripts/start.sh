#!/usr/bin/env sh
set -eu
project_directory=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_executable=${RAG_PYTHON_EXECUTABLE:-"$project_directory/.venv/bin/python"}
if [ ! -x "$python_executable" ]; then
    echo "Python environment not found. Follow README setup or set RAG_PYTHON_EXECUTABLE." >&2
    exit 1
fi
cd "$project_directory/backend"
exec "$python_executable" -m app
