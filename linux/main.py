from __future__ import annotations

import uvicorn

from agent import create_app
from config import load_config
from launcher import ProcessAppLauncher


def main() -> None:
    config = load_config()
    app = create_app(config, ProcessAppLauncher())
    uvicorn.run(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
