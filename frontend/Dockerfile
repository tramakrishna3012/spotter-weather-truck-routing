# Build stage
FROM node:24-alpine AS build
WORKDIR /app

ARG VITE_API_BASE_URL=""
ARG VITE_MAP_STYLE_URL=""
ARG VITE_MAP_PUBLIC_TOKEN=""

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_MAP_STYLE_URL=${VITE_MAP_STYLE_URL}
ENV VITE_MAP_PUBLIC_TOKEN=${VITE_MAP_PUBLIC_TOKEN}

COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build

# Runtime stage
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
