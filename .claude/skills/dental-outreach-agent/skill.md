# Dental Outreach Agent

A skill for managing dental patient outreach via Gmail.

## MCP Dependencies

Requires the `gmail` MCP server configured in `.claude/settings.json`.

## Usage

This skill uses Gmail to send outreach emails to dental patients.

## Configuration

Update `.claude/settings.json` with the actual Gmail MCP server command and args:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "<path-to-gmail-mcp-server>",
      "args": ["<arg1>", "<arg2>"]
    }
  }
}
```
