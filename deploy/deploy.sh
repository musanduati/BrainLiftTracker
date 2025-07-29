#!/bin/bash
# Twitter Manager Deployment Script for AWS Lightsail
# This script sets up the application on a fresh Ubuntu instance

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="twitter-manager"
APP_USER="ubuntu"
APP_DIR="/home/$APP_USER/$APP_NAME"
REPO_URL="https://github.com/AI-Builder-Team/BrainLiftTracker.git"
PYTHON_VERSION="python3"

echo -e "${GREEN}Starting Twitter Manager deployment...${NC}"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Update system
echo -e "${YELLOW}Step 1: Updating system packages...${NC}"
sudo apt update
sudo apt upgrade -y

# Step 2: Install required packages
echo -e "${YELLOW}Step 2: Installing required packages...${NC}"
sudo apt install -y \
    $PYTHON_VERSION \
    $PYTHON_VERSION-pip \
    $PYTHON_VERSION-venv \
    nginx \
    git \
    sqlite3 \
    supervisor \
    certbot \
    python3-certbot-nginx \
    htop \
    ufw

# Step 3: Configure firewall
echo -e "${YELLOW}Step 3: Configuring firewall...${NC}"
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable

# Step 4: Clone repository
echo -e "${YELLOW}Step 4: Cloning repository...${NC}"
cd /home/$APP_USER
if [ -d "$APP_NAME" ]; then
    echo "Directory exists, pulling latest changes..."
    cd $APP_NAME
    git pull
else
    git clone $REPO_URL $APP_NAME
    cd $APP_NAME
fi

# Step 5: Create Python virtual environment
echo -e "${YELLOW}Step 5: Setting up Python environment...${NC}"
$PYTHON_VERSION -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install wheel
pip install -r requirements.txt
pip install gunicorn

# Step 6: Create necessary directories
echo -e "${YELLOW}Step 6: Creating application directories...${NC}"
mkdir -p instance
mkdir -p logs
mkdir -p backups

# Set permissions
sudo chown -R $APP_USER:$APP_USER $APP_DIR

# Step 7: Create environment file
echo -e "${YELLOW}Step 7: Setting up environment configuration...${NC}"
if [ ! -f .env ]; then
    cp deploy/.env.production .env
    echo -e "${RED}IMPORTANT: Edit .env file with your actual values!${NC}"
    echo "Run: nano $APP_DIR/.env"
fi

# Step 8: Configure Gunicorn
echo -e "${YELLOW}Step 8: Configuring Gunicorn...${NC}"
sudo cp deploy/gunicorn.service /etc/systemd/system/twitter-manager.service
sudo systemctl daemon-reload
sudo systemctl enable twitter-manager
sudo systemctl start twitter-manager

# Step 9: Configure Nginx
echo -e "${YELLOW}Step 9: Configuring Nginx...${NC}"
sudo cp deploy/nginx.conf /etc/nginx/sites-available/twitter-manager
sudo ln -sf /etc/nginx/sites-available/twitter-manager /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

# Step 10: Set up automatic backups
echo -e "${YELLOW}Step 10: Setting up automatic backups...${NC}"
chmod +x deploy/backup.sh
(crontab -l 2>/dev/null; echo "0 2 * * * $APP_DIR/deploy/backup.sh") | crontab -

# Step 10.5: Set up token monitoring
echo -e "${YELLOW}Step 10.5: Setting up token monitoring...${NC}"
if [ -f monitor_tokens.py ]; then
    chmod +x monitor_tokens.py
    # Add token monitoring to crontab (every 30 minutes)
    (crontab -l 2>/dev/null; echo "*/30 * * * * cd $APP_DIR && /usr/bin/python3 monitor_tokens.py >> logs/token_monitor.log 2>&1") | crontab -
    echo "Token monitoring cron job added"
fi

# Step 11: Create update script
echo -e "${YELLOW}Step 11: Creating update script...${NC}"
cat > $APP_DIR/update.sh << 'EOF'
#!/bin/bash
cd /home/ubuntu/twitter-manager
source venv/bin/activate
git pull
pip install -r requirements.txt
sudo systemctl restart twitter-manager
sudo systemctl restart nginx
echo "Application updated successfully!"
EOF
chmod +x $APP_DIR/update.sh

# Step 12: Display status and next steps
echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit environment variables:"
echo "   nano $APP_DIR/.env"
echo ""
echo "2. Get your server's IP address:"
echo "   curl -4 icanhazip.com"
echo ""
echo "3. Update your Twitter app callback URL to:"
echo "   http://YOUR-IP/auth/callback"
echo "   or"
echo "   http://YOUR-IP.nip.io/auth/callback"
echo ""
echo "4. Check service status:"
echo "   sudo systemctl status twitter-manager"
echo "   sudo systemctl status nginx"
echo ""
echo "5. View logs:"
echo "   sudo journalctl -u twitter-manager -f"
echo "   tail -f $APP_DIR/logs/twitter_manager.log"
echo ""
echo "6. To update the application later:"
echo "   ./update.sh"
echo ""
echo -e "${GREEN}Your API will be available at: http://YOUR-IP/api/v1/${NC}"