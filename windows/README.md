# pc_remote — agent Windows

Petit serveur HTTP a installer sur le PC Windows a piloter depuis Neron. Il
n'expose qu'une allowlist fermee d'actions (`open`, `close`, `list`) sur des
applications explicitement declarees dans `config.yaml` — jamais une commande
arbitraire.

Cote Neron (Linux), le module correspondant est
`server/integrations/pc_remote/` (client HTTP + tool `pc_remote` enregistre
dans `ToolRuntime`).

## Pre-requis

- Windows avec [Tailscale](https://tailscale.com) installe et connecte au
  meme tailnet que le serveur Neron.
- Python 3.11+.

## Installation

Rapide, via le script d'installation (venv + dependances + `config.yaml` +
token genere automatiquement) :

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
- `apps` : une entree par application autorisee, avec un `path` absolu et le
  `process_name` exact tel qu'il apparait dans le gestionnaire des taches.

Si vous n'avez pas utilise `install.ps1`, generez un token et exportez-le
(ne jamais le mettre dans `config.yaml`) :

```powershell
$env:PC_AGENT_TOKEN = [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()
```

Notez ce token (celui affiche par `install.ps1`, ou celui genere ci-dessus) :
c'est la valeur a renseigner cote Neron dans `secrets.env`
(`PC_REMOTE_<DEVICE_ID>_TOKEN`, voir `neron.yaml: pc_remote.devices`).

## Lancer l'agent

```powershell
python main.py
```

## Lancer au demarrage

`install.ps1 -InstallScheduledTask` cree directement la tache planifiee
"NeronPcRemoteAgent" declenchee a l'ouverture de session.

Manuellement, utilisez le Planificateur de taches Windows, **"Executer
uniquement si l'utilisateur est connecte"** (pas "que l'utilisateur soit
connecte ou non") : un agent lance en tant que service SYSTEM ne peut pas
afficher d'application graphique dans la session bureau. C'est une
contrainte Windows, pas un choix de design de cet agent.

Definissez `PC_AGENT_TOKEN` comme variable d'environnement utilisateur
(Parametres systeme > Variables d'environnement), pas dans le script de
tache planifiee en clair.

## Securite (a lire avant de deployer)

- **Ne jamais** binder sur `0.0.0.0` : ce port doit n'etre joignable que via
  le tailnet. Utilisez en plus les [ACL Tailscale](https://tailscale.com/kb/1018/acls)
  pour restreindre precisement quelle machine peut atteindre ce port.
- L'allowlist (`config.yaml`) est la seule frontiere de securite reelle :
  n'ajoutez jamais une entree dont le `path` ou les `args` pourraient etre
  influences par une entree externe.
- Le token est compare en temps constant (`hmac.compare_digest`) mais reste
  un secret statique : pas de rotation automatique dans ce squelette. A
  roter manuellement si vous soupconnez une fuite.
- `close` termine (`SIGTERM` puis `SIGKILL` apres 3s) **tous** les process
  dont le nom correspond exactement a `process_name` — verifiez qu'aucune
  entree de l'allowlist ne pointe vers un processus systeme critique
  (explorer.exe, etc.).
- Limites connues de ce squelette, a durcir avant un usage plus large :
  pas de limite de debit (rate limiting), pas de rotation de token, pas de
  TLS applicatif (on s'appuie sur le chiffrement WireGuard de Tailscale).

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```
