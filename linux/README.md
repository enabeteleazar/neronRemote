# pc_remote — agent Linux (Ubuntu)

Petit serveur HTTP a installer sur la machine Ubuntu a piloter depuis Neron.
Actions exposees : `open`, `close`, `list`, jamais une commande arbitraire —
mais **pas d'allowlist fermee** : tout binaire executable trouve sur `$PATH`
est automatiquement ouvrable/fermable (voir `discovery.py`), a l'exception
d'une liste fixe de commandes destructrices (`shutdown`, `rm`, `systemctl`,
`passwd`, `sudo`...). Choix delibere, a lire dans la section
[Securite](#securite-a-lire-avant-de-deployer) avant de deployer. Code tres
proche de l'agent Windows ([`../windows/`](../windows/README.md)) : meme
protocole HTTP, seule l'installation/le demarrage different (systemd au lieu
du Planificateur de taches) et la source d'auto-discovery (`$PATH` au lieu
d'App Paths + Menu Demarrer).

Cote Neron, le module correspondant est `server/integrations/pc_remote/`
(client HTTP + tool `pc_remote` enregistre dans `ToolRuntime`), partage avec
l'agent Windows.

## Pre-requis

- Ubuntu avec [Tailscale](https://tailscale.com) installe et connecte au
  meme tailnet que le serveur Neron.
- Python 3.11+.

## Installation

### En une commande (recommande)

Sans rien cloner a la main — telecharge le repo, installe `python3`/`venv`
via `apt` si besoin, cree le venv, installe les dependances et scaffold
`config.yaml` + le token dans `~/NeronPcRemote` :

```bash
curl -fsSL https://raw.githubusercontent.com/enabeteleazar/neronRemote/main/linux/bootstrap.sh | bash
```

Dossier d'installation personnalisable : `INSTALL_DIR=/opt/neron-pc-remote curl -fsSL .../bootstrap.sh | bash`.

Cette commande n'active **pas** le demarrage automatique. Pour l'ajouter
ensuite :

```bash
cd ~/NeronPcRemote && ./install.sh --install-service
```

(voir [Lancer au demarrage](#lancer-au-demarrage-systemd)).

### Depuis un clone local

Si vous avez deja ce repo en local (`install.sh` + `config.example.yaml` a
cote), venv + dependances + `config.yaml` + token + lancement de l'agent en
une seule commande :

```bash
./install.sh
```

Par defaut, une fois tout pret, `install.sh` lance directement l'agent en
premier plan (`./run.sh`) : la commande occupe le terminal, `Ctrl+C` pour
arreter. Variantes :

```bash
./install.sh --no-run           # tout preparer sans lancer l'agent
./install.sh --install-service  # installer et activer le service systemd (deja en arriere-plan, pas de lancement en premier plan)
```

Ou manuellement :

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Editez `config.yaml` :
- `host` : l'IP Tailscale de cette machine (`tailscale ip -4`), **jamais**
  `0.0.0.0`.
- `apps` (optionnel) : uniquement pour forcer un `path`/`process_name`
  precis, ou ajouter un script hors `$PATH` (`/opt/scripts/backup.sh`).
  Tout le reste est auto-decouvert, rien a declarer.

Un serveur Ubuntu est le plus souvent headless : les binaires auto-decouverts
sont surtout des outils CLI, pas des applications graphiques. Piloter une
appli graphique exige une session X11/Wayland active avec
`DISPLAY`/`XAUTHORITY` exportes pour le process qui lance l'agent.

Si vous n'avez pas utilise `install.sh`, generez un token (ne jamais le
mettre dans `config.yaml`) et exportez-le pour un lancement manuel :

```bash
export PC_AGENT_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
```

Notez ce token (celui ecrit par `install.sh` dans `pc-remote-agent.env`, ou
celui genere ci-dessus) : c'est la valeur a renseigner cote Neron dans
`secrets.env` (`PC_REMOTE_<DEVICE_ID>_TOKEN`, voir `neron.yaml:
pc_remote.devices`).

## Lancer l'agent

`./install.sh` (sans `--no-run`/`--install-service`) le fait deja
automatiquement. Pour le relancer plus tard :

```bash
./run.sh
```

`run.sh` charge `PC_AGENT_TOKEN` depuis `pc-remote-agent.env` (ecrit par
`install.sh`/`bootstrap.sh`) puis lance `main.py` — contrairement a
systemd (`EnvironmentFile=`), un `python main.py` direct ne lit pas ce
fichier tout seul. Si vous preferez gerer le token vous-meme :

```bash
export PC_AGENT_TOKEN=...  # ou : source venv/bin/activate
venv/bin/python main.py
```

## Lancer au demarrage (systemd)

`./install.sh --install-service` installe et active directement l'unite
systemd `pc-remote-agent` (sudo requis pour la copie dans
`/etc/systemd/system` et `daemon-reload`).

Manuellement : copiez `pc-remote-agent.service.example` vers
`/etc/systemd/system/pc-remote-agent.service`, adaptez
`WorkingDirectory`/`ExecStart`/`User`, puis :

```bash
sudo cp pc-remote-agent.service.example /etc/systemd/system/pc-remote-agent.service
# creez pc-remote-agent.env avec PC_AGENT_TOKEN=... (chmod 600)
sudo systemctl daemon-reload
sudo systemctl enable --now pc-remote-agent
```

`PC_AGENT_TOKEN` doit venir d'un `EnvironmentFile` prive (permissions `600`,
proprietaire du service uniquement), jamais du fichier `.service` en clair.

## Securite (a lire avant de deployer)

**Changement de modele par rapport a l'agent Windows** : plus d'allowlist
fermee. Tout binaire executable present sur `$PATH` au moment de la requete
devient ouvrable/fermable — choix assume pour eviter la curation manuelle
app par app, au prix d'une surface d'attaque qui grandit avec chaque logiciel
installe sur la machine.

- Seul garde-fou cote agent : `discovery.DANGEROUS_NAMES` exclut en dur les
  commandes destructrices/irreversibles connues (`shutdown`, `reboot`, `rm`,
  `mkfs`, `dd`, `passwd`, `useradd`, `sudo`, `su`, `iptables`, `systemctl`,
  `kill`, `mount`...). Cette liste n'est **pas** configurable depuis
  `config.yaml` — modifiez `discovery.py` si vous devez l'etendre, et
  mesurez l'impact avant de la reduire.
- **Ne jamais** binder sur `0.0.0.0` : ce port doit n'etre joignable que via
  le tailnet. Utilisez en plus les [ACL Tailscale](https://tailscale.com/kb/1018/acls)
  pour restreindre precisement quelle machine peut atteindre ce port — avec
  l'auto-discovery, une fuite du token ou une ACL trop large expose bien
  plus qu'avec l'ancien modele a allowlist.
- Le token est compare en temps constant (`hmac.compare_digest`) mais reste
  un secret statique : pas de rotation automatique dans ce squelette. A
  roter manuellement si vous soupconnez une fuite.
- `close` termine (`SIGTERM` puis `SIGKILL` apres 3s) **tous** les process
  dont le nom correspond exactement a `process_name` — DANGEROUS_NAMES ne
  protege que les commandes qu'il liste explicitement, pas tout processus
  systeme sensible qui pourrait porter un autre nom.
- Faites tourner l'agent sous un utilisateur dedie sans privileges `sudo` :
  c'est desormais la **principale** barriere contre un abus de
  l'auto-discovery (l'agent ne peut lancer/tuer que ce que cet utilisateur
  pourrait lancer/tuer lui-meme).
- Limites connues de ce squelette, a durcir avant un usage plus large :
  pas de limite de debit (rate limiting), pas de rotation de token, pas de
  TLS applicatif (on s'appuie sur le chiffrement WireGuard de Tailscale).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```
