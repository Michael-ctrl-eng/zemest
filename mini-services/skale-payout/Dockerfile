FROM node:22-alpine

WORKDIR /app

# ethers only — no framework, minimal surface
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund

COPY skale.js index.js ./

# Journal directory (idempotency keys) on a volume
RUN mkdir -p /app/.data
VOLUME ["/app/.data"]

ENV PORT=4010
EXPOSE 4010

# Non-root
USER node

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:4010/health || exit 1

CMD ["node", "index.js"]
