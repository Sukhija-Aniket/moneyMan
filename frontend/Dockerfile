FROM node:20-slim

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json /app/
RUN npm install

COPY frontend /app

EXPOSE 5173

# --host so Vite's dev server accepts connections from outside the container, not just localhost.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
