# frontend/Dockerfile

# Build stage: create React production build
FROM node:16-alpine as build

WORKDIR /usr/src/app
COPY package*.json ./
RUN npm install

# Copy the rest of your React code
COPY . /usr/src/app
RUN npm run build

# Production stage: serve with a simple http server OR do dev server
# Option 1: Serve with "serve" or any production server
FROM node:16-alpine as production
WORKDIR /usr/src/app
COPY --from=build /usr/src/app/build ./build
RUN npm install -g serve

EXPOSE 3000
CMD ["serve", "-s", "build", "-l", "3000"]
