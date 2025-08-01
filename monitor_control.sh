#!/bin/bash

# Website Monitor Control Script
DAEMON_PATH="/Users/adityadasnurkar/Documents/website_monitor_daemon.py"
PLIST_PATH="/Users/adityadasnurkar/Documents/website_monitor.plist"
LAUNCHD_PATH="~/Library/LaunchAgents/com.user.website.monitor.plist"

case "$1" in
    install)
        echo "Installing website monitor daemon..."
        pip3 install -r requirements.txt
        cp "$PLIST_PATH" ~/Library/LaunchAgents/
        chmod +x "$DAEMON_PATH"
        echo "Installation complete. Use 'start' to begin monitoring."
        ;;
    start)
        echo "Starting website monitor daemon..."
        launchctl load ~/Library/LaunchAgents/com.user.website.monitor.plist
        echo "Daemon started. Logs available at /tmp/website_monitor.log"
        ;;
    stop)
        echo "Stopping website monitor daemon..."
        launchctl unload ~/Library/LaunchAgents/com.user.website.monitor.plist
        echo "Daemon stopped."
        ;;
    restart)
        echo "Restarting website monitor daemon..."
        launchctl unload ~/Library/LaunchAgents/com.user.website.monitor.plist
        sleep 2
        launchctl load ~/Library/LaunchAgents/com.user.website.monitor.plist
        echo "Daemon restarted."
        ;;
    status)
        if launchctl list | grep -q "com.user.website.monitor"; then
            echo "Website monitor daemon is running."
            echo "Log entries from last 10 minutes:"
            tail -n 20 /tmp/website_monitor.log 2>/dev/null || echo "No log file found yet."
        else
            echo "Website monitor daemon is not running."
        fi
        ;;
    uninstall)
        echo "Uninstalling website monitor daemon..."
        launchctl unload ~/Library/LaunchAgents/com.user.website.monitor.plist 2>/dev/null
        rm -f ~/Library/LaunchAgents/com.user.website.monitor.plist
        rm -f /tmp/website_monitor.pid
        rm -f /tmp/website_monitor*.log
        echo "Uninstallation complete."
        ;;
    *)
        echo "Usage: $0 {install|start|stop|restart|status|uninstall}"
        echo ""
        echo "Commands:"
        echo "  install   - Install daemon and dependencies"
        echo "  start     - Start the monitoring daemon"
        echo "  stop      - Stop the monitoring daemon"
        echo "  restart   - Restart the monitoring daemon"
        echo "  status    - Check daemon status and recent logs"
        echo "  uninstall - Remove daemon and cleanup files"
        exit 1
        ;;
esac