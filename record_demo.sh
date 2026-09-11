#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "    Tractor Beam: Video Demonstration Recording Script    "
echo "=========================================================="
echo ""
echo "Before we start the recording, please make sure you have:"
echo " 1. Opened Betaflight Configurator"
echo " 2. Arranged this terminal on one side of your screen"
echo " 3. Arranged Betaflight Configurator on the other side"
echo " 4. (DO NOT connect yet - the script will launch SITL first)"
echo ""
read -p "Press [Enter] when your Hyprland windows are arranged..."

echo "[1/4] Starting Betaflight SITL in the background..."
cd betaflight
# Use the known working safety configuration
rm -f eeprom.bin
./obj/main/betaflight_SITL.elf --config sitl_safety.txt > /dev/null 2>&1
./obj/main/betaflight_SITL.elf > /dev/null 2>&1 &
SITL_PID=$!
cd ..

echo "SITL is running!"
echo "Now, click 'Connect' in Betaflight Configurator to connect to tcp://127.0.0.1:5761"
echo "Go to the 'GPS' or 'Setup' tab to view the 3D model and map."
echo ""
read -p "Press [Enter] when Betaflight Configurator is connected and ready..."

echo "[2/4] Starting screen recording (wf-recorder)..."
if command -v wf-recorder &> /dev/null; then
    # Start wf-recorder in the background, recording the entire screen
    wf-recorder -f demonstration_video.mp4 > /dev/null 2>&1 &
    RECORDER_PID=$!
    echo "Recording started -> demonstration_video.mp4"
else
    echo "WARNING: 'wf-recorder' not found! Skipping screen recording."
    echo "Please use your preferred screen recorder (e.g. OBS Studio) manually."
    read -p "Press [Enter] when your manual screen recording has started..."
fi

echo "[3/4] Launching the GPS Spoofing Attack (adaptive-fake-destination)..."
echo "Executing: python3 scripts/horizontal_gate_experiment.py --profile adaptive-fake-destination"
sleep 2

# We must run this using the virtualenv python
.venv/bin/python3 scripts/horizontal_gate_experiment.py --profile adaptive-fake-destination

echo ""
echo "[4/4] Attack finished!"

if [ -n "$RECORDER_PID" ]; then
    echo "Stopping screen recording..."
    kill -INT $RECORDER_PID 2>/dev/null || true
    wait $RECORDER_PID 2>/dev/null || true
    echo "Video saved as 'demonstration_video.mp4'"
fi

echo "Stopping Betaflight SITL..."
kill -9 $SITL_PID 2>/dev/null || true

echo "Done! You can now edit your video and add the voiceover."
