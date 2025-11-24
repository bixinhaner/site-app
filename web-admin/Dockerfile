FROM node:20-alpine AS build

WORKDIR /app

COPY web-admin/package*.json ./

RUN npm install

COPY web-admin/ .

COPY web-admin-subpath.config.js ./web-admin-subpath.config.js

RUN npm run build -- --config web-admin-subpath.config.js

FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

