"""
bloom_filter.py

A from-scratch Bloom filter implementation for strings such as usernames.

This implementation uses only Python's standard library. It uses:
- bytearray as compact bit storage
- BLAKE2b (hashlib) to derive deterministic hash values
- double hashing to generate k bit positions from two hash values

A Bloom filter answers membership queries probabilistically:
- False means the item is definitely absent, provided the filter was built
  correctly and has not been corrupted.
- True means the item may be present; false positives are possible.

Important:
- This implementation is in-memory. It does not automatically persist to disk.
- It does not support deletion.
- It is not thread-safe for concurrent writes without external synchronization.
- Choose capacity and false-positive probability based on the expected number
  of inserted items. Inserting far beyond capacity increases the false-positive
  rate.
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable


class BloomFilter:
    """Space-efficient probabilistic set-membership filter."""

    def __init__(
        self,
        capacity: int,
        false_positive_rate: float = 0.01,
    ) -> None:
        """
        Create an empty Bloom filter.

        Args:
            capacity: Expected number of inserted items; must be > 0.
            false_positive_rate: Desired probability p, strictly between 0 and 1.

        Raises:
            ValueError: If either argument is outside its valid range.
        """
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise TypeError("capacity must be an integer")
        if capacity <= 0:
            raise ValueError("capacity must be greater than zero")
        if not 0.0 < false_positive_rate < 1.0:
            raise ValueError("false_positive_rate must be between 0 and 1")

        self.capacity = capacity
        self.false_positive_rate = float(false_positive_rate)

        # Optimal bit count:
        # m = ceil(-n * ln(p) / (ln(2) ** 2))
        self.m = math.ceil(
            -capacity * math.log(self.false_positive_rate)
            / (math.log(2) ** 2)
        )

        # Near-optimal number of hash positions:
        # k = round((m / n) * ln(2))
        self.k = max(
            1,
            round((self.m / capacity) * math.log(2)),
        )

        # One byte stores 8 bits. Round up to fit all m bits.
        self.bits = bytearray((self.m + 7) // 8)
        self._inserted_count = 0

    def _positions(self, item: str) -> Iterable[int]:
        """
        Yield k bit positions for an item using double hashing.

        The same string always yields the same positions in this filter.
        """
        if not isinstance(item, str):
            raise TypeError("item must be a string")

        data = item.encode("utf-8")
        digest = hashlib.blake2b(data, digest_size=16).digest()

        # Split the 128-bit digest into two 64-bit integers.
        h1 = int.from_bytes(digest[:8], byteorder="big")
        h2 = int.from_bytes(digest[8:], byteorder="big")

        # Make h2 odd. This is a simple safeguard against a zero step.
        h2 |= 1

        for i in range(self.k):
            yield (h1 + i * h2) % self.m

    def add(self, item: str) -> None:
        """Insert an item into the filter."""
        for position in self._positions(item):
            byte_index = position // 8
            bit_index = position % 8
            self.bits[byte_index] |= 1 << bit_index

        self._inserted_count += 1

    def might_contain(self, item: str) -> bool:
        """
        Return False if definitely absent; True if possibly present.

        True is not proof that the item exists in the original dataset.
        """
        for position in self._positions(item):
            byte_index = position // 8
            bit_index = position % 8
            mask = 1 << bit_index

            if (self.bits[byte_index] & mask) == 0:
                return False

        return True

    @property
    def inserted_count(self) -> int:
        """Number of add() calls, including duplicate items."""
        return self._inserted_count

    @property
    def memory_bytes(self) -> int:
        """Size of the raw bit array in bytes (not total Python object size)."""
        return len(self.bits)

    def stats(self) -> dict[str, int | float]:
        """Return basic sizing and usage information."""
        return {
            "capacity": self.capacity,
            "inserted_count": self.inserted_count,
            "target_false_positive_rate": self.false_positive_rate,
            "bit_count": self.m,
            "hash_positions_per_item": self.k,
            "bit_array_bytes": self.memory_bytes,
            "bit_array_megabytes_decimal": self.memory_bytes / 1_000_000,
            "bit_array_mebibytes_binary": self.memory_bytes / (1024 * 1024),
        }


def load_csv_column(
    csv_path: str,
    column_name: str,
    bloom: BloomFilter,
    encoding: str = "utf-8",
) -> int:
    """
    Read a CSV file row by row and insert one named column into the filter.

    This avoids loading the whole CSV into memory. It uses Python's csv module.

    Args:
        csv_path: Path to the CSV file.
        column_name: Header name of the column containing usernames.
        bloom: An already-created BloomFilter.
        encoding: File encoding, usually utf-8.

    Returns:
        Number of non-empty usernames inserted.

    Notes:
        This function strips leading/trailing whitespace and skips empty values.
        It does not lowercase usernames automatically because username
        case-sensitivity depends on the source system.
    """
    import csv

    inserted = 0
    with open(csv_path, "r", newline="", encoding=encoding) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames is None:
            raise ValueError("CSV file is empty or has no header")
        if column_name not in reader.fieldnames:
            raise ValueError(
                f"Column {column_name!r} not found. "
                f"Available columns: {reader.fieldnames}"
            )

        for row in reader:
            value = row.get(column_name)
            if value is None:
                continue

            username = value.strip()
            if not username:
                continue

            bloom.add(username)
            inserted += 1

    return inserted


def main() -> None:
    """Small runnable demonstration; no CSV file is required."""
    bloom = BloomFilter(capacity=100, false_positive_rate=0.01)

    for username in ("alice", "bob", "charlie"):
        bloom.add(username)

    print("Filter statistics:")
    for key, value in bloom.stats().items():
        print(f"  {key}: {value}")

    print("\nMembership checks:")
    for username in ("alice", "bob", "david", "charlie"):
        result = (
            "possibly present"
            if bloom.might_contain(username)
            else "definitely absent"
        )
        print(f"  {username}: {result}")


if __name__ == "__main__":
    main()
