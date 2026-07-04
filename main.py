#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qtine - A modular chatbot framework
Entry point
"""

import sys
import os
import signal

# Ensure the project and project-local dependencies are importable.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, ".deps"))

from qtine.core.app import QtineApp


def main():
    app = QtineApp()

    def shutdown_handler(sig, frame):
        app.logger.info("Received shutdown signal, gracefully stopping...")
        app.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        app.run()
    except KeyboardInterrupt:
        app.shutdown()
    except Exception as e:
        app.logger.error(f"Fatal error: {e}")
        app.shutdown()
        sys.exit(1)


if __name__ == "__main__":
    main()
