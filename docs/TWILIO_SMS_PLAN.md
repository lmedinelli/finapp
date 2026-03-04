# Twilio SMS Integration Plan (API Key Auth)

Validated on: March 3, 2026.

## Objective
Add a production-safe Twilio integration to send SMS alerts from the platform (admin diagnostics + alert engine), authenticated with Twilio API Keys.

## Confirmed Twilio Requirements (from official docs)
- Twilio recommends API Key + API Secret for production auth (HTTP Basic auth).
- For Twilio helper SDK usage, keep `Account SID` available alongside API key credentials.
- Outbound SMS is created through the Twilio Message resource.
- Delivery tracking should use outbound message status callbacks.
- Non-billable integration testing should use Twilio Test Credentials + magic phone numbers.
- Webhook endpoints should validate `X-Twilio-Signature` using Auth Token.

## Proposed Scope (Phase 1)
- Send outbound SMS notifications for system alerts and recommendation events.
- Add admin "Send test SMS" action from Diagnostics.
- Persist outbound message metadata and delivery status in admin DB.
- Add webhook endpoint for Twilio status callbacks.
- Add an agent tool operation for SMS notification dispatch (`send_sms_alert`).

## Environment Variables
Add to `.env.example` and `.env`:
- `TWILIO_ENABLED=true`
- `TWILIO_ACCOUNT_SID=AC...`
- `TWILIO_API_KEY_SID=SK...`
- `TWILIO_API_KEY_SECRET=...`
- `TWILIO_MESSAGING_SERVICE_SID=MG...` (preferred)
- `TWILIO_FROM_NUMBER=+1...` (fallback if Messaging Service is not used)
- `TWILIO_STATUS_CALLBACK_URL=https://<your-host>/v1/webhooks/twilio/message-status`
- `TWILIO_AUTH_TOKEN=...` (for webhook signature validation)
- `TWILIO_MAX_SMS_PER_MIN=30`
- `TWILIO_TIMEOUT_SECONDS=15`

## Backend Design
1. Service
- File: `app/services/twilio_sms.py`
- Public methods:
  - `is_configured() -> bool`
  - `send_sms(to: str, body: str, metadata: dict[str, str] | None = None) -> dict[str, Any]`
  - `send_bulk(messages: list[TwilioOutboundMessage]) -> list[TwilioSendResult]`
  - `validate_webhook_signature(url: str, form_data: dict[str, str], signature: str) -> bool`

2. API routes
- Admin-protected:
  - `POST /v1/admin/twilio/test-sms`
  - `GET /v1/admin/twilio/status`
  - `GET /v1/admin/twilio/messages?limit=...&status=...`
- Public webhook:
  - `POST /v1/webhooks/twilio/message-status`

3. Data model (SQLite `data/admin/admin.db`)
- `twilio_message_log`
  - `id` (pk)
  - `created_at`
  - `updated_at`
  - `message_sid` (unique)
  - `to_number`
  - `from_number`
  - `body_preview`
  - `status`
  - `error_code`
  - `error_message`
  - `source` (admin-test | alerts-engine | agent-tool)
  - `related_entity_type` / `related_entity_id` (optional linkage)
- `twilio_webhook_log` (optional, lightweight audit)

4. Alert integration
- Extend alert workflow dispatcher:
  - Trigger SMS when alert condition is met and user has opted into SMS.
  - Record every send attempt and callback status.

## Agentic Workflow Integration
- Register a Twilio tool adapter in the chat orchestration layer:
  - Tool name: `send_sms_alert`
  - Guardrails:
    - admin/subscribed permission check
    - recipient allowlist (initial rollout)
    - per-user and global rate limits

## Admin UI Changes
- Diagnostics tab:
  - Twilio card in Integration Semaphore.
  - "Send test SMS" form: `to_number`, message template.
  - Last delivery status table.
- Users tab:
  - Add optional `phone_number`, `sms_opt_in` fields.

## Testing Plan
1. Unit tests
- Mock Twilio client for send success/failure paths.
- Validate fallback behavior (`MessagingServiceSid` vs `From`).
- Validate webhook signature verification helper.

2. Integration tests
- API tests for:
  - `admin/twilio/status`
  - `admin/twilio/test-sms`
  - webhook callback persistence

3. Live-safe tests
- Use Twilio Test Credentials and magic numbers (no charges).
- Validate expected error scenarios and successful simulation.

## Security & Compliance
- Never log full secrets.
- Mask phone numbers in UI logs (`+1******1234`).
- Enforce opt-in/opt-out policy before sending SMS.
- Validate Twilio signatures for incoming webhooks.
- Add retry with backoff for transient `429`/`5xx`.

## Suggested Rollout
1. Implement backend service + DB tables + status endpoint.
2. Add admin test-SMS action.
3. Add webhook status tracking.
4. Connect alert subscriptions to SMS dispatch.
5. Enable agent tool dispatch with strict permissions.

## Sources
- Twilio API requests (auth best practices): https://www.twilio.com/docs/usage/requests-to-twilio
- Twilio API keys overview: https://www.twilio.com/docs/iam/api-keys
- Twilio Message resource: https://www.twilio.com/docs/messaging/api/message-resource
- Messaging webhooks/status callbacks: https://www.twilio.com/docs/usage/webhooks/messaging-webhooks
- Webhook security / request validation: https://www.twilio.com/docs/usage/security
- Test credentials + magic numbers: https://www.twilio.com/docs/iam/test-credentials
- Twilio Python SDK (API key constructor usage): https://github.com/twilio/twilio-python
