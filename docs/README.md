# Seven documentation

Seven is a layer between a person and their Windows computer. You say or type what you want, and Seven does it on the
machine: opens and arranges apps, changes system settings, finds files, runs routines, keeps your tasks and reminders,
and remembers what matters to you. It runs entirely on the computer and keeps working without the internet.

This folder is the engineering and product documentation for Seven. The in-app **Guide** page is the user manual;
these documents explain what Seven is, how it is built and how it is shipped.

## Where to start

| You want to | Read |
|---|---|
| Understand the product and where it is going | [Product overview](product/overview.md), [PRD](product/prd.md), [Roadmap](product/roadmap.md) |
| See how the whole system fits together | [Architecture overview](architecture/overview.md) |
| Understand one part in depth | [Components](components/README.md), starting with the [Brain](components/brain.md) |
| Run Seven from source and make a change | [Development setup](development/setup.md), [Testing](development/testing.md), [Contributing](../CONTRIBUTING.md) |
| Ship a release | [Release process](development/release-process.md) |
| Build the installer and test as a brand-new user | [Installer and fresh-install testing](development/installer-and-fresh-install-testing.md) |
| Know what data Seven keeps and what leaves the machine | [Privacy and data](architecture/privacy-and-data.md), [Security policy](../SECURITY.md) |
| Look up an endpoint | [HTTP API reference](reference/http-api.md) (generated) |
| Know why something was built a certain way | [Architecture decisions](architecture/decisions/README.md) |

## Map

```
docs/
  README.md                     this page
  product/
    overview.md                 what Seven is, who it is for, principles
    prd.md                      product requirements for the 1.x beta
    roadmap.md                  phases, versions and what ships next
    plans-and-pricing.md        tiers and how limits are enforced
  architecture/
    overview.md                 processes, data flow, folders, storage
    privacy-and-data.md         what is stored, where, and what goes online
    decisions/                  architecture decision records (ADRs)
  components/
    README.md                   index and status of each component
    brain.md                    complete: pipeline, memory, actions, learning
    hands.md                    complete: apps, windows, system, files
    workspaces.md               complete: capture, browser tabs, restore without duplicates
    knowledge.md                complete: documents, how Seven reads them
    ears.md, mouth.md, memory.md,
    backend-api.md, frontend.md, desktop-shell.md,
    background-services.md, licensing-and-updates.md   outlines, filled in as each part is reworked
  development/
    setup.md                    run Seven from source
    testing.md                  test layers and how to run them
    coding-standards.md         conventions for Python, React and writing
    release-process.md          versioning, CI, installer, publishing an update
    installer-and-fresh-install-testing.md   build the installer, test as a new user, device ID
  operations/
    troubleshooting.md          common problems and where to look
  reference/
    http-api.md                 every backend endpoint (generated)
    configuration.md            config.json sections and what they control
```

## Rules for these documents

- Describe the code that exists. Anything planned or unverified is labelled as such.
- One source of truth. If something can be generated from code (API list, app map, version), generate it.
- Plain language, short sentences. No marketing claims, no em dashes.
- When a change alters behaviour described here, update the document in the same pull request.
