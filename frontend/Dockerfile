FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json .
RUN npm install --no-audit --no-fund

# Copy source
COPY . .

# Build
RUN npm run build

# Serve with a simple static server
RUN npm install -g serve

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]
