# Finish Line TODO

## Core Workflow
- [x] Minimal landing with drag/drop upload
- [x] Auto-create doc + version + queue review
- [x] Live feed + inline highlights
- [x] Agent list hidden by default
- [x] Git-backed document history

## Reliability + Clarity
- [x] System status endpoint (redis/openai)
- [x] UI banner for missing Redis/OpenAI key
- [x] Redis helper script for start/stop/status

## Polished UI
- [x] Redesign UI per new aesthetic
- [x] Live comment arrival animation

## Testing
- [x] Backend status endpoint test
- [x] Frontend status type test
- [x] End-to-end review job test with Redis + mocked OpenAI
- [x] UI helper tests for themes + types
- [x] UI integration-style test for upload -> queue flow (mock API)

## Remaining Work
- [x] Ensure worker auto-retries + backoff
- [x] Add agent theme customization UI (advanced drawer)
