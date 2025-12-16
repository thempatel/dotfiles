FROM golang:1.25.5-trixie AS golang
FROM rust:1.92.0-slim-trixie AS rust

FROM debian:stable-20251208

# Install base packages and build tools
RUN apt-get update && apt-get install -y \
  bash \
  build-essential \
  ca-certificates \
  coreutils \
  curl \
  git \
  jq \
  libssl-dev \
  linux-headers-generic \
  pkgconf \
  protobuf-compiler \
  wget

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

# Copy bashrc configuration
COPY bashrc.sh /root/.bashrc

# Copy Node.js from official image
ENV BASH_ENV /root/.bash_env
RUN touch "${BASH_ENV}"

# Download and install nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | PROFILE="${BASH_ENV}" bash
RUN echo "24" > .nvmrc
RUN bash -lc 'nvm install'
RUN bash -lc 'npm install -g @anthropic-ai/claude-code'



# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Copy start script to PATH
COPY start.sh /usr/local/bin/start
RUN chmod +x /usr/local/bin/start

WORKDIR /workspace

CMD ["/bin/bash"]
