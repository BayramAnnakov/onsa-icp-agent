#!/usr/bin/env python3
"""
Simple script to read and display ADK agent logs with filtering options.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

def read_logs(log_file, lines=100, level=None, component=None, since=None):
    """Read and filter log file."""
    log_path = Path(log_file)
    
    if not log_path.exists():
        print(f"Log file not found: {log_file}")
        return
    
    with open(log_path, 'r') as f:
        all_lines = f.readlines()
    
    # Filter lines if needed
    filtered_lines = []
    for line in all_lines:
        # Skip empty lines
        if not line.strip():
            continue
            
        # Filter by level
        if level and f"- {level.upper()} -" not in line:
            continue
            
        # Filter by component
        if component and component not in line:
            continue
            
        # Filter by time
        if since:
            try:
                # Extract timestamp from line (assuming format: YYYY-MM-DD HH:MM:SS)
                timestamp_str = line.split(' - ')[0]
                line_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                if line_time < since:
                    continue
            except:
                pass
        
        filtered_lines.append(line)
    
    # Get last N lines
    if lines > 0:
        filtered_lines = filtered_lines[-lines:]
    
    # Print results
    print(f"=== Log: {log_file} ===")
    print(f"Total lines: {len(all_lines)}, Filtered: {len(filtered_lines)}")
    print("=" * 50)
    
    for line in filtered_lines:
        print(line.rstrip())

def main():
    parser = argparse.ArgumentParser(description='Read ADK agent logs')
    parser.add_argument('log_file', nargs='?', default='logs/adk_agent_web.log',
                        help='Log file to read (default: logs/adk_agent_web.log)')
    parser.add_argument('-n', '--lines', type=int, default=100,
                        help='Number of lines to show (0 for all)')
    parser.add_argument('-l', '--level', choices=['debug', 'info', 'warning', 'error'],
                        help='Filter by log level')
    parser.add_argument('-c', '--component', help='Filter by component name')
    parser.add_argument('-m', '--minutes', type=int,
                        help='Show logs from last N minutes')
    parser.add_argument('-f', '--follow', action='store_true',
                        help='Follow log file (like tail -f)')
    
    args = parser.parse_args()
    
    # Calculate since time if minutes specified
    since = None
    if args.minutes:
        since = datetime.now() - timedelta(minutes=args.minutes)
    
    if args.follow:
        # Simple follow mode
        import time
        last_size = 0
        while True:
            try:
                current_size = Path(args.log_file).stat().st_size
                if current_size > last_size:
                    with open(args.log_file, 'r') as f:
                        f.seek(last_size)
                        new_lines = f.read()
                        print(new_lines, end='')
                    last_size = current_size
                time.sleep(1)
            except KeyboardInterrupt:
                break
    else:
        read_logs(args.log_file, args.lines, args.level, args.component, since)

if __name__ == '__main__':
    main()