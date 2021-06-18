OS := $(shell uname)
UNAME_S := $(shell uname -s)
OS_SED :=
ifeq ($(UNAME_S),Darwin)
	OS_SED += ""
endif

ifeq ($(OS),Darwin)
	CONTAINERER=docker
else
	CONTAINERER=podman
endif
CONTAINER_TAG="quay.io/cloudservices/koku-daily"

help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo ""
	@echo "--- General Commands ---"
	@echo "  help                                  show this message"
	@echo "  lint                                  run pre-commit against the project"
	@echo "  build                                 builds the container image"
	@echo ""

lint:
	pre-commit run --all-files


build:
	$(CONTAINERER) build . -t $(CONTAINER_TAG)
