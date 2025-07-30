# 📝 Changelog

Notable changes to this project documented here.

---
## [1.1.0] - 2025-07-30
### Updated
- Simplified creation, now auto finds user clientId on install
- Updated translations, now easy for other to add languages
- Perform history pull up front, no more waiting
- Update all api Entities calls to be normilized for HA
### Added
- Added Diagnostics download, makes reporting a problem easier
- Added per Lock Revisions and versions sensor
### Note
- (Yes Sifely icons submitted, just waintg HA approval)

---
## [1.0.3] - 2025-07-27
### Added
- Setup git bug, ferature, issue reporting
- Added git LICENSE
- Adding git formats
- Updated directory structure for manual download in to HA
- Create CODEOWNERS
- Update readme
- Hacs integration
- Fixed manifest.json

---
## [1.0.0] – 2025-07-22
### Added
- Initial public release of `sifely_cloud`
- Lock discovery via `/v3/key/list`
- Entity setup for:
  - Battery sensor
  - Lock state and control
  - Open/closed sensor
  - Lock history with CSV persistence
  - Cloud error tracking
  - Privacy lock and tamper alert binary sensors
- Lock history auto-refresh every 5 minutes
- UI-friendly integration with diagnostics and YAML options





