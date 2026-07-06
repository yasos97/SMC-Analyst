# Déploiement de SalamaIQ sur un VPS (Ubuntu/Debian)

Guide pas-à-pas pour mettre SalamaIQ en production derrière **nginx + HTTPS**,
servi par **gunicorn** et géré par **systemd**.

Hypothèses : VPS Ubuntu 22.04+, un nom de domaine pointant (enregistrement A)
vers l'IP du VPS, accès `sudo`. On installe l'app dans `/opt/salamaiq`.

---

## 1. Préparer le serveur

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip nginx git
# Utilisateur dédié (sans login shell)
sudo useradd --system --create-home --home-dir /opt/salamaiq --shell /usr/sbin/nologin salamaiq
```

## 2. Déposer le code

```bash
# Option A : git clone   |   Option B : scp/rsync depuis votre PC
sudo -u salamaiq git clone <URL_DU_REPO> /opt/salamaiq
cd /opt/salamaiq
```

## 3. Environnement Python

```bash
sudo -u salamaiq python3 -m venv /opt/salamaiq/.venv
sudo -u salamaiq /opt/salamaiq/.venv/bin/pip install -r requirements.txt
```

## 4. Configurer le `.env` (IMPORTANT)

Copier le modèle et renseigner des valeurs RÉELLES :

```bash
sudo -u salamaiq cp .env.example .env
sudo -u salamaiq nano .env
```

Générer des secrets forts :

```bash
# Clé secrète Flask
python3 -c "import secrets;print(secrets.token_hex(32))"
# Secret 2FA (TOTP) — à enrôler dans Google Authenticator
python3 -c "import pyotp;print(pyotp.random_base32())"
```

Vérifier que `FLASK_DEBUG=0` et `FLASK_ENV=production`.
Protéger le fichier : `sudo chmod 600 .env && sudo chown salamaiq:salamaiq .env`

### Enrôler le 2FA
Après avoir fixé `TOTP_SECRET`, générer le QR à scanner une fois :

```bash
python3 -c "import pyotp,qrcode; uri=pyotp.TOTP('VOTRE_TOTP_SECRET').provisioning_uri(name='Analyste',issuer_name='SalamaIQ'); qrcode.make(uri).save('totp_enrollment_qr.png'); print(uri)"
```

Scanner `totp_enrollment_qr.png` avec l'app d'authentification, puis **supprimer** le PNG.

## 5. Test rapide avant systemd

```bash
sudo -u salamaiq /opt/salamaiq/.venv/bin/gunicorn -c gunicorn.conf.py app:app
# Ctrl+C pour arrêter. (curl http://127.0.0.1:8000/login doit répondre 200)
```

## 6. Service systemd

```bash
sudo cp deploy/salamaiq.service /etc/systemd/system/salamaiq.service
# Adapter User/WorkingDirectory si besoin, puis :
sudo systemctl daemon-reload
sudo systemctl enable --now salamaiq
sudo systemctl status salamaiq      # doit être "active (running)"
sudo journalctl -u salamaiq -f      # voir les logs
```

## 7. nginx (reverse proxy)

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/salamaiq
sudo sed -i 's/mondomaine.com/VOTRE_DOMAINE/g' /etc/nginx/sites-available/salamaiq
sudo ln -s /etc/nginx/sites-available/salamaiq /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 8. HTTPS avec Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d VOTRE_DOMAINE -d www.VOTRE_DOMAINE
# Renouvellement auto déjà configuré ; test :
sudo certbot renew --dry-run
```

## 9. Pare-feu (recommandé)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

## Mises à jour ultérieures

```bash
cd /opt/salamaiq
sudo -u salamaiq git pull
sudo -u salamaiq /opt/salamaiq/.venv/bin/pip install -r requirements.txt
sudo systemctl restart salamaiq
```

## Sauvegardes

La base SQLite est dans `instance/salama_iq.db`. Sauvegarde simple via cron :

```bash
0 2 * * * cp /opt/salamaiq/instance/salama_iq.db /opt/salamaiq/backups/salama_$(date +\%F).db
```

## Passer à PostgreSQL (si plusieurs utilisateurs simultanés)

1. `sudo apt install -y postgresql && sudo -u postgres createdb salamaiq`
2. `pip install psycopg2-binary`
3. Dans `.env` : `DATABASE_URL=postgresql://user:password@localhost:5432/salamaiq`
4. `sudo systemctl restart salamaiq` (les tables se créent au démarrage).

---

## Checklist sécurité avant ouverture au public

- [ ] `.env` rempli, `chmod 600`, **jamais** committé
- [ ] `FLASK_DEBUG=0`
- [ ] `ADMIN_PASSWORD` fort + `TOTP_SECRET` fixe enrôlé
- [ ] `FLASK_SECRET_KEY` aléatoire (32 octets)
- [ ] HTTPS actif (certbot) + redirection 80→443
- [ ] Pare-feu UFW activé
- [ ] Clé `OPENROUTER_API_KEY` régénérée (l'ancienne a été exposée)
- [ ] Sauvegarde de la base planifiée
