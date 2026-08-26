# Atlas n8n Skill

Purpose: design, inspect, test and maintain n8n workflows used by Atlas/ecomSX222.

## Capabilities
- Inspect workflows, nodes, connections and execution structure.
- Create and update workflows and nodes through the approved n8n MCP gateway.
- Build triggers, transformations, API calls, AI-agent chains, validation and logging.
- Connect Shopify automation to AI analysis and controlled execution.
- Diagnose failed executions and improve workflow reliability.

## Workflow
1. Inspect the existing workflow before editing it.
2. Make the smallest safe change.
3. Keep destructive operations disabled by default.
4. Validate node configuration and connections.
5. Run a test when safe and verify the saved workflow afterward.
6. Avoid duplicate nodes/actions on retries and restarts.

## Safety
- Never expose MCP/API tokens or credentials.
- Do not delete workflows/nodes or deactivate production automation without explicit approval.
- Keep credentials in n8n/Railway secret storage, not prompts or repository files.
- Require explicit approval for destructive actions.
