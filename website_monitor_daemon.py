#!/usr/bin/env python3
"""
Website Monitor Daemon - Defensive Security Tool
Monitors website visits across all major browsers for security/compliance purposes
"""

import os
import sys
import sqlite3
import json
import time
import shutil
import logging
import csv
from datetime import datetime
from pathlib import Path
from threading import Thread
import signal
import daemon
from daemon import pidfile

class WebsiteMonitor:
    def __init__(self, log_file='/tmp/website_monitor.log', csv_file='/tmp/website_visits.csv'):
        self.log_file = log_file
        self.csv_file = csv_file
        self.running = True
        self.check_interval = 10  # seconds
        self.seen_urls = set()
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Initialize CSV file with headers if it doesn't exist
        self.init_csv_file()
        
        # Browser history paths
        self.browser_paths = {
            'Chrome': '~/Library/Application Support/Google/Chrome/Default/History',
            'Firefox': '~/Library/Application Support/Firefox/Profiles/*/places.sqlite',
            'Safari': '~/Library/Safari/History.db',
            'Edge': '~/Library/Application Support/Microsoft Edge/Default/History'
        }

    def init_csv_file(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'browser', 'url', 'title', 'visit_time', 'visit_count']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

    def log_to_csv(self, visit_data):
        """Log visit data to CSV file - prepend new entries to top"""
        try:
            # Clean title field to avoid CSV issues
            title = visit_data.get('title', '').replace('"', '""').replace('\n', ' ').replace('\r', ' ') if visit_data.get('title') else ''
            
            new_row = {
                'timestamp': datetime.now().isoformat(),
                'browser': visit_data['browser'],
                'url': visit_data['url'],
                'title': title,
                'visit_time': visit_data.get('visit_time', ''),
                'visit_count': visit_data.get('visit_count', '')
            }
            
            # Read existing data if file exists
            existing_data = []
            fieldnames = ['timestamp', 'browser', 'url', 'title', 'visit_time', 'visit_count']
            
            if os.path.exists(self.csv_file):
                with open(self.csv_file, 'r', newline='', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    existing_data = list(reader)
            
            # Write new row first, then existing data
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(new_row)  # New entry first
                writer.writerows(existing_data)  # Then existing entries
                
        except Exception as e:
            self.logger.error(f"Error writing to CSV: {e}")

    def get_chrome_history(self, history_path):
        """Extract recent history from Chrome"""
        try:
            temp_path = '/tmp/chrome_history_copy.db'
            shutil.copy2(history_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            query = """
            SELECT url, title, visit_count, datetime(last_visit_time/1000000 + (strftime('%s', '1601-01-01')), 'unixepoch') as visit_time
            FROM urls 
            ORDER BY last_visit_time DESC 
            LIMIT 100
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            os.remove(temp_path)
            
            return results
        except Exception as e:
            self.logger.error(f"Error reading Chrome history: {e}")
            return []

    def get_safari_history(self, history_path):
        """Extract recent history from Safari"""
        try:
            temp_path = '/tmp/safari_history_copy.db'
            shutil.copy2(history_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            query = """
            SELECT history_items.url, history_visits.title, 
                   datetime(history_visits.visit_time + 978307200, 'unixepoch') as visit_time
            FROM history_items 
            JOIN history_visits ON history_items.id = history_visits.history_item
            ORDER BY history_visits.visit_time DESC 
            LIMIT 100
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            os.remove(temp_path)
            
            return results
        except Exception as e:
            self.logger.error(f"Error reading Safari history: {e}")
            return []

    def get_firefox_history(self, profile_path):
        """Extract recent history from Firefox"""
        try:
            temp_path = '/tmp/firefox_history_copy.db'
            shutil.copy2(profile_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            query = """
            SELECT url, title, visit_count, 
                   datetime(last_visit_date/1000000, 'unixepoch') as visit_time
            FROM moz_places 
            WHERE last_visit_date IS NOT NULL
            ORDER BY last_visit_date DESC 
            LIMIT 100
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            conn.close()
            os.remove(temp_path)
            
            return results
        except Exception as e:
            self.logger.error(f"Error reading Firefox history: {e}")
            return []

    def monitor_browsers(self):
        """Main monitoring loop"""
        while self.running:
            try:
                new_visits = []
                
                # Check Chrome
                chrome_path = os.path.expanduser(self.browser_paths['Chrome'])
                if os.path.exists(chrome_path):
                    history = self.get_chrome_history(chrome_path)
                    for url, title, visit_count, visit_time in history:
                        if url not in self.seen_urls:
                            new_visits.append({
                                'browser': 'Chrome',
                                'url': url,
                                'title': title,
                                'visit_time': visit_time,
                                'visit_count': visit_count
                            })
                            self.seen_urls.add(url)
                
                # Check Safari
                safari_path = os.path.expanduser(self.browser_paths['Safari'])
                if os.path.exists(safari_path):
                    history = self.get_safari_history(safari_path)
                    for url, title, visit_time in history:
                        if url not in self.seen_urls:
                            new_visits.append({
                                'browser': 'Safari',
                                'url': url,
                                'title': title,
                                'visit_time': visit_time
                            })
                            self.seen_urls.add(url)
                
                # Check Firefox profiles
                firefox_base = os.path.expanduser('~/Library/Application Support/Firefox/Profiles/')
                if os.path.exists(firefox_base):
                    for profile_dir in os.listdir(firefox_base):
                        places_path = os.path.join(firefox_base, profile_dir, 'places.sqlite')
                        if os.path.exists(places_path):
                            history = self.get_firefox_history(places_path)
                            for url, title, visit_count, visit_time in history:
                                if url not in self.seen_urls:
                                    new_visits.append({
                                        'browser': 'Firefox',
                                        'url': url,
                                        'title': title,
                                        'visit_time': visit_time,
                                        'visit_count': visit_count
                                    })
                                    self.seen_urls.add(url)
                
                # Check Edge
                edge_path = os.path.expanduser(self.browser_paths['Edge'])
                if os.path.exists(edge_path):
                    history = self.get_chrome_history(edge_path)  # Edge uses Chromium format
                    for url, title, visit_count, visit_time in history:
                        if url not in self.seen_urls:
                            new_visits.append({
                                'browser': 'Edge',
                                'url': url,
                                'title': title,
                                'visit_time': visit_time,
                                'visit_count': visit_count
                            })
                            self.seen_urls.add(url)
                
                # Log new visits
                for visit in new_visits:
                    self.logger.info(f"NEW VISIT: {visit['browser']} - {visit['url']} - {visit['title']} - {visit['visit_time']}")
                    self.log_to_csv(visit)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.check_interval)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info("Received shutdown signal, stopping daemon...")
        self.running = False
        sys.exit(0)

    def run(self):
        """Run the daemon"""
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.logger.info("Website Monitor Daemon starting...")
        self.monitor_browsers()

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 website_monitor_daemon.py [start|stop|restart]")
        sys.exit(1)
    
    action = sys.argv[1]
    pid_file = '/tmp/website_monitor.pid'
    log_file = '/tmp/website_monitor.log'
    csv_file = '/tmp/website_visits.csv'
    
    if action == 'start':
        try:
            with daemon.DaemonContext(
                pidfile=pidfile.TimeoutPIDLockFile(pid_file),
                stdout=open('/tmp/website_monitor_stdout.log', 'w+'),
                stderr=open('/tmp/website_monitor_stderr.log', 'w+'),
            ):
                monitor = WebsiteMonitor(log_file, csv_file)
                monitor.run()
        except Exception as e:
            print(f"Error starting daemon: {e}")
            sys.exit(1)
    
    elif action == 'stop':
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            print("Daemon stopped")
        except Exception as e:
            print(f"Error stopping daemon: {e}")
    
    elif action == 'restart':
        # Stop first
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
        except:
            pass
        
        # Then start
        try:
            with daemon.DaemonContext(
                pidfile=pidfile.TimeoutPIDLockFile(pid_file),
                stdout=open('/tmp/website_monitor_stdout.log', 'w+'),
                stderr=open('/tmp/website_monitor_stderr.log', 'w+'),
            ):
                monitor = WebsiteMonitor(log_file, csv_file)
                monitor.run()
        except Exception as e:
            print(f"Error restarting daemon: {e}")
            sys.exit(1)
    
    else:
        print("Invalid action. Use: start, stop, or restart")
        sys.exit(1)

if __name__ == "__main__":
    main()