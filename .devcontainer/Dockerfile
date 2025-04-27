# [Choice] Python version: 3.10
FROM mcr.microsoft.com/vscode/devcontainers/python:0-3.10

ENV DEBIAN_FRONTEND=noninteractive
ENV PIP_NO_CACHE_DIR=1

# Install OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    python3-dev \
    libpq-dev \
    libffi-dev \
    zlib1g-dev \
    libjpeg-dev \
    nodejs \
    npm \
  && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Set working directory
WORKDIR /usr/src/app
