from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

import uvicorn

from agent import create_app
from config import AgentConfig, load_config
from launcher import ProcessAppLauncher

logger = logging.getLogger("pc_remote_tray")

CONFIG_PATH = Path(__file__).resolve().with_name("config.yaml")


class AgentTray:
    """Pilote demarrage/arret du serveur HTTP pc_remote depuis l'icone de la
    barre d'etat systeme.

    Ne depend pas de pystray/Pillow : ces imports sont differes dans main()
    et _make_icon_image(), pour que cette classe reste testable sans
    environnement graphique (pystray echoue au chargement du module des
    qu'aucun display/backend n'est disponible).
    """

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or load_config()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.running:
                return
            app = create_app(self.config, ProcessAppLauncher())
            uv_config = uvicorn.Config(
                app, host=self.config.host, port=self.config.port, log_level="warning"
            )
            server = uvicorn.Server(uv_config)

            def _run() -> None:
                try:
                    server.run()
                except Exception:
                    logger.exception("Le serveur pc_remote s'est arrete de facon inattendue")

            thread = threading.Thread(target=_run, daemon=True, name="pc_remote_http")
            self._server = server
            self._thread = thread
            thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            server, thread = self._server, self._thread
            self._server, self._thread = None, None
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=timeout)

    def status_text(self) -> str:
        state = "en cours" if self.running else "arrete"
        return f"Neron PC Remote ({state}) - {self.config.host}:{self.config.port}"

    def open_config(self) -> None:
        os.startfile(CONFIG_PATH)  # chemin fixe local, jamais d'entree utilisateur


def _make_icon_image(color: str):
    from PIL import Image, ImageDraw

    size = 64
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((6, 6, size - 6, size - 6), fill=color)
    return image


def main() -> None:
    import pystray

    COLOR_RUNNING = "#2ecc71"
    COLOR_STOPPED = "#95a5a6"

    agent = AgentTray()

    def _refresh_icon(icon: pystray.Icon) -> None:
        icon.icon = _make_icon_image(COLOR_RUNNING if agent.running else COLOR_STOPPED)
        icon.title = agent.status_text()

    def on_start(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        del item
        agent.start()
        _refresh_icon(icon)

    def on_stop(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        del item
        agent.stop()
        _refresh_icon(icon)

    def on_config(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        del icon, item
        try:
            agent.open_config()
        except OSError:
            logger.exception("Impossible d'ouvrir config.yaml")

    def on_quit(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        del item
        agent.stop()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: agent.status_text(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Demarrer", on_start, enabled=lambda item: not agent.running),
        pystray.MenuItem("Arreter", on_stop, enabled=lambda item: agent.running),
        pystray.MenuItem("Configurer (config.yaml)", on_config),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter", on_quit),
    )

    icon = pystray.Icon("neron_pc_remote", _make_icon_image(COLOR_STOPPED), "Neron PC Remote", menu)

    def setup(icon: pystray.Icon) -> None:
        icon.visible = True
        agent.start()
        _refresh_icon(icon)

    icon.run(setup=setup)


if __name__ == "__main__":
    main()
