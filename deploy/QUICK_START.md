# Quick Start - Deploy to AWS Lightsail

## 1. Create Lightsail Instance (5 minutes)
1. Go to https://lightsail.aws.amazon.com/
2. Create instance → Ubuntu 22.04 → $3.50 plan
3. Create and attach static IP
4. Open ports 80 and 443 in firewall

## 2. Deploy Application (10 minutes)
```bash
# Connect via browser SSH (click terminal icon)
# Then run:
git clone https://github.com/AI-Builder-Team/BrainLiftTracker.git twitter-manager
cd twitter-manager
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## 3. Configure (5 minutes)
```bash
# Edit environment
nano .env

# Add your values:
API_KEY=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
ENCRYPTION_KEY=<generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
TWITTER_CLIENT_ID=<from Twitter Developer Portal>
TWITTER_CLIENT_SECRET=<from Twitter Developer Portal>
TWITTER_CALLBACK_URL=http://YOUR-IP/auth/callback
```

## 4. Start Services
```bash
sudo systemctl restart twitter-manager
sudo systemctl restart nginx
```

## 5. Update Twitter App
Go to Twitter Developer Portal and update callback URL to:
- `http://YOUR-IP/auth/callback`
- Or: `http://YOUR-IP-WITH-DASHES.nip.io/auth/callback`

## 6. Test
```bash
# Get your IP
curl -4 icanhazip.com

# Test API
curl http://YOUR-IP/api/v1/health
```

## Your API is ready at:
- Base: `http://YOUR-IP/api/v1/`
- Docs: Check README.md for all endpoints

## Common Commands
```bash
# View logs
sudo journalctl -u twitter-manager -f

# Update app
cd ~/twitter-manager && ./update.sh

# Check status
sudo systemctl status twitter-manager nginx

# Manual backup
./deploy/backup.sh
```

## Troubleshooting
- **502 Error**: `sudo systemctl restart twitter-manager`
- **Can't connect**: Check IP and firewall rules
- **OAuth fails**: Verify callback URL matches exactly

Total deployment time: ~20 minutes