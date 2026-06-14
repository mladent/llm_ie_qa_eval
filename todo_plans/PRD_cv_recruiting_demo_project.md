# PRD: CV Recruiting Enterprise Demo Project

## 1. Purpose
Create a commit-ready demo project inside this repository that demonstrates realistic CV extraction and evaluation for a business recruiting setup.

The demo must include:
- 3 realistic CV documents
- 3 corresponding gold-standard JSON files
- A dedicated extraction prompt
- A dedicated JSON schema
- A dedicated project YAML config for evaluator project mode
- Minimal docs and test updates so the demo is discoverable and verifiable

## 2. Business Goal
Show a convincing end-to-end example where enterprise recruiting data can be extracted from unstructured CV text and evaluated with this platform's repeatability and scoring pipeline.

Success for stakeholders:
- Demo assets look realistic and business-plausible.
- Demo runs with current CLI and produces standard artifacts under outputs.
- No evaluator refactor is needed for demo scope.

## 3. Scope
### In Scope
- New demo asset package under a dedicated folder.
- Rich recruiting field taxonomy represented as list-of-string fields.
- CVs with depth, years of experience, leadership, education, soft skills, languages, and recruiting signals.
- README update with run instructions.
- Focused test updates for config loading and project-run behavior.

### Out of Scope
- Nested JSON extraction output (V2).
- New scoring engines or comparator redesign.
- API/business pipeline changes.
- Multi-provider orchestration in one config.

## 4. Constraints
The current evaluator contract requires extraction output to be object fields with array-of-string values.

Implications:
- Complex structures (for example skill depth) must be encoded as structured strings.
- Demo schema and gold files must enforce list[string] for all configured fields.

## 5. Proposed Repository Additions
Target root: demo/cv_recruiting_enterprise

Planned structure:

```text
demo/
  cv_recruiting_enterprise/
    cvs/
      cv_001_senior_data_scientist.txt
      cv_002_engineering_manager.txt
      cv_003_ai_product_engineer.txt
    gold/
      cv_001_senior_data_scientist.json
      cv_002_engineering_manager.json
      cv_003_ai_product_engineer.json
    prompts/
      cv_extraction_enterprise.txt
    schema/
      cv_extraction_output.schema.json
    project.yaml
```

## 6. Planned File Changes
### 6.1 New Files
1. demo/cv_recruiting_enterprise/cvs/cv_001_senior_data_scientist.txt
2. demo/cv_recruiting_enterprise/cvs/cv_002_engineering_manager.txt
3. demo/cv_recruiting_enterprise/cvs/cv_003_ai_product_engineer.txt
4. demo/cv_recruiting_enterprise/gold/cv_001_senior_data_scientist.json
5. demo/cv_recruiting_enterprise/gold/cv_002_engineering_manager.json
6. demo/cv_recruiting_enterprise/gold/cv_003_ai_product_engineer.json
7. demo/cv_recruiting_enterprise/prompts/cv_extraction_enterprise.txt
8. demo/cv_recruiting_enterprise/schema/cv_extraction_output.schema.json
9. demo/cv_recruiting_enterprise/project.yaml

### 6.2 Modified Files
1. Readme.md
   - Add a section describing this demo project.
   - Add exact run command using project mode.
   - Clarify list-of-strings output constraint for this demo.

2. tests/test_project_config.py
   - Add a test that loads demo project config and validates expected fields/documents wiring.

3. tests/test_project_run.py
   - Add or extend a mocked run test to validate manifest and extraction fields for demo taxonomy.

## 7. Demo Extraction Field Catalog
The demo will use this explicit field set in project.yaml under data.extraction_fields:

1. candidate_identity
2. profile_summary
3. total_experience_years
4. target_roles
5. core_skills
6. skill_depth_matrix
7. tools_platforms
8. cloud_devops
9. ai_ml_specializations
10. domain_experience
11. leadership_management
12. project_achievements
13. education
14. certifications
15. languages
16. soft_skills
17. recruiting_signals
18. compensation_mobility

## 8. Data Encoding Rules
To keep complex information while preserving evaluator compatibility:

1. All values are arrays of strings.
2. Years and depth are represented in structured strings.
3. Use consistent separators for readability and model learnability.

Recommended string patterns:
- Skill depth: "Python | 8 years | expert | built production ETL and APIs"
- Leadership scope: "Managed 9 engineers | 3 squads | hiring ownership"
- Achievement: "Reduced model serving latency 42% | saved ~120k USD yearly"
- Mobility: "Location: Berlin (EU work authorization) | Notice: 2 months"

## 9. CV Content Requirements
Each of 3 CVs must include:
- Name and headline
- Summary section
- Work experience with dates and measurable outcomes
- Skills and tools
- Education
- Certifications
- Languages
- Soft skills
- Recruiting logistics (location, notice period, preferred role)

Variation requirements across profiles:
- CV 1: Senior IC specialist with deep technical impact
- CV 2: People manager with delivery and coaching responsibility
- CV 3: Product-oriented engineer blending ML + full-stack execution

## 10. Gold JSON Requirements
Each gold file must:
- Include all 18 fields listed above
- Keep each field as list of strings
- Be realistic and internally consistent with its CV text
- Include empty arrays only when truly absent in source CV

Quality bar:
- Plausible chronology
- Plausible tech stack combinations
- Plausible years of experience
- Explicit business impact statements

## 11. Demo Schema Requirements
File: demo/cv_recruiting_enterprise/schema/cv_extraction_output.schema.json

Requirements:
- Draft 2020-12 schema
- type: object
- required: all 18 fields
- each field type: array of string
- additionalProperties: false

## 12. Demo Prompt Requirements
File: demo/cv_recruiting_enterprise/prompts/cv_extraction_enterprise.txt

Requirements:
- Clearly list all 18 output fields
- Instruct model to return JSON only
- Instruct model each field must be array of strings
- Include short examples of structured strings for years/depth/scope
- Emphasize no nested objects

## 13. Demo Project Config Requirements
File: demo/cv_recruiting_enterprise/project.yaml

Requirements:
- Use project mode data.documents with 3 entries
- Include data.prompt_path and prompt_id
- Include data.extraction_fields with explicit field order
- Set model/provider defaults compatible with repo examples
- Enable hybrid scoring
- Point hybrid.schema_path to demo schema
- Initially reuse existing config/hybrid_scoring.yaml rubric

## 14. Implementation Plan
### Phase 1: Contract Freeze
- Finalize field catalog and string encoding conventions.
- Freeze scope as list[string] only.

### Phase 2: Asset Authoring
- Write 3 CV text documents.
- Write 3 gold JSON files.
- Write dedicated prompt.
- Write dedicated schema.
- Write project.yaml.

### Phase 3: Integration
- Validate config paths and extraction field alignment.
- Ensure run_evaluation project mode loads without code changes.

### Phase 4: Docs and Tests
- Update Readme.md with run instructions and demo context.
- Add focused test updates in project config and project run tests.

### Phase 5: Verification and Commit Readiness
- Run targeted tests.
- Run one mocked or local demo invocation.
- Confirm artifact generation paths.
- Prepare final commit.

## 15. Verification Checklist
1. Config load validation passes for demo project.yaml.
2. Gold files pass list[string] contract expectations.
3. run_evaluation project mode runs with demo config.
4. outputs/experiments/<id>/ contains:
   - runs.jsonl
   - provenance.json
   - config.json
   - project_manifest.json
5. README command works with committed paths.
6. Updated tests pass.

## 16. Risks and Mitigations
1. Risk: Overly long prompt harms extraction consistency.
   - Mitigation: Keep concise field instructions and stable formatting examples.

2. Risk: Inconsistent gold encoding across files.
   - Mitigation: Define strict string templates and review all gold entries for consistency.

3. Risk: Demo appears synthetic or shallow.
   - Mitigation: Include concrete outcomes, realistic stacks, realistic timelines, role-specific language.

4. Risk: Field explosion increases parse errors.
   - Mitigation: Keep strict JSON-only prompt and align schema + extraction_fields exactly.

## 17. Acceptance Criteria
1. A new demo folder exists with all planned files.
2. All 3 CV/gold pairs are plausible, detailed, and business-convincing.
3. Demo project config is runnable through existing CLI.
4. No runtime code refactor required.
5. README contains copy-paste command for demo run.
6. Focused tests for demo wiring are present and passing.

## 18. Commit Plan
Single commit recommended:
- feat(demo): add enterprise CV recruiting demo project with schema, prompt, gold data, config, docs, and tests

If split commits are preferred:
1. feat(demo): add CV/gold/schema/prompt/project assets
2. test(demo): add demo project config/run tests
3. docs(demo): add README usage section

## 19. Run Command (Target)
```bash
python run_evaluation.py --config demo/cv_recruiting_enterprise/project.yaml
```

## 20. Notes
This PRD intentionally optimizes for realistic demo quality and repository compatibility. It does not introduce nested-object extraction; that remains a separate V2 track.
