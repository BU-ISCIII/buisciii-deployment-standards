# Mailpit add-on

The Mailpit add-on provides a disposable SMTP catcher for local/test stacks.
It is deliberately test-only: production mail delivery must use the
institutional SMTP endpoint or relay selected by the deployment operator.

Containers reach the catcher at `mailpit:1025`; its inbox is published only on
host loopback by default. Select it with:

```json
"mailpit": {
  "CONFIG_SERVICE": "app",
  "MODES": ["test"]
}
```
