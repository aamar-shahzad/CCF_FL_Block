# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
BUILD=build
CCF_PREFIX_VIRTUAL=/opt/ccf_virtual
CCF_PREFIX_SGX=/opt/ccf_sgx

# CCF 5.x dev image ships clang-15; older images use clang-10/12
CC := $(shell command -v clang-15 2>/dev/null || command -v clang-12 2>/dev/null || command -v clang-10 2>/dev/null || command -v clang)
CXX := $(shell command -v clang++-15 2>/dev/null || command -v clang++-12 2>/dev/null || command -v clang++-10 2>/dev/null || command -v clang++)

OE_CC!=which clang-11
OE_CXX!=which clang++-11



CPP_FILES=$(wildcard cpp/**/*.cpp)
H_FILES=$(wildcard cpp/**/*.h)
H_FILES=$(wildcard cpp/**/*.hpp)
BIN_DIR=bin

CCF_VER=ccf-5.0.0
CCF_VER_LOWER=ccf_virtual_5.0.0
CCF_SGX_VER_LOWER=ccf_sgx_4.0.7
CCF_SGX_UNSAFE_VER_LOWER=ccf_sgx_unsafe_4.0.7

.PHONY: install-ccf-virtual
install-ccf-virtual:
	wget -c https://github.com/microsoft/CCF/releases/download/$(CCF_VER)/$(CCF_VER_LOWER)_amd64.deb # download deb
	sudo apt install ./$(CCF_VER_LOWER)_amd64.deb # Installs CCF under /opt/ccf_virtual
	/opt/ccf_virtual/getting_started/setup_vm/run.sh /opt/ccf_virtual/getting_started/setup_vm/app-dev.yml --extra-vars "platform=virtual"  # Install dependencies

.PHONY: install-ccf-sgx
install-ccf-sgx:
	wget -c https://github.com/microsoft/CCF/releases/download/$(CCF_VER)/$(CCF_SGX_VER_LOWER)_amd64.deb # download deb
	sudo apt install ./$(CCF_SGX_VER_LOWER)_amd64.deb # Installs CCF under /opt/ccf_sgx
	/opt/ccf_sgx/getting_started/setup_vm/run.sh /opt/ccf_sgx/getting_started/setup_vm/app-dev.yml --extra-vars "platform=sgx" # Install dependencies

.PHONY: install-ccf-sgx-unsafe
install-ccf-sgx-unsafe:
	wget -c https://github.com/microsoft/CCF/releases/download/$(CCF_VER)/$(CCF_SGX_UNSAFE_VER_LOWER)_amd64.deb # download deb
	sudo apt install ./$(CCF_SGX_UNSAFE_VER_LOWER)_amd64.deb # Installs CCF under /opt/ccf_sgx_unsafe
	/opt/ccf_sgx_unsafe/getting_started/setup_vm/run.sh /opt/ccf_sgx_unsafe/getting_started/setup_vm/app-dev.yml --extra-vars "platform=sgx" # Install dependencies

.PHONY: build-virtual
build-virtual: .venv
	mkdir -p $(BUILD)
	cd $(BUILD) && CC=$(CC) CXX=$(CXX) cmake -DCOMPILE_TARGET=virtual -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -DVERBOSE_LOGGING=OFF -DCCF_UNSAFE=OFF -DGENERATE_PYTHON=ON -GNinja ..
	. .venv/bin/activate && cd $(BUILD) && ninja
.PHONY: build-numcpp
build-numcpp:
	mkdir -p $(BUILD)
	cd $(BUILD) && CC=$(CC) CXX=$(CXX) cmake -DCOMPILE_TARGET=numcpp -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -DVERBOSE_LOGGING=OFF -DCCF_UNSAFE=OFF -DGENERATE_PYTHON=ON -GNinja ..
	cd $(BUILD) && ninja

.PHONY: build-virtual-verbose
build-virtual-verbose:
	mkdir -p $(BUILD)
	cd $(BUILD) && CC=$(CC) CXX=$(CXX) cmake -DCOMPILE_TARGET=virtual -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -DVERBOSE_LOGGING=ON -DCCF_UNSAFE=OFF -DGENERATE_PYTHON=ON -GNinja ..
	cd $(BUILD) && ninja

.PHONY: build-sgx
build-sgx: .venv
	mkdir -p $(BUILD)
	cd $(BUILD) && CC=$(OE_CC) CXX=$(OE_CXX) cmake -DCOMPILE_TARGET=sgx -DCMAKE_EXPORT_COMPILE_COMMANDS=1 -DVERBOSE_LOGGING=OFF -DCCF_UNSAFE=OFF -DGENERATE_PYTHON=ON -GNinja ..
	. .venv/bin/activate && cd $(BUILD) && ninja

.PHONY: build-docker-virtual
build-docker-virtual:
	docker build -t lskv:latest-virtual -f Dockerfile.virtual .

.PHONY: build-docker-sgx
build-docker-sgx:
	docker build -t lskv:latest-sgx -f Dockerfile.sgx .

.PHONY: build-docker
build-docker: build-docker-virtual build-docker-sgx

.PHONY: run-docker-virtual
run-docker-virtual: .venv
	. .venv/bin/activate && python3 benchmark/lskv_cluster.py --enclave virtual

.PHONY: run-docker-sgx
run-docker-sgx: .venv
	. .venv/bin/activate && python3 benchmark/lskv_cluster.py --enclave sgx

.PHONY: debug-dockerignore
debug-dockerignore:
	docker build --no-cache -t build-context -f Dockerfile.ignore .
	docker run --rm build-context

SANDBOX_USERS ?= 100

.PHONY: run-virtual
run-virtual: build-virtual
	VENV_DIR=.venv $(CCF_PREFIX_VIRTUAL)/bin/sandbox.sh -p $(BUILD)/liblskv.virtual.so -e virtual -t virtual --initial-member-count 3 --initial-user-count $(SANDBOX_USERS) --max-http-body-size 104857600
	


.PHONY: run-virtual-verbose
run-virtual-verbose: build-virtual-verbose
	VENV_DIR=.venv $(CCF_PREFIX_VIRTUAL)/bin/sandbox.sh

.PHONY: run-virtual-http1
run-virtual-http1: build-virtual
	VENV_DIR=.venv $(CCF_PREFIX_VIRTUAL)/bin/sandbox.sh -p $(BUILD)/liblskv.virtual.so -e virtual -t virtual

.PHONY: run-virtual-verbose-http1
run-virtual-verbose-http1: build-virtual-verbose
	VENV_DIR=.venv $(CCF_PREFIX_VIRTUAL)/bin/sandbox.sh -p $(BUILD)/liblskv.virtual.so -e virtual -t virtual

.PHONY: run-sgx
run-sgx: build-sgx
	VENV_DIR=.venv $(CCF_PREFIX_SGX)/bin/sandbox.sh -p $(BUILD)/liblskv.enclave.so.signed -e release -t sgx --http2



.PHONY: run-experiment run-fl-virtual run-fl-sgx
run-experiment run-fl-virtual: .venv
	. .venv/bin/activate && python -m experiments.runner.run_ccf_fl --platform virtual --config experiments/config/mnist_iid.yaml

run-fl-sgx: .venv build-sgx
	. .venv/bin/activate && python -m experiments.runner.run_ccf_fl --platform sgx --config experiments/config/mnist_iid.yaml

.PHONY: run-paper-batch
run-paper-batch: .venv
	. .venv/bin/activate && python -m experiments.runner.run_paper_batch

.PHONY: figures
figures: .venv
	. .venv/bin/activate && python experiments/plots/generate_figures.py

.PHONY: test-ahda
test-ahda:
	g++ -std=c++17 -I cpp/app tests/test_aggregation.cpp -o /tmp/test_ahda && /tmp/test_ahda

.PHONY: tests
tests: .venv
	. .venv/bin/activate && pytest -v tests/




.PHONY: .venv
.venv: requirements.txt
	python3 -m venv .venv
	. .venv/bin/activate && pip3 install -r requirements.txt


.PHONY: execute-notebook





$(BIN_DIR)/cfssljson: $(BIN_DIR)/cfssl


.PHONY: clean
clean:
	rm -rf $(BUILD)