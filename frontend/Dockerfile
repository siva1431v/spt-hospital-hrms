FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# Build argument for the backend API URL (set at build time on Railway)
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_APP_NAME="SPT Hospital HRMS"

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
