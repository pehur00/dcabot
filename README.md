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
1. Setup environment variables
- API_KEY, API_SECRET, SYMBOL
2. Start script
To start the bot with standard installation:
```
python /Users/jasperoudejans/Documents/repos/private/diptrader/MartingaleTradingStrategy.py 
```

# Deployment
1. Render

I currently use render.com to build and run a docker container as cron job. It watches my github repo and on commits it will rebuild etc.

## Features
- Automated trading based on predefined strategies
- Configurable trading parameters
- Detailed logging for monitoring and analysis

## License
This project is licensed under the MIT License - see the LICENSE file for details.