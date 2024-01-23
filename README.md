# Intro


## Docker
- Build container
  - docker build -t diptrader . 
- Start the container locally:
  - docker run -d -v ./config.ini:/app/config.ini diptrader
- Follow log
  - docker exec {name} tail -f bot.log
