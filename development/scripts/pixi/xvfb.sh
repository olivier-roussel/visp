#! /bin/bash

export DISPLAY=:99
Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp &
echo "Xvfb started"

