FROM node:22-alpine AS build

WORKDIR /app
COPY frontend/package.json /app/package.json
RUN npm install
COPY frontend/ /app/
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
