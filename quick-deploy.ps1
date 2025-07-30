# ==============================================
# TeleMirror - Quick Deploy to VPS (Windows)
# ==============================================

# Check PowerShell version
if ($PSVersionTable.PSVersion.Major -lt 3) {
    Write-Host "Need PowerShell version 3.0 or higher" -ForegroundColor Red
    exit 1
}

# Color functions
function Write-Info { param($Message) Write-Host "[INFO] $Message" -ForegroundColor Green }
function Write-Warn { param($Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Error { param($Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Write-Step { param($Message) Write-Host "[STEP] $Message" -ForegroundColor Blue }
function Write-Success { param($Message) Write-Host "[SUCCESS] $Message" -ForegroundColor Magenta }

# Function to read input
function Read-InputValue {
    param(
        [string]$Prompt,
        [string]$Default = ""
    )
    
    if ($Default) {
        $userInput = Read-Host "$Prompt (default: $Default)"
        if ([string]::IsNullOrEmpty($userInput)) {
            return $Default
        }
        return $userInput
    } else {
        return Read-Host $Prompt
    }
}

# Header
Write-Host ""
Write-Host "==================================================" -ForegroundColor Magenta
Write-Host "TeleMirror - Quick Deploy to VPS (Windows)" -ForegroundColor Magenta
Write-Host "==================================================" -ForegroundColor Magenta
Write-Host ""



# Step 1: Check required files
Write-Step "1. Checking required files"
if (!(Test-Path ".env")) {
    Write-Error ".env file not found!"
    Write-Info "Create .env file with your configuration first"
    exit 1
}

if (!(Test-Path "docker-compose.yaml")) {
    Write-Error "docker-compose.yaml file not found!"
    exit 1
}

Write-Success "Required files found!"

# Step 2: Application name
Write-Step "2. Application Settings"
$APP_NAME = Read-InputValue "Application Name (for deployment folder)"
if ([string]::IsNullOrEmpty($APP_NAME)) {
    Write-Error "Application name is required!"
    exit 1
}

# Step 3: VPS connection settings
Write-Step "3. VPS Connection Settings"
$VPS_HOST = "144.172.98.77"
$VPS_USERNAME = Read-InputValue "SSH Username" "root"
$SSH_KEY_PATH = Read-InputValue "SSH Key Path" "$env:USERPROFILE\.ssh\id_rsa"
$SUDO_PASSWORD_PLAIN = "150319"

# Fix SSH key path for Windows
if ($SSH_KEY_PATH -match "^~/") {
    $SSH_KEY_PATH = $SSH_KEY_PATH -replace "^~/", "$env:USERPROFILE\"
}

Write-Info "App: $APP_NAME"
Write-Info "VPS: $VPS_HOST"
Write-Info "User: $VPS_USERNAME"
Write-Info "SSH Key: $SSH_KEY_PATH"
Write-Info "Sudo Password: ****" 

# Step 4: Check SSH connection
Write-Step "4. Checking SSH Connection"
Write-Info "Testing SSH connection to VPS..."

# Check if SSH key exists
if (!(Test-Path $SSH_KEY_PATH)) {
    Write-Error "SSH key not found: $SSH_KEY_PATH"
    Write-Info "Create SSH key or specify correct path"
    exit 1
}

# Test SSH connection
try {
    $testConnection = ssh -i $SSH_KEY_PATH -o ConnectTimeout=10 -o BatchMode=yes "$VPS_USERNAME@$VPS_HOST" "exit" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "SSH connection failed"
    }
    Write-Success "SSH connection successful!"
} catch {
    Write-Error "Failed to connect to VPS via SSH"
    Write-Info "Check:"
    Write-Info "- VPS IP: $VPS_HOST"
    Write-Info "- SSH key: $SSH_KEY_PATH"
    Write-Info "- Username: $VPS_USERNAME"
    Write-Info "- SSH access allowed on VPS"
    exit 1
}

# Step 5: Copy files to VPS
Write-Step "5. Copying files to VPS"
try {
    # Copy .env file
    scp -i $SSH_KEY_PATH ".env" "$VPS_USERNAME@$VPS_HOST`:/tmp/.env" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy .env file"
    }
    
    # Copy docker-compose.yaml
    scp -i $SSH_KEY_PATH "docker-compose.yaml" "$VPS_USERNAME@$VPS_HOST`:/tmp/docker-compose.yaml" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy docker-compose.yaml"
    }
    
    Write-Success "Files copied to VPS!"
} catch {
    Write-Error "Error copying files to VPS: $_"
    exit 1
}

# Step 6: Deploy on VPS
Write-Step "6. Deploying on VPS"

# Set deployment directory based on app name
$DEPLOY_DIR = "/opt/telemirror-$APP_NAME"

# Create deployment script with proper line endings
$deployScript = @'
set -e
echo "Starting TeleMirror deployment for app: APPNAME_PLACEHOLDER..."

# Create deployment directory
printf "150319\n" | sudo -S mkdir -p DEPLOYDIR_PLACEHOLDER
printf "150319\n" | sudo -S chown $(whoami):$(whoami) DEPLOYDIR_PLACEHOLDER
cd DEPLOYDIR_PLACEHOLDER

# Move files from tmp
mv /tmp/.env .env
mv /tmp/docker-compose.yaml docker-compose.yaml

# Check if docker and docker-compose are installed
if ! command -v docker >/dev/null 2>&1; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    printf "150319\n" | sudo -S sh get-docker.sh
    printf "150319\n" | sudo -S systemctl enable docker
    printf "150319\n" | sudo -S systemctl start docker
    rm get-docker.sh
    
    # Add current user to docker group
    printf "150319\n" | sudo -S usermod -aG docker $(whoami)
    echo "User added to docker group. You may need to re-login for changes to take effect."
fi

if ! command -v docker-compose >/dev/null 2>&1; then
    echo "Installing Docker Compose..."
    printf "150319\n" | sudo -S curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    printf "150319\n" | sudo -S chmod +x /usr/local/bin/docker-compose
fi

# Stop existing containers
echo "Stopping existing containers..."
printf "150319\n" | sudo -S docker-compose down || true

# Start containers
echo "Starting containers..."
printf "150319\n" | sudo -S docker-compose up -d --build

echo "Cleaning up..."
printf "150319\n" | sudo -S docker system prune -f

echo "Deploy completed for app: APPNAME_PLACEHOLDER!"
echo "Container status:"
printf "150319\n" | sudo -S docker-compose ps
'@

# Replace placeholders with actual values
$deployScript = $deployScript -replace "APPNAME_PLACEHOLDER", $APP_NAME
$deployScript = $deployScript -replace "DEPLOYDIR_PLACEHOLDER", $DEPLOY_DIR

# Convert Windows line endings to Unix line endings and create temporary file
$deployScript = $deployScript -replace "`r`n", "`n"
$tempScriptPath = "$env:TEMP\telemirror-deploy-$(Get-Date -Format 'yyyyMMdd-HHmmss').sh"

try {
    # Write script to temporary file with UTF-8 encoding without BOM
    $utf8NoBomEncoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tempScriptPath, $deployScript, $utf8NoBomEncoding)
    
    Write-Info "Created temporary deployment script: $tempScriptPath"
    
    # Copy deployment script to VPS
    $scpTarget = "${VPS_USERNAME}@${VPS_HOST}:/tmp/deploy-script.sh"
    scp -i $SSH_KEY_PATH $tempScriptPath $scpTarget
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to copy deployment script"
    }
    
    # Execute deployment script on VPS
    $sshTarget = "${VPS_USERNAME}@${VPS_HOST}"
    ssh -i $SSH_KEY_PATH $sshTarget "printf '150319\n' | sudo -S chmod +x /tmp/deploy-script.sh && printf '150319\n' | sudo -S /tmp/deploy-script.sh && printf '150319\n' | sudo -S rm /tmp/deploy-script.sh"
    if ($LASTEXITCODE -ne 0) {
        throw "Deploy failed"
    }
} catch {
    Write-Error "Error during deployment: $_"
    exit 1
} finally {
    # Clean up temporary file
    if (Test-Path $tempScriptPath) {
        Remove-Item $tempScriptPath -Force
        Write-Info "Cleaned up temporary deployment script"
    }
    # Password is hardcoded, no need to clear from memory
}

# Final info
Write-Success "Deploy completed successfully!"
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "TeleMirror '$APP_NAME' is running on VPS!" -ForegroundColor Green
Write-Host "Deployment directory: $DEPLOY_DIR" -ForegroundColor Green
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Green
Write-Host "   Logs: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd $DEPLOY_DIR && sudo docker-compose logs -f'" -ForegroundColor Green
Write-Host "   Status: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd $DEPLOY_DIR && sudo docker-compose ps'" -ForegroundColor Green
Write-Host "   Restart: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd $DEPLOY_DIR && sudo docker-compose restart'" -ForegroundColor Green
Write-Host "   Stop: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd $DEPLOY_DIR && sudo docker-compose down'" -ForegroundColor Green
Write-Host "   Shell: ssh -i $SSH_KEY_PATH $VPS_USERNAME@$VPS_HOST 'cd $DEPLOY_DIR && bash'" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green 