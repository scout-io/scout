# frontend/Dockerfile

# Build stage: create React production build
FROM node:16-alpine as build

WORKDIR /usr/src/app

# Copy package files
COPY package*.json ./

# Install dependencies with reduced memory usage
ENV NODE_OPTIONS="--max-old-space-size=2048"
RUN npm ci --only=production

# Copy the rest of your React code
COPY . /usr/src/app

# Build with reduced memory usage
RUN npm run build

# Production stage: serve with a simple http server
FROM node:16-alpine as production
WORKDIR /usr/src/app
COPY --from=build /usr/src/app/build ./build
RUN npm install -g serve

EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
