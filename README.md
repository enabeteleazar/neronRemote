# neronRemote

Agents de controle a distance pour Neron : ouvrir/fermer des applications et
lister leur etat sur une machine distante, via un agent HTTP minimal deploye
sur cette machine et pilote depuis Neron par le tool `pc_remote`
(`server/integrations/pc_remote/` dans le repo principal
[neronOS](https://github.com/enabeteleazar/neronOS)).

Aucune commande arbitraire n'est jamais executee : chaque agent n'expose
qu'une allowlist fermee d'actions (`open`, `close`, `list`) sur des
applications explicitement declarees dans son `config.yaml`.

## Installation rapide

Windows, en une commande PowerShell (telecharge et installe tout, voir
[`windows/README.md`](windows/README.md#installation)) :

```powershell
irm https://raw.githubusercontent.com/enabeteleazar/neronRemote/main/windows/bootstrap.ps1 | iex
```

Linux, apres avoir clone ce repo (voir [`linux/README.md`](linux/README.md#installation)) :

```bash
cd linux && ./install.sh
```

## Contenu

- [`windows/`](windows/README.md) — agent pour PC Windows.
- [`linux/`](linux/README.md) — agent pour serveur Ubuntu.

Les deux exposent le meme protocole HTTP (voir les README respectifs pour
l'installation, la securite et les tests) ; seules l'installation et les
options de demarrage automatique different selon l'OS.
