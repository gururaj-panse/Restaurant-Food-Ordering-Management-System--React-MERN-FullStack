"""
Password hashing — DB-layer behavior, not a service-layer concern.

Current Node backend hashes in a Mongoose `pre("save")` hook at cost factor
8 (models/user.ts). Replicated here at the same cost factor deliberately —
this is a "preserve exactly" item, not an opportunity to silently strengthen
hashing cost, per the project's no-unrequested-behavior-change rule.
"""

import bcrypt

_COST_FACTOR = 8  # matches bcrypt.hash(this.password, 8) in models/user.ts


def hash_password(plain_password: str) -> str:
    salt = bcrypt.gensalt(rounds=_COST_FACTOR)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
