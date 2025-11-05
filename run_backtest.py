#!/usr/bin/env python3
"""
Wrapper script to run backtests from the main directory
"""
import sys
import subprocess

if __name__ == '__main__':
    # Run the backtest with all arguments
    args = sys.argv[1:]
    cmd = [sys.executable, '-m', 'backtest.backtest'] + args
    subprocess.run(cmd)
