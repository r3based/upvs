FROM node:20-alpine

WORKDIR /app

COPY apps/web/package.json /app/
RUN npm install

COPY apps/web /app/apps/web

WORKDIR /app/apps/web

RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
