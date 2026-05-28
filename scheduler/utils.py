from collections.abc import Iterable


def ordered_slot_blocks(timeslots: Iterable, duration: int) -> list[tuple[int, ...]]:
    """Return consecutive non-break slot id blocks for a session duration."""
    ordered = sorted(timeslots, key=lambda slot: slot.slot_number)
    blocks: list[tuple[int, ...]] = []

    for index in range(len(ordered) - duration + 1):
        block = ordered[index : index + duration]
        if any(slot.is_break for slot in block):
            continue

        slot_numbers = [slot.slot_number for slot in block]
        expected = list(range(slot_numbers[0], slot_numbers[0] + duration))
        if slot_numbers != expected:
            continue

        blocks.append(tuple(slot.slot_id for slot in block))

    return blocks


def constraint_name(value: str) -> str:
    return value.strip().upper().replace(" ", "_")
