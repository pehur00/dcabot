# DipTrader Bot

A sophisticated trading bot designed for the cryptocurrency market, leveraging the Pybit Unified Trading API.

## Requirements
- Python 3.x
- Pybit Unified Trading API
- Docker (optional for Docker deployment)

## Installation

### Standard Installation
1. Clone the repository:
```
git clone [repository-url]
```

2. Navigate to the bot directory:
```
cd [directory]
```

3. Install the required dependencies:
```
pip install -r requirements.txt
```

### Docker Installation
If you prefer to run the bot inside a Docker container, you can build the Docker image:
```
docker build -t diptrader-bot .
```

And then run the container:
```
docker run -v diptrader-bot
```

## Configuration
Before running the bot, make sure to update the `Config map inside the code` file with your prefferred trading parameters.

## Usage
To start the bot with standard installation:
```
python MartingaleTradingStrategy.py --api-key YOUR_API_KEY --api-secret YOUR_API_SECRET --symbol BTCUSDT
```

To use the testnet, use the testnet parameter
```
python MartingaleTradingStrategy.py --api-key YOUR_API_KEY --api-secret YOUR_API_SECRET --symbol BTCUSDT --testnet
```

# Deployment
## Docker
1. Build
```
docker build -t martingale_strategy .
```

2. Run local
```
docker run --rm martingale_strategy --api-key API_KEY --api-secret API_SECRET --symbol INJUSDT >> bot.log 2>&1
```

3. Deploy

I currently use render.com to build and run a docker container as cron job. 
- 

## Features
- Automated trading based on predefined strategies
- Configurable trading parameters
- Detailed logging for monitoring and analysis

## License
This project is licensed under the MIT License - see the LICENSE file for details.