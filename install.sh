#!/bin/bash

# HydroRigs Installation Script
# Senior Software Engineer Style: Surgical and safe.

PROJECT_DIR=$(pwd)
CONFIG_DIR="$HOME/.config/hydrorigs"
BIN_PATH="/usr/local/bin/hydrorigs"

echo "Installing dependencies..."
pip install pyyaml --quiet

# Create a proper entry point in /usr/local/bin
echo "Setting up CLI entry point..."
sudo tee $BIN_PATH > /dev/null <<EOF
#!/bin/bash
export PYTHONPATH=$PROJECT_DIR:\$PYTHONPATH
$(which python3) -m hydrorigs.cli "\$@"
EOF
sudo chmod +x $BIN_PATH

# Initialize config and discovery
echo "Discovering AI CLIs..."
PYTHONPATH=$PROJECT_DIR python3 -m hydrorigs.cli discover

# Setup Systemd Service
echo "Configuring systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
cp "$PROJECT_DIR/hydrorigs.service" "$HOME/.config/systemd/user/hydrorigs.service"
# Update the ExecStart path and Environment in the service file to be absolute
sed -i "s|ExecStart=.*|ExecStart=$(which python3) -m hydrorigs.cli daemon|" "$HOME/.config/systemd/user/hydrorigs.service"
sed -i "/\[Service\]/a Environment=PYTHONPATH=$PROJECT_DIR" "$HOME/.config/systemd/user/hydrorigs.service"

systemctl --user daemon-reload
systemctl --user enable hydrorigs.service
systemctl --user start hydrorigs.service

# Alias Setup
echo "Generating aliases..."
ALIAS_FILE="$HOME/.hydrorigs_aliases"
echo "# HydroRigs Aliases" > "$ALIAS_FILE"

# Load current config to see which CLIs to alias
python3 -c "
import yaml
from pathlib import Path
config_path = Path.home() / '.config/hydrorigs/config.yaml'
if config_path.exists():
    with open(config_path) as f:
        conf = yaml.safe_load(f)
        for name in conf.get('rigs', {}):
            print(f\"alias {name}='hydrorigs wrap {name}'\")
" >> "$ALIAS_FILE"

echo "Aliases generated in $ALIAS_FILE."
echo "To activate, add 'source $ALIAS_FILE' to your .bashrc or .zshrc."
echo "HydroRigs setup complete. Run 'hydrorigs status' to see the status."
