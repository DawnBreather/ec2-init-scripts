# Rules and Purpose
* This scripts are supposed to be used as User Init Scripts in AWS EC2s (we have an "entrypoint" User Init script, which then pulls scripts from "gists" library: a kind of modular system)
* Key assumption: we consider Ubuntu OS v24+
* All scripts shall be idempotent
* We shall stick to DRY + KISS
