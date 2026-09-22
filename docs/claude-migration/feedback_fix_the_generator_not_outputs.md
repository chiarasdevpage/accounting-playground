---
name: feedback-fix-the-generator-not-outputs
description: "For LLM-generated artifacts (role YAMLs, prompts, configs), fix the generator's prompt — don't hand-edit individual outputs"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3f2e51a8-ff48-4233-8f29-81f6dc5ae9ec
---

In projects where an LLM generates structured artifacts (e.g. `RoleCriteria` YAMLs in the Interview Assistant), the user treats existing files as **test baselines / demo data, not production data**. When a generated artifact looks wrong, the fix goes in the generator's prompt — never in the artifact file itself.

**Why:** During the Interview Assistant build (2026-05-26), the user explicitly redirected after I hand-edited the PwC role YAML to include `certifications` in `must_have_sections`: *"focus less on the specific role yaml files, focus on the generation of those files as well. those already present yaml files should be considered more like the demo resumes, as baselines to test the program with."* The point of the generator is that the system handles any new role at runtime; hand-curating individual outputs masks generator weaknesses and creates artifacts that can't be reproduced.

**How to apply:**
- When an LLM-generated output is wrong, find which prompt produced it and fix THAT. Test by regenerating, not by editing the output.
- When tempted to "just fix this one file to demonstrate the feature works" — instead, regenerate it via the production path and let the prompt prove the system works.
- Existing checked-in artifacts can be regenerated freely; their purpose is to give the dev environment something to test against, not to be authoritative.
- This is the same principle as [[feedback-prefer-root-cause-fixes]] applied to data: hand-curating outputs is a per-case patch; fixing the generator is the root cause.
