# Build the React app, then serve it with an unprivileged nginx (no Node.js at runtime).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Public, non-secret site settings baked into the build (canonical URLs, sitemap, legal pages).
ARG VITE_SITE_URL=""
ARG VITE_OPERATOR_NAME=""
ARG VITE_CONTACT_EMAIL=""
ENV VITE_SITE_URL=$VITE_SITE_URL VITE_OPERATOR_NAME=$VITE_OPERATOR_NAME VITE_CONTACT_EMAIL=$VITE_CONTACT_EMAIL
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
