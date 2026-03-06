# Privacy Notice

## What data we collect

When you use the OpenForge CLI, the following telemetry events may be sent to `openforge.gitguardian.com`:

| Event | Data sent |
|-------|-----------|
| `add` | Source identifier (e.g., `owner/repo`), content type, skill names, agent names |
| `remove` | Package name, content type |
| `find` | Number of search results (search queries are NOT transmitted) |

No personally identifiable information (PII) is collected. No IP addresses are stored server-side.

## How to opt out

Any of these methods will disable telemetry:

```bash
# Environment variable (respected by convention: https://consoledonottrack.com/)
export DO_NOT_TRACK=1

# CLI config
openforge config set telemetry.enabled false
```

Telemetry is also automatically disabled in CI environments (detected via `CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, `CIRCLECI`, `TRAVIS`, `BUILDKITE`, `JENKINS_URL` environment variables).

## Purpose

Telemetry helps us understand which plugins and skills are popular, and which agents are most used. This data guides development priorities.

## Data controller

GitGuardian SAS
Contact: privacy@gitguardian.com

## Your rights

If you have questions about your data or wish to exercise your rights under GDPR or other privacy regulations, contact privacy@gitguardian.com.
