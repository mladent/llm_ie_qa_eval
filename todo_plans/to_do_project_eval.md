## Plan: Single-File Evaluation Project

Add a project-spec layer on top of the existing evaluation pipeline so one YAML file becomes the source of truth for a repeatable run: which CV files to read, which prompt file to use, which provider/model to call, where outputs go, and whether MLflow tracking is enabled. Reuse the current run recording, provenance, metric computation, artifact export, and MLflow logging instead of replacing them; the main change is to convert the YAML project spec into the dataset/prompt/config inputs that the current runner already expects.

**Steps**
1. Phase 1 — Project spec design. Define a single YAML schema for one evaluation project with sections for experiment metadata, CV document file paths, prompt file path, model/provider settings, execution settings, tracking settings, and exports. Keep one provider/model per project, prompt by file path, and explicit CV file paths only.
2. Phase 1 — Runtime input contract. Decide the normalized in-memory document shape the runner will consume after project-spec loading. Reuse the current dataset item shape used by run_evaluation.py: each item should still provide id, text, and gold so the downstream metric pipeline remains unchanged.
3. Phase 1 — Gold answer strategy. Define each CV entry in the project YAML as document path plus a separate gold JSON file path. This keeps the YAML readable while still satisfying the current compute_metrics flow in run_evaluation.py, which requires gold labels for precision, recall, and F1.
4. Phase 2 — Config loader extension. Extend load_eval_config in /home/mladent/Documents/Projects/llm_ie_qa_eval/config_loader.py so it can load either the current eval settings YAML or the new project YAML, validate the new required fields, and keep the same precedence model for optional CLI overrides. Add fail-fast validation for missing CV files, missing prompt file, invalid provider, invalid model settings, and missing gold data.
5. Phase 2 — Project materialization. Add a narrow project-spec materialization step before the main loop in /home/mladent/Documents/Projects/llm_ie_qa_eval/run_evaluation.py. That step should read each CV file, build the current dataset list expected by validate_dataset_shape and the document loop, resolve the prompt file, and derive stable identifiers and SHA256 hashes for provenance.
6. Phase 2 — Provenance upgrade. Extend ExperimentProvenance in /home/mladent/Documents/Projects/llm_ie_qa_eval/evaluation/run_record.py so the recorded metadata reflects the project-spec source, the set of CV files used, and hashes or a manifest hash for the project inputs. Keep the existing per-run timestamping and run-level CanonicalRunRecord untouched.
7. Phase 3 — Orchestration adjustments. Update main in /home/mladent/Documents/Projects/llm_ie_qa_eval/run_evaluation.py to use the project-materialized dataset instead of assuming a dataset.json file. Keep the existing retry loop, append_run_record persistence, metric computation, final console printing, and MLflowTracker calls intact.
8. Phase 3 — Artifact story. Persist the resolved project spec alongside the current config snapshot and provenance so each experiment directory contains the exact declarative project input used for the run. This should live next to config.json and provenance.json in the existing outputs/experiments/{experiment_id}/ structure.
9. Phase 3 — MLflow alignment. Extend the parameter logging in /home/mladent/Documents/Projects/llm_ie_qa_eval/mlflow_utils.py call sites so MLflow captures the project-spec path/name, document count, and a stable project hash in addition to the existing provider/model/prompt/dataset fields.
10. Phase 4 — Tests. Add focused tests around: project-spec parsing and validation; CV file materialization into dataset items; end-to-end mocked repeated runs from a project YAML; and failure cases such as missing files or missing gold data. Reuse the style of /home/mladent/Documents/Projects/llm_ie_qa_eval/tests/test_repeated_runs.py and preserve the existing metrics/provider normalization tests.
11. Phase 4 — Example and docs. Replace or supplement the current single settings example with one sample project YAML and update /home/mladent/Documents/Projects/llm_ie_qa_eval/Readme.md so the documented command is a single --config project.yaml run. Document the required YAML fields and the expected CV-plus-gold input pattern.

**Relevant files**
- /home/mladent/Documents/Projects/llm_ie_qa_eval/config_loader.py — extend EvalConfig loading and validation, likely by adding a project-spec-aware data section or a parallel project config object.
- /home/mladent/Documents/Projects/llm_ie_qa_eval/run_evaluation.py — add the project-spec-to-runtime-input materialization step before the current document loop in main.
- /home/mladent/Documents/Projects/llm_ie_qa_eval/evaluation/run_record.py — extend ExperimentProvenance to capture project-spec identity and project input manifest details.
- /home/mladent/Documents/Projects/llm_ie_qa_eval/mlflow_utils.py — keep the MLflow wrapper but expand logged params via current call sites.
- /home/mladent/Documents/Projects/llm_ie_qa_eval/persistence.py — reuse the current experiment directory and add a persisted copy of the resolved project spec if needed.
- /home/mladent/Documents/Projects/llm_ie_qa_eval/tests/test_repeated_runs.py — template for the new end-to-end mocked project-spec test.
- /home/mladent/Documents/Projects/llm_ie_qa_eval/tests/test_metrics.py — verify existing metric behavior still holds once the input source changes.
- /home/mladent/Documents/Projects/llm_ie_qa_eval/Readme.md — document the new one-file project workflow.

**Verification**
1. Add unit tests for project YAML validation covering missing CV file, missing prompt file, invalid provider, invalid numeric settings, and missing gold reference.
2. Add a focused integration test that creates temporary CV files, a prompt file, and one project YAML, then runs run_evaluation.main() with mocked provider calls and asserts: runs.jsonl exists, provenance/config artifacts exist, MLflow tracker receives project params, and final aggregate artifacts are produced.
3. Confirm the final console summary still prints total runs, failures, precision, recall, and F1 for the project-based invocation.
4. Confirm experiment provenance and MLflow params now identify the project-spec path/hash and document count.
5. Run the existing tests for repeated runs, metrics, and provider normalization to guard against regressions in the downstream evaluation pipeline.

**Decisions**
- Included scope: one YAML file per evaluation project, explicit CV file paths, prompt referenced by file path, single provider/model per project, existing run recording and MLflow tracking preserved.
- Required design decision: every document must still have gold/reference output available, either inline in the project YAML or via a referenced gold JSON file, because evaluation metrics cannot be computed otherwise.
- Deliberately excluded from the first version: multiple provider/model variants in one project file, inline prompt text, resumable partial runs, and cross-project comparison orchestration.

**Further Considerations**
1. Recommended gold-data option: support a gold file path per CV entry rather than large inline JSON blocks, because that keeps the project YAML readable while preserving the single source of run configuration.
2. Recommended implementation boundary: keep project-spec parsing/materialization separate from the extraction loop so the current metrics and MLflow code stay stable and low-risk.
3. Recommended compatibility path: allow the old dataset.json-based config to continue working so the new project mode is additive rather than a breaking rewrite.