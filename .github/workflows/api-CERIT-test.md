---
on:
  workflow_dispatch:

permissions:
  contents: read

engine:
  id: copilot

---

# CERIT API Test

Ask the configured AI model to:

1. Reply with exactly: "CERIT API connection successful".
2. State which model it believes it is using.
3. Explain the result in one short sentence.

Do not modify any repository files.
