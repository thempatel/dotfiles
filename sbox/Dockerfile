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
  rsync \
  sudo \
  unzip \
  wget

SHELL ["/bin/bash", "-ic"]

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

# Create non-root user and switch to it
RUN useradd -m -s /bin/bash claude && \
    echo "claude ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers && \
    mkdir -p /workspace && chown claude:claude /workspace

USER claude
ENV HOME="/home/claude"
ENV BASH_ENV="/home/claude/.bash_env"
WORKDIR /home/claude

RUN touch "${BASH_ENV}"

# Download and install nvm
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | PROFILE="${BASH_ENV}" bash
RUN echo "24" > .nvmrc
RUN bash -lc 'nvm install'

RUN sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin
RUN curl -fsSL https://deno.land/install.sh | sh
RUN curl -fsSL https://claude.ai/install.sh | bash

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy start script and bashrc
COPY --chown=claude:claude start.sh /usr/local/bin/start
COPY --chown=claude:claude bashrc.sh /home/claude/.bashrc

WORKDIR /workspace

CMD ["/bin/bash"]
