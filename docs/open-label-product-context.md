# Open Label Product Context

Source spec: https://app.clickup.com/9016532895/v/dc/8cpuqwz-7776/8cpuqwz-12236

## Decision

Open Label is OpenTrain's first-party data labeling platform. It is not merely a recruiting assessment feature, and it is not an external provider integration.

OpenTrain is the product shell, control plane, and source of truth. This repository is the internal Open Label annotation runtime. It can use Label Studio-compatible primitives, but it must not become the normal user-facing product boundary.

## Control Plane vs Runtime

OpenTrain owns:

- employer organizations, teams, permissions, and tenant isolation
- Open Label project/workspace records
- datasets, assets, tasks, assignments, and worker access
- job, proposal, contract, and milestone relationships
- review, rework, approval, quality, dispute, reporting, audit, and payment evidence state

The runtime may own annotation-specific execution details:

- rendering labeling and review interfaces
- executing runtime task sessions
- exporting annotation artifacts for internal sync
- emitting webhooks or API callbacks to OpenTrain
- supporting operator diagnostics and repair paths

Runtime ownership does not make the runtime the product shell or source of truth.

## User-Facing Boundary

Normal users should enter Open Label through OpenTrain. They should not be asked to:

- create a Label Studio account
- sign into Label Studio separately
- configure runtime projects
- paste runtime project IDs
- manage runtime provisioning
- create API tokens
- connect Open Label as if it were Labelbox, SuperAnnotate, Encord, or another external provider

Use product language such as project, workspace, dataset, task, assignment, review, rework, workspace ready, prepare workspace, and setup pending.

Runtime IDs, provisioning records, runtime API credentials, webhook details, and environment names are internal implementation details. They may appear in code, operator docs, logs, and diagnostics, but not as normal customer workflow concepts.

## Assessment Scope

Job-linked assessments are valid as an initial Open Label workflow because employers can use small labeling tasks to evaluate candidates. They are not the whole product.

The target product is a standalone employer-owned Open Label workspace inside OpenTrain where employers can create projects, upload or connect datasets, define instructions and schemas, assign AI Trainers, review/rework output, and use completed work for reporting and payment evidence.

When making implementation decisions, check whether the architecture can grow into standalone production data labeling. If a change only works for one-off assessments and blocks standalone projects, call that out explicitly.

## External Provider Distinction

External provider integrations are for customer-owned or third-party labeling tools such as Labelbox, SuperAnnotate, Encord, external/self-hosted Label Studio, Snorkel AI, and Argilla. Those integrations use provider connections, credentials, external project IDs, sync runs, provider evidence, and admin controls.

Open Label is different: OpenTrain owns the platform. Open Label should emit shared OpenTrain labeling-work evidence directly. External providers map evidence into the shared model through adapters.

