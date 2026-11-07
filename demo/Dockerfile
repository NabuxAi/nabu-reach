FROM python:3.12-alpine AS build
WORKDIR /build
COPY reach/web/ ./reach/web/
COPY demo/ ./demo/
RUN python demo/build.py

FROM nginx:1.27-alpine
COPY demo/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /build/dist/demo/ /usr/share/nginx/html/
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=4s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
