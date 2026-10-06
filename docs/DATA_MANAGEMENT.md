# Data management

Keep synthetic examples separate from benchmark cases. Case files contain hidden labels and reference patches; only generated reviewer prompts belong in the reviewer session. Never send full case records directly to the model.

Archive dataset revision IDs, selection manifests, run manifests, dependency environment, results, scored tables, annotation decisions and analysis output together. Preserve original files when repairing or transforming data. Record timestamps and any transformations. The API response ID and prompt hash are retained in each result.

Large datasets, prompts and results are ignored by Git. Share research artifacts through an appropriate archive after checking licenses and trace contents for credentials, personal information and other sensitive material. Check the upstream dataset terms at the pinned revisions; this project does not grant rights to redistribute them.
