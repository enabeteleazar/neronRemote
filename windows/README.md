# pc_remote — agent Windows

Petit serveur HTTP a installer sur le PC Windows a piloter depuis Neron.
Actions exposees : `open`, `close`, `list`, jamais une commande arbitraire —
mais **pas d'allowlist fermee** : toute application installee normalement
(trouvee via le registre App Paths ou un raccourci du Menu Demarrer) est
automatiquement ouvrable/fermable (voir `discovery.py`), a l'exception d'une
liste fixe de commandes destructrices (`cmd.exe`, `powershell.exe`,
`shutdown.exe`, `reg.exe`, `net.exe`, `sc.exe`, `taskkill.exe`...). Choix
delibere, a lire dans la section
[Securite](#securite-a-lire-avant-de-deployer) avant de deployer. Code tres
proche de l'agent Linux ([`../linux/`](../linux/README.md)) : meme protocole
HTTP, seule l'installation/le demarrage different (Planificateur de taches au
lieu de systemd) et la source d'auto-discovery (App Paths + Menu Demarrer au
lieu de `$PATH`).

Cote Neron (Linux), le module correspondant est
`server/integrations/pc_remote/` (client HTTP + tool `pc_remote` enregistre
dans `ToolRuntime`).

## Pre-requis

- Windows avec [Tailscale](https://tailscale.com) installe et connecte au
  meme tailnet que le serveur Neron.
- Python 3.11+.

## Installation

### En une commande (recommande)

Depuis PowerShell, sans rien cloner a la main — telecharge le repo, installe
Python via `winget` si besoin, cree le venv, installe les dependances et
scaffold `config.yaml` + le token dans `%LOCALAPPDATA%\NeronPcRemote` :

```powershell
irm https://raw.githubusercontent.com/enabeteleazar/neronRemote/main/windows/bootstrap.ps1 | iex
```

Cette commande n'active **pas** le demarrage automatique. Pour l'ajouter
ensuite :

```powershell
cd $env:LOCALAPPDATA\NeronPcRemote
powershell -ExecutionPolicy Bypass -File install.ps1 -InstallScheduledTask
```

(voir [Lancer au demarrage](#lancer-au-demarrage)).

### Depuis un clone local

Si vous avez deja ce repo en local (`install.ps1` + `config.example.yaml`
a cote), venv + dependances + `config.yaml` + token en une commande :

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
# Ajoutez -InstallScheduledTask pour aussi creer la tache planifiee au demarrage
```

Ou manuellement :

```powershell
py -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config.example.yaml config.yaml
```

Editez `config.yaml` :
- `host` : l'IP Tailscale de cette machine (`tailscale ip -4`), **jamais**
  `0.0.0.0`.
- `apps` : optionnel, uniquement pour forcer un `path`/`process_name` precis
  ou ajouter une app absente d'App Paths et du Menu Demarrer (voir
  `config.example.yaml`). L'auto-discovery couvre le reste.

Si vous n'avez pas utilise `install.ps1`, generez un token et exportez-le
(ne jamais le mettre dans `config.yaml`) :

```powershell
$env:PC_AGENT_TOKEN = [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()
```

Notez ce token (celui affiche par `install.ps1`, ou celui genere ci-dessus) :
c'est la valeur a renseigner cote Neron dans `secrets.env`
(`PC_REMOTE_<DEVICE_ID>_TOKEN`, voir `neron.yaml: pc_remote.devices`).

## Lancer l'agent

Avec une icone dans la barre d'etat systeme (recommande) :

```powershell
venv\Scripts\pythonw.exe tray.py
```

`pythonw.exe` (pas `python.exe`) evite l'ouverture d'une fenetre de console :
l'icone est le seul point de controle. Clic droit sur l'icone :
- **Demarrer** / **Arreter** : controle le serveur HTTP sans redemarrer tout
  le processus (utile pour couper temporairement l'acces sans desinstaller).
- **Configurer (config.yaml)** : ouvre le fichier avec l'editeur par defaut.
- **Quitter** : arrete le serveur et ferme l'icone.

L'icone est verte quand le serveur repond, grise quand il est arrete ; le
survol affiche l'etat et `host:port` actuels.

Sans interface (arriere-plan pur, utile pour du debug en console) :

```powershell
python main.py
```

## Lancer au demarrage

`install.ps1 -InstallScheduledTask` cree directement la tache planifiee
"NeronPcRemoteAgent" declenchee a l'ouverture de session, qui lance
`tray.py` via `pythonw.exe` (icone barre d'etat, pas de console).

Manuellement, utilisez le Planificateur de taches Windows, **"Executer
uniquement si l'utilisateur est connecte"** (pas "que l'utilisateur soit
connecte ou non") : un agent lance en tant que service SYSTEM ne peut pas
afficher d'application graphique dans la session bureau. C'est une
contrainte Windows, pas un choix de design de cet agent.

Definissez `PC_AGENT_TOKEN` comme variable d'environnement utilisateur
(Parametres systeme > Variables d'environnement), pas dans le script de
tache planifiee en clair.

## Securite (a lire avant de deployer)

**Plus d'allowlist fermee** : toute application trouvee via App Paths ou le
Menu Demarrer au moment de la requete devient ouvrable/fermable — choix
assume pour eviter la curation manuelle app par app, au prix d'une surface
d'attaque qui grandit avec chaque logiciel installe sur la machine.

- Seul garde-fou cote agent : `discovery.DANGEROUS_NAMES` exclut en dur les
  commandes destructrices/irreversibles connues (`cmd.exe`, `powershell.exe`,
  `shutdown.exe`, `reg.exe`, `net.exe`, `sc.exe`, `taskkill.exe`,
  `msiexec.exe`...), plus toute cible dont le nom contient `uninst`. Cette
  liste n'est **pas** configurable depuis `config.yaml` — modifiez
  `discovery.py` si vous devez l'etendre, et mesurez l'impact avant de la
  reduire.
- **Ne jamais** binder sur `0.0.0.0` : ce port doit n'etre joignable que via
  le tailnet. Utilisez en plus les [ACL Tailscale](https://tailscale.com/kb/1018/acls)
  pour restreindre precisement quelle machine peut atteindre ce port — avec
  l'auto-discovery, une fuite du token ou une ACL trop large expose bien plus
  qu'avec l'ancien modele a allowlist.
- Le token est compare en temps constant (`hmac.compare_digest`) mais reste
  un secret statique : pas de rotation automatique dans ce squelette. A
  roter manuellement si vous soupconnez une fuite.
- `close` termine (`SIGTERM` puis `SIGKILL` apres 3s) **tous** les process
  dont le nom correspond exactement a `process_name` — DANGEROUS_NAMES ne
  protege que les commandes qu'il liste explicitement, pas tout processus
  systeme sensible qui pourrait porter un autre nom (`explorer.exe`, etc.).
- Faites tourner l'agent sous une session utilisateur standard, sans
  privileges administrateur : c'est desormais la **principale** barriere
  contre un abus de l'auto-discovery (l'agent ne peut lancer/tuer que ce que
  cet utilisateur pourrait lancer/tuer lui-meme).
- Limites connues de ce squelette, a durcir avant un usage plus large :
  pas de limite de debit (rate limiting), pas de rotation de token, pas de
  TLS applicatif (on s'appuie sur le chiffrement WireGuard de Tailscale).

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```
