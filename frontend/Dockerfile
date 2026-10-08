FROM nginx:1.30.5-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY public/ /usr/share/nginx/html/
USER nginx
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=6 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
