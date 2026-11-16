# Brand assets

Home Assistant brand images (icon.png / logo.png) are published through the
official [home-assistant/brands](https://github.com/home-assistant/brands) repo,
keyed by the `chore_assistant` domain, not shipped inside the integration.

To add them:
1. Create a 256x256 (and optional 512x512 `@2x`) `icon.png`.
2. Open a PR to `home-assistant/brands` under `custom_integrations/chore_assistant/`.

Until then HACS and HA fall back to a default icon, which is fine for local use.
