FROM node:18-alpine AS base

WORKDIR /app

# Install dependencies based on the preferred package manager
COPY src/frontend/package.json ./
RUN npm install

COPY src/frontend ./

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "start"]

