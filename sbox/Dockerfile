FROM golang:1.25.5-alpine3.23 AS golang
FROM rust:alpine3.23 AS rust
FROM node:24-alpine3.23 AS node

FROM alpine:3.23.0

# Install base packages and build tools
RUN apk add --no-cache \
  bash \
  curl \
  wget \
  git \
  coreutils \
  build-base \
  linux-headers \
  ca-certificates \
  openssl-dev \
  pkgconf \
  jq

# Copy Go from official image
COPY --from=golang /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOPATH="/go"
ENV PATH="${GOPATH}/bin:${PATH}"

# Copy Rust from official image
COPY --from=rust /usr/local/rustup /usr/local/rustup
COPY --from=rust /usr/local/cargo /usr/local/cargo
ENV RUSTUP_HOME="/usr/local/rustup"
ENV CARGO_HOME="/usr/local/cargo"
ENV PATH="/usr/local/cargo/bin:${PATH}"

# Copy Node.js from official image
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
  && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx


RUN npm install -g @anthropic-ai/claude-code

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy bashrc configuration
COPY bashrc.sh /root/.bashrc

# Copy start script to PATH
COPY start.sh /usr/local/bin/start
RUN chmod +x /usr/local/bin/start

WORKDIR /workspace

CMD ["/bin/bash"]
