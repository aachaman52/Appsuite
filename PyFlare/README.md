# PyFlare

<div align="center">
  <img src="branding/logos/svg/pyflare.svg" width="120" alt="PyFlare Logo">
  <h3>AI-native, hardware-aware development operating environment</h3>
  <p>Ubuntu 24.04 LTS · GNOME 46 · Unity-first development automation</p>
</div>

---

## Overview

PyFlare, developed under Aachman Studios, is a long-term development operating
environment designed to convert developer intent into coordinated, validated work
across deterministic tools, AI models, Unity, Blender, compilers, project knowledge,
version control, assets and local or remote compute.

PyFlare is not one AI doing everything and is not merely an Ubuntu distribution with
AI applications installed. Its core architecture is a deterministic control plane that
selects the smallest reliable capability, protects workstation resources, grants bounded
permissions and requires validation before output becomes project state.

The operating-system image and branding are an existing foundation. The complete
orchestration platform is under active development and must not be treated as
production-ready.

## Current implementation

The control-plane foundation is under [control_plane](control_plane/README.md). It now
includes strict TaskSpec decoding, registries, deterministic routing, resource admission,
scoped authorization, audit primitives, a durable task journal, workflow state,
validation and retry policies, Unity protocol gates and an authenticated Python Unity
client.

The first Unity Editor package is under
[integrations/unity/com.aachmanstudios.pyflare.automation](integrations/unity/com.aachmanstudios.pyflare.automation/README.md).
It is experimental until it compiles and passes integration tests inside supported Unity
6 editor versions.

See [Implementation Status](docs/IMPLEMENTATION_STATUS.md) for the explicit separation
between implemented, planned and research-stage components. See
[Last Work](../Last_Work.md) for the dated implementation and validation walkthrough.

## Repository structure

    PyFlare/
    ├── control_plane/         Deterministic orchestration foundation and Python client
    ├── integrations/unity/    Experimental structured Unity Editor package
    ├── branding/              Logos, icons, wallpapers, themes and cursors
    ├── branding_generator/    Branding generation pipeline
    ├── config/                OS build configuration
    ├── filesystem/            Linux filesystem overlay
    ├── desktop/               GNOME settings, dock and menu overrides
    ├── packages/              Package manifests and dependency definitions
    ├── installer/             Installer configuration and branding
    ├── applications/          Bundled application prototypes
    ├── validation/            OS and asset validators
    ├── scripts/               Build orchestration
    ├── docs/                  Architecture and development documentation
    └── tests/                 Existing OS build tests

## Control-plane development

    cd PyFlare/control_plane
    python -m pip install -e ".[dev]"
    ruff check src tests
    python -m unittest discover -s tests -v

## OS image development

Prerequisites on Ubuntu/Debian:

    sudo apt update
    sudo apt install -y squashfs-tools xorriso grub-pc-bin grub-efi-amd64-bin \
      mtools dosfstools python3 python3-pip libcairo2-dev
    pip install -r PyFlare/requirements.txt

Run validators:

    cd PyFlare
    python validation/run_all.py

Build the experimental ISO on Linux:

    cd PyFlare
    sudo python3 build.py --config config/default.yaml

## Primary architectural rules

- Hardware should limit execution speed, not ambition.
- The final routing authority is deterministic software.
- Sometimes the correct AI is no AI.
- Models are replaceable workers, not the architecture.
- Share validated project knowledge, not complete conversations.
- Unity is the primary game-engine automation target.
- Generated work remains untrusted until validation passes.
- AI workers receive task-scoped permissions.

## License

PyFlare is distributed under the repository's PyFlare license. Third-party components
retain their own licenses.
