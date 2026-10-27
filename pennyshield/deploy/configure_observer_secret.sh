#!/usr/bin/env bash
set -euo pipefail

secret_dir="$HOME/.config/pennyshield"
install -d -m 700 "$secret_dir"
read -r -s -p 'Paste the NEW Alchemy API key (input hidden): ' ALCHEMY_API_KEY
printf '\n'
if [[ -z "$ALCHEMY_API_KEY" || "$ALCHEMY_API_KEY" == *$'\n'* ]]; then
  printf 'No valid key entered; nothing changed.\n' >&2
  exit 1
fi

umask 077
tmp_file="$(mktemp "$secret_dir/.observer.env.XXXXXX")"
printf 'ALCHEMY_API_KEY=%s\n' "$ALCHEMY_API_KEY" > "$tmp_file"
chmod 600 "$tmp_file"
mv -f "$tmp_file" "$secret_dir/observer.env"
unset ALCHEMY_API_KEY
printf 'Saved the key in %s/observer.env with owner-only access.\n' "$secret_dir"
