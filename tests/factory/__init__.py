"""Factory test suite — business-documentary pipeline governance.

Covers the contracts the Master Plan declares non-negotiable:

- the 12-stage manifest and its 13 director skills exist and load;
- every tool a stage declares is a real registry tool;
- every stage artifact validates against its schema;
- no downstream artifact may reference an evidence/source/scene/asset ID
  that does not exist in the artifact that defines it;
- strict zero-cost mode blocks unknown cost, unknown route and unapproved
  paid actions, and never reroutes after auth/billing/rate-limit failures;
- the whole artifact chain can be checkpointed through ``lib.checkpoint``
  in manifest order, including its human gates.
"""
