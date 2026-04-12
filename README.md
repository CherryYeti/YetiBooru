# YetiBooru
YetiBooru is a passion project of mine, born from features that were missing from szurubooru.

Keep in mind that this is extremely alpha software, and it is not meant to be exposed on a public instance quite yet.

- [x] Handle image/video uploads
- [x] Handle basic account creation
- [x] Handle gif uploads
- [x] Test if uploads need chunking
- [x] Add admin account/permissions
- [ ] Add moderation tools
- [ ] Make API gelbooru/szurubooru compatible?

Bootstrap notes:
- Set `OWNER_EMAILS` to a comma-separated list of trusted emails to pin the initial owner account(s).
- If `OWNER_EMAILS` is empty, the first authenticated user can claim owner access from the admin user screen.


## How to run
- Clone the repository
- Run `docker compose up -d`