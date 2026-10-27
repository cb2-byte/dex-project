FROM node:20-alpine
RUN npm install -g openclaw
WORKDIR /data/workspace
CMD ["sh", "-c", "while true; do sleep 3600; done"]
