# Publication review

Reviewed on **2026-11-25**.

## Source and history

- The repository contains the recognition engine, tests, examples, documentation and license notices.
- Generated data, model downloads, environment files, credentials and local build products are excluded from Git.
- Personal email addresses have been replaced with the maintainer's public GitHub noreply identity in reachable commits.
- Gitleaks 8.30.1 reported no credential findings in reachable Git history. CI repeats that scan with full history and a checksum-verified scanner.
- Source download URLs point to public model and card-data providers. The engine does not include account-specific hosting, storage, authentication or application-deployment configuration.

## Repository settings

The review found no repository Actions secrets or variables, environments, deploy keys, webhooks, deployment records or uploaded Actions artifacts. Pages and Wiki were disabled.

## Published index artifacts

Both index releases were checked against their manifests and all **80 assets** were checksum-verified. Each transport bundle contains exactly these six files:

```text
models/dinov2-small.onnx
DINOV2_LICENSE.txt
indexes/snapshot/embeddings.npy
indexes/snapshot/hashes.npy
indexes/snapshot/catalog.sqlite
indexes/snapshot/manifest.json
```

Archive user/group names are empty and numerical ownership fields are normalized. Bundles contain neither source photographs nor environment files. Metadata describes public card references and index provenance.

The full snapshot has 115,084 indexed faces. The older evaluation snapshot is explicitly partial. Their coverage and data/model licensing remain documented separately.

## Attribution

Public repository ownership, license authorship, dependency credits and fixture provenance remain visible. They are not authentication credentials. Required upstream copyright notices and model/data rights must accompany redistribution.

This review covers reachable source history, current repository configuration and the published artifacts. It cannot attest to previously downloaded copies or unreferenced objects retained by the hosting service.
