#!/bin/zsh

exec /usr/bin/env python3 "${0:A:h}/workflow.py" --web "$@"
