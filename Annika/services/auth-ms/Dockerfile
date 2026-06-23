# Auth Microservice -- Windows Container

FROM node:20-windowsservercore-ltsc2025

WORKDIR C:/auth_service

COPY package.json package-lock.json ./
RUN npm ci

COPY app.js .

EXPOSE 3000

CMD ["node", "app.js"]