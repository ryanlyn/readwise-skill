# Objective

Determine token efficiency between the Readwise skill and the official Readwise MCP on the narrow set of read-only tasks that both can complete.

The benchmark should answer three questions:

- For the same user intent, does the skill reduce end-to-end model-visible tokens?
- If there are savings, are they mostly caused by smaller tool-result payloads or by broader differences in the trace?
- Do the two approaches lead the model into meaningfully different retrieval and reasoning behavior?

The benchmark should preserve these constraints:

- Use real Readwise data, not synthetic fixtures.
- Compare only the overlap between the two approaches.
- Treat end-to-end trace length as the headline measure.
- Treat tool-result payload size as a diagnostic sub-measure, not the headline.
- Be explicit about which prompt/context costs are actually included in the harness.
- Prefer a simple, inspectable harness over infrastructure-heavy benchmarking machinery.
