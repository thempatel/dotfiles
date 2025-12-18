if command -v docker || ! command -v podman ; then
  exit 0
fi

mkdir -p $HOME/.local/bin

ln -sf `which podman` $HOME/.local/bin/docker
