# Agent Instructions

This repository is OpenTrain's internal Open Label annotation runtime. It is not the customer-facing product, not the system of record, and not a generic Label Studio product surface.

## Required Product Boundary

- OpenTrain app is the product shell, control plane, and source of truth.
- Open Label is OpenTrain's first-party data labeling platform.
- This runtime is internal annotation infrastructure used to render annotation/review experiences and return runtime evidence to OpenTrain.
- Job-linked assessments are one optional workflow. They do not define the product boundary.
- The long-term product is standalone employer-owned production data labeling inside OpenTrain.

## User-Facing Rules

Normal employers, candidates, AI Trainers, and freelancers should not see or manage:

- Label Studio login, signup, account setup, or separate runtime accounts.
- Runtime project IDs, runtime provisioning IDs, API tokens, webhook secrets, or runtime setup flows.
- Provider-connection, provider-linking, shared-account, or external-credential UX for Open Label.

Use OpenTrain/Open Label language in user-facing copy:

- project
- workspace
- dataset
- task
- assignment
- review
- rework
- workspace ready
- prepare workspace
- setup pending

Runtime, provisioning, webhook, environment, and Label Studio implementation language is acceptable in source code, operator docs, API names, and internal diagnostics, but it should stay hidden from normal product workflows.

## Before Changing Product Behavior

Read the central product spec:

https://app.clickup.com/9016532895/v/dc/8cpuqwz-7776/8cpuqwz-12236

Also read `docs/open-label-product-context.md` in this repository.

When implementing a change, check whether it keeps OpenTrain as the control plane. If it asks normal users to configure Label Studio/runtime details, paste runtime IDs, create runtime accounts, or connect Open Label like an external provider, it is misaligned with the product direction.

## What This Task Does Not Mean

Keeping upstream Label Studio implementation code is acceptable. Open Label can use Label Studio-compatible annotation primitives. The product error to avoid is letting upstream Label Studio framing, setup flows, account models, or tenant assumptions become the normal OpenTrain user experience.

