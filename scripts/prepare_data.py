"""Download Banking77 (if needed) and write the message pools."""

import httpx
import yaml

from app.banking77 import read_messages, split_into_pools, write_pools
from app.config import PROJECT_ROOT


def main() -> None:
    """Download and split."""
    config = yaml.safe_load((PROJECT_ROOT / "config" / "data.yaml").read_text())
    source, splits = config["banking77"], config["splits"]
    target = PROJECT_ROOT / source["dir"]
    target.mkdir(parents=True, exist_ok=True)
    for name in source["files"]:
        path = target / name
        if not path.exists():
            response = httpx.get(f"{source['base_url']}/{name}", timeout=60, follow_redirects=True)
            response.raise_for_status()
            path.write_bytes(response.content)
    pools = split_into_pools(
        read_messages(target / "test.csv"), splits["per_intent"], splits["seed"]
    )
    write_pools(pools, target / "pools")
    print({name: len(messages) for name, messages in pools.items()})


if __name__ == "__main__":
    main()
