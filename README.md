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
cd diptrader-bot
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
docker run -v /path/to/config.ini:/app/config.ini diptrader-bot
```

## Configuration
Before running the bot, make sure to update the `config.ini` file with your API keys and other trading parameters.

## Usage
To start the bot with standard installation:
```
python bot.py
```

For Docker, after the container is running, the bot will automatically start and use the provided configuration.

## Features
- Automated trading based on predefined strategies
- Easy setup with Docker support
- Configurable trading parameters
- Detailed logging for monitoring and analysis

## License
This project is licensed under the MIT License - see the LICENSE file for details.