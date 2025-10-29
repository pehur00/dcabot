#!/bin/bash

# Test different leverage values on a symbol
# Usage: ./test_leverages.sh SYMBOL DAYS BALANCE SIDE

SYMBOL=${1:-HBARUSDT}
DAYS=${2:-30}
BALANCE=${3:-200}
SIDE=${4:-Long}

echo "========================================"
echo "Testing Different Leverage Values"
echo "========================================"
echo "Symbol: $SYMBOL"
echo "Period: $DAYS days"
echo "Balance: \$$BALANCE"
echo "Side: $SIDE"
echo ""

# Test different leverage values
for LEVERAGE in 5 10 15 20
do
    echo "========================================"
    echo "Testing: Leverage ${LEVERAGE}x"
    echo "========================================"

    dcabot-env/bin/python backtest/backtest.py \
        --symbol "$SYMBOL" \
        --days "$DAYS" \
        --balance "$BALANCE" \
        --side "$SIDE" \
        --leverage "$LEVERAGE" \
        --max-margin-pct 0.50 \
        --interval 1 \
        --source binance

    # Rename result files to include leverage
    LATEST_CHART=$(ls -t backtest/results/${SYMBOL}_${SIDE}_bal${BALANCE}_profit0.10_*_chart.png 2>/dev/null | head -1)
    LATEST_BALANCE=$(ls -t backtest/results/${SYMBOL}_${SIDE}_bal${BALANCE}_profit0.10_*_balance.csv 2>/dev/null | head -1)
    LATEST_TRADES=$(ls -t backtest/results/${SYMBOL}_${SIDE}_bal${BALANCE}_profit0.10_*_trades.csv 2>/dev/null | head -1)

    if [ -f "$LATEST_CHART" ]; then
        mv "$LATEST_CHART" "backtest/results/${SYMBOL}_lev${LEVERAGE}x_${DAYS}d_chart.png"
    fi
    if [ -f "$LATEST_BALANCE" ]; then
        mv "$LATEST_BALANCE" "backtest/results/${SYMBOL}_lev${LEVERAGE}x_${DAYS}d_balance.csv"
    fi
    if [ -f "$LATEST_TRADES" ]; then
        mv "$LATEST_TRADES" "backtest/results/${SYMBOL}_lev${LEVERAGE}x_${DAYS}d_trades.csv"
    fi

    echo ""
done

echo "All tests complete! Results saved in backtest/results/"
