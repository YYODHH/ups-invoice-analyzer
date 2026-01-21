"""UPS Invoice Analyzer - CLI Entry Point.

Use this to launch the Streamlit dashboard or run analysis from command line.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Launch the Streamlit dashboard."""
    app_path = Path(__file__).parent / "app.py"

    print("🚀 Starting UPS Invoice Analyzer...")
    print("   Opening dashboard in your browser...")
    print("   Press Ctrl+C to stop the server\n")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.headless",
            "true",
        ]
    )


if __name__ == "__main__":
    main()
