#!/bin/bash
cd "$(dirname "$0")" || exit
export PATH="/opt/homebrew/bin:$PATH"
/opt/homebrew/bin/uv run python main.py --monitor dexterityboost
