"""Checks run against the rendered Kubernetes manifests before they reach the cluster.

The single Always Free node has 12 GB and 2 OCPU, so a manifest that asks for too much
memory or forgets a hardening field is a production incident waiting to happen. These
checks read the output of `kustomize build` and fail the build instead.
"""
