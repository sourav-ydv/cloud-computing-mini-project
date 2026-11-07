# AI use

This project was built with help from Claude (Anthropic) as allowed in the assignment handout.

Where it was used:
- Explaining the sequence-level knowledge distillation method from Kim and Rush (2016) in plain terms before implementation.
- Drafting the first version of the worker, training, service and Kubernetes manifests, which I then ran, debugged, and adjusted against my own cluster and data.
- Help with the subnetting arithmetic in network/subnets.md, which I verified by hand.
- Help structuring the GitHub Actions workflow.

How it was checked:
- Every script was run against the real data (commands_pool.jsonl, validation.jsonl) and the real cluster, not just read.
- score.py, nacl_sim.py and the unit tests in tests/ were used to verify behaviour rather than trusting the generated code.
- The counts and numbers reported in the report come from actual runs recorded in results/, not from the AI's suggestions.

What I would not use AI for: judging whether the actual measured numbers (loss, accuracy, latency, cost) were "good enough" — those are reported as measured, not adjusted.
